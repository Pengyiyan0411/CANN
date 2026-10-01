# Case8 检测日志审查

## 不能用退出码0判断通过

本次普通构建的racecheck/initcheck明确显示未启用编译插桩并跳过；后续的`No error detected`不能覆盖这个事实。归档原日志，改用`--cce-enable-sanitizer -gline-tables-only`分别编译r12、r18，实际启用检测。插桩运行的输出仍逐例对照FP64，但数值正确也不能替代工具验收。

## 同输入、同编译选项对照

输入为合成M1041/N1105/K1032，FP16 NN负数、BF16 TT最后一列主导，均实际运行Case8路径。日志全部位于`evidence/results/`。

| 检测 | r12 | r18 | 定位 |
|---|---:|---:|---|
| memcheck ERROR | 64 | 64 | 最终Max归约的UB读写，分别r12:3910、r18:5488 |
| racecheck ERROR | 24 | 16 | 双方L0C MMAD RAW/WAW；r12另有UB WAW/WAR |
| initcheck ERROR | 19827 | 4596 | GM中间量与PRIVATE计划字段，r12另有4条UB |
| PRIVATE初始化报告 | 920 | 920 | Init中复制后的plan字段读取 |

每类两版都完成2个kernel的检测、输出正确，仍不能称为无告警通过。报告数量不同受到搬运指令数量/格式及报告去重影响，不能把“条数更少”解释成风险同比减少。

## 源码审查

1. `NzProducer`除`LoadStage`外，与r12的`ReuseProducer`相同；原`MaskedRowMaxConsumer`逐字一致。新旧模块完整差异及源hash存档。
2. MMAD第一次K迭代清零C，后续累加；`(mr/16)*(nr/16)<10`时插入PIPE_M barrier。这与[CATLASS TileMmad的阈值策略](https://catlass.readthedocs.io/en/latest/1_Practice/06_tile_development/)一致。被报告的累加指令是保留代码。此证据支持进一步区分检测建模与真实依赖问题，但不是“所有告警必为误报”的证明。
3. PRIVATE计划在`Init`内先整体赋值，再读取各字段。GM中间量包括pack写出的A/B、Fixpipe写出的ring和各worker写出的partial。静态依赖分别由全核pack屏障、READY/FREE握手、SyncAll建立；这些路径均有数值验证。尚未逐条证明检测工具是否完整识别这些依赖。
4. r12/r18最终Max均为`Max(merged,merged,tmp,p.M)`计数模式，三个相关TBuf分别申请p.M个float，输入复制p.M个float；没有发现源码级计数大于申请大小。插桩工具仍报UB读写，不能直接忽略。r19只在新Case8模块中将它改成显式完整64元素重复＋末尾掩码；原r12不改，另行检查工具结果与性能。
5. 新pack逐job覆盖唯一的NZ矩形，最后不足256行/128列独立处理，缺失行/列初始化为零，32B块重排后批量写回。UB两半不重叠；MTE3→V事件保护复用。未发现由本轮新pack产生的UB非法访问报告。

## 结论边界

上述检查覆盖2个形状/layout实例，不能代替全域异步安全证明。本轮会优先交付显式尾块改写经验证的候选；若仍有继承的race/init告警，必须在报告和交付说明保留，不能宣称全面sanitizer通过。

旧Case15报告也发现普通构建racecheck被跳过却误判通过，已更正该报告、README、SUMMARY及解析脚本。r12的主线接受依据仍是用户Judge反馈，源代码未改变。

## r19 实际检测结果

r19已用相同全指令插桩选项、相同两例完成三个检查，均实际执行而非跳过：memcheck **0 ERROR**，racecheck **16 ERROR**，initcheck **4596 ERROR**（GM 3676、PRIVATE 920）。三个检查的数值输出全部通过。

显式64元素重复及末尾掩码消除了这两例中最终Max的UB访问报告；不能据此反向断言原版本在真实硬件上必然越界。race/init仍有与r18同类、同数量的报告，尚未逐条关闭，不计为检测通过，也不因父版存在相似报告而自动判为误报。

最终交付r19为等待Judge验证的实验候选。258组合成输入、每组3次的非插桩数值回归均通过；两轮40例性能复测保留收益。完整计时和其他路径控制数据见[最终报告](REPORT.md)，原r12主线及Case15源码保持不变。
