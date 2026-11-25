"""Generate isolated native-kernel entry points and a U-only intervention copy."""
import pathlib,re,json,hashlib,difflib
ROOT=pathlib.Path(__file__).resolve().parents[1]
R1=ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
R2=ROOT.parent/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1'
base=(R1/'02_candidate/task005b_kernels.cu').read_text(encoding='utf-8')
r2=(R2/'02_candidate/task005b_r2_kernels.cu').read_text(encoding='utf-8')
def fun(text,name):
    start=text.index('std::vector<torch::Tensor> '+name+'(')
    return text[start:text.index('\n}\n',start)+3]
def once(text,needle,add):
    assert text.count(needle)==1,needle
    return text.replace(needle,needle+'\n'+add,1)
def cap(name,expr):return f'    trace.push_back({expr}.detach().cpu().clone()); // R3_OBSERVE {name}\n'
def make(name):
    old=fun(r2,'ba_trace_'+name+'_cuda')
    v=old.replace('ba_trace_'+name+'_cuda(','ba_r3_'+name+'_cuda(',1)
    before=v[:v.index('\n{')]
    assert before.endswith(')')
    v=before[:-1]+',\n    const bool freeze_U)'+v[len(before):]
    v=v.replace('R2 bounded trace contract','R3 bounded trace contract')
    v=once(v,'  auto opts = poses.options();','  torch::Tensor frozen_U = uncertainties.detach().clone(); // U-only control; no affine/temp freeze')
    marker='      dx = (A - S).solve(lm, ep);     // compute delta_pose'
    v=once(v,marker,'''
      SparseBlock r3_H = A - S;
      trace.push_back(task005b_matrix(A.A)); // R3_OBSERVE A
      trace.push_back(task005b_vector(A.b)); // R3_OBSERVE v
      trace.push_back(task005b_matrix(S.A)); // R3_OBSERVE schur_subtraction
      trace.push_back(task005b_vector(S.b)); // R3_OBSERVE schur_rhs_subtraction
      trace.push_back(task005b_matrix(r3_H.A)); // R3_OBSERVE H_raw
      trace.push_back(task005b_vector(r3_H.b)); // R3_OBSERVE rhs
      Eigen::SparseMatrix<double> r3_L(r3_H.A);
      r3_L.diagonal().array() += ep + lm * r3_L.diagonal().array();
      trace.push_back(task005b_matrix(r3_L)); // R3_OBSERVE L_damped_raw
''')
    needle='    trace.push_back(uncertainties.detach().cpu().clone()); // R2_OBSERVE U_after'
    assert v.count(needle)==1
    v=v.replace(needle,cap('U_computed','uncertainties')+'    if (freeze_U) uncertainties.copy_(frozen_U); // R3_U_ONLY_INTERVENTION\n'+needle,1)
    fields=re.findall(r'// R[23]_OBSERVE (\w+)',v)
    assert len(fields)==len(set(fields))
    return v,old,fields
ref,oldref,names=make('reference');paths,oldpaths,pnames=make('paths');assert names==pnames
wrappers=r'''
std::vector<torch::Tensor> isolated_jjj_cuda(
    torch::Tensor targets, torch::Tensor uncertainties, torch::Tensor dino_feats,
    torch::Tensor poses, torch::Tensor disps, torch::Tensor intrinsics,
    torch::Tensor ii, torch::Tensor jj, int t1) {
  TORCH_CHECK(poses.is_cuda() && disps.is_cuda() && ii.is_cuda(), "CUDA inputs required");
  auto opts=poses.options(); const int num=ii.size(0), ht=disps.size(1), wd=disps.size(2);
  auto Jii_data=torch::zeros({num,ht*wd},opts), Jjj_data=torch::zeros({num,ht*wd},opts);
  auto kf_count=torch::zeros({t1},opts), loss_data=torch::zeros({num},opts);
  dino_feats_projective_transform_kernel<<<num, THREADS>>>(
      targets.packed_accessor32<float,4,torch::RestrictPtrTraits>(),
      uncertainties.packed_accessor32<float,3,torch::RestrictPtrTraits>(),
      dino_feats.packed_accessor32<float,4,torch::RestrictPtrTraits>(),
      poses.packed_accessor32<float,2,torch::RestrictPtrTraits>(),
      disps.packed_accessor32<float,3,torch::RestrictPtrTraits>(),
      intrinsics.packed_accessor32<float,1,torch::RestrictPtrTraits>(),
      ii.packed_accessor32<long,1,torch::RestrictPtrTraits>(),
      jj.packed_accessor32<long,1,torch::RestrictPtrTraits>(),
      Jii_data.packed_accessor32<float,2,torch::RestrictPtrTraits>(),
      Jjj_data.packed_accessor32<float,2,torch::RestrictPtrTraits>(),
      kf_count.packed_accessor32<float,1,torch::RestrictPtrTraits>(),
      loss_data.packed_accessor32<float,1,torch::RestrictPtrTraits>(),false);
  return {Jii_data,Jjj_data,kf_count};
}
std::vector<torch::Tensor> isolated_linear_cuda(
    torch::Tensor J_total, torch::Tensor dino_feats, torch::Tensor uncertainties,
    torch::Tensor temp_y_cdot, torch::Tensor kx) {
  TORCH_CHECK(J_total.is_cuda() && dino_feats.is_cuda(), "CUDA inputs required");
  auto J_linear=torch::zeros({kx.size(0),dino_feats.size(1)+1},J_total.options());
  linear_transform_kernel<<<kx.size(0), THREADS>>>(
      J_total.packed_accessor32<float,2,torch::RestrictPtrTraits>(),
      J_linear.packed_accessor32<float,2,torch::RestrictPtrTraits>(),
      dino_feats.packed_accessor32<float,4,torch::RestrictPtrTraits>(),
      uncertainties.packed_accessor32<float,3,torch::RestrictPtrTraits>(),
      temp_y_cdot.packed_accessor32<float,3,torch::RestrictPtrTraits>(),
      kx.packed_accessor32<long,1,torch::RestrictPtrTraits>());
  return {J_linear};
}
'''
decls=[]
for v in (ref,paths,wrappers[wrappers.index('std::vector'):wrappers.index('\nstd::vector',1)],wrappers[wrappers.index('\nstd::vector',1)+1:]):
    decls.append(v[:v.index('{')].rstrip()+';\n')
bindings='#include <torch/extension.h>\n#include <vector>\n'+''.join(decls)+'''PYBIND11_MODULE(TORCH_EXTENSION_NAME,m) {
 m.def("ba_reference", &ba_r3_reference_cuda);
 m.def("ba_paths", &ba_r3_paths_cuda);
 m.def("isolated_jjj", &isolated_jjj_cuda);
 m.def("isolated_linear", &isolated_linear_cuda);
}
'''
out=ROOT/'02_candidate'
(out/'task005b_r3_kernels.cu').write_text(base+'\n// R3 independent diagnostics; R1 functions above preserved.\n'+ref+'\n'+paths+'\n'+wrappers,encoding='utf-8',newline='\n')
(out/'task005b_r3_bindings.cpp').write_text(bindings,encoding='utf-8',newline='\n')
(out/'TRACE_SCHEMA.json').write_text(json.dumps(names,indent=2)+'\n')
for label,old,new in [('reference',oldref,ref),('paths',oldpaths,paths)]:
    (out/(label+'_vs_R2.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='R2/'+label,tofile='R3/'+label)),encoding='utf-8')
proof={'R1_prefix_preserved':(out/'task005b_r3_kernels.cu').read_bytes().startswith(base.encode('utf-8')),'R1_source_SHA':hashlib.sha256(base.encode()).hexdigest(),'R2_source_SHA':hashlib.sha256(r2.encode()).hexdigest(),'trace_fields_per_iteration':len(names),'freeze_U_only':True,'affine_and_temp_native_updates_preserved':True,'original_and_R1_R2_extensions_replaced':False,'isolated_kernels_use_unmodified_R1_bodies':True}
(out/'GENERATION_AUDIT.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
