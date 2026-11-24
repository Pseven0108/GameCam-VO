# 存储与保护

真实C0精确大小2,517,456,938bytes；852个Storage压缩载荷合计2,514,178,958bytes。未压缩Storage 10,027,350,972bytes。逻辑字节精确，文件系统分块/元数据使用明确预留，不冒称物理开销精确。

退出时数据盘可用14,654,013,440bytes，13.647614GiB。新Arena共5个文件、4,492,800,016bytes（capture与restore两套），均保留，未清理。旧Arena和历史失败证据未删除。

3,759个受保护源/配置/权重/扩展身份全部一致；C0 metadata最终回读未变，源工作区clean；GPU compute apps为空。实例仍在线。无重启、关机、数据删除或其他Baseline运行。

记录：evidence/POST_FAILURE_PRESERVATION_SUMMARY.json；evidence/FINAL_RUNTIME_STATE_SUMMARY.json；raw_evidence/evidence/POST_FAILURE_PRESERVATION_AUDIT.json。
