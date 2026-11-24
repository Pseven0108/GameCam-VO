# 如何审查最新实验

当前仓库为公开状态，可直接读取公开的Markdown/CSV/JSON。也可通过已连接的GitHub按仓库Pseven0108/GameCam-VO、分支codex/research-review-20261124和路径读取。

先读README.md、PROJECT_STATUS.md、REVIEW_INDEX.md，再读reviews/task004c-b-gpu-c0-r2-20261124/FINAL_REVIEW.md及同目录的TASK004C_B_GPU_C0_R2_REPORT.md、C0_CLOSURE_BLOCKER.md和TASK004C_B_C0_STATE_MANIFEST.json。

重点核对：NativeViperRGB严格零占位合同；21项真实Loader/152项回归的原始记录和首次缺测试对照文件的失败；真实16+8初始化更新与24次BA；保存器拒绝Metric3D lora_dropout；完整C0和47族未持久化；未自动重试。

不能将初始化完成当成完整C0成功，不能把GPU前的CPU测试当成真实运行证明，也不能把Rerun文件存在当成浏览器渲染成功。运行源码与GitHub快照提交分开见source/SOURCE_PROVENANCE.json。

未来若仓库改回私有，应在ChatGPT中连接GitHub并授权此仓库，具体见[官方连接说明](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt)。
