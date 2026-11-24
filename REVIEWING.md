# GPT-chat 评审入口

指定仓库Pseven0108/GameCam-VO、分支codex/task004c-b-format-runner-20261124；先读README、PROJECT_STATUS和REVIEW_INDEX，再读reviews/task004c-b-format-runner-20261124/FINAL_REVIEW.md。

重点检查：Format原单例恢复；CPU fixture与真实C0的区分；854文件SHA；新GPU进程18,143节点恢复证据；SummaryWriter目录副作用；217项Mock盲区；RGB019未处理、Short80/正式组0次；失败即停和source pin保护。

公开副本脱敏，不能拿公开的C0结构元数据直接恢复模型，不能要求脱敏后原始文件SHA保持。只以公开FILE_SHA256_MANIFEST计算交付完整性。原始Tensor、RGB、GT、Arena和Rerun二进制没有上传。

本分支附服务器清理完整包：review_packages/GAMECAM_SERVER_DISK_CLEANUP_20261124_R2_REVIEW.zip，展开材料reviews/server-disk-cleanup-20261124-r2。重点审查缓存可重建性、七份归档副本核验、白名单删除与前后保护哈希。本次没有新增算法实验。
