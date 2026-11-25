"""Append observational functions; preserve both R1 functions byte-for-byte."""
import pathlib,re,json,hashlib,difflib
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
src=(OLD/'02_candidate/task005b_kernels.cu').read_text(encoding='utf-8')
def function(name):
 start=src.index('std::vector<torch::Tensor> '+name+'(')
 end=src.index('\n}\n',start)+3
 return src[start:end]
original=function('ba_cuda')
trace=original.replace('ba_cuda(','ba_trace_reference_cuda(',1)
names=[]
def cap(expressions):
 lines=[]
 for name,expr in expressions:
  names.append(name);lines.append(f'    trace.push_back({expr}.detach().cpu().clone()); // R2_OBSERVE {name}')
 return '\n'.join(lines)+'\n'
def insert_after(text,needle,addition):
 assert text.count(needle)==1,needle
 return text.replace(needle,needle+'\n'+addition,1)
trace=trace.replace('  auto opts = poses.options();','  std::vector<torch::Tensor> trace;\n  TORCH_CHECK(iterations == 2 && !motion_only && !depth_only && enable_update_uncer && enable_affine_transform && !debug, "R2 bounded trace contract");\n  auto opts = poses.options();',1)
trace=insert_after(trace,'  for (int itr=0; itr<iterations; itr++) {',cap([('poses_before','poses'),('disps_before','disps'),('U_before','uncertainties'),('temp_before','temp_y_cdot'),('affine_before','affine_weights')]))
trace=insert_after(trace,'      enable_bidirectional_uncer);',cap([('Cii_geometry','Cii'),('wi_geometry','wi'),('Hs_geometry','Hs'),('vs_geometry','vs')]))
trace=insert_after(trace,'      torch::Tensor Q = 1.0 / C;',cap([('C','C'),('w','w'),('Q','Q'),('kx','kx')]))
trace=insert_after(trace,'      dx = (A - S).solve(lm, ep);     // compute delta_pose',cap([('dx','dx')]))
trace=insert_after(trace,'      dz = Q * (w - accum_cuda(dw, ii_exp, kx));      // compute delta_d',cap([('dz','dz')]))
trace=trace.replace('    if (enable_update_uncer)\n',cap([('poses_after_geometry','poses'),('disps_after_geometry','disps')])+'    if (enable_update_uncer)\n',1)
needle='      torch::Tensor J_total = coeff_data.unsqueeze(1) * (accum_cuda(Jii_data, ii, kx) + accum_cuda(Jjj_data, jj, kx)) + gamma_prior * J_prior;'
trace=insert_after(trace,needle,cap([('Jii_data','Jii_data'),('Jjj_data','Jjj_data'),('kf_count','kf_count'),('J_prior','J_prior'),('J_total','J_total'),('J_linear_before','J_linear'),('U_before_linear','uncertainties'),('temp_before_linear','temp_y_cdot'),('affine_before_linear','affine_weights')]))
trace=trace.replace('        // get the mean of J_linear for the dimension of 0',cap([('J_linear','J_linear')])+'        // get the mean of J_linear for the dimension of 0',1)
trace=insert_after(trace,'        torch::Tensor du = - lr * J_linear.mean(0);',cap([('affine_du','du')]))
trace=insert_after(trace,'        affine_weights += (du - weight_decay * affine_weights);  // L2 regularization',cap([('affine_after','affine_weights')]))
after_u='          kx.packed_accessor32<long,1,torch::RestrictPtrTraits>());\n        \n        if (debug) {'
assert trace.count(after_u)==1
trace=trace.replace(after_u,'          kx.packed_accessor32<long,1,torch::RestrictPtrTraits>());\n'+cap([('U_after','uncertainties'),('temp_after','temp_y_cdot')])+'\n        if (debug) {',1)
trace=trace.replace('  return {dx, dz};','  std::vector<torch::Tensor> result{dx, dz};\n  result.insert(result.end(), trace.begin(), trace.end());\n  return result;',1)
# The trace_paths counterpart differs only by explicit C/G masks and function signature.
paths=trace.replace('ba_trace_reference_cuda(','ba_trace_paths_cuda(',1)
paths=paths.replace('    const bool debug)\n','    const bool debug,\n    const bool curvature_path,\n    const bool gradient_path)\n',1)
paths=paths.replace('      torch::Tensor C = accum_cuda(Cii, ii, kx) + m * alpha + (1 - m) * eta.view({-1, ht*wd});','      torch::Tensor mc = curvature_path ? m : torch::zeros_like(m);\n      torch::Tensor C = accum_cuda(Cii, ii, kx) + mc * alpha + (1 - mc) * eta.view({-1, ht*wd});',1)
paths=paths.replace('      torch::Tensor w = accum_cuda(wi, ii, kx) - m * alpha * (disps.index({kx, "..."}) - disps_sens.index({kx, "..."})).view({-1, ht*wd});','      torch::Tensor mg = gradient_path ? m : torch::zeros_like(m);\n      torch::Tensor w = accum_cuda(wi, ii, kx) - mg * alpha * (disps.index({kx, "..."}) - disps_sens.index({kx, "..."})).view({-1, ht*wd});',1)
assert 'mc * alpha' in paths and 'mg * alpha' in paths
cpp=(OLD/'02_candidate/task005b_bindings.cpp').read_text(encoding='utf-8')
decl1=trace[:trace.index('\n{')]+';\n'
decl2=paths[:paths.index('\n{')]+';\n'
bindings=cpp[:cpp.index('PYBIND11_MODULE')]+decl1+decl2+'''PYBIND11_MODULE(TORCH_EXTENSION_NAME,m) {
  m.def("ba_trace_reference", &ba_trace_reference_cuda);
  m.def("ba_trace_paths", &ba_trace_paths_cuda);
}
'''
out=ROOT/'02_candidate'
(out/'task005b_r2_kernels.cu').write_bytes((OLD/'02_candidate/task005b_kernels.cu').read_bytes()+('\n// R2 isolated observational copies; originals above are unchanged.\n'+trace+'\n'+paths).encode('utf-8'))
(out/'task005b_r2_bindings.cpp').write_text(bindings,encoding='utf-8',newline='\n')
(out/'TRACE_SCHEMA.json').write_text(json.dumps(names,indent=2)+'\n')
proof={'original_ba_body_SHA':hashlib.sha256(original.encode()).hexdigest(),'original_prefix_SHA':hashlib.sha256((OLD/'02_candidate/task005b_kernels.cu').read_bytes()).hexdigest(),'original_prefix_preserved':(out/'task005b_r2_kernels.cu').read_bytes().startswith((OLD/'02_candidate/task005b_kernels.cu').read_bytes()),'trace_fields_per_iteration':len(names),'trace_names':names,'C_G_change_only_in_trace_paths':True,'installed_extension_replaced':False,'existing_candidate_replaced':False}
(out/'GENERATION_AUDIT.json').write_text(json.dumps(proof,indent=2)+'\n')
(out/'trace_reference_vs_original.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),trace.splitlines(True),fromfile='R1/original_ba_cuda',tofile='R2/observed_reference')),encoding='utf-8')
(out/'trace_paths_vs_trace_reference.diff').write_text(''.join(difflib.unified_diff(trace.splitlines(True),paths.splitlines(True),fromfile='observed_reference',tofile='observed_paths')),encoding='utf-8')
print(json.dumps(proof,indent=2))
