# GameCam-VO · TASK006A-R2.2 评审入口

先读 `FINAL_REVIEW.md` 和 `R2_2_DECISION.json`。本轮是深度恢复与GT评价资格审计，不是新的模型训练或VO性能实验。

**要点：237个旧负值截零→0；整体AbsRel没有改善；GT内部几何有支持，物理单位仍未核实。**

- `05_reports/`：GT资格、恢复数学、focal差异、误差/Confidence、局限、复现合同。
- `02_restoration/torch_CPU/`：16份完整恢复输出、原生CPU收据及插值fixture。
- `02_restoration/source_grid_examples/`：五环境原RGB网格的深度示例。
- `03_gt_audit/`：200帧元数据、198相邻几何检查及控制。
- `04_evaluation/pixel_maps/`：6张GT配对帧的全分辨率误差/置信度/严重错误数组。
- `figures/`：PNG、SVG、PDF及图注；RGB缩略图仅用于科学比较，不替代原始数据分发。
- `code/`、`tests/`、`logs/`：可检查源码、71项测试和完整执行证据。

本轮依赖已封存R2.1的canonical预测，不包含其原始RGB/EXR/权重。
完整R2.1评审基准Commit：`9e8e1f609796ed78a0a27b942d3d7440bcf23d72`。
R2.1完整ZIP SHA256：`fc8dfeb8e2746c8033621af9647a382e9e3138ff09bf46e8ddee453f678c7ae8`。
R2.1 ZIP获取位置见`05_reports/REPRODUCIBILITY.md`。

当前是原生GT单位下的配对审计；不能称作米制benchmark或新鲜独立Test。
新增GPU前向0；没有修改生产Baseline；不自动进入R2.3、R2.4、R2.5或R3。
