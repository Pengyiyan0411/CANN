# v12_r62：Case12 宽块实验

**研究版本，不晋升、不推荐本轮 Judge15；主线仍为 r41。**

保留原分核与宽块，用 dstGap 减少 A 的 L1→L0 装载指令。

- [完整源码](v12_r62_case12_wide_load_gap.asc)；SHA256：`f782bbf7bbf7a78d7e5a7d71cb9e7076ec796439a285d95537be84c21b69b1a7`。
- CANN9.0.0 / Ascend910_9362 / 20 Cube 核完整编译通过。
- 164配置×3次 + 22配置×5次，共186配置、602次精度调用，全部通过。
- 同批 r41 的8组性能首筛：中位耗时下降 0.04%（正数更快），最好 0.34%，最差 -0.23%。r62在噪声范围；r63/r64的稳定退化阻止通用替换。
- 没有执行独立性能留出、新的mssanitizer或Judge15；不能把合成样本的收益当作隐藏Case12收益。
- [完整报告、逐项性能及计数器](../V12_npu_lab/results/case12_wide_load_20261001/REPORT.md)；[版本manifest](v12_r62_manifest.json)。
