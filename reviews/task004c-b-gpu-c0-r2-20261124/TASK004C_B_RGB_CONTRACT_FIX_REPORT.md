# 首帧RGB-only合同修复

本次运行候选：`02f8c8308274489ff7eff83fa9b87b98db74122e`，唯一父提交`668a88c74c7f7a88a572679d2bd8e86c0a05514b`，再上一层为完整候选`0931141cf88247dc8fb0c7628c1d91b6531fea90`。GitHub评审快照提交不作为运行提交。

与668a88c7比较，运行源码只修改`native_control/dataset.py`。父类Dataset、BA、CUDA扩展、原R2、权重和RGB保持不变。

修改前SHA：`dcb87c7294a71ddaa772545ba3b38ce9402dfd47031357a57a3ef315972a8d12`；修改后SHA：`2b2eeee4beff110def2bcbdf57c96384780aacd26853aaa296ec4b6890e523d9`。原文件、改后文件和Git diff均保存在`remote_evidence/evidence/`。

## 严格接受条件

- 在调用父类前拒绝任何非None的depth_paths或poses，防止标签读取。
- row RGB ID必须是int并等于index+1；timestamp必须为对应int，游标必须连续。
- color必须是Tensor，shape=(1,3,360,640)；返回pose必须为None。
- depth必须是CPU、float32、strided Tensor，shape等于RGB的H/W，元素全部严格为零。
- 原tuple和Tensor对象原样返回；失败不推进seen。

没有删除depth检查。非零、NaN、Inf、错误shape/dtype、非CPU和标签输入均拒绝。

**depth=None兼容性测试按本指令的“必须为Tensor”条款解释为拒绝用例。** 真实父类使用全零Tensor，运行路径不受此解释影响。非CPU负例用meta Tensor，CPU测试没有创建CUDA Tensor。

## 结果

21/21真实Loader及负例测试通过，真实RGB001～018连续验证通过。后续GPU确实处理完18帧，旧首帧错误没有再次出现。该修复不代表C0序列化或恢复已经成功。
