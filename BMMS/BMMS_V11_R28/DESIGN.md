# R28：紧凑 Split-K 中间结果和按行条带归并

## 证据与范围

L04/L06 的 Case15 分别为 37.05/36.87 μs，匹配 L00 单分片对照 36.78 μs。与 L05 结合，支持 B1、M≤64、N≤128、MN≤4096、K4096..8192/32 对齐、原空间任务数1、S∈{8,16}。不把 S 固定为8，不猜精确 dtype/转置/几何。

基线为 R25_NATIVE_TARGETED，SHA256 `7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2`。R26/R27 不合入。新策略按运行时公开元数据选择，不读取输入数值、不使用测试点编号。

## 原实现的可削减工作

R23/R25 的 Split-K 已将约 37 μs 降到约 15 μs。每个 K 分片写一个部分 C，所有 AIV 在发布屏障后由一个 owner 完成 K 求和、N 最大值和 M 求和。

原部分 C 的 GM/UB 行距固定为 128 个 float。consumer 每次处理16行，对每个 K 分片单独 DataCopyPad 和 fence；小 N 还要初始化 UB 填充列。空间并行已充分确定，本版将一次次小搬运合并，减少归并阶段的指令工作。实际主要瓶颈是否在此仍是待验证假说。

## 生产和消费必须同时切换

生产端仅把 Fixpipe 的 ND 目标行距从128改为实际N。每个分片的 **32 KiB GM 槽位** 保留，写入该槽位前 M×N 个 float。原 A/B LoadData、MMAD、K 起点、K 尾段、累加和分片数保持不变。

消费端以原最大输入缓冲32768个 float 为上限：

```text
stripeRows = min(M, floor(32768 / S / N / 16) * 16)
mr = min(stripeRows, M - m0)
cells = mr * N
cp.blockCount = S
cp.blockLen = cells * 4
cp.srcStride = (8192 - cells) * 4
起始 GM 偏移 = m0 * N
```

一次 DMA 将所有分片的同一行条带读到连续 UB 区间。srcStride 是前一个块结束至下一个块开始的字节间隔，必须按本条带 `cells` 计算，不能误用整个 `M*N`。条带最大3个：S16/M48/N80 是三条带边界。S8 下本范围全部一次读完。

K 树每轮按原 `width/2` 分成两半相加，逐个 C 元素的加法顺序不变。N>64 时把后 N−64 列折叠到前部，再对最多64列执行原样式 WholeReduceMax；最后保留原 M 维 ReduceSum。保持最大值对负数的行为，没有拿未写入的 GM 填充参与计算。

全部 AIV 仍先等待本组 READY，再参加原 SyncAll，然后非 owner 退出。没有增加跨组自旋或改变 flag ID；不把部分参与者提前移出全局屏障。

| 示例（不是已知 Case15 精确形状） | 原 DMA 调用 | R28 DMA 调用 | 原 K Add 元素数 | R28 K Add 元素数 |
|---|---:|---:|---:|---:|
| M32/N64/K4096/S8 | 16 | 1 | 28672 | 14336 |
| M48/N80/K8192/S16 | 48 | 3 | 92160 | 57600 |
| M64/N64/K8192/S16 | 64 | 2 | 122880 | 61440 |

GM A/B/C 有效数据字节数、MMAD 次数、workspace 及全局屏障数量保持不变。收益来源是假设中的调用、fence、填充和向量工作减少，不能按 DMA 次数比例推导端到端加速。

## API 契约核对

[华为 Fixpipe 官方 API](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0251.html)规定 NZ2ND 的 dstStride 按目标 ND 行的元素间距计；N 为16倍数，沿用 FixpipeParamsV220 和原默认 ND 模式，仅调整行距。

[华为 DataCopyPad 官方 API](https://www.hiascend.com/doc_center/source/zh/canncommercial/800/apiref/ascendcopapi/atlasascendc_api_07_0265.html)给出的 GM 侧 srcStride 按字节、UB 侧 dstStride 按32字节块。这里 blockCount≤16，blockLen≤16384字节，实际块长与所有 UB 起点均32字节对齐，无需尾部 padding。没有引入新 API 家族或手写向量汇编。

## 验证结果与限制

- 直接抽取实际提交文件的 Producer/Consumer，在继承的 FP16/BF16、Cube/Vector、GM/UB 初始化和发布协议模型中运行；模型头文件重新生成并核对旧 hash，旧验证目录不写入。
- R25/R28 各76次运行，38组反向线程启动重复，零精度失败；所有输出逐位相等。包括两dtype/四转置、K4128/4160尾段、S8/S16、三条带、全负数/零/普通随机输入，以及 MN>4096 的旧路径对照。
- 223010组真实host函数分派对比，129170组命中紧凑策略，93840组非目标完整启动记录相同，224组Case5元数据保护检查；六种旧route均覆盖。
- 目标范围静态枚举 UB 最大131872字节，少于继承模型192KiB预算。GM未初始化读取、重复/遗漏消费、写错分片、flag守恒和屏障参与均检查。
- 故意改错 Fixpipe 行距、DMA 跨片步长、K求和为max、删发布屏障，全部被检出；删掉B==1 guard也被host对照检出。

CPU 数学模型不是实际 Cube 微架构，也不证明全部 FP16/BF16 值域的误差上界；普通有限输入检验不能替代平台精度。没有 CANN/NPU 环境，本地未做 CANN 编译、sanitizer 或硬件计时。不宣称已证明性能收益或所有测试点不退化。

Case5/13/14 的已知K128以及Case7的K<512均不满足新guard；保留原R25路径。Case6元数据仍未知。平台验收必须包括15点，与相邻CONTROL_R25交替比较后再决定是否替换基线。

## 复现

在工作区根目录：

```text
python V11_split_compact28/build.py
python V11_split_compact28/run_checks.py
python V11_split_compact28/check_host.py
python V11_split_compact28/record_results.py
```

依赖现有归档内的历史生成器、Python 和支持 C++20 的 g++。构建输出在本版 cpu_build/host_build。报告带实际源码、验证脚本和模型头文件 hash。
