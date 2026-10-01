# v12_r63：Case12 宽块实验

**研究版本，不晋升、不推荐本轮 Judge15；主线仍为 r41。**

N256 连续 N-major 分核，缓存前 K512 的 B，A256/B128 独立双缓冲。

- [完整源码](v12_r63_case12_wide_partial_b.asc)；SHA256：`d18e766a573791a1e4f756ddc7680fdc7418da2c8886535cd48da0005cad3fca`。
- CANN9.0.0 / Ascend910_9362 / 20 Cube 核完整编译通过。
- 164配置×3次 + 22配置×5次，共186配置、602次精度调用，全部通过。
- 同批 r41 的8组性能首筛：中位耗时下降 -1.73%（正数更快），最好 8.50%，最差 -4.34%。r62在噪声范围；r63/r64的稳定退化阻止通用替换。
- 没有执行独立性能留出、新的mssanitizer或Judge15；不能把合成样本的收益当作隐藏Case12收益。
- [完整报告、逐项性能及计数器](../V12_npu_lab/results/case12_wide_load_20261001/REPORT.md)；[版本manifest](v12_r63_manifest.json)。
