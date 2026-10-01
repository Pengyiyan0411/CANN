# BMMS V13

> 已确认先前“Fail”为 HTTP 413 上传请求过大，代码未进入测评。请提交 `v13_r2_submit_compact.asc`；它与原 r2 的 Host/Device 预处理代码一致。已接受基线仍为 r1。

- 已接受基线：[v13_r1_baseline_r72.asc](v13_r1_baseline_r72.asc)，与用户确认的r72完全相同。
- 本次15点提交：[v13_r2_submit_compact.asc](v13_r2_submit_compact.asc)，r72 + 队友Case12 O10路线，已去除NBIT1减速探针。
- [分支与形状分析、下一步优化顺序](CASE12_BRANCH_ANALYSIS.md)
- [编译、精度、配对性能及未解决问题](VALIDATION.md)

r2已在卡上完成本地验证，尚未提交Judge。93个合成配置中92通过；唯一严格抵消用例在旧版也以相同结果失败。race/init检测仍有旧新版共同出现的未排除报告。请保留r1作为回退，不将本地合成结果等同15个隐藏测试点。

上传413的原因、更正与等价校验见 [R2_UPLOAD_413.md](R2_UPLOAD_413.md)。原始可读源码仍保留。
