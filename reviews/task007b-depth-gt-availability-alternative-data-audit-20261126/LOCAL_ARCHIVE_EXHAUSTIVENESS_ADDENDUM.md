# 本地归档补查：修正TASK007A的文件名筛选范围

承认TASK007A的归档名正则没有覆盖所有命名；原16个归档不是穷尽性证明。TASK007A原包保持封存，本文件是独立补充。

## 本轮实际检查

先用rg枚举项目内所有ZIP/TAR/TGZ/TAR.GZ/7z，以及用户Downloads/Desktop顶层归档，**不按train/val/img/dense归档文件名排除ZIP**。

- 发现1,080个归档路径；471个ZIP全部成功读取中央目录。
- 按成员路径内容识别20个VIPER相关ZIP，包括原来文件名规则漏掉的两个`synthetic_camera.zip`、两个RGB样本ZIP。
- 这些ZIP识别到的VIPER成员为RGB或camera/table，没有depth候选；不做整包payload CRC或解码认证。
- 初始609个非ZIP容器显式登记未解析；进一步对VIPER/dense上下文中的20个TAR类容器取头部，19个完整读完头部。
- `VAL007_OBSERVATION_EVIDENCE.tar.gz`达到256MiB解压扫描保护，仅检查前缀；其剩余内容保持UNVERIFIED。
- 其余589个非ZIP容器未解析，不能据此宣称全盘所有容器已被排除。项目外Downloads/Desktop子目录及其他磁盘也不在本次范围。

TAR中若名字包含depth/groundtruth，会列为待判定，不能按名字直接承认为深度GT。
本次可见条目包括Euroc位姿文本、DROID源码、BA重放目录及日志，未建立目标VIPER逐像素GT来源。
所有候选名、读取范围和中止状态在`local_audit/VIPER_TAR_FOLLOWUP.json`中保留。

## train_dense究竟是什么？

| 历史目录 | 成员数 | 实际类型 |
|---|---:|---|
| train_dense_0_catalog.json | 24,138 | 24,137 JPG + 1 Terms_of_use.txt |
| train_dense_1_catalog.json | 18,483 | 18,482 JPG + 1 Terms_of_use.txt |
| val_dense2to9_catalog.json | 13,047 | 13,046 JPG + 1 Terms_of_use.txt |

历史download index中的dense video说明，与上述成员及当前`*_2-9_jpg.zip`吻合。
这些历史变量名表示**连续采样RGB**，不是depth模态。三个目录均按原文件SHA核验，不自动更名或覆盖。

历史Range二进制、HTML响应和flow u/v的TASK007A分类仍保留；归档尾部不是完整payload验证。
最终结论限定为：**本轮没有找到可准入的目标深度GT**，不是“任何本地文件都绝不可能有深度”。
