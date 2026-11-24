# 在ChatGPT中评审本项目

## 一次性连接

本仓库为私有仓库。需要在ChatGPT的设置中找到GitHub应用/插件，连接Pseven0108账号，并明确允许访问`Pseven0108/GameCam-VO`。仅粘贴私有链接并不能授予访问权限。不同账号方案和聊天模式的GitHub支持范围可能不同。

官方说明：[Connecting GitHub to ChatGPT](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt)。如果普通聊天没有GitHub入口，可检查账号支持的Deep Research/agent等模式。若仓库不可见，先查GitHub应用是否获准访问该仓库。

## 可以直接给ChatGPT的请求

请通过已连接的GitHub读取私有仓库Pseven0108/GameCam-VO的默认分支。

先读README.md、PROJECT_STATUS.md和REVIEW_INDEX.md，再评审reviews/task004c-b-release-fixes/FINAL_REVIEW.md与同目录五份TASK004C_B报告。

请重点核对：

1. native_control/install.py的Local BA失败关闭、motion_only和INIT_D边界。
2. native_control/file_backed.py的跨进程storage恢复、dtype/shape/stride/offset/alias保持。
3. CPU共享worker替身和真实Tracker/Rerun证据的区别。
4. 完整真实C0预算仍未知、多arena累计容量是否构成后续阻断。
5. 原118项加34项的真实测试日志、失败迭代记录和原资产保护证据。

使用source/DROID-W/对照当前源码；必要时沿REVIEW_INDEX.md追溯Task001至Task004C历史证据。明确区分实测、静态推导和未验证事项；不要将CPU合成测试写成GPU或轨迹性能结论。

## 内容身份

GitHub快照提交与原运行源码提交不同。规范身份见source/SOURCE_PROVENANCE.json；原源码文件逐SHA对应source/SOURCE_FILE_MANIFEST.json。最新评审包的原始SHA清单保持不变。历史出版省略见publication/manifests，不把省略附件说成已审查。
