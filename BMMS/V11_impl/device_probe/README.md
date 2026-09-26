# P01 / V11 R01 最小真机诊断

此目录为私有诊断工程，**不是比赛提交工程**。提交仍只替换官方 `code/kernel.asc`。
目的：确认新路线编译/真实结果/调度和耗时，停止仅凭隐藏15点猜瓶颈。
本脚本未在CANN上执行；P01和R01源码与提交包通过SHA绑定。

Python3 + numpy，CANN9.0/Atlas A2，实际可用AIC核组数1..64。先按机器方式
source CANN环境。`--cores`填AIC核组数，不能填AIV数。默认架构dav-2201，
设备由 `ASCEND_DEVICE_ID` 指定（默认0）。仅在已分配的设备上执行。

```bash
# 无设备动作：准备量化输入和完整FP64 oracle。
python3 run_probe.py --cores 20 --out ./run_a2

# 可选：有CANN的CPU机器可先编译；不会运行ACL/NPU。
python3 run_probe.py --cores 20 --out ./run_a2 --build-only --budget-seconds 1200

# 两版本正确性→两种密集shape的ABBA profiler。
python3 run_probe.py --cores 20 --out ./run_a2 --execute --budget-seconds 1200
```

这里20是示例，必须替换为机器的实际可用AIC数；脚本不固定设备核数。
每次调用有20分钟总墙钟上限；可用 `--budget-seconds` 调整至60..1800秒。
编译耗时也计入预算；若耗尽会保留日志和已完成构建，下次调用按输入/源码/可执行文件
hash重用构建。单个正确性进程60秒、profile进程120秒超时即终止，不继续烧卡。
卡死进程被杀后若设备仍报忙，应由环境管理员检查，不会自动重置整机。

22个不同输入：完整2×2宏块和尾块各覆盖FP16/BF16×四布局，两个小K回退用例，
两个密集shape各双dtype；每版本3次结果+1次预热，检查严格误差/组合误差/有限性/位重复。
正确性任一失败就结束，不采集性能。密集shape按实际核数增加B，使公开guard进入R01；
它们是自建用例，不能与隐藏点号对应。

性能阶段仅两个FP16 NN密集用例，P01→R01→R01→P01，20次输出调用，排除显式
预热和前10次调用。采集Task Duration和PipeUtilization，保留原始CSV。
脚本打印的host_call_mean_us包含分配/调度/同步，绝不可当比赛kernel耗时。
MIX可能有多个task类型，汇总脚本保留独立组；不擅自相加制造加速比。
验收时还要检查R01实际kernel名是 `bmms11_*`，没有走回退。

需要取回 `run_a2/session_*/` 下 `results.json`、编译日志、`task_durations.json`
及profile目录。不要只截汇总耗时。依据MTE2/MTE1/M/FIX/AIV利用情况，决定
下一步是输入驻留、Mmad粒度/流水、还是row-max消费融合。R01尚不能承诺快于P01。
