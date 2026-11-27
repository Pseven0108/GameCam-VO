"""Export immutable upstream objects and build an isolated, uncompiled candidate.

The installed droid_backends is never replaced. Added prior control is inside
the native two-iteration loop, so native uncertainty feedback remains intact.
"""
import difflib
import subprocess
from pathlib import Path

from common import TASK,sha,dump

SOURCE=Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W')
COMMIT='c3414af6047d06bafc1a6645d09f23247f3b2cdc'

HELPER=r'''
// TASK011B: prior-free geometry from the same native linearization.
// This helper has no Metric3D, mono-disparity or depth-reliability input.
torch::Tensor task011b_geometry_statistics(
    const SparseBlock& A, torch::Tensor E, torch::Tensor Q0,
    torch::Tensor ii_exp, torch::Tensor jj_exp, torch::Tensor kk_exp,
    torch::Tensor kx, torch::Tensor disps, int t0, int t1, float lm, float ep) {
  auto zero_rhs = torch::zeros_like(Q0);
  SparseBlock S0 = schur_block(E, Q0, zero_rhs, ii_exp, jj_exp, kk_exp, t0, t1);
  Eigen::MatrixXd H = Eigen::MatrixXd(A.A - S0.A);
  // Native damping is after Schur, not on A before elimination.
  H.diagonal().array() += ep + lm * H.diagonal().array();
  TORCH_CHECK(H.allFinite(), "TASK011B prior-free Schur matrix is nonfinite");
  Eigen::LLT<Eigen::MatrixXd> factor(H);
  TORCH_CHECK(factor.info() == Eigen::Success,
              "TASK011B prior-free damped Schur matrix is not SPD; no added jitter");
  auto ecpu = E.to(torch::kCPU).to(torch::kFloat64).contiguous();
  auto qcpu = Q0.to(torch::kCPU).to(torch::kFloat64).contiguous();
  auto jcpu = jj_exp.to(torch::kCPU).contiguous();
  auto kcpu = kk_exp.to(torch::kCPU).contiguous();
  auto dcpu = disps.index_select(0, kx).to(torch::kCPU).to(torch::kFloat64).contiguous();
  auto e = ecpu.accessor<double,3>();
  auto q = qcpu.accessor<double,2>();
  auto j = jcpu.accessor<long,1>();
  auto source = kcpu.accessor<long,1>();
  auto disp = dcpu.accessor<double,3>();
  int K = Q0.size(0), D = Q0.size(1), P = t1-t0, wd = disps.size(2);
  std::vector<double> values(K*3, 0.0);
  for (int frame=0; frame<K; ++frame) {
    Eigen::MatrixXd block = Eigen::MatrixXd::Zero(P*6, D);
    for (int edge=0; edge<E.size(0); ++edge) {
      int pose = int(j[edge])-t0;
      if (source[edge] != frame || pose<0 || pose>=P) continue;
      for (int component=0; component<6; ++component)
        for (int pixel=0; pixel<D; ++pixel)
          block(pose*6+component,pixel) += e[edge][component][pixel];
    }
    std::vector<double> relative_std;
    for (int first=0; first<D; first+=256) {
      int count = std::min(256, D-first);
      Eigen::MatrixXd eq = block.middleCols(first,count);
      for (int p=0; p<count; ++p) eq.col(p) *= q[frame][first+p];
      Eigen::MatrixXd whitened = factor.matrixL().solve(eq);
      for (int p=0; p<count; ++p) {
        int pixel = first+p;
        double v = q[frame][pixel] + whitened.col(p).squaredNorm();
        double d = disp[frame][pixel/wd][pixel%wd];
        TORCH_CHECK(std::isfinite(v) && v>=0.0,
                    "TASK011B nonfinite/negative geometry inverse-normal diagonal");
        if (std::isfinite(d) && d>1e-6)
          relative_std.push_back(std::sqrt(v)/(std::abs(d)+1e-6));
      }
    }
    TORCH_CHECK(!relative_std.empty(), "TASK011B empty positive-disparity geometry domain");
    std::sort(relative_std.begin(), relative_std.end());
    int n = relative_std.size();
    double u = n%2 ? relative_std[n/2] : .5*(relative_std[n/2-1]+relative_std[n/2]);
    TORCH_CHECK(std::isfinite(u), "TASK011B nonfinite frame geometry score");
    values[frame*3] = u/(1.0+u);
    values[frame*3+1] = u;
    values[frame*3+2] = n;
  }
  return torch::from_blob(values.data(), {K,3},
    torch::TensorOptions().dtype(torch::kFloat64)).to(E.device()).to(torch::kFloat32);
}

'''

CONTROL=r'''
      if (control_enable) {
        auto strength = prior_strength.index({kx, "..."}).view({-1, ht*wd});
        if (geometry_enable) {
          auto C0 = accum_cuda(Cii, ii, kx) + eta.view({-1, ht*wd});
          TORCH_CHECK(torch::isfinite(C0).all().item<bool>() && (C0>0).all().item<bool>(),
                      "TASK011B nonpositive/nonfinite prior-free depth curvature");
          auto geometry = task011b_geometry_statistics(
            A, E, 1.0/C0, ii_exp, jj_exp, kk_exp, kx, disps, t0, t1, lm, ep);
          geometry_trace.select(0,itr).slice(1,0,3).copy_(geometry);
          geometry_trace.select(0,itr).select(1,3).copy_(kx.to(torch::kFloat32));
          strength = strength * geometry.select(1,0).unsqueeze(1);
        }
        auto weighted_m = m * strength;
        C = accum_cuda(Cii, ii, kx) + weighted_m * alpha + (1-weighted_m) * eta.view({-1, ht*wd});
        w = accum_cuda(wi, ii, kx) - weighted_m * alpha *
            (disps.index({kx, "..."})-disps_sens.index({kx, "..."})).view({-1, ht*wd});
        Q = 1.0/C;
      }

'''


def original(name):
    return subprocess.check_output(['git','-C',str(SOURCE),'show',COMMIT+':'+name]).decode('utf-8')


def main():
    out=TASK/'CADP_DR_EXPERIMENTAL_BRANCH/native'
    out.mkdir(parents=True,exist_ok=False)
    names=['droid.cpp','droid_kernels.cu','correlation_kernels.cu','altcorr_kernel.cu']
    upstream={n:original('src/lib/'+n) for n in names}
    for n,text in upstream.items():
        (out/('upstream_'+n+'.txt')).write_text(text,encoding='utf-8',newline='\n')
    cu=upstream['droid_kernels.cu']
    before,body=cu.split('std::vector<torch::Tensor> ba_cuda(',1)
    signature,remainder=body.split(')\n{',1)
    if signature.count('const bool debug')!=1:raise RuntimeError('Native BA signature drift')
    signature=signature.replace('const bool debug','const bool debug,\n    torch::Tensor prior_strength,\n    const bool control_enable,\n    const bool geometry_enable')
    guard=r'''
  TORCH_CHECK(!geometry_enable || control_enable, "Geometry requires independent prior control");
  if (control_enable) {
    TORCH_CHECK(!motion_only, "TASK011B may not intervene in motion-only BA");
    TORCH_CHECK(prior_strength.is_cuda() && prior_strength.scalar_type()==torch::kFloat32 &&
                prior_strength.sizes()==disps.sizes() && prior_strength.is_contiguous(),
                "TASK011B strengths must match native contiguous float32 CUDA disparity grid");
    TORCH_CHECK(torch::isfinite(prior_strength).all().item<bool>() &&
                (prior_strength>=0).all().item<bool>() && (prior_strength<=1).all().item<bool>(),
                "TASK011B strengths outside [0,1]");
  }
'''
    remainder=guard+remainder
    marker='  const int num_kf = kx.size(0);'
    if remainder.count(marker)!=1:raise RuntimeError('Active-frame initialization drift')
    remainder=remainder.replace(marker,marker+'\n  auto geometry_trace = torch::full({iterations, num_kf, 4}, -1.0, opts);')
    marker='      SparseBlock S = schur_block(E, Q, w, ii_exp, jj_exp, kk_exp, t0, t1);'
    if remainder.count(marker)!=1:raise RuntimeError('Native Schur call drift')
    remainder=remainder.replace(marker,CONTROL+marker)
    if remainder.count('  return {dx, dz};')!=1:raise RuntimeError('Native return drift')
    remainder=remainder.replace('  return {dx, dz};','  return {dx, dz, geometry_trace};')
    candidate_cu=before+'\n#include <Eigen/Dense>\n#include <algorithm>\n#include <cmath>\n'+HELPER+'std::vector<torch::Tensor> ba_cuda('+signature+')\n{'+remainder
    # No existing U update or retraction/geometry kernel body may change.
    original_u=cu.split('    if (enable_update_uncer)',1)[1].split('  return {dx, dz};',1)[0]
    candidate_u=candidate_cu.split('    if (enable_update_uncer)',1)[1].split('  return {dx, dz, geometry_trace};',1)[0]
    if original_u!=candidate_u:raise RuntimeError('Native uncertainty update changed')
    cpp=upstream['droid.cpp']
    if cpp.count('    const bool debug)')!=2:raise RuntimeError('C++ declaration/wrapper signature drift')
    candidate_cpp=cpp.replace('    const bool debug)','    const bool debug,\n    torch::Tensor prior_strength,\n    const bool control_enable,\n    const bool geometry_enable)')
    marker='enable_update_uncer, enable_udba, enable_affine_transform, enable_bidirectional_uncer, debug);'
    if candidate_cpp.count(marker)!=1:raise RuntimeError('C++ call forwarding drift')
    candidate_cpp=candidate_cpp.replace(marker,'enable_update_uncer, enable_udba, enable_affine_transform, enable_bidirectional_uncer, debug, prior_strength, control_enable, geometry_enable);')
    candidates=dict(upstream,**{'droid.cpp':candidate_cpp,'droid_kernels.cu':candidate_cu})
    for n,text in candidates.items():
        (out/n).write_text(text,encoding='utf-8',newline='\n')
    patches=[]
    for n in names:
        patches.extend(difflib.unified_diff(upstream[n].splitlines(True),candidates[n].splitlines(True),fromfile='upstream/'+n,tofile='candidate/'+n))
    (out.parent/'task011b_prior_control.patch').write_text(''.join(patches),encoding='utf-8')
    dump(out.parent/'SOURCE_PROVENANCE.json',dict(upstream_commit=COMMIT,
        project_main_commit='7a4d93a8ace18ca37f97949622953ade5b129d86',
        exported_original_git_objects=True,upstream_worktree_changed=False,installed_extension_replaced=False,
        existing_kernel_bodies_changed=False,native_U_update_body_exact=True,
        native_Schur_solve_retraction_body_unchanged=True,
        endpoint_numeric_GPU_verification='NOT_RUN_GPU_UNAVAILABLE',
        geometry_formula='Q0=1/(Cg+eta); H0=A-EQ0Et; Hd=H0+diag(ep+lm*diag(H0)); diagSigma=Q0+colnorm(L^-1 E Q0)^2',
        geometry_mapping='u=median_positive_disparity(sqrt(diagSigma)/(abs(d)+1e-6));g=u/(1+u); no target fitting',
        inverse_normal_not_independently_calibrated_physical_covariance=True,
        sources=[dict(file=n,upstream_sha256=sha(out/('upstream_'+n+'.txt')),candidate_sha256=sha(out/n)) for n in names]))
    print('ISOLATED_NATIVE_CANDIDATE_PREPARED_NOT_COMPILED',flush=True)


if __name__=='__main__':main()
