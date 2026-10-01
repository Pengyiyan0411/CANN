# v12_r64：Case12 宽块实验

**研究版本，不晋升、不推荐本轮 Judge15；主线仍为 r41。**

r63 的对照：B缓存前 K256，A/B均K256双缓冲，减少阶段切换。

- [完整源码](v12_r64_case12_wide_cached_stage.asc)；SHA256：`892be012d85cee5e50756da556401aa3fe8106aee813843f08ab498327c25ee6`。
- CANN9.0.0 / Ascend910_9362 / 20 Cube 核完整编译通过。
- 164配置×3次 + 22配置×5次，共186配置、602次精度调用，全部通过。
- 同批 r41 的8组性能首筛：中位耗时下降 -4.17%（正数更快），最好 3.35%，最差 -5.20%。r62在噪声范围；r63/r64的稳定退化阻止通用替换。
- 没有执行独立性能留出、新的mssanitizer或Judge15；不能把合成样本的收益当作隐藏Case12收益。
- [完整报告、逐项性能及计数器](../V12_npu_lab/results/case12_wide_load_20261001/REPORT.md)；[版本manifest](v12_r64_manifest.json)。
