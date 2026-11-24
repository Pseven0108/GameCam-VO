# ConfigDict 安装实现与原始快照审计

审计日期：2026-11-24（Asia/Shanghai）。本文件描述已取得的源码与 CPU 证据。真实权重新进程恢复失败于独立的 timm Format 类型；CPU 总门槛未通过，GPU 阶段未启动。

## 当前证据与身份

- 起始候选提交：`a324b57760fdaf4929385f2271991d773533799d`。
- 起始源码树：`19b22b429226383c3ef996e40c4a5483a5339acf`。
- 初始清点记录包含 3,738 个受 Git 管理的条目；不能用提交号代替这份文件身份核验。
- ConfigDict 专项第一轮候选提交：`aa0cca3ed0d6e5d381422d8219234b8c0c6ad065`。
- 本轮修改范围为 `native_control/configdict_adapter.py` 与 `native_control/snapshot.py`。

## 真实安装版本

| 项目 | 读取到的实现 |
|---|---|
| Python | 3.10.20 |
| MMCV distribution | mmcv-full 1.7.2 |
| ConfigDict 精确类 | `mmcv.utils.config:ConfigDict` |
| Addict | 2.4.0 |
| 继承链 | ConfigDict → addict.Dict → dict → object |
| 类构造签名 | `(*args, **kwargs)` |
| 额外 slots | 本次两份类源码中未发现 |
| MMCV 源码 SHA-256 | `02cb37945ed38c4cfcf606ae535369ca45abefb9ebffbee1a2b721c74d89d384` |
| Addict 源码 SHA-256 | `49c39f72568033bba0c99a17396d871cbf60097b7f5cf7be8b96d32e263cb9f5` |

以上来自安装环境中实际类、MRO、方法归属和源码文件内容，而不是对其他版本文档的推断。公开副本应使用经脱敏的结构化摘录，不发布原始传输日志中的连接信息。

## Mapping 与属性是两类不同状态

ConfigDict 的业务配置键位于 dict mapping；`vars(obj)` 只提供对象属性。Addict 初始化时创建 `__parent`、`__key`、`__frozen`。仅保存后者会遗漏配置内容，即使三项属性都存在，也不能证明配置已被完整保存。

安装源码的方法归属表显示：

- `__new__`、`__getitem__` 来自内建 dict。
- `__init__`、`__setattr__`、`__setitem__`、`freeze/unfreeze`、`_hook` 来自 Addict。
- ConfigDict 自己覆盖 `__missing__` 与 `__getattr__`。
- ConfigDict 缺少 mapping 键时抛出 KeyError；缺少属性时转换为 AttributeError。不能把 Addict 本身的自动嵌套行为直接归给 ConfigDict。

## Parent、Key 与冻结行为

Addict 的 `__setitem__` 不只是写入字典：若存在待关联的父对象，它会将子对象写入父对象，然后删除子对象的 `__parent` 与 `__key` 属性。因此，恢复时调用此方法可能再次触发父对象修改，并改变原快照中的属性存在状态。

冻结检查阻止增加新键，但允许替换已有键。`freeze` 使用对象属性更新冻结状态，并递归处理已有的 Addict 子对象；`unfreeze` 调用 `freeze(False)`。原始属性缺失也是状态，恢复时不能无条件补出不存在的 parent/key 字段。

## 历史快照缺失的证据

被保留的 CPU fixture 快照为 800 个文件：798 份 Tensor Storage，以及 manifest 和完成标记。记录大小为 1,635,317,622 bytes，state SHA-256 为：

`1aa48a77cea13322ef250e3281b2d91278e3dbf2737ae501d6ac8c3f7a236ea0`

其中 ConfigDict 被编码为普通 object node，只保存了 `__parent`、`__key`、`__frozen`，未保存 mapping items。丢失的 mapping 不能从该 manifest 反推出，改变分配函数也不能补回这些数据。

本轮真实模型测试必须重新读取实际加权模型的对象元数据，并仅在内容 SHA 一致时复用历史 Tensor 文件；不得改写旧 manifest 来假装恢复了遗漏字段。该历史产物始终属于 CPU fixture，不能被命名或解释为原生 C0。

## 可核验来源

- `evidence/CONFIGDICT_ROUND1_SOURCE_RECEIPT.json`
- `evidence/VERIFIED_CONFIGDICT_UNIT_TESTS.json`
- `evidence/VERIFIED_CPU_LEGACY152_CONFIGDICT_R1_RECEIPT.json`
- `candidate_patch/native_control/configdict_adapter.py`
- `candidate_patch/native_control/snapshot.py`
- 安装源码审计的脱敏摘录（应由最终发布程序从本地原始证据生成）


## 本轮最终边界

ConfigDict 专项修复消耗 1/2；剩余额度未用于独立 timm Enum 类型。完整 CPU 门槛失败，因此 GPU C0 0/2、短程交叉 0/4、完整 B1～B4 0/4。正式 487 帧 runner 的阶段控制接入仍未完成。该任务没有产生关于 D 关闭、轨迹压缩原因或算法改进收益的新实验证据。详细失败链见 `TASK004C_B_REAL_MODEL_ROUNDTRIP.md`。
