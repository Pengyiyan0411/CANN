# 已装载技能与本题适配记录

2026-09-26；用户明确要求先装载已有算子开发技能，再离线分析设计。以下技能已阅读并用于本次工作；“装载”不表示安装 CANN 或完成端到端开发。

| Skill | 本次应用 | 当前阶段 |
|---|---|---|
| [ascendc-operator-dev](C:/Users/cc/.agents/skills/ascendc-operator-dev/SKILL.md) | 用开发编排区分需求、设计、用例、编译、精度、性能交付 | 只完成分析设计与用例规格 |
| [ascendc-operator-design](C:/Users/cc/.agents/skills/ascendc-operator-design/SKILL.md) | ABI、两级 tiling、workspace、API级伪代码、完整 buffer 表 | 已应用 |
| [ascendc-operator-performance-optim](C:/Users/cc/.agents/skills/ascendc-operator-performance-optim/SKILL.md) | 审查 tiling、内存与流水假说；单变量、同集对照、最多三轮 | 离线设计，未声称性能优化闭环完成 |
| [ascendc-operator-testcase-gen](C:/Users/cc/.agents/skills/ascendc-operator-testcase-gen/SKILL.md) | 双 dtype、全部布局、常规/边界场景及共享用例 | 已生成规格，设备执行未开始 |
| [catlass-operator-design](C:/Users/cc/.agents/skills/catlass-operator-design/SKILL.md) | 官方源组件选型、自定义归约契约、接口、资源约束 | 已应用，组件兼容性待编译 |
| [catlass-operator-performance-optim](C:/Users/cc/.agents/skills/catlass-operator-performance-optim/SKILL.md) | 基线冻结、同 shape 比较、调参留痕 | 已转成未来实验计划 |

已读取的设计参考包括 AscendC `templates/design-template.md`、`references/reduction-tiling.md`、`references/general-tiling-principles.md`，性能 `tiling-prof.md`、`memory-prof.md`、`pipeline-prof.md`，用例 `templates/test-cases-template.md`；CATLASS 的 `design-document.md`、`matmul-templates.md`、`epilogue-components.md`、`custom-epilogue.md`。CATLASS 固定仓库的实际代码及优化文档由独立研究一起核对，来源见 `catlass_feasibility.md`。

适配依据：

1. 用户已指定目前没有算力，任务是分析设计。开发 skill 中环境配置、编译、上机精度与 profiler 流程留到实现阶段，不据此要求立即申请环境或中断设计。
2. 官方单文件 `kernel.asc` 与 `run_kernel` ABI 优先于通用 skill 的 `ascend-kernel/csrc/ops`、torch 注册、aclnn 工程目录模板。设计放在本项目 `V9_design`，不修改官方框架。
3. 含矩阵乘的设计采用 Cube 路线。通用 Vector 模板中“半精度必须先 Cast”的说明不能扩展为 Cube 不支持 half/BF16；Cube 保持半精度输入与 FP32 累加，Vector 归约使用 FP32。
4. 512 B 对齐用作性能考虑；不能把建议对齐升级为输入合法性限制，也不能让 padding 越界。UB、L1、L0 按所选模板逐项核算，不能无差别套 elementwise 的 bufferCoefficient。
5. 现有成绩只作历史基线。本次没有当前设备上的 before/after profiler，相关表格标成 NOT_RUN；不生成伪造的精度 Pass、性能提升或最终汇总报告。
6. 题目输出 FP32 且 golden 为完整 FP64，精度门槛不能按输入半精度降为1e-3。历史组合容差与严格双门槛分别记录，不自行替官方裁定。

这不是因 skill 而停止已授权工作：当前离线分析与设计已完成，上机阶段本就不在本次用户要求中。
