#include <torch/extension.h>
#include <vector>
std::vector<torch::Tensor> ba_paths_cuda(
    torch::Tensor poses,        // [buffer, 7]
    torch::Tensor disps,        // [buffer, height, width]
    torch::Tensor intrinsics,
    torch::Tensor disps_sens,
    torch::Tensor targets,
    torch::Tensor weights,
    torch::Tensor uncertainties,
    torch::Tensor temp_y_cdot,
    torch::Tensor dino_feats,
    torch::Tensor affine_weights,
    torch::Tensor eta,          // used for ragularizing of estimated disparity
    torch::Tensor ii,
    torch::Tensor jj,
    const int t0,
    const int t1,
    const int iterations,
    const float lm,             // Levenberg-Marquardt damping factor
    const float ep,             // 
    const float gamma_data,
    const float gamma_prior,
    const float gamma_depth,
    const float lr,
    const float weight_decay,
    const bool motion_only,
    const bool depth_only,
    const bool enable_update_uncer,
    const bool enable_udba,
    const bool enable_affine_transform,
    const bool enable_bidirectional_uncer,
    const bool debug,
    const bool curvature_path,
    const bool gradient_path);
std::vector<torch::Tensor> ba_cuda(
    torch::Tensor poses,        // [buffer, 7]
    torch::Tensor disps,        // [buffer, height, width]
    torch::Tensor intrinsics,
    torch::Tensor disps_sens,
    torch::Tensor targets,
    torch::Tensor weights,
    torch::Tensor uncertainties,
    torch::Tensor temp_y_cdot,
    torch::Tensor dino_feats,
    torch::Tensor affine_weights,
    torch::Tensor eta,          // used for ragularizing of estimated disparity
    torch::Tensor ii,
    torch::Tensor jj,
    const int t0,
    const int t1,
    const int iterations,
    const float lm,             // Levenberg-Marquardt damping factor
    const float ep,             // 
    const float gamma_data,
    const float gamma_prior,
    const float gamma_depth,
    const float lr,
    const float weight_decay,
    const bool motion_only,
    const bool depth_only,
    const bool enable_update_uncer,
    const bool enable_udba,
    const bool enable_affine_transform,
    const bool enable_bidirectional_uncer,
    const bool debug);
std::vector<torch::Tensor> ba_trace_reference_cuda(
    torch::Tensor poses,        // [buffer, 7]
    torch::Tensor disps,        // [buffer, height, width]
    torch::Tensor intrinsics,
    torch::Tensor disps_sens,
    torch::Tensor targets,
    torch::Tensor weights,
    torch::Tensor uncertainties,
    torch::Tensor temp_y_cdot,
    torch::Tensor dino_feats,
    torch::Tensor affine_weights,
    torch::Tensor eta,          // used for ragularizing of estimated disparity
    torch::Tensor ii,
    torch::Tensor jj,
    const int t0,
    const int t1,
    const int iterations,
    const float lm,             // Levenberg-Marquardt damping factor
    const float ep,             // 
    const float gamma_data,
    const float gamma_prior,
    const float gamma_depth,
    const float lr,
    const float weight_decay,
    const bool motion_only,
    const bool depth_only,
    const bool enable_update_uncer,
    const bool enable_udba,
    const bool enable_affine_transform,
    const bool enable_bidirectional_uncer,
    const bool debug);
std::vector<torch::Tensor> ba_trace_paths_cuda(
    torch::Tensor poses,        // [buffer, 7]
    torch::Tensor disps,        // [buffer, height, width]
    torch::Tensor intrinsics,
    torch::Tensor disps_sens,
    torch::Tensor targets,
    torch::Tensor weights,
    torch::Tensor uncertainties,
    torch::Tensor temp_y_cdot,
    torch::Tensor dino_feats,
    torch::Tensor affine_weights,
    torch::Tensor eta,          // used for ragularizing of estimated disparity
    torch::Tensor ii,
    torch::Tensor jj,
    const int t0,
    const int t1,
    const int iterations,
    const float lm,             // Levenberg-Marquardt damping factor
    const float ep,             // 
    const float gamma_data,
    const float gamma_prior,
    const float gamma_depth,
    const float lr,
    const float weight_decay,
    const bool motion_only,
    const bool depth_only,
    const bool enable_update_uncer,
    const bool enable_udba,
    const bool enable_affine_transform,
    const bool enable_bidirectional_uncer,
    const bool debug,
    const bool curvature_path,
    const bool gradient_path);
PYBIND11_MODULE(TORCH_EXTENSION_NAME,m) {
  m.def("ba_trace_reference", &ba_trace_reference_cuda);
  m.def("ba_trace_paths", &ba_trace_paths_cuda);
}
