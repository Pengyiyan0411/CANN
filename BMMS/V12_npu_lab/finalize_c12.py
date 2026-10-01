from pathlib import Path
import json,hashlib,statistics as st,zipfile
r=Path(__file__).resolve().parents[1];d=r/'V12_npu_lab/results/case12_20260928';q=d/'evidence/results';o=r/'BMMS_V12'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
src=o/'v12_r20_case12_packet_plan.asc';base=o/'v12_baseline_r19.asc'
assert sha(src)=='be93902adf688fc7e791747f015984ac2de78ee63b3be0c2d5417af545c1ee2b'
assert sha(src)==sha(d/'evidence/r20.asc')
assert sha(base)=='27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021'
t=src.read_bytes();start=t.index(b'\n// BMMS1220_BEGIN');end=t.index(b'// BMMS1220_END\n\n')+len(b'// BMMS1220_END\n\n');t=t[:start]+t[end:]
hook=next(x for x in t.splitlines(keepends=True) if b'if(bmms1220::TryLaunch' in x);assert t.replace(hook,b'',1)==base.read_bytes()
precision=[]
for tag in ['screen','holdout','random','original','c8','split','controls']:
 p=q/f'c12_r20_{tag}_correctness.jsonl';rows=[json.loads(l) for l in p.read_text().splitlines()]
 assert all(x['pass'] for x in rows)
 precision.append(dict(group=tag,cases=len(rows),calls=sum(x['repeats'] for x in rows),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rows)))
count=sum(x['cases'] for x in precision);calls=sum(x['calls'] for x in precision);assert count==308 and calls==924
events={k:read(q/f'c12_r20_{k}_summary.json') for k in ['holdout_event','holdout_event_repeat','random_event','random_event_repeat','aa']}
for k in ['holdout_event','holdout_event_repeat','random_event','random_event_repeat']:
 assert all(x['windows']==10 for x in events[k]['cases'])
 assert events[k]['stats']['selected']['min']>0
controls={k:read(q/f'c12_r20_{k}_summary.json') for k in ['public','c8_control','split_control','other_control','c8_reverse']}
san=read(q/'c12_sanitizer_comparison.json')
for version in ['r19','r20']:
 for tool in ['memcheck','racecheck']:
  assert not san[version][tool]['skipped'] and san[version][tool]['finished_kernel_count']==2
  rows=[json.loads(l) for l in (q/f'c12_{version}_instrumented_{tool}.jsonl').read_text().splitlines()]
  assert len(rows)==2 and all(x['pass'] for x in rows)
host=read(r/'V12_npu_lab/host_c12/RESULTS.json');assert host['passed']
def deltas(x,reverse=False):
 return [dict(case=t['case'],r19_us=t['candidate_median_us'] if reverse else t['baseline_median_us'],r20_us=t['baseline_median_us'] if reverse else t['candidate_median_us']) for t in x['summary']]
control_rows={k:deltas(x,k=='c8_reverse') for k,x in controls.items()}
summary=dict(candidate=src.name,parent=base.name,sha256=sha(src),parent_sha256=sha(base),parent_recovered_byte_for_byte=True,judge_baseline='../V12_results/2026-09-28_r19_feedback/RESULTS.json',precision=precision,total_cases=count,total_calls=calls,host_checks=host,events=events,controls=control_rows,sanitizers=san,status='awaiting Judge; r19 remains accepted')
dump(d/'SUMMARY.json',summary)
def resultrow(label,key):
 x=events[key]['stats'];y=events[key+'_repeat']['stats'];return f"| {label} | {x['all']['count']} | {x['selected']['count']} | {x['selected']['median']:.2f}% / {y['selected']['median']:.2f}% | {x['selected']['min']:.2f}%～{x['selected']['max']:.2f}% | {x['all']['median']:.2f}% / {y['all']['median']:.2f}% |"
def control_table(key):
 return '\n'.join(f"| {x['case'][0]} | {x['r19_us']:.3f} | {x['r20_us']:.3f} | {x['r20_us']-x['r19_us']:+.3f} |" for x in control_rows[key])
sanrows='\n'.join(f"| {c} | {san['r19'][c]['errors']} | {san['r20'][c]['errors']} |" for c in ['memcheck','racecheck'])
report=f'''# Case12：v12_r20 任务分配候选

已接受主线是 **r19**：用户截图15/15 Pass，Case8=46.88 μs、Case15=11.29 μs。本轮交付[v12_r20_case12_packet_plan.asc](../../../BMMS_V12/v12_r20_case12_packet_plan.asc)，等待完整Judge反馈后才晋升。

## 改动与正确性依据

r20只增加host任务计划和一个入口分支，直接启动原有R06 kernel；没有修改任何device类、宏块尺寸、K流水、矩阵乘累加顺序或归约指令。移除新模块及调用可逐字节恢复r19。Case8与Case15优化完整保留。

目标元数据域为B1、M/N≥1024且按16对齐、1536≤K<2048且按32对齐，并满足原R06的8192维度上界、输入规模及实际核数限制。域外回原dispatch。域内原计划与新计划均使用原核函数，新计划为pM=mTiles、pN=nTiles、tasks=mTiles*nTiles、blocks=min(tasks,cores)，每任务一个128×256或尾宏块，按核号轮转。

仅当**最忙核宏块数至少减少10%，且峰值有效C元素数/输入长度都不增加**时采用新计划，否则使用原计划。所有指标由实际task-to-core分配计算，是筛选代理，不是硬件耗时证明。partial空间根据新pN分配，UB/L1/L0和ring每核容量不增加。新增host比较遍历至多2048个候选任务，未做host缓存；公共入口包含该工作。

每个(m,n)宏块、每个(ns,row)partial区间有唯一写者，完整K在同一宏块内累加，全部N分片Max后才sum M。沿用原READY/FREE环、全部活跃AIV的SyncAll。未改变浮点M求和次序，仍使用实际输入量化后的CPU FP64参考逐输出检查，阈值1e-4+1e-4*abs(ref)。

独立宏块遍历核对原/新峰值及partial覆盖：**{host['shape_core_checks']}组shape/core组合**，其中{host['changed']}组变更；另{host['out_of_scope_checks']}组域外维持原计划。设备数值回归**{count}组×3次={calls}次全部通过**，包含32组初筛、32组规则冻结后的手工形状/数值用例、32组随机形状、34组原始合成集、40组Case8、128组Split-K、10组其他路径控制。调用前NaN输出哨兵；事件循环另外逐窗口验证工作区反复复用。

## 初筛与独立复验

初筛先只用原kernel比较两种任务划分：1–2个N宏块/任务的方案32例中位降幅4.18%，最差慢3.24%；单宏块/任务中位降幅9.52%，最差慢0.18%。选择单宏块方案并加入上述固定工作量门槛，没有移植历史无收益的消费者微调。

下面两批均在规则冻结后生成，结果没有再用于修改门槛。配置数量包含dtype/layout，不等同于不同M/N数量。两轮为独立进程；同一进程内预计算两版Plan和workspace，100次预热、10个AB/BA窗口，每窗32次。属于设备流执行时间，含提交间隙，不含公共入口分配/同步，不冒充Judge时间。

| 复验集 | 全部配置 | 切换配置 | 切换配置降幅中位数：两轮 | 首轮切换降幅范围 | 全部配置降幅中位数：两轮 |
|---|---:|---:|---:|---:|---:|
{resultrow('手工形状','holdout_event')}
{resultrow('随机对齐尺寸','random_event')}

**56组复验配置中17组切换，两轮均为正收益；39组保留原计划。** 全集降幅中位数接近0，不能把命中子集的收益写成全部样本收益。A/A对照中位差为{events['aa']['stats']['all']['median']:.3f}%。因此r20更适用于原矩形网格负载不均的形状，无法保证未知Case12一定切换或提高。

公共入口另用task-time profiler确认原kernel名、单kernel执行数与数值输出。在手工复验的四个切换配置上，原/新耗时如下；真实设备上的r19是对照基线，没有用CPU耗时充当标杆。

| 配置ID | r19 μs | r20 μs | 差值 μs |
|---|---:|---:|---:|
{chr(10).join(line for line in control_table('public').splitlines() if int(line.split('|')[1]) in (12,13,14,15))}

## 已有成果回归

公共入口分别交替运行各2个独立进程，每例80次，去掉前20次。ID均为合成输入编号，不对应隐藏Case号。

Case8首轮有统一的小幅上移，必须保留；没有直接断言是噪声。

| Case8控制ID | r19 μs | r20 μs | 差值 μs |
|---|---:|---:|---:|
{control_table('c8_control')}

随后交换起始版本、各4窗口复测：

| Case8控制ID | r19 μs | r20 μs | 差值 μs |
|---|---:|---:|---:|
{control_table('c8_reverse')}

Split-K控制：

| 控制ID | r19 μs | r20 μs | 差值 μs |
|---|---:|---:|---:|
{control_table('split_control')}

其他路径控制（含K2048的R06、Native、短向量与残余路径）：

| 控制ID | r19 μs | r20 μs | 差值 μs |
|---|---:|---:|---:|
{control_table('other_control')}

有限回归不能保证所有隐藏点无退化；Judge重点核对Case12是否有真实收益，同时检查Case8≈46.88 μs、Case15≈11.29 μs的既有成果。

## 插桩检测限制

使用真正带`--cce-enable-sanitizer -gline-tables-only`的完整r19/r20二进制，分别对M1040/N1296/K1568、FP16/BF16、非零全负输出两例运行。两例新计划均切换，测试跨任务ring复用和扩大的partial；每版每类完成2次实际kernel检测且数值通过，没有把普通构建跳过的检测算作通过。

| ERROR报告数 | r19 | r20 |
|---|---:|---:|
{sanrows}

完整按源码位置和消息分类见SUMMARY.json及evidence/results/c12_sanitizer_comparison.json。存在ERROR的项不计为检测通过；父版也存在报告不能自动证明其为误报。r19历史race/init未闭环状态仍保留，本轮没有宣称完整sanitizer安全证明，也未重跑全域initcheck。

## 复现与后续

设备Ascend910_9362、逻辑NPU0、20 Cube、CANN9.0.0、dav-2201；NPU测量串行，编译与计时分开。所有输入均为自行构造，精确隐藏形状不可得。

- 源hash：`{sha(src)}`；父版hash：`{sha(base)}`。
- `case12_evidence.zip`：原始窗口、profile CSV、精度记录、插桩日志、编译参数及输入seed/hash。大型tensor可由归档generator重建。
- 本地生成：`prepare_c12_r20.py`；独立host检查：`check_c12_host.py`。
- 远端`/home/developer/bmms_v12_lab_20260928`加载CANN后构建`c12_r20_build`。`check_c12_r20.sh`、`check_c12_random.sh`和`sanitize_c12_r20.sh`保留原实验步骤；复测必须换profile tag，避免覆盖证据。

下一步先测r20完整15点。若Case12持平，不能仅凭耗时认定没有切换；结合一次覆盖确认或进一步本地热点证据再决定，不直接扩大到Case9/10/11。r19继续主线。
'''
(d/'REPORT.md').write_text(report,encoding='utf-8')
readme=f'''# v12_r20 Case12任务分配候选

基于已接受的r19，仅在Case12元数据范围内调整host计划，直接复用原R06 kernel。最忙核宏块数降低至少10%、峰值cells/input不增加时，使用单宏块任务轮转分配；否则保留原计划。Case8/15源码保留。

308组×3次精度通过；3000组独立host核对。规则冻结后56组复验配置中17组切换、两轮全部正收益，其余39组保留原计划。随机复验命中13/32，命中子集降幅中位数约16%；不能推广成所有样本或隐藏Case12必然收益。

插桩检测仍有未闭环限制，完整数据、控制点及复测见[报告](../V12_npu_lab/results/case12_20260928/REPORT.md)。待Judge完整15点反馈，r19保持主线。

源码：v12_r20_case12_packet_plan.asc\n\nSHA256：`{sha(src)}`
'''
(o/'v12_r20_README.md').write_text(readme,encoding='utf-8')
mp=o/'v12_r20_manifest.json';m=read(mp);m.update(status=summary['status'],precision=precision,host_checks=host,validation_report='../V12_npu_lab/results/case12_20260928/REPORT.md',performance={k:v['stats'] for k,v in events.items()},sanitizers=san);dump(mp,m)
m=read(o/'MAINLINE.json');assert m['accepted_version']=='v12_r19'
m['candidates']=[x for x in m['candidates'] if x['version']!='v12_r20']+[dict(version='v12_r20',file=src.name,parent=base.name,sha256=sha(src),status=summary['status'],npu_report='../V12_npu_lab/results/case12_20260928/REPORT.md')]
m.update(recommended_candidate=src.name,next_action='Judge r20 all15; preserve accepted r19 until confirmed');dump(o/'MAINLINE.json',m)
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r19](v12_baseline_r19.asc)，Judge 15/15 Pass，Case8 46.88 μs、Case15 11.29 μs。下一候选为[r20 Case12任务分配](v12_r20_README.md)，等待Judge反馈。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(o/'v12_r20_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [src,o/'v12_r20_README.md',mp,d/'REPORT.md',d/'SUMMARY.json']:z.write(p,p.relative_to(r).as_posix())
with zipfile.ZipFile(o/'v12_r20_submission.zip') as z:assert z.testzip() is None
print(json.dumps(dict(precision=count,calls=calls,host=host,events={k:v['stats'] for k,v in events.items()},sanitizers={v:{c:san[v][c]['errors'] for c in san[v]} for v in san}),ensure_ascii=False))
