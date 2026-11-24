# S1/S0完整调度记录与强制重放协议

状态：DESIGN_ONLY；没有实际S1/S0调度文件。两个JSON是规范，不是历史日志改写出来的事件流。

## 范围和身份

S1由B1(D=1)自然产生，S0由B4(D=0)自然产生；两者从唯一C0的独立恢复启动。主循环局部W=U=1；初始化已经包含在C0中。调度从C0.next_input到RGB487，连同Final BA两阶段及Filler离散图结构完整记录。原始loop/online BA/mapping关闭，不能引入额外阶段。

每个事件包括唯一递增ordinal、stage/phase、实际RGB ID、零基input index、原始stream timestamp、执行前后counter、前一事件hash和本事件hash；RGB ID和timestamp分开，避免把RGB312错误索引为数组312。使用输入Manifest的显式映射。Final/Filler的批处理保留自身输入ID列表，不捏造单帧时间。

## 稳定身份与拓扑摘要

关键帧实例ID由输入RGB、候选代次、tracking/filler角色构成；slot可被重用，不能用slot代替永久ID。边实例ID包括graph_id、产生事件ordinal、方向和边代次，两个相反方向是两条边。同一几何pair再次加入是新实例。

图摘要按实际tensor顺序编码：graph类型、slot→实例/RGB映射、active/inactive/bad ordered edge tuples、age、active window与BA有序support。维护active、inactive、bad三个pool及数值缓存行的对应关系。不能对edge排序后只做集合哈希，因为原生规约顺序与缓存行顺序有影响。完整源/目标slot和RGB身份同时记录。保留相等anchor去重的实际结果，不编造额外边。

规范化控制摘要只包含离散数据及冻结配置，不包含Pose、disp、target、weight、U、eta、残差、距离或预期轨迹。D的臂值在独立执行合同记录，不能因为跨臂D不同而要求整个运行manifest hash相同。

## 逐帧事件与副作用

1. frame_begin核验游标、输入ID、slot map和C0身份。
2. 在MotionFilter的97行admission布尔门控处记录原生delta门槛结果、force flag、选定结果和原因；数值幅度写独立诊断日志。自然臂selected=natural。强制臂由schedule选择分支，真实feature/context/prior仍从当前RGB算。MotionFilter.track的返回值不是admission，不能靠覆盖返回值实现。
3. 接纳分支完整执行上下文/深度/DINO生成、net/inp/fmap更新、append和count重置；拒绝分支保留count递增。不得执行后再倒改counter“伪造拒绝”。
4. 记录候选的边龄清退、add_proximity请求顺序、内部去重、max_factors容量驱逐、实际新增边与store-to-inactive标志；执行3次predecision graph.update。
5. 每次graph.update记录active/inactive选入mask及原生BA最终有序ii/jj（不只活跃图），t0/t1、inner iterations=2、use_inactive、motion_only、lm/ep、EP、lr/weight_decay、source unique slots和调用阶段。target/weight/damping由当前网络及当前Pose正常生成，不从产生调度的臂复制。
6. 记录Local BA判决：drop或retain及阈值/连续drop上限/force原因；原生BA没有收敛“accept”返回值。删除须经过原生rm_keyframe的复制、重排和counter/t1回退；保留须执行原生2次retained更新。保存drop计数与下一预测slot更新结果的hash，数值不作为强制调度输入。
7. 记录graph.age增量、清理和本帧结束控制hash，包含无BA/无候选帧，不能只写关键帧日志。

## 重放入口和不变量

强制B2(S1)和B3(S0)在每个原生离散门控点取记录决策。必须从C0正确重建所有受控前驱状态，才能使用相同slot和边引用。新增边仍走原生add_factors，为当前分支产生corr、初始target、net和inp；不直接覆盖ii/jj跳过缓存。

对于嵌套自动行为，事件只消费一次：例如add_factors内部容量删除既有自己的rm_factors事件，就不能预先执行删除后又让原生自动删除第二遍。采用“单一primitive执行 + 门控拦截 + 前后摘要校验”，不是“执行原生 + 手动再套一遍效果”。去重、cap、age清退、inactive过滤、slot重排和图clear均纳入事件账本。任何未经登记的自动变化、无效引用或重复/漏消费都使整次运行失败。

自然分支结果不同于强制事件不是错误；它应被记录为counterfactual gate disagreement。只有所选事件执行后不满足拓扑/slot/调用顺序不变量才是协议失败。可以强制保留低视差候选或保留投影支持很少的边，这会使数值退化；不得为改善结果另删边、调权、换anchor或夹紧新数值。

## Final BA 与 Filler

必须固定最终BA各自新建图的精确边序和步数。原生流程仍临时关闭depth正则、执行7和12次update_lowmem outer step，每次2个原生内部迭代；U更新沿原生默认关闭，W沿原生开启，恢复metric flag后再Filler。两臂同一Schedule若最终图自然不同，必须按所选Schedule强制其离散建图；允许数值结果、对应、U/weight响应不同。

Filler冻结16帧批次划分、input IDs、t0/t1锚点身份、临时slot[N,N+M)、两次add_factors的实际去重顺序和12次motion_only更新。其插值Pose、特征、U插值、权重和优化输出不能复制自然臂值。counter必须回退；N+16<=500作为硬门槛。R2已有filler缺少DINO输入时的处理保持原样，不能为了协议另开模型路径。

如果用户最终只批准固定前端、允许Final BA自然建图，则必须另立较窄协议；本稿不把那种设计称为全过程固定拓扑。

## 原子封存和证据

每个调度分块append-only写入、逐事件hash链；所有图变化可由事件还原，BA before/native-after/clamp-after必须成对。pipeline_end、完整调用数、frame覆盖、各图最终控制hash核对后才生成complete=true的封存版本。失败只有incomplete诊断，不得当S1/S0重放。历史974帧判决和2488条BA边界可作需求参考，但缺少图突变/缓存，不能补造现有调度。

独立numeric audit保存自然门槛值、反事实门槛值、权重/U摘要、native负值/clamp计数和各阶段Pose；它不参与控制调度。禁止把另一臂的预测数值喂给当前臂。

## 目前可行性

从源码看，同一C0且同一完整离散事件前缀可保持相同slot和图索引，这是设计可行性推断，不是已运行证明。原生代码没有持久事件调度器、完整恢复入口和primitive gate，必须未来批准独立harness实现及短重放验证。遇到必须修改BA公式或修复原生缓存才能维持图兼容的情况，停止，不在本任务内实施。

## 设计文件交付自检

两份schema对22类事件逐类规定payload必填项，包括graph_create/clear、inactive support、edge age和slot reindex；不能只声明事件名称却允许空payload。JSON字段约束仍不能证明hash链、引用有效性或实际native重放，这些必须按恢复验收合同在另获批准后执行。本轮没有生成任何真实事件流。
