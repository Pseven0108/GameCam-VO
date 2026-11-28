# 来源和许可证

所有官方引用固定提交，链接不依赖main后续变化。

| 资产 | 固定来源 | 本轮用途 |
|---|---|---|
| DROID-Splat | https://github.com/ChenHoy/DROID-Splat/tree/f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2 | 固定Pose的尺度/偏移LS及过滤思路；本轮只用尺度 |
| 先验对齐实现 | https://github.com/ChenHoy/DROID-Splat/blob/f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2/src/depth_video.py#L591 | linear_align_prior、全地图支持门槛、正尺度保护 |
| confidence归约 | https://github.com/ChenHoy/DROID-Splat/blob/f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2/src/depth_video.py#L440 | 边均值，再对xy向量取范数 |
| 加权LS | https://github.com/ChenHoy/DROID-Splat/blob/f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2/src/geom/__init__.py#L159 | 独立scale-only特例及CPU测试 |
| DROID-W | https://github.com/MoyangLi00/DROID-W/tree/c3414af6047d06bafc1a6645d09f23247f3b2cdc | 冻结Tracker、Frontend、原生BA、FinalBA与Filler |

包内 `source_reference/DROID-Splat/LICENSE` 与 `source_reference/DROID-W/LICENSE` 保留各自Apache2.0正文。
原作者信息及版权以对应原文件为准，保留原始声明。本地adaptation不主张原作者实现了本轮候选。
A5控制、reliability.py和冻结R2 YAML来自GameCam-VO TASK011B，原样副本及SHA清单放入source_reference/GameCam-VO。
本地A5构建保留CUDA源与API兼容副本，编译.so不发布。

208项DROID-W源文件使用Git blob审计；包内选择代码、配置和许可证，省略上游媒体/示例图片和数据split清单；清单见SOURCE_EXPORT_PACKAGE_SELECTION.json。第三方依赖源码借用本机已有只读目录。
官方源码链接仅用于出处；本轮精度证据来自独立输出、轨迹和离线评分，不能用官方论文结论替代本轮验证。
