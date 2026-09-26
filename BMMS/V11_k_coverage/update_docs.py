"""Publish the conservative feedback decision and the independently checked next candidates."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R15_R16'
PREVIOUS='7559b36a96b47f0a586fb9ca82beca189cafc86b';AUDIT='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    result=json.loads((ROOT/'V11_results/2026-09-26_r13_r14_submission/RESULT.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    for row in [manifest['control'],*manifest['variants']]:
        assert hashlib.sha256((OUT/row['file']).read_bytes()).hexdigest()==row['sha256']==checks['sources'][row['file']]
    assert checks['old_452_ordinary_outputs_equal_archived_R11'] and all(x['rejected'] for x in checks['negative_controls'].values())
    old=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+AUDIT],cwd=ROOT/'CANN_archive')
    snapshot=ROOT/'audit_current/AUDIT_R13_R14_DELIVERY.md'
    if not snapshot.exists():snapshot.write_bytes(old)
    assert snapshot.read_bytes()==old
    scores='\n'.join(f'| {k} | {v:.6f} |' for k,v in result['scores_same_current_T'].items())
    points='\n'.join(f'| {r["case"]} | {r["R11_us"]:.2f} | {r["R13_us"]:.2f} | {r["R14_us"]:.2f} | {r["T_us"]:.2f} |' for r in result['rows'])
    testrows='\n'.join(f'| {v} | {r["source_runs"]} | {r["repeat_pairs"]} | {r["domain_checks"]:,} | {r["strict_misses"]} |' for v,r in checks['runs'].items())
    write(ROOT/AUDIT,f'''# BatchMatmulMaxSum 当前审计：保留R11，验证R15/R16覆盖缺口

2026-09-26。最新图1是R14、图2是R13，均15/15 Pass。相同T下R14分数高于R11，
但差别不足以排除平台波动；当前不合并R13/R14，继续使用冻结R11工作基线。
R15/R16已完成本地离线检查并打包，等待平台提交，没有申请或消耗NPU卡时。

## 测量与噪声判断

| 版本 | 按本轮相同T复算分数 |
|---|---:|
{scores}

本轮T与上轮完全相同。R13对R11为−0.082309分，R14为+0.322480分。
每版只有一张逐点截图，无相邻R11控制或原始重复样本；无法计算可信的性能置信区间。
不按全局比例“去噪”，不拼接最短点，不把分数上升直接认作改动有效。

| 点 | R11 μs | R13 μs | R14 μs | T μs |
|---|---:|---:|---:|---:|
{points}

点10、11基本维持R11水平，未出现前两轮明显的单点改善。R14的其他微幅变化暂记为
未分辨，不能断言零收益，也不据此迁移基线。平台误差栏0.00%不是逐位相等证明。
[原图、CSV及源码身份记录](V11_results/2026-09-26_r13_r14_submission/AUDIT.md)。

## 当前路线

- R10的单轮网格收益曾由用户明确报告稳定；R11点11的明显改善已记录，仍作为开发依据。
- R12并行N归约、R13/R14减少启动核数均暂不合并，保留完整独立源码和反馈。
- 停止继续围绕同一网格微调，本轮验证旧fallback覆盖缺口；不推定隐藏测试形状。
- R09无明显收益、R07点5运行TLE根因未知、3项极端数值限制的历史结论保持不变。

## 已实现的两份独立候选

R11现有手写路径只覆盖K=32/64/128或K≥256且32对齐。其余规则K可能仍落入旧分发。
本轮通过公开形状guard复用已有分块Cube流水线；两版都从R11派生，不叠加R13/R14。

| 候选 | 新接管K | 保持条件 |
|---|---|---|
| R15_K32_GAPS | 96、160、192、224 | M/N均16对齐，沿用B/输入大小/核数与宏块门槛 |
| R16_K16_TAILS | 48..8176，K%32==16 | 同上；与R15新增范围互斥 |

仅修改两处K guard及一处说明注释。device指令、规划器、事件协议和缓冲布局逐字保留；
TryLaunch中的Tiny/Resident保护与K=32/64/128原生小K路径仍保留。
避免把SmallKProducer直接扩为192/224，从而突破原有L0B容量；使用固定KB的现有流水线。
R16会首次在这些路线使用16元素K尾部，已经检查实际kr搬运、转置地址和单槽事件收尾。

这是覆盖实验，不保证隐藏测试命中，也不保证命中后变快。不能凭点8长期不变就确定它的
K或分支。若两版都无已分辨收益，停止继续扩K guard，转向M/N尾块或向量路径定位。
[设计、地址/同步推导及官方API依据](V11_k_coverage/DESIGN.md)。

## 本地验证

| 版本 | 普通源码执行 | 重复输出对 | 新增guard枚举 | 普通精度失败 |
|---|---:|---:|---:|---:|
{testrows}

每版复用原452次普通用例，并增加R15的176次、R16的288次新域执行；覆盖四种转置、
两种dtype、负数、全零、多batch、M/N/K尾块与K=8176边界。旧用例与冻结R11逐位一致；
新增用例与FP64标杆比较，未执行旧通用fallback，不能称其与旧fallback逐位一致。

每版另有4494项原调度、7560项原guard、22次隔离归约检查。检查器使用实际Classify，
不把裸Eligible等同于最终TryLaunch。误接管K128、丢弃K尾16元素两种注入错误均被拒绝。
片上最大申请与R11相同：UB 132256、L1 393216、L0A 32768、L0B 65536、L0C 131072字节。

每版仍复现3项已知极端FP32消去/BF16中间溢出限制，未宣称全域精度达标。
本地没有CANN编译或NPU测试；CPU模型不验证设备缓存、流水、舍入或耗时。
[检查与SHA绑定](V11_k_coverage/CHECKS.json)。R11源码未改变，沿用其冻结结果作为回归标杆。

## 提交和归档

先提交 **R15**，再独立提交 **R16**。每份asc整体替换官方code/kernel.asc，保留官方main/CMake。
包内包含完全相同的R11_CONTROL。若有明显变化，用相邻R11控制复核，再决定是否合并；
小幅波动先按未分辨处理，保留完整15点和当次T。不要求本轮另外申请测试环境。

[提交包](BMMS_V11_R15_R16_提交包.zip) / [使用说明](BMMS_V11_R15_R16/README.md)。
[上轮交付快照](audit_current/AUDIT_R13_R14_DELIVERY.md)保留当时待测结论。
全部历史源码、截图、提交包保持冻结，归档至[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
实际推送与归档校验记录见本地ARCHIVE_STATUS.json。
''')
    hashes='\n'.join(f'- `{r["file"]}`：`{r["sha256"]}`' for r in [manifest['control'],*manifest['variants']])
    write(OUT/'README.md',f'''# R15 / R16提交包

先提交R15_K32_GAPS.asc，再独立提交R16_K16_TAILS.asc；均以R11为父版本。
每次将对应文件完整替换官方code/kernel.asc，保留官方main与CMake，不拼接两个候选。

| 文件 | 用途 |
|---|---|
| R11_CONTROL.asc | 与已交付R11完全相同的对照 |
| R15_K32_GAPS.asc | 新覆盖K=96/160/192/224 |
| R16_K16_TAILS.asc | 新覆盖K=48..8176且K%32==16，与R15独立 |

两版仅调整M/N均16对齐时的K准入，复用已有Cube流水线；保留Tiny/Resident与原生K32/64/128。
不含R13/R14网格变化。R13/R14均Pass，但单次小变化尚不能排除噪声，R11继续作为基线。
若候选出现明显变化，再用R11_CONTROL做相邻复核；保留完整结果与当次T。

本地R15/R16分别628/740次普通源码CPU执行通过，旧域输出与冻结R11一致。
新增域与FP64标杆比较，不等同于目标硬件精度通过。每版3项已知极端数值限制仍存在。
没有本地CANN编译/NPU验证，候选性能与平台正确性均待确认。

SHA256：

{hashes}
''')
    readme='''# BatchMatmulMaxSum：R11基线，R15/R16覆盖实验待测

R13/R14均15/15 Pass。同一T下R11/R13/R14为36.937232/36.854923/37.259712。
差别尚不足以排除波动，暂不合并R13/R14，保留R11。

- [提交包：R11控制、R15、R16](BMMS_V11_R15_R16_提交包.zip) / [使用说明](BMMS_V11_R15_R16/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R13/R14反馈及原图](V11_results/2026-09-26_r13_r14_submission/AUDIT.md)
- [设计与官方依据](V11_k_coverage/DESIGN.md) / [CPU检查](V11_k_coverage/CHECKS.json)
- [上轮交付快照](audit_current/AUDIT_R13_R14_DELIVERY.md)

R15新覆盖K=96/160/192/224；R16新覆盖K%32==16。两版独立从R11派生，
只改公开形状guard，device指令不变，保留小K和向量专用路径。先R15，再独立提交R16；
明显变化用相邻R11控制确认，不拼接最短点。

R15/R16分别628/740次普通源码CPU执行通过，314/370对重复输出核对通过。
每版1964169项K域guard枚举、两项故障注入通过；旧452次输出与冻结R11一致。
每版3项已知极端数值限制仍保留。本地无CANN/NPU验证，性能待平台反馈。

```bash
python V11_k_coverage/build.py
python V11_k_coverage/run_checks.py
python V11_k_coverage/update_docs.py
python V11_k_coverage/package.py
```

历史文件保持交付时状态，以当前审计和对应结果目录为最新结论。文档快照依赖CANN_archive。
归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
'''
    write(ROOT/'README.md',readme)
    # Repo-level links need the BMMS prefix; keep the reproduction commands explicit.
    repo_readme=readme.replace('](BMMS_V','](BMMS/BMMS_V').replace('](BatchMatmul','](BMMS/BatchMatmul').replace('](V11_','](BMMS/V11_').replace('](audit_current/','](BMMS/audit_current/').replace('```bash\n','```bash\ncd BMMS\n')
    write(HERE/'CANN_README.md',repo_readme)
    print('Current audit, frozen prior snapshot and submission instructions updated.')
if __name__=='__main__':main()
