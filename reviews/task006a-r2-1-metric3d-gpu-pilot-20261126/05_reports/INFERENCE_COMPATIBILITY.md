# 权重兼容性与只读取值

初始Attempt01因仅缺少depth_model.encoder.mask_token停止，0 forward。
实际固定ViT_DINO_reg.py定义mask_token为零，只有masks!=None才读取。
RGB路径不提供mask；限定只允许此键缺失，并在encoder输入前以只读hook验证masks=None。
任何别的missing/unexpected键仍停止；没有删除参数或改checkpoint。
所有33前向都有encoder输入记录，mask均None。参数不用于实际推理，没有随机未加载权重参与输出。
qualified Smoke的bin hook与无hook结果depth/confidence都max_abs_diff=0。
读bin hook只返回None，不改变原生forward输出。保留旧严格源码、加载失败收据、新源码与每阶段SHA。
