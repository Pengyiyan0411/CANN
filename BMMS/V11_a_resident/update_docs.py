"""Report implemented scope, observed baseline and measured logical work without claiming NPU speed."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R17_R18_R19'
PREVIOUS='e8782205d6477e86e3de31bdcad7c736087a1047';AUDIT='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    for row in [manifest['control'],*manifest['variants']]:
        assert hashlib.sha256((OUT/row['file']).read_bytes()).hexdigest()==row['sha256']==checks['sources'][row['file']]
    assert checks['R14_R19_ordinary_outputs_equal_bitwise'] and all(x['rejected'] for x in checks['negative_controls'].values())
    frozen=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+AUDIT],cwd=ROOT/'CANN_archive')
    snapshot=ROOT/'audit_current/AUDIT_R15_R16_DELIVERY.md'
    if not snapshot.exists():snapshot.write_bytes(frozen)
    assert snapshot.read_bytes()==frozen
    rows='\n'.join(f'| {v} | {r["source_runs"]} | {r["repeat_pairs"]} | {r["resident_route_runs"]} | {r["strict_misses"]} |' for v,r in checks['runs'].items())
    flows=[]
    for k in ['K256','K512']:
        a=checks['runs']['R14']['dataflow_fixtures'][k];b=checks['runs']['R19']['dataflow_fixtures'][k]
        flows.append(f'| {k} | {a["a_gm_bytes"]//1024}→{b["a_gm_bytes"]//1024} KiB | {a["gm_bytes"]//1024}→{b["gm_bytes"]//1024} KiB | {a["b_gm_bytes"]//1024} KiB不变 | {a["l1_peak_bytes"]//1024}→{b["l1_peak_bytes"]//1024} KiB |')
    traffic='\n'.join(flows)
    write(ROOT/AUDIT,f'''# BatchMatmulMaxSum 当前审计：按计划采用R14，交付R17/R18/R19

2026-09-26。用户要求按《BMMS_R14_技术审计与下一轮突破_20260926.md》推进，现将R14
作为开发与比较起点。R11和所有历史交付原样保留。这是按新计划调整工作基线，
不是新增测量证明R14优于R11；本轮没有新的平台截图或NPU时延数据。

## 当前性能证据

| 版本 | 现有平台状态 | 同一最新T复算 | 当前定位 |
|---|---|---:|---|
| R11 | 15/15 Pass | 36.937232 | 归因与回退 |
| R13 | 15/15 Pass | 36.854923 | 独立实验归档 |
| R14 | 15/15 Pass | 37.259712 | 按用户计划选定的开发基线 |
| R15/R16 | 尚未收到反馈 | 未知 | 冻结的R11后代 |
| R17/R18/R19 | 待提交 | 未知 | 本轮三个独立R14后代 |

R14对R11的+0.322480分仍可能含波动。点11为100.71→100.56μs，仅约−0.15%；
不能把R10到约100μs的主要改善重复归功于R14。现有单图证据不支持伪置信区间、全局
比例去噪或拼接各版最短点。[原始截图和逐点记录](V11_results/2026-09-26_r13_r14_submission/AUDIT.md)。

## 按计划完成的实现

| 实验 | 本轮编号 | 独立改动 |
|---|---|---|
| A：补32对齐K缺口 | R17_R14_K32_GAPS | 将R15的K=96/160/192/224 guard原样迁移到R14 |
| B：补16元素K尾部 | R18_R14_K16_TAILS | 将R16的K%32==16 guard原样迁移到R14 |
| C：完整A跨N驻留 | R19_R14_A_RESIDENT | K=256/512、每任务≥2个N宏块时，A每个M扫描只加载一次 |

三版没有叠加。R17/R18不冒充新发明，R19也不包含它们的覆盖扩展。
共同保留R14网格、输入精度、完整K→Max(N)→Sum(M)的顺序及原消费者。
R19单独增加固定RK的生产者和16个入口，原生产者作为fallback；B仍按K1=256双缓冲，
L0仍按K0=64和四微块次序计算，C ring及READY/FREE不变。

R19采用保守的launch条件nTiles≥2*pN，保证每个N分片均能复用A；混合1/2块分片仍走R14。
K512的A寻址包含kBase，转置A使用完整RK作为NZ步长，跨M块和batch均刷新。
新增A生命周期事件成对分配/释放，原B面板与L0事件独立保留。
[实现设计与官方API依据](V11_a_resident/DESIGN.md) / [原计划快照](V11_a_resident/INPUT_PLAN.md)。

## 减少的是逻辑搬运，实际时延待测

以下为同一个合成输入B=1/M=128/N=1024、1核组，实际源码CPU调用计数；不是隐藏点形状：

| K | A的GM→L1读取 | A+B读取 | B读取 | 每AIC L1申请 |
|---|---|---|---|---|
{traffic}

四个N宏块时，A读取下降75%，总输入读取下降25%；B、L1→L0、MMAD次数、C读写和
ring握手次数保持一致。该百分比不能解释为HBM事务或设备耗时下降25%。缓存、计算与
额外同步仍可能使收益很小。R19没有实现L0C双缓冲，也没有改变C的FP32中转精度。

## 本地检查结果

| 源码 | 普通执行次数 | 重复输出核对次数 | 驻留路径执行次数 | 普通精度失败 |
|---|---:|---:|---:|---:|
{rows}

R14/R19的普通输出逐位一致；所有候选的旧464次用例与冻结R14一致。
R17/R18新域在实际R14计划下执行，并与已有R15/R16相同输入结果核对。
R19额外覆盖K256/K512、两dtype、四布局、M/N尾块、多batch、同组多任务、多N分片、
单N及混合1/2块fallback；从真实模型API调用统计A/B字节、L0字节、计算和通信次数。

每版保留4494项原规划、7560项原guard、22次隔离归约检查。R17/R18另各1964169项K域
枚举通过。新增host选择验证{checks['host_checks']['checked']}组、16个kernel模板绑定通过。
转置步长错误、遗漏kBase、不刷新M块A三种故障注入均被拒绝。

本轮检查器单独记录单次L1峰值，避免把全测试历史峰值混同于K256实例申请。
每版仍复现3项已知极端FP32消去/BF16中间溢出限制，未声称全数学输入域通过。
本地未执行CANN编译/NPU正确性或性能测试；CPU模型不能认证真实流水可见性和缓存行为。
[完整检查与源码SHA绑定](V11_a_resident/CHECKS.json)。

## 下一次提交

按计划顺序 **R17 → R18 → R19**，每版都与包内R14_CONTROL比较。
每次整体替换官方code/kernel.asc，沿用官方main/CMake，三版不要手动叠加。
出现明显变化后进行R14→候选→R14复核，保存全部15点与当次T。
没有shape日志时，不通过故意失败猜点；无明显变化也不能自动证明目标域未命中。

完成首轮反馈后，再按计划选择半宏块双L0C或AIV预取的独立实验；不继续单纯微调网格门槛。
卡时仍不申请，本轮可先走平台提交。R07点5运行TLE根因未知的历史记录保持不变。

[提交包](BMMS_V11_R17_R18_R19_提交包.zip) / [使用说明](BMMS_V11_R17_R18_R19/README.md)。
[上轮交付快照](audit_current/AUDIT_R15_R16_DELIVERY.md)保留当时R11工作基线决策。
归档至[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)，推送校验见本地ARCHIVE_STATUS.json。
''')
    hashes='\n'.join(f'- `{r["file"]}`：`{r["sha256"]}`' for r in [manifest['control'],*manifest['variants']])
    write(OUT/'README.md',f'''# R17 / R18 / R19：三个独立R14后代

按用户技术审计计划推进，顺序R17→R18→R19。每份asc完整替换官方code/kernel.asc，
保留官方main/CMake，不能叠加不同文件片段。R14_CONTROL与已通过R14完全相同。

| 文件 | 只改变 |
|---|---|
| R17_R14_K32_GAPS.asc | 将R15的K96/160/192/224覆盖修改迁移到R14 |
| R18_R14_K16_TAILS.asc | 将R16的K%32==16覆盖修改迁移到R14 |
| R19_R14_A_RESIDENT.asc | K256/512且每任务≥2个N宏块，完整A跨N驻留L1 |

R17/R18不是R15/R16原文件；它们保留R14的规划层。R19独立从R14派生，不含覆盖实验。
同父版比较使用R14→候选→R14，保存全部15点及当次T，小变化暂按未分辨处理。

本地普通源码执行和新增地址/搬运/host选择检查通过，具体结果见CPU_CHECKS.json。
合成四N宏块样例中R19的A逻辑读取减少75%，这不是硬件耗时提升比例。
本地没有CANN/NPU验证；每版3项已知极端数值限制仍保留，平台正确性和性能待确认。

SHA256：

{hashes}
''')
    readme='''# BatchMatmulMaxSum：按计划以R14为基线，交付R17/R18/R19

R14已有15/15 Pass、同当前T复算37.259712分。用户计划指定R14为开发起点；
相对R11的0.322480分仍未排除波动，没有新的NPU性能结论。

- [提交包：R14控制与三个独立候选](BMMS_V11_R17_R18_R19_提交包.zip) / [使用说明](BMMS_V11_R17_R18_R19/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [用户计划快照](V11_a_resident/INPUT_PLAN.md) / [实现设计](V11_a_resident/DESIGN.md)
- [CPU检查](V11_a_resident/CHECKS.json) / [上轮交付快照](audit_current/AUDIT_R15_R16_DELIVERY.md)

R17/R18分别迁移已有两项K覆盖修改，保留R14网格。R19独立实现K256/512的完整A跨N驻留，
保留MMAD顺序、FP32 ring和消费者。按R17→R18→R19提交，各自用R14控制，不预先合并。
四N宏块合成样例中A读取减少75%、总输入读取减少25%；这只表示源码逻辑流量减少。
普通离线用例通过，3项已知极端数值限制仍保留；无本地CANN/NPU验证，实际收益待提交。

```bash
python V11_a_resident/build.py
python V11_a_resident/run_checks.py
python V11_a_resident/update_docs.py
python V11_a_resident/package.py
```

历史源码与结果保持冻结，以当前审计为最新工作状态。原计划已有INPUT_PLAN.md冻结副本，
文档快照依赖CANN_archive。归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
'''
    write(ROOT/'README.md',readme)
    write(HERE/'CANN_README.md',readme.replace('](BMMS_V','](BMMS/BMMS_V').replace('](BatchMatmul','](BMMS/BatchMatmul').replace('](V11_','](BMMS/V11_').replace('](audit_current/','](BMMS/audit_current/').replace('```bash\n','```bash\ncd BMMS\n'))
    print('Baseline choice, implementation audit and submission instructions updated.')
if __name__=='__main__':main()
