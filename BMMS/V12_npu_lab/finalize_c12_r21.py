from pathlib import Path
import json,hashlib,shutil,zipfile,statistics as st
r=Path(__file__).resolve().parents[1];d=r/'V12_npu_lab/results/case12_20260928';e=d/'evidence';q=e/'results';o=r/'BMMS_V12'
def rd(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
src=o/'v12_r21_case12_packet_tail.asc';base=o/'v12_baseline_r19.asc'
assert sha(src)=='2cb7454a99ee245d69afeb942f3e1835d9f068948fe217820ad47f4ba4a4708c'
assert sha(src)==sha(e/'r21.asc');assert sha(base)=='27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021'
t=src.read_bytes();a=t.index(b'\n// BMMS1221_BEGIN');b=t.index(b'// BMMS1221_END\n\n')+len(b'// BMMS1221_END\n\n');t=t[:a]+t[b:]
hook=next(x for x in t.splitlines(keepends=True) if b'if(bmms1221::TryLaunch' in x);assert t.replace(hook,b'',1)==base.read_bytes()
def planner(p,tag):
 s=p.read_text(encoding='utf-8');a=s.index('static inline bool Eligible',s.index('// BMMS'+tag+'_BEGIN'));b=s.index('static inline bool Changed',a);return s[a:b]
assert planner(src,'1221')==planner(o/'v12_r20_case12_packet_plan.asc','1220')
precision=[]
for tag in ['screen','holdout','random','original','c8','split','controls']:
 rows=[json.loads(l) for l in (q/f'c12_r21_{tag}_correctness.jsonl').read_text().splitlines()]
 assert all(x['pass'] for x in rows)
 precision.append(dict(group=tag,cases=len(rows),calls=sum(x['repeats'] for x in rows),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rows)))
assert sum(x['cases'] for x in precision)==308 and sum(x['calls'] for x in precision)==924
events={k:rd(q/f'c12_r21_{k}_summary.json') for k in ['holdout_event','holdout_event_repeat','random_event','random_event_repeat','aa']}
for k,v in events.items():
 if k=='aa':continue
 assert all(x['windows']==10 for x in v['cases']) and v['stats']['selected']['min']>0
 prev=rd(q/f'c12_r20_{k}_summary.json');assert {x['case'] for x in v['cases'] if x['selected']}=={x['case'] for x in prev['cases'] if x['selected']}
controls={k:rd(q/f'c12_r21_{k}_summary.json') for k in ['public','c8_control','split_control','other_control']}
san=rd(q/'c12_sanitizer_comparison.json')
for tool in ['memcheck','racecheck']:
 assert not san['r21'][tool]['skipped'] and san['r21'][tool]['finished_kernel_count']==2
 rows=[json.loads(l) for l in (q/f'c12_r21_instrumented_{tool}.jsonl').read_text().splitlines()];assert len(rows)==2 and all(x['pass'] for x in rows)
assert san['r21']['memcheck']['errors']==0
host=rd(r/'V12_npu_lab/host_c12/RESULTS.json');audit=rd(r/'V12_npu_lab/host_c12/R21_AUDIT.json');assert audit['passed']
if not (d/'R20_REPORT.md').exists():
 shutil.copyfile(d/'REPORT.md',d/'R20_REPORT.md');shutil.copyfile(d/'SUMMARY.json',d/'SUMMARY_R20.json')
summary=dict(candidate=src.name,sha256=sha(src),parent=base.name,parent_sha256=sha(base),parent_recovered_byte_for_byte=True,planner_identical_to_r20=True,host_checks=host,consumer_audit=audit,precision=precision,total_cases=308,total_calls=924,events=events,controls=controls,sanitizers=san,status='experimental Judge candidate; r19 accepted; race/init limitations remain')
dump(d/'SUMMARY.json',summary)
def evrow(label,key):
 x=events[key]['stats'];y=events[key+'_repeat']['stats'];return f"| {label} | {x['all']['count']} | {x['selected']['count']} | {x['selected']['median']:.2f}% / {y['selected']['median']:.2f}% | {x['selected']['min']:.2f}%～{x['selected']['max']:.2f}% | {x['all']['median']:.2f}% / {y['all']['median']:.2f}% |"
def table(key,ids=None):
 return '\n'.join(f"| {x['case'][0]} / {'×'.join(map(str,x['case'][1:5]))} | {x['baseline_median_us']:.3f} | {x['candidate_median_us']:.3f} | {x['candidate_median_us']-x['baseline_median_us']:+.3f} |" for x in controls[key]['summary'] if ids is None or x['case'][0] in ids)
report=f'''# Case12最终候选：v12_r21

主线已冻结为**r19**，用户截图15/15 Pass、Case8=46.88μs、Case15=11.29μs。下一次只提交 **[v12_r21_case12_packet_tail.asc](../../../BMMS_V12/v12_r21_case12_packet_tail.asc)**；r20为本地任务计划实验对照，已被r21替代。真实Judge反馈前不晋升。

## 最终改动

在Case12已有元数据范围内，把原矩形任务改为单宏块轮转分配，并给新增消费者使用显式尾部Max掩码。原r19所有函数逐字节保留；移除新模块和单个入口调用即可恢复父版。

范围：B1、M/N≥1024、1536≤K<2048，M/N按16对齐、K按32对齐，另满足原R06的8192上界、输入规模和实际核数约束。域外回原dispatch。域内仅当新计划最忙核宏块数降低至少10%，且峰值有效C元素数、输入长度都不增加，才启用；否则走原R06。

计划为pM=mTiles、pN=nTiles，tasks=mTiles*nTiles，blocks=min(tasks,cores)。每个任务一个128×256或尾宏块，按task%blocks分配。精确遍历任务计算峰值，而非假设矩形网格满占用就是最优。该指标是代理模型，不等于硬件时间保证。host额外比较最多2048个任务，未用缓存；辅助事件测试预计算计划，公共入口测试则执行完整host逻辑。

每个(m,n)宏块与每个(ns,row)partial有唯一写者；workspace随新pN正确扩展。Cube直接复用原`bmms11r2::ReuseProducer`，AM/BN、K1/K0、完整K的FP32累加和READY/FREE环不变。全部N分片Max后才sum M，原M求和次序保留。UB/L1/L0容量不增加。

新增消费者与原类的唯一逻辑差异是最终Max由计数模式改为64元素完整重复及16/32/48元素尾部掩码；M≤8192保证repeat≤128。这个改写与上一轮Case8消除同类检测报告的做法一致。代码差异与设备验证分别保存，未以源码审查替代测试。

## 试验过程及性能

初筛32例：1–2个N宏块/任务方案中位降幅4.18%、最差退化3.24%；单宏块方案中位降幅9.52%，随后选定工作量门槛并冻结。r20的两批独立复验确认选择性收益，但插桩仍报告最终Max访问问题，故用r21补齐显式尾部。没有因随机复验结果再调分派规则。

下面是**最终r21对已接受r19**的同卡数据。规则冻结后的24组手工形状配置与32组随机配置，用于r21回归尾部改写；它们此前已经测过r20，因此不声称是r21从未接触的第三批调参集。两轮独立进程，每轮同进程AB/BA、100次预热、10窗口×32调用，每窗口核对输出。

| 配置集 | 全部 | 切换 | 切换子集降幅中位数：两轮 | 首轮切换降幅范围 | 全集降幅中位数：两轮 |
|---|---:|---:|---:|---:|---:|
{evrow('手工形状','holdout_event')}
{evrow('随机对齐尺寸','random_event')}

56组配置中17组切换，39组回退；**不能把切换子集的收益称为全部配置收益**。A/A对照为{events['aa']['stats']['all']['median']:.3f}%。输入均为自行构造，同环境不提供隐藏shape。事件计时不含公共入口分配/同步，不能直接换算Judge Case12最终微秒数。

公共入口轻量task-time profiler另行确认实际kernel名、单次kernel数量和输出，每版2个交替独立进程，每例80次、丢弃前20次。四个切换配置：

| ID / B×M×N×K | r19 μs | r21 μs | 差值 μs |
|---|---:|---:|---:|
{table('public',[12,13,14,15])}

## 精度、覆盖与已有成果

**308组×3次，共924次非插桩数值检查全部通过**。具体为初筛32、手工形状/数值32、随机32、原合成34、Case8 40、Split-K 128、其他控制10。FP16/BF16、四布局、MN/K尾块、负数、零、动态范围、相同列和8192边界均覆盖。参考是实际量化输入的CPU FP64点积→max N→sum M；阈值1e-4+1e-4*abs(ref)，每次入口调用前输出填NaN。

host独立宏块遍历覆盖3000组shape/core及206组作用域外输入；逐宏块峰值与生产公式一致，partial覆盖无空洞/重叠。r21与r20的Eligibility/MakePlan文本相同；消费者单点差异审计通过。

Case8控制：

| ID / B×M×N×K | r19 μs | r21 μs | 差值 μs |
|---|---:|---:|---:|
{table('c8_control')}

Split-K控制：

| ID / B×M×N×K | r19 μs | r21 μs | 差值 μs |
|---|---:|---:|---:|
{table('split_control')}

其他路径控制（含Native、短向量、残余以及K2048的R06）：

| ID / B×M×N×K | r19 μs | r21 μs | 差值 μs |
|---|---:|---:|---:|
{table('other_control')}

这些是有限合成回归，不能保证全部隐藏点无退化。Case8这轮未见退化，但其源码与分派未变，表中的约1μs下降不归因为新增优化。Split-K控制差值为+0.040～+0.070μs，其他路径为−0.010～+0.285μs；其中10.8μs的Native样本增加0.255μs（约2.36%），保留为复测关注项，不用“全部不变”概括。控制点原始窗口、波动和各例绝对差值保留，不仅报告总体平均。r20阶段的Case8两轮细微差异另见[R20历史报告](R20_REPORT.md)，不混作r21测量。

## 插桩结果与限制

相同M1040/N1296/K1568、FP16/BF16非零全负输出两例：原计划9×3/27tasks/20cores，新计划9×6/54tasks/20cores，确实覆盖新增多任务和partial。每版都是真正全指令插桩构建，完成2个kernel的实际检查，数值输出通过。

| ERROR报告数 | r19 | r20 | r21 |
|---|---:|---:|---:|
| memcheck | {san['r19']['memcheck']['errors']} | {san['r20']['memcheck']['errors']} | {san['r21']['memcheck']['errors']} |
| racecheck | {san['r19']['racecheck']['errors']} | {san['r20']['racecheck']['errors']} | {san['r21']['racecheck']['errors']} |

r19/r20的memcheck均指向R06最终计数模式Max；r21显式掩码使这两例的报告归零。这不反向证明旧版在硬件上必然越界。racecheck仍涉及原MMAD的L0C RAW/WAW，未计为通过，也不因为父版有同类报告就认定误报。r19历史initcheck未闭环状态保留，本轮没有重跑initcheck，不能宣称完整sanitizer通过。

## 文件、复现与后续

源码SHA256：`{sha(src)}`；父版SHA256：`{sha(base)}`。

设备Ascend910_9362、逻辑0、20 Cube、CANN9.0.0、dav-2201。编译与性能测试分开；NPU任务串行。`case12_evidence.zip`和`evidence/`保存原始窗口/profile CSV、构建参数、插桩报告、generator与输入seed/hash；tensor二进制可重建。

本地`prepare_c12_r21.py`生成源码，`check_c12_host.py`检验计划。远端加载CANN后构建`c12_r21_build`；`check_c12_r21.sh`保存完整流程，重测必须使用新profile tag以免覆盖旧证据。

下一步只提交r21，重点看Case12能否明显改善，并检查Case8约46.88μs、Case15约11.29μs。若Case12持平，仍需区分守卫未切换与命中后无收益，不能只凭耗时作单向推断；必要时一次覆盖确认即可。Case9/10/11仍保持原路径，下一优化方向由真实反馈决定，不扩散修改。
'''
(d/'REPORT.md').write_text(report,encoding='utf-8')
readme='''# v12_r21 Case12候选

只提交v12_r21_case12_packet_tail.asc。父版为已接受的r19；Case8/15优化保留。

单宏块轮转分配，仅在峰值工作量门槛满足时启用；新增消费者采用显式最终Max尾部掩码。308组×3次精度通过，56组计划复验中17组切换且两轮全部正收益，其余39组回原计划。切换收益不能当成全部shape收益。

两例插桩memcheck无ERROR；原MMAD同类race报告及历史init限制尚未闭环，详见[完整报告](../V12_npu_lab/results/case12_20260928/REPORT.md)。真实Case12收益待Judge验证，主线保持r19。
'''
(o/'v12_r21_README.md').write_text(readme,encoding='utf-8')
mp=o/'v12_r21_manifest.json';m=rd(mp);m.update(status=summary['status'],precision=precision,host_checks=host,consumer_audit=audit,performance={k:v['stats'] for k,v in events.items()},sanitizers=san['r21'],validation_report='../V12_npu_lab/results/case12_20260928/REPORT.md');dump(mp,m)
main=rd(o/'MAINLINE.json');assert main['accepted_version']=='v12_r19'
for c in main['candidates']:
 if c['version']=='v12_r20':c.update(status='superseded by r21 explicit final-Max tail; research control only',npu_report='../V12_npu_lab/results/case12_20260928/R20_REPORT.md')
main['candidates']=[c for c in main['candidates'] if c['version']!='v12_r21']+[dict(version='v12_r21',file=src.name,parent=base.name,sha256=sha(src),status=summary['status'],npu_report=m['validation_report'])]
main.update(recommended_candidate=src.name,next_action='Judge r21 all15; r19 remains accepted');dump(o/'MAINLINE.json',main)
old=rd(o/'v12_r20_manifest.json');old.update(status='superseded by r21; research control only',validation_report='../V12_npu_lab/results/case12_20260928/R20_REPORT.md');dump(o/'v12_r20_manifest.json',old)
p=o/'v12_r20_README.md';t=p.read_text(encoding='utf-8');notice='> 已由[r21](v12_r21_README.md)替代，本轮不提交r20。以下为历史记录。\n\n'
if not t.startswith(notice):p.write_text(notice+t,encoding='utf-8')
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r19](v12_baseline_r19.asc)，Judge 15/15 Pass，Case8 46.88 μs、Case15 11.29 μs。下一候选为[r21 Case12任务分配](v12_r21_README.md)，等待Judge反馈。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(o/'v12_r21_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [src,o/'v12_r21_README.md',mp,d/'REPORT.md',d/'SUMMARY.json',d/'R20_REPORT.md']:z.write(p,p.relative_to(r).as_posix())
with zipfile.ZipFile(o/'v12_r21_submission.zip') as z:assert z.testzip() is None
print(json.dumps(dict(candidate=src.name,precision=308,calls=924,events={k:v['stats'] for k,v in events.items()},sanitizers={k:v['errors'] for k,v in san['r21'].items()}),ensure_ascii=False))
