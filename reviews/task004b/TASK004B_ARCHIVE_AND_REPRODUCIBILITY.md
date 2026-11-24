# 原始资产与复算

完整的16个新增逐运行ZIP保存在本目录raw_archives，包含observer、native/video.npz、native_rerun.rrd、配置、轨迹、日志和运行收据；每个文件已逐个CRC、SHA256、大小核验。Seed43的8份历史ZIP原位保留。外部原始ZIP索引见TASK004B_RAW_ARCHIVE_INDEX.csv。

轻量评审包包含最终报告、全部汇总和必要逐帧表、配置、收据和轨迹；完整评审包另加入24次observer及resource原始日志和完整衍生事件表。为避免重复数GB原始数据，native/video.npz和.rrd仍在逐运行完整原始ZIP中，其SHA与成员索引随评审包提供。没有删除远端产物。

CPU复算入口：tools/analyze_repeated.py；统计入口：tools/summarize_repeated.py。依赖原Task004A的已校验公式模块及本地GT，不导入torch，不执行GPU工作。执行脚本、版本SHA、输出校验和退出码均附在证据目录。
