# v12_r66：实验分支

直接计算 BᵀAᵀ；256×128 矩阵乘与列最大值，保留原输出行 ownership。直接基于 r41，删除新增模块和唯一入口后可逐字节恢复基线。

实卡186配置、602次精度调用全部通过（另有短测和性能运行内检查）。8配置串行ABBA初筛，中位耗时下降 -1.94%，范围 -3.25%～-0.41%。正数表示更快。

不晋升，不建议本轮 Judge15。未运行独立性能留出及新 sanitizer；不能将合成数据当成隐藏 Case12 的收益。

完整实现：[v12_r66_case12_transposed_product.asc](v12_r66_case12_transposed_product.asc)；[详细报告](../V12_npu_lab/results/rethink_20261001/REPORT.md)。
