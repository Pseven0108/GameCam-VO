# 精确源码节选

来源：D:\aaa\GameCam-VO\experiments\VIPER_VAL007_STAGE_OBSERVABILITY_R2\review\frozen_source\DROID-W\src\lib\droid_kernels.cu

SHA-256：4cbb9132ea7bd8daaa8a0e429762b9265ee31530c5a9d3fa6ca921cb1a34fdd7

```text
1877:       // add depth residual if there are depth sensor measurements
1878:       const float alpha = gamma_depth;
1879:       torch::Tensor m = (disps_sens.index({kx, "..."}) > 0).to(torch::TensorOptions().dtype(torch::kFloat32)).view({-1, ht*wd});
1880:       torch::Tensor C = accum_cuda(Cii, ii, kx) + m * alpha + (1 - m) * eta.view({-1, ht*wd});
1881:       torch::Tensor w = accum_cuda(wi, ii, kx) - m * alpha * (disps.index({kx, "..."}) - disps_sens.index({kx, "..."})).view({-1, ht*wd});
1882:       torch::Tensor Q = 1.0 / C;
1883: 
1884:       torch::Tensor Ei = accum_cuda(Eii.view({num, 6*ht*wd}), ii, ts).view({t1-t0, 6, ht*wd});
1885:       torch::Tensor E = torch::cat({Ei, Eij}, 0);
1886: 
1887:       SparseBlock S = schur_block(E, Q, w, ii_exp, jj_exp, kk_exp, t0, t1);   // simulataneouly construct the lhs and rhs of the linear system
1888:       dx = (A - S).solve(lm, ep);     // compute delta_pose
1889: 
1890:       torch::Tensor ix = jj_exp - t0;
1891:       torch::Tensor dw = torch::zeros({ix.size(0), ht*wd}, opts);
1892: 
1893:       EvT6x1_kernel<<<ix.size(0), THREADS>>>(
1894:         E.packed_accessor32<float,3,torch::RestrictPtrTraits>(),
1895:         dx.packed_accessor32<float,2,torch::RestrictPtrTraits>(),
1896:         ix.packed_accessor32<long,1,torch::RestrictPtrTraits>(),
1897:         dw.packed_accessor32<float,2,torch::RestrictPtrTraits>());
1898: 
1899:       dz = Q * (w - accum_cuda(dw, ii_exp, kx));      // compute delta_d
1900: 
1901:       if (!depth_only){
1902:         // update poses
1903:         pose_retr_kernel<<<1, THREADS>>>(
1904:           poses.packed_accessor32<float,2,torch::RestrictPtrTraits>(),
1905:           dx.packed_accessor32<float,2,torch::RestrictPtrTraits>(), t0, t1);
1906:       }
1907: 
1908:       // update disparity maps
1909:       disp_retr_kernel<<<kx.size(0), THREADS>>>(
1910:         disps.packed_accessor32<float,3,torch::RestrictPtrTraits>(),
1911:         dz.packed_accessor32<float,2,torch::RestrictPtrTraits>(),
1912:         kx.packed_accessor32<long,1,torch::RestrictPtrTraits>());         // index of the keyframes
1913:     }
1914: 
1915:     if (enable_update_uncer)
1916:     {
```
