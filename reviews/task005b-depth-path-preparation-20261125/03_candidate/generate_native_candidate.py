"""Generate a separate BA research entry. Never edit or compile the baseline."""
import os,sys,pathlib,re,hashlib,json,difflib
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'VIPER_VAL007_STAGE_OBSERVABILITY_R2/review/frozen_source/DROID-W/src/lib/droid_kernels.cu'
EXPECTED_BLOB='9c171af1bfafc278e9776f2f89667054a66dc2bf'
TRACE_NAMES=['poses_before','disps_before','U_before','C_geometry','w_geometry','C','w','Q','E','kx','A','v','schur_subtraction','schur_rhs_subtraction','H_raw','rhs','L_damped_raw','dx','dz','poses_after','disps_after','U_after']

def build(raw):
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if blob!=EXPECTED_BLOB:raise ValueError('Frozen source blob differs')
    text=raw.decode();match=re.search(r'std::vector<torch::Tensor> ba_cuda\([\s\S]*?\n\}',text)
    if not match:raise ValueError('Native BA body missing')
    original=match.group();entry=original
    def change(old,new):
        nonlocal entry
        if entry.count(old)!=1:raise ValueError('Ambiguous source anchor: '+old[:70])
        entry=entry.replace(old,new)
    change('ba_cuda(','ba_paths_cuda(')
    change('    const bool debug)','    const bool debug,\n    const bool curvature_path,\n    const bool gradient_path)')
    change('  auto opts = poses.options();','''  TORCH_CHECK(!motion_only && !depth_only, "TASK005B requires joint pose-depth BA");
  TORCH_CHECK(iterations == 2, "TASK005B captures two iterations in one native call");
  TORCH_CHECK(!debug, "TASK005B does not enable optional legacy debug loss");
  std::vector<torch::Tensor> trace;
  auto opts = poses.options();''')
    change('  for (int itr=0; itr<iterations; itr++) {','''  for (int itr=0; itr<iterations; itr++) {
    trace.push_back(poses.detach().cpu().clone());
    trace.push_back(disps.detach().cpu().clone());
    trace.push_back(uncertainties.detach().cpu().clone());''')
    oldC='      torch::Tensor C = accum_cuda(Cii, ii, kx) + m * alpha + (1 - m) * eta.view({-1, ht*wd});'
    newC='''      torch::Tensor C_geometry = accum_cuda(Cii, ii, kx);
      torch::Tensor m_curvature = curvature_path ? m : torch::zeros_like(m);
      torch::Tensor C = C_geometry + m_curvature * alpha + (1 - m_curvature) * eta.view({-1, ht*wd});'''
    change(oldC,newC)
    oldw='      torch::Tensor w = accum_cuda(wi, ii, kx) - m * alpha * (disps.index({kx, "..."}) - disps_sens.index({kx, "..."})).view({-1, ht*wd});'
    neww='''      torch::Tensor w_geometry = accum_cuda(wi, ii, kx);
      torch::Tensor m_gradient = gradient_path ? m : torch::zeros_like(m);
      torch::Tensor w = w_geometry - m_gradient * alpha * (disps.index({kx, "..."}) - disps_sens.index({kx, "..."})).view({-1, ht*wd});'''
    change(oldw,neww)
    change('      dx = (A - S).solve(lm, ep);     // compute delta_pose','''      SparseBlock H = A - S;
      dx = H.solve(lm, ep);     // SAME native Eigen LLT and damping
      for (const auto& t : std::vector<torch::Tensor>{C_geometry,w_geometry,C,w,Q,E,kx})
        trace.push_back(t.detach().cpu().clone());
      trace.push_back(task005b_matrix(A.A)); trace.push_back(task005b_vector(A.b));
      trace.push_back(task005b_matrix(S.A)); trace.push_back(task005b_vector(S.b));
      trace.push_back(task005b_matrix(H.A)); trace.push_back(task005b_vector(H.b));
      Eigen::SparseMatrix<double> L_dump(H.A);
      L_dump.diagonal().array() += ep + lm * L_dump.diagonal().array();
      trace.push_back(task005b_matrix(L_dump));''')
    change('      dz = Q * (w - accum_cuda(dw, ii_exp, kx));      // compute delta_d','''      dz = Q * (w - accum_cuda(dw, ii_exp, kx));      // compute delta_d
      trace.push_back(dx.detach().cpu().clone());
      trace.push_back(dz.detach().cpu().clone());''')
    change('  return {dx, dz};','''  std::vector<torch::Tensor> result{dx, dz};
  result.insert(result.end(), trace.begin(), trace.end());
  return result;''')
    # The closing loop delimiter immediately precedes the original return.
    anchor='\n  }\n\n  std::vector<torch::Tensor> result'
    if entry.count(anchor)!=1:raise ValueError('End-of-iteration anchor missing')
    entry=entry.replace(anchor,'''
    trace.push_back(poses.detach().cpu().clone());
    trace.push_back(disps.detach().cpu().clone());
    trace.push_back(uncertainties.detach().cpu().clone());
  }

  std::vector<torch::Tensor> result''')
    helpers='''
// TASK005B: diagnostic row-major copies; no changes to SparseBlock::solve.
torch::Tensor task005b_matrix(const Eigen::SparseMatrix<double>& input) {
  auto out=torch::empty({input.rows(),input.cols()},torch::TensorOptions().dtype(torch::kFloat64).device(torch::kCPU));
  auto a=out.accessor<double,2>();
  for(int r=0;r<input.rows();++r) for(int c=0;c<input.cols();++c) a[r][c]=input.coeff(r,c);
  return out;
}
torch::Tensor task005b_vector(const Eigen::VectorXd& input) {
  auto out=torch::empty({input.size()},torch::TensorOptions().dtype(torch::kFloat64).device(torch::kCPU));
  auto a=out.accessor<double,1>();for(int r=0;r<input.size();++r) a[r]=input(r);return out;
}
'''
    generated=text+'\n'+helpers+'\n'+entry+'\n'
    decl=entry[:entry.index('\n{')]
    original_decl=original[:original.index('\n{')]
    binding='#include <torch/extension.h>\n#include <vector>\n'+decl+';\n'+original_decl+''';
PYBIND11_MODULE(TORCH_EXTENSION_NAME,m) {
  m.def("ba_paths", &ba_paths_cuda);
  m.def("ba_reference", &ba_cuda);
}
'''
    return generated,binding,original,entry

def main():
    raw=SOURCE.read_bytes();cu,cpp,original,entry=build(raw)
    out=ROOT/'03_candidate/native';out.mkdir(exist_ok=False)
    (out/'task005b_kernels.cu').write_text(cu,encoding='utf-8',newline='\n')
    (out/'task005b_bindings.cpp').write_text(cpp,encoding='utf-8',newline='\n')
    (ROOT/'02_source/native_ba_path_diff.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),entry.splitlines(True),fromfile='frozen/ba_cuda',tofile='candidate/ba_paths_cuda')),encoding='utf-8')
    (ROOT/'02_source/SOURCE_PROVENANCE.json').write_text(json.dumps({'original':str(SOURCE),'baseline_commit':'c3414af6047d06bafc1a6645d09f23247f3b2cdc','original_git_blob':EXPECTED_BLOB,'original_sha256':hashlib.sha256(raw).hexdigest(),'original_preserved_byte_for_byte_as_prefix':cu.encode().startswith(raw),'candidate_entry':'ba_paths_cuda','isolated_module':'gamecam_task005b_depth_paths','compiled':False,'GPU_validated':False,'diagnostic_tensors_per_iteration':TRACE_NAMES,'outputs_prefix':['dx_last','dz_last'],'no_inner_iteration_clamp_added':True},indent=2)+'\n')
    print(json.dumps({'candidate_written':True,'compiled':False,'native_GPU_runs':0,'trace_fields':len(TRACE_NAMES)}))
if __name__=='__main__':main()
