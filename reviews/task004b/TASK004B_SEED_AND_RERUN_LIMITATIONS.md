# 随机源与原生记录

原始主进程setup_seed设置Python、NumPy、PyTorch和CUDA种子；跟踪spawn入口未统一重新设种子。收据记录实际RNG状态，未为收据额外抽样。主进程和子进程的cudnn标志可能不同，完整保留原生行为，未附加新的deterministic/benchmark设置。

每组原生Rerun writer保持开启；本轮增加服务端独立.rrd保存和原生解码核验，每组唯一recording ID。Seed43历史归档没有.rrd，不伪造历史记录。服务端录制增加I/O开销；因此跨区组runtime不应被当作纯模型耗时差异。浏览器实时渲染未核实，且用户已取消该项作为GPU启动门槛。

Rerun服务在模型正常完成后由本次控制器终止，服务退出码-15代表受控SIGTERM；模型退出码独立记录为0。停止服务后再用原生rrd print检查可解码性；这证明文件可解码，不证明浏览器看到了全部对象。
