from pathlib import Path
import json,hashlib,zipfile,re,collections
r=Path(__file__).resolve().parents[1];d=r/'V12_npu_lab/results/c1112_20260928';e=d/'evidence';q=e/'results';o=r/'BMMS_V12'
def rd(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
src=o/'v12_r22_dense_nz_pitch.asc';base=o/'v12_baseline_r19.asc'
assert sha(src)=='96b12f4eb4b0f2717591b20211213779604ba1dcf71c0886d4153ac1332a6d39'
assert sha(e/'r22.asc')==sha(src) and sha(e/'r19.asc')==sha(base)
t=src.read_bytes();a=t.index(b'\n// BMMS1222_BEGIN');b=t.index(b'// BMMS1222_END\n\n')+len(b'// BMMS1222_END\n\n');t=t[:a]+t[b:]
hook=next(l for l in t.splitlines(keepends=True) if b'if(bmms1222::TryLaunch' in l)
assert t.replace(hook,b'',1)==base.read_bytes()
precision=[]
for tag in ['screen','holdout','original','c8','split','controls','gap']:
 rows=[json.loads(l) for l in (q/f'c1112_r22_{tag}_correctness.jsonl').read_text().splitlines()]
 assert all(x['pass'] for x in rows)
 precision.append(dict(group=tag,cases=len(rows),calls=sum(x['repeats'] for x in rows),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rows)))
assert sum(x['cases'] for x in precision)==348 and sum(x['calls'] for x in precision)==1044
events={k:rd(q/f'c1112_r22_{k}_summary.json') for k in ['screen_event','holdout_event','holdout_event_repeat','holdout_aa_event']}
for key in ['screen_event','holdout_event','holdout_event_repeat']:
 v=events[key];assert all(x['windows']==8 for x in v['cases']);assert v['stats']['selected']['min']>0
selected={x['id'] for x in events['holdout_event']['cases'] if x['selected']}
assert selected=={x['id'] for x in events['holdout_event_repeat']['cases'] if x['selected']}
controls={k:rd(q/f'c1112_r22_{k}_summary.json') for k in ['public','c8_control','split_control','other_control','c910_control','other_reverse']}
for run in controls['public']['runs']:
 _,B,M,N,K,dt,ta,tb=run['case']
 prefer=(ta and M%64!=0) or (K if tb else N)%64!=0
 ns='bmms1219_' if run['version']=='r22' and prefer else 'bmms11r2_'
 assert len(run['kernels'])==1 and ns in run['kernels'][0],run
san={}
exit_codes=dict(line.split() for line in (q/'c1112_r22_sanitizer_status.txt').read_text().splitlines())
assert exit_codes=={'memcheck':'0','racecheck':'0'}
for c in ['memcheck','racecheck']:
 p=q/f'c1112_r22_instrumented_{c}.log';text=p.read_text(errors='replace')
 vals=[json.loads(l) for l in (q/f'c1112_r22_instrumented_{c}.jsonl').read_text().splitlines()];assert len(vals)==2 and all(x['pass'] for x in vals)
 san[c]=dict(errors=text.count('====== ERROR:'),skipped='temporarily ignored' in text,finished_kernel_count=text.count('Sanitizer finished on kernel'),
  messages=dict(collections.Counter(re.sub(r' in ".*','',x) for x in re.findall(r'====== ERROR: ([^\n]+)',text))))
 assert not san[c]['skipped'] and san[c]['finished_kernel_count']==2
assert san['memcheck']['errors']==0
host=rd(r/'V12_npu_lab/host_c1112/RESULTS.json')
summary=dict(candidate=src.name,parent=base.name,sha256=sha(src),parent_sha256=sha(base),parent_recovered_byte_for_byte=True,host=host,precision=precision,events=events,controls=controls,sanitizers=san,status='local validation complete; Judge pending; r19 remains accepted')
dump(d/'SUMMARY.json',summary)
def row(name,k):
 s=events[k]['stats'];a=s['all'];b=s['selected'];return f"| {name} | {a['count']} | {b['count']} | {b['median']:.2f}% | {b['min']:.2f}%～{b['max']:.2f}% | {a['median']:.2f}% |"
def table(key):
 lines=[]
 for x in controls[key]['summary']:
  a=x['candidate_median_us'] if key=='other_reverse' else x['baseline_median_us']
  b=x['baseline_median_us'] if key=='other_reverse' else x['candidate_median_us']
  lines.append(f"| {x['case'][0]} / {'×'.join(map(str,x['case'][1:5]))} / {x['case'][5]} / {x['case'][6]}{x['case'][7]} | {a:.3f} | {b:.3f} | {b-a:+.3f} |")
 return '\n'.join(lines)
report=f'''# v12_r22：11/12范围内按物理跨度选择NZ预排布

主线是已接受的r19；r21 Judge全15点Pass，但Case12=122.28μs，无明确收益，不晋升。新候选[源码](../../../BMMS_V12/v12_r22_dense_nz_pitch.asc)尚未上Judge。输入形状仍是区间，所有NPU实验输入均为自行构造，不能当作隐藏case。

## 新证据与判断

据用户转述队友探针：11/12都B1、1024≤M<2048、2048≤N≤8192，MN按16对齐；Case11 K=2048～4064、Case12 K=1536～1760，K按32对齐。K12更短但耗时更长，排除了单纯K更长的解释。M仍能相差近2倍、N可相差4倍，dtype/layout及物理跨度未知，不能仅凭相同区间判断工作量接近或planner有问题。

R06的网格选择不依赖K。20 Cube下穷举24640组新域M/N，r21只在9606组切换（等权网格比例，并非隐藏case命中概率）；其Judge持平不能判断是否触发。

## 排查和本轮修改

本轮固定原R06的pM/pN/tasks/blocks、AM128/BN256、K1=256/K0=64、完整K的FP32累加和max N→sum M。比较原ND完整路径与r19已有NZ完整路径：主要差异是每宏块重复ND→NZ搬运改成一次全A/B预排布，但NZ路径也保留其显式尾部消费者，不能把全部时间差严格归因于单条搬运指令。预排布成本、全部输入重新写workspace和屏障均在kernel计时内，不缓存输入数据。

初筛强行对32组几何/布局都使用NZ：中位降幅**−5.74%**，最差慢约30%，最好降52.35%，因此拒绝全域启用。冻结与r19相同的物理跨度规则：

```cpp
(ta && M % 64 != 0) || ((tb ? K : N) % 64 != 0)
```

仅在B1、1024≤M<2048、2048≤N≤8192、1536≤K<4096且满足原R06约束时评估规则。false仍走原R06；true复用r19的PackInputs/NzProducer/显式尾部消费者，原planner不变。源码仅增加host包装与一处入口调用，移除后逐字节恢复r19；没有复制修改设备算法。

新ValidPlan审计更大的N/K，最大取样workspace {host['max_workspace_bytes']:,}字节、显式UB {host['max_app_ub_bytes']:,}字节，分别受128MiB和原190KiB门槛约束。host3200组shape/core/layout检查了打包覆盖、NZ地址上界、容量和计划一致。动态buffer仍按实际shape分配。

## 性能验证

设备Ascend910_9362、20 Cube、CANN9.0.0、dav-2201；构建和计时分离，NPU任务串行。初筛后冻结规则，再生成64组新配置，包含单独A跨度不利、单独B跨度不利、两边不利和两边对齐。四布局与FP16/BF16均有覆盖。每例先对照CPU FP64参考，之后100预热、8窗口AB/BA×32调用；保留全部窗口，不只挑最快值。

| 集合 | 全部配置 | 切换NZ | 切换子集中位降幅 | 切换范围 | 全集中位降幅 |
|---|---:|---:|---:|---:|---:|
{row('初筛集，应用冻结规则','screen_event')}
{row('新配置首轮','holdout_event')}
{row('新配置复测','holdout_event_repeat')}

A/A对照中位降幅{events['holdout_aa_event']['stats']['all']['median']:.3f}%。事件计时不包含host分配/同步及未知Judge框架开销，不能预测隐藏Case11/12具体耗时。

另用完整公共入口与msprof轻量task-time，在16组配置上验证同样分派和单kernel，每版2个交替独立进程，80调用丢弃前20：

| ID / B×M×N×K / dtype / ta,tb | r19 μs | r22 μs | 差值μs |
|---|---:|---:|---:|
{table('public')}

## 数值与回归

348组×3次=1044次公共入口数值检查全部通过：初筛40、独立配置64、原用例34、Case8 40、Split-K 128、其他控制10、旧Case12范围32（含1792～2048间隔及域外M/N）。FP64参考来自实际量化输入，逐输出阈值1e-4+1e-4*abs(ref)，每次调用前输出填NaN。事件和profiler也逐例检查输出，不合并计入1044次。

Case8控制：

| ID / B×M×N×K / dtype / ta,tb | r19 μs | r22 μs | 差值μs |
|---|---:|---:|---:|
{table('c8_control')}

Case15对应Split-K控制：

| ID / B×M×N×K / dtype / ta,tb | r19 μs | r22 μs | 差值μs |
|---|---:|---:|---:|
{table('split_control')}

其他路径：

| ID / B×M×N×K / dtype / ta,tb | r19 μs | r22 μs | 差值μs |
|---|---:|---:|---:|
{table('other_control')}

首轮Native控制ID9慢0.645μs（6.23%），因此另开反向版本顺序复测，每版4窗口、100调用丢弃前30。下表已将文件中的baseline=r22/candidate=r19翻转，仍按r19→r22展示：

| ID / B×M×N×K / dtype / ta,tb | r19 μs | r22 μs | 差值μs |
|---|---:|---:|---:|
{table('other_reverse')}

ID9复测为11.36→11.09μs，未重现最初退化；各控制差值为−0.270～+0.015μs。两次方向不同，支持存在运行间变动，但不能证明所有小差异都是噪声或保证隐藏点零退化。初测保留，不删除不利结果。

Case9/10区间的较短K R06控制：

| ID / B×M×N×K / dtype / ta,tb | r19 μs | r22 μs | 差值μs |
|---|---:|---:|---:|
{table('c910_control')}

控制点不在新分派域，但真实重新编译测量仍可能有差异，不能声称全部隐藏case必定不变，也不把小幅变快归因于本次修改。

## 检测与局限

实际全指令插桩检查两例M1040/N2064/K1568的非零全负输入，分别FP16/BF16，ta=0,tb=1，确实执行NZ：memcheck报告{san['memcheck']['errors']}条ERROR，racecheck报告{san['racecheck']['errors']}条ERROR。检测均完成2个kernel且没有跳过。不能把退出码0或数值Pass视作检测全通过；race与历史init限制未闭环，本轮未跑initcheck。

第一轮构建因新ValidPlan与原类型命名空间产生ADL歧义而失败；显式限定bmms1222::ValidPlan后全量重编通过。初次失败日志保留，后续所有测试对应最终源hash。

## 结论与下一步

1. 已证实NZ不是普遍更快，物理跨度判定比直接扩大路由更合适；冻结规则后独立样本结果见表。
2. r21只解决部分几何负载问题，本轮隔离搬运变化，未叠加r21，基线仍为r19。
3. 隐藏shape的dtype/layout/跨度仍未知；如果r22仍持平，一次覆盖相同Eligible+Prefer的已校准R06 stress探针比继续盲改更有价值。若继续定位形状，优先N≥4096与M≥1536；同区间不意味着相同工作量。

下一步提交r22全15点，重点11/12，同时核对Case8约47μs、Case15约11μs，取得明确真实收益后再晋升。

源码SHA256 `{sha(src)}`；父版 `{sha(base)}`。复现流程`check_c1112_r22.sh`与`finish_c1112_r22.sh`；同输入生成器、seed/hash、原始事件/profile CSV、构建参数和插桩日志保存在`c1112_evidence.zip`。本项目为独立ASC ABI，沿用ACL/msprof，无torch扩展；用例自行设计。
'''
(d/'REPORT.md').write_text(report,encoding='utf-8')
mp=o/'v12_r22_manifest.json';m=rd(mp);m.update(status=summary['status'],validation_report='../V12_npu_lab/results/c1112_20260928/REPORT.md',precision=precision,performance={k:v['stats'] for k,v in events.items()},sanitizers=san,host=host);dump(mp,m)
(o/'v12_r22_README.md').write_text('''# v12_r22：按物理跨度选择NZ

父版为r19；r21不合入。本版仅在B1、M∈[1024,2048)、N∈[2048,8192]、K∈[1536,4096)且原R06 eligible时，按物理ND跨度决定是否复用r19的NZ kernel；不改变原planner。Case8/15和其他原实现保留。

348组、1044次数值通过；同卡独立性能验证及检测局限见[完整报告](../V12_npu_lab/results/c1112_20260928/REPORT.md)。两例memcheck无ERROR；race与历史init仍未闭环，不能声称完整sanitizer通过。实际Judge收益待反馈，r19保持主线。
''',encoding='utf-8')
main=rd(o/'MAINLINE.json');assert main['accepted_version']=='v12_r19'
main['candidates']=[c for c in main['candidates'] if c['version']!='v12_r22']+[dict(version='v12_r22',file=src.name,parent=base.name,sha256=sha(src),status=summary['status'],npu_report=m['validation_report'])]
main.update(recommended_candidate=src.name,next_action='Judge r22 all15; inspect 11/12 and preserve8/15; r19 accepted');dump(o/'MAINLINE.json',main)
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r19](v12_baseline_r19.asc)。r21无明确Judge收益，不晋升。下一候选为[r22](v12_r22_README.md)，等待Judge反馈。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(o/'v12_r22_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [src,o/'v12_r22_README.md',mp,d/'REPORT.md',d/'SUMMARY.json']:z.write(p,p.relative_to(r).as_posix())
with zipfile.ZipFile(o/'v12_r22_submission.zip') as z:assert z.testzip() is None
print(json.dumps(dict(source=src.name,sha256=sha(src),precision=348,calls=1044,events={k:v['stats'] for k,v in events.items()},sanitizers=san),ensure_ascii=False))
