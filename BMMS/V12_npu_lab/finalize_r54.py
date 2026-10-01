"""Archive validated evidence and record the candidate without promoting r41."""
from pathlib import Path
import csv,hashlib,json,tarfile,statistics,re
ROOT=Path(__file__).resolve().parents[1];V=ROOT/'BMMS_V12';OUT=ROOT/'V12_npu_lab/results/case12_k1_20261001'
archive=OUT/'evidence.tar.gz';E=OUT/'evidence';E.mkdir(exist_ok=True)
with tarfile.open(archive) as tf:
    members=tf.getmembers()
    for m in members:
        p=(E/m.name).resolve()
        assert p==E.resolve() or E.resolve() in p.parents,m.name
        assert not m.issym() and not m.islnk(),m.name
    tf.extractall(E,members=members,filter='data')
def readj(path):return json.loads(path.read_text(encoding='utf-8'))
checks={}
for version in ['r41','r51','r52','r53','r54']:
    rows=[json.loads(x) for x in (E/f'results/{version}_correctness.jsonl').read_text().splitlines()]
    assert len(rows)==164 and all(x['pass'] for x in rows)
    checks[version]={'configurations':len(rows),'calls':sum(x['repeats'] for x in rows),
                     'max_tolerance_ratio':max(x['max_tolerance_ratio'] for x in rows)}
analyses={p.stem:readj(p) for p in (E/'results').glob('*_analysis.json')}
for version in ['r51','r52','r53','r54']:
    p=V/f'v12_{version}_manifest.json';meta=readj(p)
    assert hashlib.sha256((E/f'{version}.asc').read_bytes()).hexdigest()==meta['sha256']
    name=next(V.glob(f'v12_{version}_*.asc'))
    assert name.read_bytes()==(E/f'{version}.asc').read_bytes()
    meta['numerical_validation']=checks[version]
    meta['screen']=analyses[f'{version}_screen_analysis']['overall']
    meta['npu_report']='../V12_npu_lab/results/case12_k1_20261001/REPORT.md'
    if version=='r51':meta['status']='rejected: TA=false regressions; TA=true gains too small'
    elif version=='r52':meta['status']='rejected: broad performance regressions'
    elif version=='r53':meta['status']='ungated research control; superseded by r54 selector'
    else:
        meta['status']='ready for Judge 15-case evaluation; not promoted'
        meta['holdout']=analyses['r54_holdout_analysis']
    p.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

sanlog=(E/'san_r54/memcheck_full.log').read_text()
sanstatus=(E/'results/r54_memcheck_full_status.txt').read_text().strip()
sanprecision=[json.loads(s) for s in (E/'san_r54/full_precision.jsonl').read_text().splitlines()]
tail_log=(E/'san_r54/memcheck_full_tail.log').read_text()
tail_status=int((E/'results/r54_memcheck_full_tail_status.txt').read_text().strip())
tail_precision=[json.loads(s) for s in (E/'san_r54/tail_precision.jsonl').read_text().splitlines()]
all_sanlog=sanlog+'\n'+tail_log
completed=sorted(set(re.findall(r'Sanitizer finished on kernel "([^"]+)"',all_sanlog)))
warnings=[s for s in all_sanlog.splitlines() if 'Warning:' in s]
san=dict(tool='mssanitizer memcheck',blocks='all',configurations=4,shape=[1,1280,4160,1536],
         dtype_TA='FP16/BF16 x TA=false/true, TB=false',initial_exit_code=int(sanstatus),tail_exit_code=tail_status,
         initial_finishes=sanlog.count('Sanitizer finished'),tail_finishes=tail_log.count('Sanitizer finished'),completed_kernels=completed,
         warning_count=len(warnings),warning_types=sorted(set(s.split(' in block ')[0] for s in warnings)),
         numerical_pass=len(sanprecision)==4 and all(r['pass'] for r in sanprecision) and len(tail_precision)==1 and tail_precision[0]['pass'],
         scope_limit='Memcheck only on four configurations. Does not certify racecheck/initcheck/synccheck or all shapes.')
assert san['initial_exit_code']==124 and san['tail_exit_code']==0 and len(completed)==4 and san['numerical_pass'],san
assert 'ERROR:' not in all_sanlog and all('Register FFTS_BASE_ADDR was not reset' in s for s in warnings),all_sanlog
san['memory_access_errors_reported']=False
(OUT/'SANITIZER.json').write_text(json.dumps(san,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

perf=[]
for split in ['screen','holdout']:
    d=readj(E/f'results/r54_{split}_summary.json')
    for run in d['runs']:
        kernel='bmms1254_' if run['version']=='r54' and run['case'][3]%128==64 else 'bmms1230_'
        assert all(kernel in x for x in run['kernels'])
    for row in d['summary']:
        cid,B,M,N,K,dt,ta,tb=row['case'];aa=row['baseline_median_us'];bb=row['candidate_median_us']
        perf.append(dict(split=split,id=cid,B=B,M=M,N=N,K=K,dtype=dt,TA=ta,TB=tb,
                         r54_hit=N%128==64,r41_us=aa,r54_us=bb,reduction_pct=100*(1-bb/aa),
                         baseline_windows=json.dumps(row['baseline_medians_us']),candidate_windows=json.dumps(row['candidate_medians_us'])))
with (OUT/'R54_PERFORMANCE.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(perf[0]));w.writeheader();w.writerows(perf)

summary=dict(baseline='v12_baseline_r41.asc',candidate='v12_r54_case12_stride_gated_m256.asc',
             synthetic_not_Judge=True,correctness=checks,sanitizer=san,
             performance=analyses,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
(OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest=readj(V/'MAINLINE.json');assert manifest['accepted_sota']=='v12_baseline_r41.asc'
assert hashlib.sha256((V/manifest['accepted_sota']).read_bytes()).hexdigest()==manifest['accepted_sha256']
for version in ['r51','r52','r53','r54']:
    meta=readj(V/f'v12_{version}_manifest.json')
    entry=dict(version=f'v12_{version}',file=next(V.glob(f'v12_{version}_*.asc')).name,parent='v12_baseline_r41.asc',
               sha256=meta['sha256'],status=meta['status'],npu_report=meta['npu_report'])
    manifest['candidates']=[x for x in manifest['candidates'] if x.get('version')!=entry['version']]+[entry]
manifest['active_candidate']='v12_r54_case12_stride_gated_m256.asc'
manifest['latest_experiment_report']='../V12_npu_lab/results/case12_k1_20261001/REPORT.md'
(V/'MAINLINE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

report='''# Case12：r51–r54 实验与提交候选（2026-10-01）

**推荐提交 v12_r54 跑完整15点；主线仍为 r41。** 只在新的行跨度入口命中时使用 AM256×BN128，其他输入保留 r41。未向 Judge 自动上传，以下全是本地合成输入实验。

## 顺序、结果与决策

|版本|独立改动|32组初筛中位耗时降幅|决定|
|---|---|---:|---|
|r51|K1 256→320，保留原macro与预取|-0.23%|不提交；TA=false约慢7%，TA=true约快1%|
|r52|K1 256→192，机制对照|-5.42%|不提交|
|r53|AM256×BN128，K1=256，保留r30跨宏块预取|5.28%|全范围仍有-1.72%退化，收窄入口|
|r54|r53几何只用于N%128==64|命中16组中位12.11%|提交候选；独立预留集确认|

所有实验分别基于r41，不叠加失败变更。r53与历史r29不同：保留r30跨宏块预取，保留原逐fractal LoadData，保留显式final-Max尾部处理；没有混入早期r29的LoadData合并试验。

## 为什么选择这个入口

K=1536、TB=false、pN=2、pM>=8、tasks=blocks=cores来自用户新探针报告。源码枚举表明，在本地确认的20核下，该交集只有M=1280；N仍为4096..6080步长64。该结论以比赛使用相同核数/源码为条件，不是对Judge exact shape的额外实测。

当前r30各核心只有一个M宏块，简单交换循环无法创造同核跨M B复用。AM256×BN128将20核任务网格由10×2改为5×4，B重复读取次数减半、A读取增加；合计逻辑请求字节并不必然下降，不能称为总HBM流量减半。

初筛发现N%128==64在TA两值、两dtype下都明显改善；N%128==0收益微小且有退化。**在查看96组预留集性能前已冻结这个整除条件**，不是按具体N白名单选择结果。报告保留全96组数据，包括回退组。

TA=false时K1=320/192让部分A分段起点偏离原来的512字节对齐；TA=true时没有这个变化。这是第一轮转置差异的合理解释，尚无硬件计数器因果验证，不能把全部退化归因于它。

## r54 独立复测

|数据组|配置数|耗时降幅中位数|最小～最大|两个窗口均更快|
|---|---:|---:|---:|---:|
|初筛命中|16|12.11%|7.02%～16.75%|16/16|
|预留命中|48|11.86%|6.49%～16.62%|48/48|
|预留回退|48|0.25%|-0.04%～1.09%|28/48，不计收益|

已逐条核对msprof实际kernel：命中为bmms1254，回退仍为bmms1230。共覆盖32种N×2种TA×2种dtype=128组；筛选32组和预留96组没有重叠。
计时使用实际提交CABI的run_kernel，串行A/B、B/A两个窗口，各30次调用丢弃前5次，比较窗口中位数；不是host wall time、不是隐藏15点成绩。未对微小回退路径波动宣称收益。

设备：Ascend910_9362、ACL查询20 Cube，CANN9.0.0、dav-2201。新容器没有旧实验目录，本轮从本地归档恢复源码并重新编译。只使用逻辑device0，无并发NPU实验。

## 正确性与静态检查

164组输入包含128组shape/dtype/TA组合、20组全负/零/宽动态范围/相同列/正负抵消以及16组范围外回归。r41/r51/r52/r53每组3次均通过，r54每组5次、共820次均通过。参考为实际FP16/BF16量化输入的CPU FP64 `sum_M(max_N(A@B))`，阈值1e-4+1e-4×abs(ref)，每次输出先以NaN填充。

K0=64和完整K累加顺序不变，仍在完整K结束后maxN，再sumM。r54删除新增模块及一行入口可逐字节恢复r41。r51/52的75条L1事件状态轨迹、NZ块覆盖；r53的M/N尾块布局与部分结果唯一写入；r54的32768组selector对照全部通过。CPU模型不是硬件race证明。

## 内存检查及限制

r54带 `--cce-enable-sanitizer` 完整编译。先block0、再全block，对M1280/N4160/K1536的FP16/BF16×TA两值共4配置执行memcheck。组合运行在180秒分析限时结束（退出码124），此前前三组已完成；随后单独补跑最后一组并完成（退出码0）。合计四个不同kernel的全block检查完成，数值通过，未报告内存访问错误。没有把限时退出直接计作通过。
日志仍包含 **FFTS_BASE_ADDR未复位告警**，没有将其标成零告警。未重跑全域racecheck/initcheck/synccheck，历史相关问题仍保留；不能以这四组memcheck宣称所有配置的同步/初始化均已证明。
第一次工具启动因日志目录权限拒绝而未执行，即使退出码为0也未计入通过；修正本实验日志目录权限后重新执行。详情见SANITIZER.json及原始日志。

## 交付与下一步

- 提交完整文件：`../../../BMMS_V12/v12_r54_case12_stride_gated_m256.asc`。
- SHA256：`24d183f027a78e4637c828dc6766aea07626c351053137ec73919ef9fe8cbaaa`。
- 全128配置时延表：`R54_PERFORMANCE.csv`；汇总：`SUMMARY.json`；原始证据：`evidence.tar.gz`及解包目录。
- 所有输入的生成脚本、种子、量化输入哈希、参考结果、源文件哈希、编译和msprof日志均已保存；二进制输入可由脚本重建。

**Case12是否满足N%128==64仍未知。** 若N为128的倍数，本版按设计不会改变Case12。先取得r54完整15点结果，确认Case12收益及Case8/11/15旧收益；然后再决定升级主线或进入原计划第三步B布局/NZ。r41没有被覆盖，r51/52不建议占用Judge提交次数。
'''
(OUT/'REPORT.md').write_text(report,encoding='utf-8')
readme=V/'v12_r54_README.md'
s=readme.read_text(encoding='utf-8').replace('完整检查记录及内存检查结果见实验报告。',
    '四个新kernel的全block memcheck已完成，未报告内存访问错误，但存在FFTS_BASE_ADDR未复位告警；这不是全域race/init/sync检查。完整记录见实验报告。')
readme.write_text(s,encoding='utf-8')
files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json']
(OUT/'SHA256SUMS.json').write_text(json.dumps({str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n')
print(json.dumps({'candidate':summary['candidate'],'correctness':checks['r54'],'sanitizer':san,'baseline_unchanged':manifest['accepted_sota'],'report':str(OUT/'REPORT.md')},ensure_ascii=False,indent=2))
