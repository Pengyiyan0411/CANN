# R05 / R06 提交说明

两版分别从冻结的R04派生，互不包含。建议提交顺序：

1. **R06_MACRO_MMAD.asc**：整宏块MMAD、重排L0输入并合并LoadData；只改宏块生产者。
2. **R05_DEFERRED_MAX.asc**：N扫描结束再归约行最大值，完整C块跳过清填；改两类消费者。

每次选择一份`.asc`整体替换官方`code/kernel.asc`。入口仍为题目规定的`run_kernel`，
不改官方main/CMake，不额外设置ASCENDC_CUBE_ONLY，不手动拼接两版。
请按对应R05/R06保留平台全部15点、T列；若编译或精度失败，保留完整日志。

本轮R04截图15/15 Pass，按最新T复算34.496451，为现有记录最好。
用户仅标“SOTA”，R04归属依据唯一前序交付；平台源hash未提供。
该成绩不是R05/R06的成绩，两版均待平台编译、正确性和性能反馈。

R04/R05/R06各256次普通源码CPU运行通过，每版128对重复输出核对，普通输出记录逐位相同。
调度4494项、guard7560项；故意破坏尾N清填和L0C步长均被检查捕获。
原有3个极端数值限制仍复现。CPU模型不是硬件仿真；本地未CANN编译、未NPU测试。

在128×256、K256控制例，R06 MMAD调用16→4、LoadData64→32；三个宽N控制例中
R05行归约调用降到1/4。以上仅为源码API计数，不能当作设备提速比例。
R05微块消费者UB峰值181280B，GM workspace维持R04。两版保留既有路由及FP32点积。

父版SHA256：`f39d584297451a4ef15d559b67879571e3de86e21007f4a02b0b3552a904a09c`。

- `R05_DEFERRED_MAX.asc`：`ad5f140cdd401097975c65da5ffee8ba8922e66066cac1bfd73651619f7227aa`
- `R06_MACRO_MMAD.asc`：`435c3ff5e91f084bea95bf52423efe2e8d55db4c9b13d7f3225e8f8d4fd276a8`

MANIFEST.json与CPU_CHECKS.json记录相同源码SHA；完整设计和差异见仓库V11_lowlevel目录。
