"""Patch only the new candidate build, preserving every original kernel body."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate'
def replace_one(text,old,new):
    if text.count(old)!=1:raise RuntimeError('Source contract drift: '+old[:80])
    return text.replace(old,new,1)
def main():
    cpp=TASK/'native/droid.cpp';cu=TASK/'native/droid_kernels.cu'
    c=cpp.read_text();k=cu.read_text()
    old='const bool geometry_enable)'
    new='const bool geometry_enable,\n    const bool robust_enable,\n    const float robust_relative_scale,\n    const bool capture_detail)'
    if c.count(old)!=2 or k.count(old)!=1:raise RuntimeError('Signature drift')
    c=c.replace(old,new);k=k.replace(old,new)
    c=replace_one(c,'debug, prior_strength, control_enable, geometry_enable);',
        'debug, prior_strength, control_enable, geometry_enable, robust_enable, robust_relative_scale, capture_detail);')
    declaration='''
// Candidate-only Cauchy IRLS terms, also exposed for independent CPU/GPU oracles.
std::vector<torch::Tensor> robust_prior_terms_cuda(
    torch::Tensor Cg, torch::Tensor bg, torch::Tensor eta,
    torch::Tensor dm, torch::Tensor d, torch::Tensor strength,
    const float alpha, const float relative_scale);
'''
    c=replace_one(c,'// CUDA forward declarations',declaration+'\n// CUDA forward declarations')
    c=replace_one(c,'  // bundle adjustment kernels','  m.def("prior_terms", &robust_prior_terms_cuda, "Cauchy IRLS prior oracle entry");\n  // bundle adjustment kernels')
    helper='''
// MP-SfM-style Cauchy robustification of DROID-W's linear disparity residual.
// The A5 coefficient is independent of the residual-dependent IRLS weight.
// In particular q NEVER changes the eta damping branch.
std::vector<torch::Tensor> robust_prior_terms_cuda(
    torch::Tensor Cg, torch::Tensor bg, torch::Tensor eta,
    torch::Tensor dm, torch::Tensor d, torch::Tensor strength,
    const float alpha, const float relative_scale) {
  TORCH_CHECK(std::isfinite(relative_scale) && relative_scale>0,
              "Cauchy relative scale must be finite and positive");
  TORCH_CHECK(std::isfinite(alpha) && alpha>=0, "Invalid prior alpha");
  auto m = (dm>0).to(d.scalar_type());
  auto residual = d-dm;
  auto tau = (relative_scale*dm.abs()).clamp_min(1e-6);
  auto q = 1.0/(1.0+(residual/tau).square());
  auto ma = m*strength;
  auto C = Cg+ma*alpha*q+(1.0-ma)*eta;
  auto b = bg-ma*alpha*q*residual;
  auto objective = 0.5*ma*alpha*tau.square()*torch::log1p((residual/tau).square());
  return {C,b,q,objective};
}

'''
    k=replace_one(k,'std::vector<torch::Tensor> ba_cuda(',helper+'std::vector<torch::Tensor> ba_cuda(')
    k=replace_one(k,'  TORCH_CHECK(!geometry_enable || control_enable, "Geometry requires independent prior control");',
        '''  TORCH_CHECK(!robust_enable || control_enable, "Robust prior requires independent coefficient");
  TORCH_CHECK(!robust_enable || !geometry_enable, "No geometry controller in this transfer");
  TORCH_CHECK(!geometry_enable || control_enable, "Geometry requires independent prior control");''')
    k=replace_one(k,'  const int dim_feats = dino_feats.size(1);',
        '''  auto robust_trace = torch::full({iterations,num_kf,10},-1.0,opts);
  auto robust_detail = capture_detail ? torch::zeros({iterations,num_kf,ht*wd,9},opts) : torch::empty({0},opts);
  const int dim_feats = dino_feats.size(1);''')
    marker='''        Q = 1.0/C;
      }

      SparseBlock S = schur_block'''
    block='''        if (robust_enable) {
          auto d = disps.index({kx,"..."}).view({-1,ht*wd});
          auto dm = disps_sens.index({kx,"..."}).view({-1,ht*wd});
          auto damp = eta.view({-1,ht*wd});
          auto Cg = accum_cuda(Cii,ii,kx);
          auto bg = accum_cuda(wi,ii,kx);
          auto terms = robust_prior_terms_cuda(Cg,bg,damp,dm,d,strength,alpha,robust_relative_scale);
          C=terms[0];w=terms[1];auto q=terms[2];
          TORCH_CHECK(torch::isfinite(C).all().item<bool>() && (C>0).all().item<bool>() &&
                      torch::isfinite(w).all().item<bool>(), "Invalid robust linear system");
          auto valid=(m>0).to(opts.dtype());auto counts=valid.sum(1);auto den=counts.clamp_min(1.0);
          auto ma=m*strength;
          robust_trace.select(0,itr).copy_(torch::stack({
            kx.to(torch::kFloat32),counts,(q*valid).sum(1)/den,
            std::get<0>(torch::where(m>0,q,torch::ones_like(q)).min(1)),
            ((q<0.1).to(opts.dtype())*valid).sum(1)/den,
            ((q<0.5).to(opts.dtype())*valid).sum(1)/den,
            ((ma*alpha*q*(d-dm)).square().sum(1)).sqrt(),
            (ma*alpha*q).mean(1),((1-ma)*damp).mean(1),terms[3].sum(1)},1));
          if (capture_detail) robust_detail.select(0,itr).copy_(torch::stack({d,dm,damp,strength,q,C,w,Cg,bg},2));
        }
        Q = 1.0/C;
      }

      SparseBlock S = schur_block'''
    k=replace_one(k,marker,block)
    k=replace_one(k,'  return {dx, dz, geometry_trace};','  return {dx, dz, geometry_trace, robust_trace, robust_detail};')
    cpp.write_text(c);cu.write_text(k)
    receipt=dict(only_independent_candidate_changed=True,original_kernel_bodies_unchanged=True,
        robust_reweighting_location='inside native itr loop, after geometry and before Schur',
        damping='(1-m*a)*eta; never includes q',returned_trace_fields=['kx','valid_count','mean_q','min_q','fraction_q_lt_0.1','fraction_q_lt_0.5','prior_rhs_l2','mean_prior_curvature','mean_eta_damping','robust_prior_objective'],
        detail_fields=['d','dm','eta','a','q','C','b','Cg','bg'],
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [cpp,cu]})
    (TASK/'reports/NATIVE_PATCH_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
