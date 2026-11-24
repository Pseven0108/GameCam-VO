# 真实GPU C0采集

PASS。GPU仅一次采集；退出码0；436.311431s（模型子进程计时，含完整序列化/核验）。

RGB001～018真实输入；INIT_D=0；12个初始化关键帧；8+8+8=24次原生BA；RGB018 frame-end停点；RGB019尚未读取。原始R2配置、K、buffer500、seed43、模块和权重保持。

state SHA `18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92`；manifest原始SHA `f55ed3744c2d0d7af0db7d99c019c558fd36e2ef2f99186abec7ce8821758d47`。完整C0 854个文件（852 Storage、manifest及COMPLETE）共2,517,456,938 bytes，全部SHA核验。

47状态族、18,143对象节点，Storage未压缩10,027,350,972 bytes。保存前精确压缩预算：2,517,456,938 bytes；最低free要求13,810,778,112 bytes，含10GiB底线及预留。实际文件数与预算匹配。

源commit `5d357c1d3079de134dd8b41a20a00632da37f0b0`，tree `c018a65009aaf4f7457e2da5225a5f322a168b77`；其后未改源码。C0是不可变真实快照，后续恢复检查亦核验所有载荷；没有把CPU fixture改名为C0。

原生Rerun recording生成，3495924bytes，SHA `04b87c29dcebcc7a7215469fade2e5817badbc1cf6c7adaad1076b0b0bb8f5bb`。仅确认文件与退出状态，浏览器实时画面未验证。
