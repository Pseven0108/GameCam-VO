# RGB019 阶段化续跑

实现并测试 capture / restore19 / short80 / formal487 模式；每个模式独立准入、独立 attempt、固定 source commit，前序阶段必须成功。实际 C0 捕获停在 RGB018 frame-end，next index18、next RGB019。

CPU 模拟验证了 next-input/cursor/graph/stage 合同。真实 GPU 恢复成功后，目录创建在进入 Tracker 之前失败。没有 STAGE_RESUME_INPUT.json、没有 RGB019 frame event、没有 SUCCESS.json。不能用修改 index 或伪造日志补足。

真实状态：RESTORE_STATE_PASS / ACTUAL_RGB019_NOT_REACHED。详见 `TASK004C_B_RESTORE_FINAL_REPORT.md`。
