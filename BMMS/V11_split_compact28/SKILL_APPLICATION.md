# 技能应用范围

本轮使用 `C:/Users/cc/.agents/skills/ascendc-operator-performance-optim/SKILL.md`，已阅读 tiling、data-copy、api-usage、memory、pipeline 的 references，并查阅 precision-eval/performance-eval 技能约束。

沿用已授权的离线开发方式：用户已明确无测试环境且要求继续推进，不重复索要NPU。交付遵循现有竞赛单ASC ABI，不改造成另一个工程；继续FP16/BF16输入和FP32 Cube累加。没有硬件环境就不伪称Profiler、CANN、sanitizer或NPU验收通过。

优化技能引用的独立 `ascendc-operator-code-gen` GUIDE/约束资源未安装；本轮使用已通过平台的原实现、现有源码模型及 DESIGN.md 链接的华为主文档核对新参数契约。没有引入新编译依赖，也未根据缺失资源额外申请权限。

已落实：明确元数据范围、单一策略变更、保留基线、资源边界核对、实际源码模型与反例、正反条件分派比较、平台复测与波动排除说明。实际精度和性能结论留待用户平台结果。
