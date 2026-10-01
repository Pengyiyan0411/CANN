# r2 HTTP 413 上传修复

## 原因

用户返回的 HTML 明确为 `413 Request Entity Too Large`。这是 HTTP 请求内容超过服务器或代理的限制，不是 kernel 的编译、精度或运行失败。服务端具体阈值未知，也可能按包含编码/表单开销的整个请求计算；本次不臆测固定上限。

## 提交文件

- 使用：[`v13_r2_submit_compact.asc`](v13_r2_submit_compact.asc)。
- 原始可读源码 `v13_r2_case12_o10.asc` 保留。
- 文件体积：380,535 → **300,552 字节**，减少 **21.02%**。
- 压缩版小于此前用户确认能提交的 r72（363,256 字节）。实际服务器接收仍需重新上传确认。
- 只删除注释、空行和冗余横向空白，按 C++ 规则先处理反斜线续行；字符串/字符常量及预处理指令逻辑边界保持不变。
- 保留全部 kernel、路由、r72 小点优化和 Case12 O10；不引入算法修改，不新增版本号。

## 等价验证

1. 本地校验原始/压缩源码的逻辑行词法内容一致。
2. 在原 NPU 环境使用 CANN 9.0 Bisheng 对同一路径下的两份源码分别做 Host、Device 预处理。排除空白后，字符串及其他代码内容完全一致：
   - Host 438,790 个 token chunks，SHA256 `3ef749b08c1203e766a83b677a93c4acc257bf6cbd1ab75184936f4f54022fa3`。
   - Device 1,108,002 个 token chunks，SHA256 `e8ff7d0cf6d108445a27582904f8ecb5ae18f0674ce7d4afc44ee8c6a123482e`。
3. 沿用原 r2 的编译及 NPU 实验记录，不因仅注释/空白变化重复整个性能实验。历史严格抵消精度用例及 sanitizer 限制仍见 `VALIDATION.md`；413 本身与这些问题无关。

压缩版 SHA256：`e799dbe1443231c957e4b4cc334571742d4fddd3807fe80af883da113de11a6f`。

生成脚本：`../V13_npu_lab/compact_submission.py`。
编译器等价证据：`evidence/compact_preprocess.json`。
版本状态已更正：r1 仍为已接受基线，压缩 r2 为待 Judge15 的提交候选。
