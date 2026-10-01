"""Finalize completed evidence; never regenerate source or change accepted r12."""
from pathlib import Path
from collections import defaultdict
import json,hashlib,statistics as st,zipfile,re,collections
R=Path(__file__).resolve().parents[1]
D=R/'V12_npu_lab/results/case8_20260928'
E=D/'evidence';Q=E/'results';O=R/'BMMS_V12'
def dump(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def rows(name):return [json.loads(x) for x in (Q/name).read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def events(name):
    rr=rows(name);groups=defaultdict(lambda:defaultdict(list));selected=set()
    for x in rr:
        groups[x['case']][x['label']].append(x['device_stream_us_per_call'])
        if x['label']=='B' and x['kernel']=='bmms1218':selected.add(x['case'])
    out=[]
    for case,g in sorted(groups.items()):
        a=st.median(g['A']);b=st.median(g['B'])
        out.append(dict(case=case,baseline_us=a,candidate_us=b,reduction_pct=100*(1-b/a),selected=case in selected))
    stats={}
    for label,dd in [('all',out),('nz',[x for x in out if x['selected']]),('fallback',[x for x in out if not x['selected']])]:
        if dd:
            v=[x['reduction_pct'] for x in dd]
            stats[label]=dict(count=len(v),median_reduction_pct=st.median(v),min_reduction_pct=min(v),max_reduction_pct=max(v))
    return dict(file=name,stats=stats,cases=out)
baseline=O/'v12_baseline_r12.asc';source=O/'v12_r18_case8_adaptive_nz.asc'
assert sha(baseline)=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
assert sha(source)=='75853cabc656f40725f669f12b82c18d49bf53d7ef4cc69fa2fe2bf77705835c'
assert sha(E/'r18.asc')==sha(source)
data=source.read_bytes();a=data.index(b'// BMMS1218_BEGIN');end=data.index(b'// BMMS1218_END\n\n',a)+len(b'// BMMS1218_END\n\n')
recovered=data[:a]+data[end:]
hook=next(x for x in recovered.splitlines(keepends=True) if b'if(bmms1218::TryLaunch' in x)
assert recovered.replace(hook,b'',1)==baseline.read_bytes()
correct=[]
for f in ['c8_r18_correctness.jsonl','c8_r18_holdout_correctness.jsonl','c8_r18_final_correctness.jsonl','c8_r18_controls_correctness.jsonl','c8_r18_split_retention.jsonl']:
    rr=rows(f);assert all(x['pass'] for x in rr)
    correct.append(dict(file=f,cases=len(rr),calls=sum(x['repeats'] for x in rr),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rr)))
primary=events('c8_r18_final_event.jsonl');repeat=events('c8_r18_final_event_repeat.jsonl');aa=events('c8_r18_event_aa.jsonl')
control=json.loads((Q/'c8_r18_controls_repeat_summary.json').read_text())
split=json.loads((Q/'c8_r18_split_repeat_summary.json').read_text())
for d in [control,split]:
    for x in d['summary']:
        x['delta_us']=x['candidate_median_us']-x['baseline_median_us']
        x['reduction_pct']=100*(1-x['candidate_median_us']/x['baseline_median_us'])
san={}
for check in ['racecheck','initcheck']:
    f=f'c8_r18_instrumented_{check}'
    log=(Q/(f+'.log')).read_text(errors='replace')
    rr=rows(f+'.jsonl')
    assert len(rr)==2 and all(x['pass'] for x in rr)
    assert 'temporarily ignored' not in log and 'No active sanitizer' not in log
    old=(Q/f'c8_r12_instrumented_{check}.log').read_text(errors='replace')
    old_rows=rows(f'c8_r12_instrumented_{check}.jsonl')
    assert len(old_rows)==2 and all(x['pass'] for x in old_rows)
    assert 'temporarily ignored' not in old
    def findings(s):
        return dict(errors=s.count('====== ERROR:'),spaces=dict(collections.Counter(re.findall(r' on (GM|UB|L1|L0A|L0B|L0C|PRIVATE) in ',s))),
                    has_skipped='temporarily ignored' in s)
    san[check]=dict(cases=2,instrumented=True,log=f+'.log',r18=findings(log),r12=findings(old),
        verdict='findings in both versions; not a clean sanitizer pass')
statuses=(Q/'c8_r18_instrumented_status.txt').read_text().splitlines()
assert set(statuses)=={'racecheck 0','initcheck 0'},statuses
mem=rows('c8_r18_memcheck.jsonl');assert len(mem)==2 and all(x['pass'] for x in mem)
san['memcheck']=dict(cases=2,instrumented=False,log='c8_r18_memcheck.log',warnings=['FFTS_BASE_ADDR not reset','missing debug_line'])
imlog=(Q/'c8_r18_instrumented_memcheck.log').read_text(errors='replace')
imrows=rows('c8_r18_instrumented_memcheck.jsonl')
assert len(imrows)==2 and all(x['pass'] for x in imrows)
oldmem=(Q/'c8_r12_instrumented_memcheck.log').read_text(errors='replace')
assert len(rows('c8_r12_instrumented_memcheck.jsonl'))==2
san['instrumented_memcheck']=dict(cases=2,r18_errors=imlog.count('====== ERROR:'),r12_errors=oldmem.count('====== ERROR:'),
    log='c8_r18_instrumented_memcheck.log',verdict='both versions report UB Max errors; unresolved, not a clean pass',warnings='FFTS_BASE_ADDR not reset')
summary=dict(parent=baseline.name,parent_sha256=sha(baseline),candidate=source.name,sha256=sha(source),parent_recovered_byte_for_byte=True,
    device='Ascend910_9362 logical0;20 Cube cores;CANN9.0.0;dav-2201',synthetic_not_hidden=True,
    correctness=correct,total_cases=sum(x['cases'] for x in correct),total_calls=sum(x['calls'] for x in correct),
    final40=primary,independent_repeat40=repeat,aa=aa,controls=control['summary'],split_retention=split['summary'],sanitizers=san,
    decision='r18 experimental Judge candidate; inherited sanitizer findings remain unresolved and disclosed; keep r12 accepted until feedback')
dump(D/'SUMMARY.json',summary)
def performance_table(d):
    return '\n'.join(f"| {x['case'][0]} / {'×'.join(map(str,x['case'][1:5]))} | {x['baseline_median_us']:.3f} | {x['candidate_median_us']:.3f} | {x['delta_us']:+.3f} |" for x in d['summary'])
table='\n'.join(f"| {x['file']} | {x['cases']} | {x['calls']} | {x['max_tolerance_ratio']:.6f} |" for x in correct)
perf='\n'.join(f"| {label} | {primary['stats'][key]['count']} | {primary['stats'][key]['median_reduction_pct']:.2f}% | {repeat['stats'][key]['median_reduction_pct']:.2f}% |" for label,key in [('全部新样本','all'),('NZ 分支','nz'),('原路径回退','fallback')])
report=f'''# Case8：r18 条件 NZ 整理与设备验证

## 结论和主线

用户已确认 r12 的 Case15 稳定约11.5 μs、其他点基本无影响；已冻结 `v12_baseline_r12.asc`，r03保留为历史回退。本轮推荐 **v12_r18_case8_adaptive_nz.asc** 进入 Judge，尚未晋升。比赛 Case8 原有约62 μs来自用户历史反馈；下面全部是本地合成样本，未知真实Case8精确形状及转置。

40组在分派规则冻结后新生成的样本，整体耗时中位缩短 {primary['stats']['all']['median_reduction_pct']:.2f}%，独立进程复测 {repeat['stats']['all']['median_reduction_pct']:.2f}%。新分支26例的中位缩短约27%，14例回退原路径。不能把该均值换算成真实Case8必然达到的延迟，也不能保证隐藏Case8会命中新分支。

## 修改及原因

原 R43 路径是一个混合 kernel：AIV 输入补齐整理、全局屏障、Cube 计算、AIV 归约。r18沿用这个结构、128×256宏块、原 pM/pN planner、K1=256双缓冲、K0=64双缓冲、完整K累加顺序和输出归约；只改变符合条件的输入整理及GM→L1读取方式。

将A/B物理矩阵整理为 `[column/16, padded_row,16]`。每个pack job读取最多256×128个原始16位元素，先在UB用32B块重排，再批量写GM；Cube直接把已有NZ片段搬入L1，减少反复ND→NZ读入的代价。FP16/BF16输入位模式原样复制，M/N/K尾部显式补零；N尾部在max前仍掩成负无穷。

新入口沿用原R43完整元数据域：B1、FP16/BF16、M/N∈[1024,2048)、1024<K<1280且K%8=0、至少一个轴不满足16/16/32对齐，另检查planner和资源边界。只在以下实测性能条件成立时调用NZ路径，否则在分配/launch前回退原R43：

```cpp
(TA && Mp % 64 != 0) || ((TB ? Kp : Np) % 64 != 0)
```

Mp/Np/Kp是16/16/32补齐尺寸，64个16位元素为128B。这是有限实测支持的性能启发式，不是API合法性要求或普遍硬件定律。规则由初始12例和扩展40例观察确定；最终新40例没有用于回调该规则。程序只依赖形状、dtype、转置与设备核数，不依赖测试ID、输入内容或参考答案。

## 资源与同步审查

- pack复用原128KiB UB：64KiB ND输入区＋64KiB NZ输出区，顺序拥有；本轮未提高显式UB峰值，最大189088B，预算190KiB。
- L1 393216B，L0A 32768B，L0B 65536B，L0C 131072B；workspace大小和原R43相同。
- 每个job的目标NZ区间唯一；写回完成的MTE3→V事件保护下一job复用，所有worker（含零job）参与pack屏障；原batch调度模式保留。
- 新模块和一个host入口调用删除后，父版r12逐字节恢复。Case15、Native、Dot、R06等原有函数源码保留；这证明修改范围，不等同于所有隐藏点性能已获保证。

UB→UB DataCopy处于PIPE_V，核对实际CANN9.0 dav_c220头文件。有关32B C0/stride单位参照官方 [ND2NZ API](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_00127.html)，UB复制管线参照官方 [copy_ubuf_to_ubuf](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta2/API/cceintrinsicapi/cceapi_0070.html)；提交使用公开DataCopy接口。

## 实验筛选

所有版本都从已接受r12派生，未合入失败版本的优化；r18复用r17的NZ实现并加性能守卫。

| 候选 | 主改动 | 初始12例结果/决定 |
|---|---|---|
| r13 | 每16列整条高度整理NZ | 耗时中位增加26.10%，淘汰；AIC读取变快但AIV读变慢 |
| r14 | 128×128宏块，L1 K512/L0 K128 | 耗时中位增加8.76%，最大退化31.60%，淘汰 |
| r15 | 原始ragged输入直入L1，省全量pack | 耗时中位增加54.19%，全部变慢，淘汰 |
| r16 | 256×128读入，再多条32B跨距写GM | 耗时中位增加138.79%，MTE3代价过大，淘汰 |
| r17 | UB内重排后批量写NZ | 收益依赖stride/layout，扩展40例亦有退化，不能全域采用 |
| r18 | r17实现＋有依据的回退条件 | 新40例及独立复测通过，唯一推荐提交候选 |

r14事件程序初版workspace少计partial大小，在运行前发现并停止该项、修复重编；归档性能来自修正后程序，公共提交源码的workspace计算始终正确。每个候选首轮24例精度通过并不能抵消其性能退化。

阶段定位：原路径pack-only约12.4–15.2 μs，full减compute-only约5.8–9.3 μs；管线时长不可简单相加，不能把pack-only全部当作可回收收益。代表NN样本原AIC MTE2约24.629 μs，NZ首版降至7.341 μs，但前端读/写开销使首版更慢。最终方案针对这一前后端矛盾做UB重排。

## 正确性

独立CPU FP64参考使用先量化的实际FP16/BF16输入，完整K求和→真实N max→真实M sum。阈值为 `1e-4 + 1e-4*abs(reference)`；tolerance ratio≤1通过。每次调用前输出写NaN，检查所有输出有限、满足阈值。

| 记录文件（evidence/results） | 输入组数 | 实际调用数 | 最大tolerance ratio |
|---|---:|---:|---:|
{table}

合计 {summary['total_cases']} 组、{summary['total_calls']} 次全部通过（包含回退/控制样本，不能全称为新NZ路径）。涵盖两精度、四转置、单轴/多轴尾部、负数、全零、等列、宽幅和最后行/列主导数据。额外事件窗口和公共入口profiler运行也做正确性门禁，未计入以上774次。

## 性能证据与测量边界

Ascend910_9362，逻辑设备0，20 Cube cores，CANN9.0.0，dav-2201。NPU任务串行；性能计时与CPU编译分开。设备事件测试在同进程预分配输入/workspace，100次热身，12个AB/BA交替窗口，每窗口64次调用，第二次使用独立进程。此指标含流执行间隙，不含公共入口分配/同步，不冒充Judge计时。

| 最终新40例 | 组数 | 首测耗时中位缩短 | 独立复测 |
|---|---:|---:|---:|
{perf}

新分支首测范围 {primary['stats']['nz']['min_reduction_pct']:.2f}%–{primary['stats']['nz']['max_reduction_pct']:.2f}%；复测范围 {repeat['stats']['nz']['min_reduction_pct']:.2f}%–{repeat['stats']['nz']['max_reduction_pct']:.2f}%。回退样本最差差异约0.107%。初始12例A/A对照的耗时差范围 {aa['stats']['all']['min_reduction_pct']:.3f}%–{aa['stats']['all']['max_reduction_pct']:.3f}%，中位 {aa['stats']['all']['median_reduction_pct']:.3f}%。这是本实验噪声标尺，不等同于比赛噪声范围。

公共入口另以msprof仅task-time采集ABBA：确认实际kernel名、每输入恰好一次混合kernel、保留分派/分配和同步。代表1041×1105×1064 FP16 NN，kernel中位从49.745降至40.665 μs；1537×1599×1128 FP16 TN约117.700降至84.280 μs。轻量profiler仍会影响计时，和device-event绝对值不混用。

## 其他路径回归

首轮部分短路径出现0.05–0.18 μs差异，因此做独立复测：每版本4个交替独立进程，每输入80次、去掉前20次。下表为各进程中位数的中位数，B×M×N×K为合成输入，ID不是比赛Case编号。

| 控制ID / B×M×N×K | r12 μs | r18 μs | 差值 μs |
|---|---:|---:|---:|
{performance_table(control)}

| Split-K ID / B×M×N×K | r12 μs | r18 μs | 差值 μs |
|---|---:|---:|---:|
{performance_table(split)}

逐窗口原始值保留在SUMMARY.json和 `c8_r18_*repeat_summary.json`。所有控制调用均正确，但有限合成集不能证明全15个隐藏点无退化；最终仍由Judge同时核对Case15约11.5 μs的成果。

## 内存与竞争检查

memcheck完成2例（FP16 NN负数、BF16 TT最后一列主导；M1041/N1105/K1032），正常退出且计算通过。工具报告原同步机制相关FFTS_BASE_ADDR未复位警告、缺少debug_line警告，不能称为零警告。

第一次普通构建的racecheck/initcheck被工具明确跳过，虽退出码0也**不计为通过**，原始日志保留。随后用同一源码单独编译 `sanitize_r18`，加入 `--cce-enable-sanitizer -gline-tables-only`，并对r12做相同编译、相同2例对照；插桩构建不参与任何性能数据。

**三类插桩检查均有告警，未作为通过项。** r18 racecheck报告{san['racecheck']['r18']['errors']}条L0C累加RAW/WAW，r12报告{san['racecheck']['r12']['errors']}条（另含UB）；r18 initcheck报告{san['initcheck']['r18']['errors']}条，r12报告{san['initcheck']['r12']['errors']}条，包含GM中间量与PRIVATE计划字段。补做全指令memcheck，r18报告{san['instrumented_memcheck']['r18_errors']}条、r12报告{san['instrumented_memcheck']['r12_errors']}条UB非法访问，均定位到继承的最终 `Max(merged,merged,tmp,p.M)`。两版插桩计算结果均正确。两版都有告警并不能单独证明它们是误报；详细位置、同步审查与未关闭项保留在SANITIZER_REVIEW.md。普通构建memcheck没有覆盖这些完整指令，不能替代插桩结论。

MMAD后的尺寸阈值barrier与[CATLASS TileMmad的同步策略](https://catlass.readthedocs.io/en/latest/1_Practice/06_tile_development/)一致；新版未改变这一计算循环。初始化告警涉及跨核流水中间量与在Init中赋值的计划字段；Max的局部tensor均申请p.M个float，计数同为p.M。静态审查未找到新增未写即读或索引越界路径，但工具结论仍未消除，不能仅以数值通过或父版同样告警断言无风险。检测只覆盖2个实例，r18仍为实验候选，r12主线不动。

## 交付与复现

提交文件：[v12_r18_case8_adaptive_nz.asc](../../../BMMS_V12/v12_r18_case8_adaptive_nz.asc)。父版：[v12_baseline_r12.asc](../../../BMMS_V12/v12_baseline_r12.asc)。源hash分别为 `{sha(source)}`、`{sha(baseline)}`。

本目录SUMMARY.json给出汇总；evidence保存输入清单、seed/输入hash、正确性JSONL、计时窗口、profiler CSV、构建参数和sanitizer日志。原始tensor二进制可按归档generator重建；不将这些合成清单称为隐藏测试形状。

远端工作目录 `/home/developer/bmms_v12_lab_20260928`。加载CANN环境后，`cmake --build build --target c8_r18_build -j2`；生成 `cases_c8`、`cases_c8_holdout`、`cases_c8_final`；按 `validate_c8_r18.sh` 和 `finish_c8_r18.sh` 串行运行。profiler输出tag已存在时必须换新tag；复用结果前核对hash。不要为了复现运行会覆盖主线状态的prepare/finalize旧脚本。

比赛只需测r18这一版；未获实测反馈前r12继续主线。若Case8无收益，先判断可能回退或隐藏shape上的效应不足，不能仅凭合成26例有收益就扩大守卫；保留原始15点结果再定下一步。
'''
(D/'REPORT.md').write_text(report,encoding='utf-8')
manifest=json.loads((O/'v12_r18_manifest.json').read_text())
manifest.update(status='experimental Judge candidate: numerical/performance tests passed; instrumented sanitizer findings in both r12/r18 unresolved; r12 remains accepted',validation_report='../V12_npu_lab/results/case8_20260928/REPORT.md',
    precision=dict(cases=summary['total_cases'],calls=summary['total_calls'],all_pass=True),
    final40_stats=primary['stats'],repeat40_stats=repeat['stats'],sanitizers=san)
dump(O/'v12_r18_manifest.json',manifest)
main=json.loads((O/'MAINLINE.json').read_text());assert main['accepted_version']=='v12_r12'
for v in range(13,19):
    mp=O/f'v12_r{v:02}_manifest.json';mm=json.loads(mp.read_text())
    status=('rejected: synthetic regressions' if v<=16 else 'not recommended ungated: mixed synthetic performance' if v==17 else manifest['status'])
    item=dict(version=f'v12_r{v:02}',file=mm['candidate'],sha256=mm['sha256'],parent='v12_baseline_r12.asc',status=status,npu_report=manifest['validation_report'])
    main['candidates']=[x for x in main['candidates'] if x['version']!=item['version']]+[item]
    if v==17:mm['status']=status;dump(mp,mm)
main['next_action']='Judge v12_r18 Case8 candidate, verify all15 including retained Case15; r12 remains accepted pending feedback'
main['review']['historical']=True;main['active_diagnostic']['historical']=True
main['recommended_candidate']='v12_r18_case8_adaptive_nz.asc';dump(O/'MAINLINE.json',main)
readme=f'''# v12_r18：Case8 条件NZ整理

直接提交 **v12_r18_case8_adaptive_nz.asc**。从已确认的r12主线派生，完整保留Case15优化；r12继续作为对照和回退，r18等待Judge确认。

在Case8原有元数据域内，按stride/转置选择UB内NZ重排，减少Cube反复ND→NZ读取；未获益的组合回到原R43。宏块、planner、K累加次序及其他路径源码保留。删除新模块与单个入口调用可逐字节恢复r12。

- NPU精度：258组×3次，共774次全部通过，含128组Split-K回归。
- 冻结规则后的新40组合成样本：耗时中位缩短15.30%，独立复测15.49%；其中26组新路径中位约27%，其余14组回退原路径。
- 公共入口计时、其他路径和Split-K复测已归档；三类插桩检查都有r12/r18双方告警，包括继承归约的UB Max访问，尚未关闭，不能称为全面通过，详见报告。

真实Case8形状未知，不能保证它命中新路径或达到上述合成收益。请用这一版的完整15点结果验收，尤其Case8以及Case15约11.5 μs的保留情况。

[完整实验、资源/同步审查和测量限制](../V12_npu_lab/results/case8_20260928/REPORT.md) · [机器可读记录](v12_r18_manifest.json)

SHA256：`{sha(source)}`
'''
(O/'v12_r18_README.md').write_text(readme,encoding='utf-8')
with zipfile.ZipFile(O/'v12_r18_case8_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in [source,O/'v12_r18_README.md',O/'v12_r18_manifest.json']:
        z.write(p,p.name)
    z.write(D/'REPORT.md','CASE8_REPORT.md');z.write(D/'SUMMARY.json','CASE8_SUMMARY.json')
with zipfile.ZipFile(O/'v12_r18_case8_submission.zip') as z:assert z.testzip() is None
print(json.dumps(dict(source_sha256=sha(source),cases=summary['total_cases'],calls=summary['total_calls'],report=str(D/'REPORT.md')),ensure_ascii=False))
