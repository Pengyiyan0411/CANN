# R26_DENSE_PACKET 提交说明

先提交 `R26_DENSE_PACKET.asc`。它是完整单文件，不需要与其他文件拼接。
`CONTROL_R25.asc` 与之前 `R25_NATIVE_TARGETED.asc` 原字节相同，用于回退或相邻对照。

保持 Case5 的多 batch 专用入口；仅对原 Native 中 B1、K128、M/N>32、blocks>1 使用 packet 消费者。
完整N列的相邻块合并DMA，尾列按有效范围搬入；入UB后释放GM槽位，原plan/Cube/partial与最终归约不变。

本地源码回放、host分派、边界检查通过，详情见三个 CHECKS 文件。没有本地 CANN/NPU 测试。
先核对15/15及误差，再比较13/14；Case5以当前6.45–6.60 μs的观测为参考，保留评测波动余量。
若只变化零点几微秒，不凭一次提交认定收益；用 CONTROL_R25 相邻对照。其余点同样需要完整回传。
失败或13/14无可重复收益，回退CONTROL_R25。暂不推进其他测试点，也不追加shape探针。

`DESIGN.md` 包含同步、尾块、UB复用及数值边界。`MANIFEST.json` 绑定源码hash。
在完整归档仓库根目录的 BMMS 文件夹，可按主 README 的命令重建源码和CPU检查。
