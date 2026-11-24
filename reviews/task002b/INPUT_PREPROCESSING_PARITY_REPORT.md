# Task 002B｜输入预处理一致性

**结论：没有发现足以解释 R2 配对差异的输入预处理不一致。** 同一来源、同一几何变换、同一有效 K、同一 DROID 编码器归一化公式均有证据。两次历史运行没有保存编码器入口的 GPU 张量，不能声明它们在设备上逐位相同。

| 证据层次 | 所能确认的事实 |
| --- | --- |
| 原始输入与历史运行回执 | 92 个区段使用相同的冻结 RGB-ID 序列与 JPEG 内容清单。SLAM 运行的逐段 BGR 缓冲哈希与 R2 预检一致；其 tracking 与 filler BGR 哈希相同。预检对同一 BGR 缓冲按历史表示转换得到的 RGB f32 哈希与历史 DROID-W tracking 回执在 92/92 区段相同。预检与实际版本的回执只有记录耗时的 `seconds` 字段不同。 |
| 本地 CPU 独立重建 | 两条预处理路径的 280 个分层样本在 BGR 像素、RGB f32 归一化后均零偏差；`val_007_full_00001-00487` 与 `val_042_full_00001-00529` 的 487 和 529 帧完整回放均重得各自的历史 BGR/RGB tensor 哈希。当前 OpenCV 4.13.0，历史回执 4.8.1；没有声称本轮重解码了全部 49,815 张。 |
| 未直接记录的量 | DROID-W filler 回执封存了帧数及顺序检查，没有独立 filler tensor 哈希。源码支持使用同一 loader 的解释。两模型真实 GPU 归一化张量以及特征激活未留存；不同算子舍入、精度模式、特征与后端不能由这次审计判为相同。 |

## 图像路径

1. **JPEG → BGR uint8 HWC。** 冻结分辨率 1920×1080。SLAM 由 `R2/pipeline/verify_pixels.py:58–88` 解码至连续 BGR 暂存；DROID-W 原生 loader 读取相同 JPEG，虚拟分支由任务 runner 接管几何变换。未调用官方 demo 的额外缩放或默认跳帧。
2. **BGR 变换 → 640×360。** 固定 K：OpenCV `INTER_LINEAR`，DROID-W 的 `cv2.resize` 使用相同默认插值；`H_edge=W_edge=0`，无裁剪、填充或畸变校正。虚拟相机：按每帧源 K 对同一输出网格执行一次反向 `remap`，使用 `INTER_LINEAR`、`BORDER_CONSTANT`；源图内插，无另一次 resize。核对 6,403 帧角点映射，采样中心距最近源图边界至少 1.499 px，未触发越界填充。这会重采样视场，所以分组报告。
3. **Loader 与 encoder。** SLAM 送入 `[1,3,360,640]` BGR uint8（像素 0…255），`MotionFilter.track` 转 RGB 并除以 255。DROID-W 在 loader 完成通道转换和 `/255`，`MotionFilter.track` 已收到 `[1,3,360,640]` RGB float32（0…1）；没有再次 `/255`。在 DROID 的 `fnet`/`cnet` 前应用同一式子 `(RGB/255 − mean)/std`，RGB 顺序 `mean=(.485,.456,.406)`、`std=(.229,.224,.225)`。特征路径中的批次/帧轴不改变 H/W 或通道次序。理论按通道得到范围 R `[−2.118,2.249]`、G `[−2.036,2.429]`、B `[−1.804,2.640]`。两个 filler 源码同样归一化。CPU float32 的算术敏感性试验中，直接除法与乘已舍入倒数之间最大归一化差 `7.15e−7`；这是舍入敏感性，非实测设备差异。
4. **算法内分支。** DROID-W 的 Metric3D 深度与 FiT3D/DINO 特征从模型内部另走路径。共同 DROID encoder 的输入一致有证据；这些新增分支是被比较算法的一部分，不能视为共同 encoder 输入不公，也不能由本次审计判定为 RPE 的根因。

## K 的来源和数值

`R1/pipeline/audit_viper.py:33–66,182–197` 从 Camera CSV 的 OpenGL 投影项 `P` 按 0 基索引提取 `fx=960·P00, fy=540·P11, cx=960·(1−P02)−0.5, cy=540·(1+P12)−0.5`。本轮重新验 47 个成员 CRC、SHA 及封存数组；49,815 行 K 完全相同。

- **固定 K：** 45 序列、82 区段、43,412 帧。按源序列首行 K 固定，原分辨率逐分量跨度上限 `0.001 px`。`s=1/3`，`f'=s f`，`c'=s(c+0.5)−0.5`。R2 重用的是 R1 这套已封存近似，未从轨迹结果重新选择 K。
- **虚拟 K：** `val_042` 和 `val_043`，10 区段、6,403 帧。保留 Camera CSV 逐帧 K，用每条源序列的全部 K 和有效视场构造一个居中目标 K；先在原分辨率计算安全焦距，再应用同一半像素缩放。逆映射 `u_src = cx_src + fx_src·(u_out−cx_out)/fx_out`（`v` 同理）。两序列的名义目标 `(fx,fy,cx,cy)` 分别约 `(408.144,408.309,319.5,179.5)` 和 `(405.836,406.001,319.5,179.5)`。使用了标注校准及全序列可用性，不能据此称未标定 RGB 自标定或实时可用方案；没有将位姿真值送入模型。
- **实际 K：** 名义输出 K 复算最大差 `5.68e−14 px`。DROID-W runner 将 `3·K_out` 交给只做传统缩放的原生 loader，再用 float32 缩小到实际值；SLAM 用相同的实际值。92/92 区段四个参数 float32 逐位一致；共同回执与名义 K 的最大差 `4.053e−5 px` 是同向量化，非跨模型差。比如 `val_001` 两者收到 `[386.01123047,386.01123047,319.5,179.5]`。
- **1/8 网格：** DROID-SLAM runner 对保存的关键帧 K/8 做了运行时逐元素断言；DROID-W 源码在进入关键帧缓存和 filler 时按 8 缩放，`down_scale=8`。可从共同实值重建相同 K/8，DROID-W 的逐关键帧 GPU K 缓冲未单独导出。两个后端的投影/BA 都读取缓存内参，未给其中一方额外用位姿真值。

## 可核查的源码锚点

下列路径以相应实验或已核验源码快照为根；`TASK002B_SOURCE_EXCERPTS.txt` 保存精确行号、内容和文件 SHA。

| 路径 | 入口与证据 |
| --- | --- |
| R1 `pipeline/plan_segments.py:16–34,54–82`、`pipeline/segment_input.py:17–37,59–79` | 序列首 K / 虚拟相机选法、半像素缩放、源 K 的帧索引、连续帧约束和 remap |
| R2 `pipeline/verify_pixels.py:36–96,121–136`、`pipeline/run_original.py:36–69,88–139` | CPU 像素预检、来源转换与 BGR 记录；实际跟踪和 filler 输入、有据可查的 K/8 |
| R1 `pipeline/run_segment.py:81–149,183–207` | DROID-W 的运行 loader、虚拟支路、输入/补位回执、不裁剪及内参调整 |
| DROID-SLAM `droid_slam/motion_filter.py:36–88`、`droid_slam/trajectory_filler.py:34–72`、`droid_slam/droid_net.py:149–164` | RGB、`/255`、归一化、K/8 与 feature encoder |
| DROID-W `src/utils/datasets.py:134–168`、`src/motion_filter.py:33–110`、`src/tracker.py`、`src/trajectory_filler.py:28–78,100–137`、`src/modules/droid_net/droid_net.py:159–160` | 原生 loader、跟踪和 filler 归一化、K/8、DROID 特征与额外先验分支 |

逐阶段判定见 `INPUT_PREPROCESSING_STAGE_TABLE.csv`；完整回执及 CPU 对照分别见 `R2_RUNTIME_INPUT_RECEIPT_PARITY.csv`、`CPU_PREPROCESSING_REPLAY_SAMPLES.csv`。
