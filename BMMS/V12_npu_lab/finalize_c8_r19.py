"""Finalize explicit-tail candidate after actual results exist; preserve r12 mainline."""
from pathlib import Path
from collections import defaultdict
import json,hashlib,statistics as st,zipfile,shutil
R=Path(__file__).resolve().parents[1];D=R/'V12_npu_lab/results/case8_20260928';E=D/'evidence';Q=E/'results';O=R/'BMMS_V12'
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def read(name):return [json.loads(x) for x in (Q/name).read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def event(name):
 g=defaultdict(lambda:defaultdict(list));sel=set()
 for x in read(name):
  g[x['case']][x['label']].append(x['device_stream_us_per_call'])
  if x['label']=='B' and x['kernel']=='bmms1219':sel.add(x['case'])
 out=[]
 for i,x in sorted(g.items()):
  a=st.median(x['A']);b=st.median(x['B']);out.append(dict(case=i,baseline_us=a,candidate_us=b,reduction_pct=100*(1-b/a),selected=i in sel))
 stats={}
 for key,d in [('all',out),('nz',[x for x in out if x['selected']]),('fallback',[x for x in out if not x['selected']])]:
  if d:
   a=[x['reduction_pct'] for x in d];stats[key]=dict(cases=len(a),median=st.median(a),min=min(a),max=max(a))
 return dict(file=name,stats=stats,cases=out)
src=O/'v12_r19_case8_nz_explicit_tail.asc';base=O/'v12_baseline_r12.asc'
assert sha(src)=='27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021'
assert sha(src)==sha(E/'r19.asc')
assert sha(base)=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
s=src.read_bytes();a=s.index(b'// BMMS1219_BEGIN');b=s.index(b'// BMMS1219_END\n\n')+len(b'// BMMS1219_END\n\n');rec=s[:a]+s[b:]
hook=next(x for x in rec.splitlines(keepends=True) if b'if(bmms1219::TryLaunch' in x)
assert rec.replace(hook,b'',1)==base.read_bytes()
precision=[]
for f in ['correctness','holdout_correctness','final_correctness','controls_correctness','split_retention']:
 x=read(f'c8_r19_{f}.jsonl');assert all(r['pass'] for r in x)
 precision.append(dict(file=f'c8_r19_{f}.jsonl',cases=len(x),calls=sum(r['repeats'] for r in x),max_tolerance_ratio=max(r['max_tolerance_ratio'] for r in x)))
first=event('c8_r19_final_event.jsonl');repeat=event('c8_r19_final_event_repeat.jsonl');aa=event('c8_r19_event_aa.jsonl')
assert first['stats']['nz']['min']>-1 and repeat['stats']['nz']['min']>-1
san={}
for c in ['memcheck','racecheck','initcheck']:
 p=Q/f'c8_r19_instrumented_{c}.log';t=p.read_text(errors='replace');r=read(f'c8_r19_instrumented_{c}.jsonl')
 assert len(r)==2 and all(x['pass'] for x in r) and t.count('Sanitizer finished on kernel')==2
 assert 'temporarily ignored' not in t
 san[c]=dict(errors=t.count('====== ERROR:'),cases=2,log=p.name)
assert san['memcheck']['errors']==0,san
controls=json.loads((Q/'c8_r19_controls_repeat_summary.json').read_text())['summary']
split=json.loads((Q/'c8_r19_split_repeat_summary.json').read_text())['summary']
reverse_raw=json.loads((Q/'c8_r19_split_reverse_summary.json').read_text())
reverse=[dict(case=x['case'],baseline_median_us=x['candidate_median_us'],candidate_median_us=x['baseline_median_us']) for x in reverse_raw['summary']]
task=json.loads((Q/'c8_r19_task_summary.json').read_text())['summary']
for x in controls+split+task+reverse:x['delta_us']=x['candidate_median_us']-x['baseline_median_us']
total=sum(x['cases'] for x in precision);calls=sum(x['calls'] for x in precision)
summary=dict(candidate=src.name,parent=base.name,sha256=sha(src),parent_sha256=sha(base),parent_recovered_byte_for_byte=True,
 precision=precision,total_cases=total,total_calls=calls,final40=first,repeat40=repeat,aa=aa,controls=controls,split_retention=split,split_reverse_order=reverse,task_time=task,sanitizers=san,
 verdict='experimental Judge candidate; r12 remains accepted; race/init reports remain disclosed')
if not (D/'R18_REPORT.md').exists():
 shutil.copyfile(D/'REPORT.md',D/'R18_REPORT.md');shutil.copyfile(D/'SUMMARY.json',D/'SUMMARY_R18.json')
dump(D/'SUMMARY.json',summary)
def table(rows):return '\n'.join(f"| {x['case'][0]} / {'×'.join(map(str,x['case'][1:5]))} | {x['baseline_median_us']:.3f} | {x['candidate_median_us']:.3f} | {x['delta_us']:+.3f} |" for x in rows)
performance='\n'.join(f"| {label} | {first['stats'][k]['cases']} | {first['stats'][k]['median']:.2f}% | {repeat['stats'][k]['median']:.2f}% |" for label,k in [('全部','all'),('NZ新分支','nz'),('原R43回退','fallback')])
report=f'''# Case8 最终候选：v12_r19

## 交付结论

推荐 **[v12_r19_case8_nz_explicit_tail.asc](../../../BMMS_V12/v12_r19_case8_nz_explicit_tail.asc)** 作为唯一比赛实验候选。用户已接受的主线仍是r12，Case15约11.5 μs的实际成果保留；等待Judge完整15点反馈再晋升。

r19沿用r18的条件NZ整理，仅把新Case8消费者最后一步行Max合并改成显式64元素完整重复＋尾部掩码。此次改写消除了本轮两个检测样本中的UB非法访问告警，同时保留性能收益。没有修改原R12的任何函数；移除新模块及单个调用可逐字节恢复父版。

## 核心优化

原R43输入补齐为ND后，Cube反复做ND→NZ。新分支每次读取最多256×128元素，在原128KiB pack UB的两半完成32B块重排，批量写NZ，Cube直接按NZ搬入L1。原128×256宏块、pM/pN计划、K分片/累加和N max→M sum数学次序保持。

新分支只在原R43 guard内启用：B1、FP16/BF16、1024≤M,N<2048、1024<K<1280且K%8=0，至少一个轴未按16/16/32对齐；同时满足以下实测分派条件：

```cpp
(TA && Mp % 64 != 0) || ((TB ? Kp : Np) % 64 != 0)
```

Mp/Np/Kp是补齐维度。条件为假则沿用原R43；条件是样本支持的性能启发式，不是API要求，不保证所有未知形状均获益。两精度都按原始16位字搬运，边界补零，真实N以外的列在max前屏蔽。显式UB上限189088B，L1/L0和workspace不增加。

完整设计、被淘汰的r13–r17以及r18阶段定位见[R18实验记录](R18_REPORT.md)。其中r18的“推荐提交”状态由r19替代。r18的代表NN计数器显示AIC MTE2约24.63→7.36 μs、AIV MTE3约1.36 μs；r19的搬运实现相同，这些计数器标明为r18测量，不充作r19新采样。

## 正确性与收益

Ascend910_9362、逻辑设备0、20 Cube cores、CANN9.0.0、dav-2201。编译与性能计时分开、NPU任务串行。独立CPU FP64参考先量化到实际输入精度，再完整K求和→真实N max→真实M sum，阈值为`1e-4+1e-4*abs(reference)`。每次入口调用前将输出写NaN。

**{total}组合成输入，每组3次，共{calls}次全部通过**，含两精度四布局、尾部/负数/全零/极值位置数据、其他route控制和128组Split-K回归。详细分项见SUMMARY.json。事件和公共入口profile还有额外正确性门禁，未重复计入774次。

| 40组Case8合成样本 | 组数 | 首次耗时中位缩短 | 独立进程复测 |
|---|---:|---:|---:|
{performance}

NZ分支两轮的最小收益为{first['stats']['nz']['min']:.2f}% / {repeat['stats']['nz']['min']:.2f}%，最大为{first['stats']['nz']['max']:.2f}% / {repeat['stats']['nz']['max']:.2f}%。A/A对照范围{aa['stats']['all']['min']:.3f}%～{aa['stats']['all']['max']:.3f}%。分派规则在这40例生成前已冻结；r19用同集回归显式掩码改写，没有用它们再调分派。

事件计时为预分配后的同进程AB/BA，100次热身、12窗口×每窗口64调用；反映设备流执行，包含提交间隙，不含公共入口分配/同步。真实Case8精确shape/layout未知，这些合成数据不能换算成比赛必然用时。

公共入口另做轻量task-time profiler，检查实际kernel名、单kernel次数与输出；原始窗口保留，不混用两类计时的绝对值。

## 其他路径与Case15保留

各版本4个交替独立进程，每例80次、去掉前20次；下表为各窗口中位数的中位数，ID是合成输入编号。

| 控制ID / B×M×N×K | r12 μs | r19 μs | 差值 μs |
|---|---:|---:|---:|
{table(controls)}

| Split-K ID / B×M×N×K | r12 μs | r19 μs | 差值 μs |
|---|---:|---:|---:|
{table(split)}

首次Split-K控制统一增加0.070～0.165 μs，因此专门交换版本的起始运行顺序，再做各4个独立窗口，而非直接归因于噪声。复测如下：

| Split-K ID / B×M×N×K | r12 μs | r19 μs | 差值 μs |
|---|---:|---:|---:|
{table(reverse)}

交换顺序后的差值为−0.060～+0.035 μs，没有复现统一退化。两轮原始窗口均保留；这支持当前小差异受测量条件影响，但没有单独证明具体来源。

有限回归不能证明所有隐藏点无退化。Case15的旧源码与分派顺序保留，最终仍要结合Judge约11.5 μs基准检查。

## 检测告警与改写依据

**r19全指令插桩memcheck在2例上无ERROR**；原r12和r18各有64条，均指向最终计数模式Max。r19显式掩码改写后该类报告消失。这说明改写在当前工具检查下通过，并不反向证明旧版硬件执行必然越界。

**racecheck仍报告{san['racecheck']['errors']}条、initcheck仍报告{san['initcheck']['errors']}条，未计为通过。** r12同条件分别为24条/19827条，r18为16条/4596条；涉及保留的MMAD累加及跨核GM/PRIVATE计划读取。数值检查全部正确，源码审查未找到新增相关缺陷，但未逐条消除工具报告，不能宣称全面sanitizer通过。详情和依据见[SANITIZER_REVIEW.md](SANITIZER_REVIEW.md)。工具同步寄存器警告亦保留。

普通构建的race/init曾被明确跳过，退出0不代表通过；本轮使用真正插桩构建重测，并更正旧Case15报告的相同误判。r12主线接受依据是用户实际Judge反馈，不依赖被跳过的检测。

## 文件与复现

源SHA256：`{sha(src)}`。父版SHA256：`{sha(base)}`。

`evidence/`保留输入清单/seed/hash、测试及profile原始文件、所有sanitizer报告与构建参数；tensor二进制由归档generator重建。远端工作目录`/home/developer/bmms_v12_lab_20260928`，加载CANN后执行`cmake --build build --target c8_r19_build -j3`及`check_c8_r19.sh`。复测需新输出tag，保留旧结果。

下一步先收r19完整15点Judge反馈；r19若稳定改善再冻结。后续优先Case12的局部空间规划，按既有K区间隔离9/10/11，见[后续方向](../../../BMMS_V12/NEXT_DIRECTIONS_r18.md)。
'''
(D/'REPORT.md').write_text(report,encoding='utf-8')
readme=f'''# v12_r19 Case8 候选

直接提交 **v12_r19_case8_nz_explicit_tail.asc**。以已接受r12为父版，保留Case15成果。

Case8按stride/转置选择UB内NZ整理，并采用显式归约尾部掩码；其他组合回退原R43。

- {total}组、{calls}次精度验证全部通过，含128组Split-K回归。
- 40组合成Case8：两轮耗时中位缩短{first['stats']['all']['median']:.2f}% / {repeat['stats']['all']['median']:.2f}%；新分支26例中位约{first['stats']['nz']['median']:.1f}%。
- 插桩memcheck的2例无ERROR；race/init仍有父版同类告警，尚未全面闭环，详见报告。

真实Case8形状未知，仍需Judge完整15点验收；r12继续已接受主线。r18保留为研究对照，本轮只提交r19。

[完整报告](../V12_npu_lab/results/case8_20260928/REPORT.md) · [记录](v12_r19_manifest.json)

SHA256：`{sha(src)}`
'''
(O/'v12_r19_README.md').write_text(readme,encoding='utf-8')
mp=O/'v12_r19_manifest.json';manifest=json.loads(mp.read_text());manifest.update(status=summary['verdict'],precision=precision,performance=first['stats'],repeat_performance=repeat['stats'],sanitizers=san,npu_report='../V12_npu_lab/results/case8_20260928/REPORT.md');dump(mp,manifest)
main=json.loads((O/'MAINLINE.json').read_text());assert main['accepted_version']=='v12_r12'
for x in main['candidates']:
 if x['version']=='v12_r18':x['status']='superseded by r19 explicit-tail candidate; retained as experiment';x['npu_report']='../V12_npu_lab/results/case8_20260928/R18_REPORT.md'
main['candidates']=[x for x in main['candidates'] if x['version']!='v12_r19']+[dict(version='v12_r19',file=src.name,sha256=sha(src),parent=base.name,status=summary['verdict'],npu_report=manifest['npu_report'])]
main.update(recommended_candidate=src.name,next_action='Judge r19 all15; preserve accepted r12 until confirmed');dump(O/'MAINLINE.json',main)
old=json.loads((O/'v12_r18_manifest.json').read_text());old.update(status='superseded by r19; research comparison only',validation_report='../V12_npu_lab/results/case8_20260928/R18_REPORT.md');dump(O/'v12_r18_manifest.json',old)
rp=O/'v12_r18_README.md';oldtxt=rp.read_text(encoding='utf-8')
notice='> 已由r19显式尾部改写候选替代；本轮请提交[v12_r19](v12_r19_README.md)。以下为历史记录。\n\n'
if not oldtxt.startswith(notice):rp.write_text(notice+oldtxt,encoding='utf-8')
rp=O/'README.md';txt=rp.read_text(encoding='utf-8');lines=txt.splitlines();lines[2]='**当前状态：** r12已接受为主线（Case15约11.5 μs）。Case8唯一推荐候选为[r19](v12_r19_README.md)，合成验证结果与尚未关闭的检测告警见[报告](../V12_npu_lab/results/case8_20260928/REPORT.md)。等待Judge后再晋升。以下为历史交付记录。';rp.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(O/'v12_r19_case8_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [src,O/'v12_r19_README.md',mp,O/'NEXT_DIRECTIONS_r18.md']:z.write(p,p.relative_to(R).as_posix())
 for name in ['REPORT.md','SUMMARY.json','SANITIZER_REVIEW.md','R18_REPORT.md']:
  p=D/name;z.write(p,p.relative_to(R).as_posix())
 z.writestr('README.md','# v12_r19 Case8 候选\n\n提交源码：[v12_r19_case8_nz_explicit_tail.asc](BMMS_V12/v12_r19_case8_nz_explicit_tail.asc)。\n\n[验证报告](V12_npu_lab/results/case8_20260928/REPORT.md)。主线继续保留r12，等待Judge完整15点反馈。\n')
with zipfile.ZipFile(O/'v12_r19_case8_submission.zip') as z:assert z.testzip() is None
print(json.dumps(dict(candidate=src.name,sha256=sha(src),performance=first['stats'],repeat=repeat['stats'],sanitizers=san),ensure_ascii=False))
