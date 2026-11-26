# TASK007B 最终评审：VIPER深度GT渠道与替代数据源

2026-11-26，Asia/Shanghai。

**本轮数据源可行性审查完成；VIPER像素Confidence校准仍为NO-GO。首选下一步候选是Virtual KITTI 2.0.3的小样本GT准入，不是立即推理或训练。**

## 六项任务的结果

| 任务 | 结论 | 证据 |
|---|---|---|
| VIPER官方GT渠道 | 有在线PFM预测提交与排行榜；没有找到可准入的公开配对Train/Validation像素GT渠道 | 固定官方源码、RVC 2022任务说明、当前页面元数据 |
| 本地归档补查 | 471个ZIP均按成员检查，识别20个VIPER相关ZIP；train_dense历史目录全是JPG+条款 | ZIP中央目录清单、3份dense目录、20个TAR补查 |
| 替代深度数据 | Virtual KITTI 2优先；TartanAir v1次选；NYUv2可作传感器有效区域辅助对照 | 官方单位/格式说明、现时HTTP HEAD及MD5清单 |
| MVS-Synth相对实验 | 可定义非米制log-shape诊断，但会消除整帧尺度错误，不能验证绝对尺度不确定性 | 独立数学说明及18项CPU合同测试 |
| Calibration/Evaluation划分 | 提出按母Scene隔离方案，0000/0001及VIPER已观察缓存继续隔离 | JSON分组和泄漏检查要求；没有伪造实际frame清单 |
| 项目入口 | 本次发布提交的README、PROJECT_STATUS、REVIEW_INDEX、REVIEWING统一指向TASK007B | project_entries及发布回读收据 |

## 最重要的证据与限制

**1. 官方渠道并非公开像素GT认证。**
VIPER的提交代码接收用户预测PFM，不是GT下载器。RVC 2022明确此深度任务不供training data，不能把这句话扩大成VIPER其他模态没有Train。
当前匿名下载页仍是许可表单，本轮未提交表单或联系作者；未证明在任何条件下官方都不可能提供GT。

**2. dense不是depth。**
train_dense_0：24,137 JPG；train_dense_1：18,482 JPG；val_dense2to9：13,046 JPG；各另有1条款文件。
已确认历史dense命名对应连续RGB采样。原TASK007A包保持封存，局限由本轮补充纠正。

本轮枚举1,080个归档路径，读取471个ZIP中央目录；其余609个非ZIP先列为未核实。
进一步对20个VIPER/dense相关TAR做有界头部检查，19个完整完成，1个压缩包到达256MiB保护后保留未读部分。
另589个非ZIP未解析。因此这不是全盘所有数据模态的穷尽性证明，也不是ZIP payload CRC认证；最终只宣称没有找到可准入的目标GT。

**3. 推荐Virtual KITTI 2，仍未获得真实样本准入。**
其官方说明明确uint16 PNG Z-depth的厘米编码，并提供K/外参/class颜色。HTTP HEAD确认官方RGB、depth、textgt归档可访问，官方MD5清单已取得。
RGB+depth+textgt为约14.62GiB，尚不含class。未下载数据归档；Accept-Ranges声明不等于已经验证小样本按成员传输。
只有5个母场景，没有VIPER Night/Snow及第三人称跟随视角；候选校准结论不能直接当作VIPER五环境结果。

**4. 数据划分是待批准的预注册方案，不是已运行正式数据集。**
Scene01/02用于Calibration，Scene06用于Development，Scene18/20用于Evaluation；同母场景天气、视角、双目变体禁止跨组。
建议先审查Calibration-only 12对样本，后续目标240对；实际取得0对，实际frame清单为null。
不改变原VIPER划分，不使用Test拟合，不承诺候选数据未进入Metric3D预训练。

## 执行和交付验收

- 使用现有gamecam-vo环境、本地CPU；18/18软件合同测试真实通过，没有导入torch。
- 没有Metric3D前向、CUDA、GPU实验、Scalix训练、DROID-W修改、SLAM或全量数据下载。
- 有界网络访问仅为官方文本、代码、587-byte校验清单及HEAD；原始数据payload下载0。
- 官方源码Blob、已读取历史证据及TASK007A封存文件再核验；完整ZIP有独立SHA清单和CRC收据。
- 详细归档范围、数学边界、候选矩阵、下一阶段门禁均随包发布；封存后发布验证单独记录，不倒改历史结果。

建议下一步审核小样本GT获取及单位/mask/对齐计划；本轮到此结束，不自行启动该阶段。
