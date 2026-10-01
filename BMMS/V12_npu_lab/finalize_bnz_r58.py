from pathlib import Path
import json,hashlib,statistics,csv,zipfile,tarfile
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/case12_bnz_20261001'
archive=out/'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='6c5e6b9a6b2e0036e3896504a30fe04473b07c593f4018c7844d27b6281244da'
with tarfile.open(archive) as t:t.extractall(out/'evidence',filter='data')
e=out/'evidence';baseline=v/'v12_baseline_r41.asc'
assert (e/'r41.asc').read_bytes()==baseline.read_bytes()
names={56:'v12_r56_case12_b_nz_prepack.asc',57:'v12_r57_case12_b_panel_nz.asc',58:'v12_r58_probe_case12_nstride_channels.asc'}
precision={}
for n,name in names.items():
 assert (v/name).read_bytes()==(e/f'r{n}.asc').read_bytes()
 rows=[json.loads(s) for s in (e/f'results/r{n}_correctness.jsonl').read_text().splitlines()]
 assert len(rows)==164 and all(x['pass'] and x['repeats']==3 for x in rows)
 precision[f'r{n}']=dict(configurations=164,calls=492,all_pass=True,max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rows))
def stats(xs):
 vals=[100*(1-x['candidate_median_us']/x['baseline_median_us']) for x in xs]
 return dict(configurations=len(xs),median_reduction_pct=statistics.median(vals),min_pct=min(vals),max_pct=max(vals),
             both_windows_faster=sum(all(b<a for a,b in zip(x['baseline_medians_us'],x['candidate_medians_us'])) for x in xs))
screens={};table=[]
for n in [56,57]:
 r=json.loads((e/f'results/r{n}_screen_summary.json').read_text())
 assert r['source_sha256'][f'r{n}']==hashlib.sha256((v/names[n]).read_bytes()).hexdigest()
 assert all(all(f'bmms12{n}_' in k for k in x['kernels']) for x in r['runs'] if x['version']==f'r{n}')
 screens[f'r{n}']={'all':stats(r['summary'])}
 for residue in [0,64]:screens[f'r{n}'][f'N_mod128_{residue}']=stats([x for x in r['summary'] if x['case'][3]%128==residue])
 for x in r['summary']:
  table.append(dict(version=f'r{n}',case=x['case'][0],N=x['case'][3],dtype=x['case'][5],TA=x['case'][6],baseline_us=x['baseline_median_us'],candidate_us=x['candidate_median_us'],reduction_pct=100*(1-x['candidate_median_us']/x['baseline_median_us'])))
labels={x['case']:x['groups'] for x in json.loads((out/'LABELS_R58.json').read_text())}
channel={0:[],1:[],2:[]};channel_times={0:[],1:[],2:[]};counts={0:0,1:0,2:0}
for tag in ['r58_calibration','r58_fallback']:
 r=json.loads((e/f'results/{tag}_summary.json').read_text())
 for x in r['summary']:
  group=labels[x['case'][0]];counts[group]+=1
  channel[group].extend(b/a for a,b in zip(x['baseline_medians_us'],x['candidate_medians_us']))
  channel_times[group].extend(x['candidate_medians_us'])
assert counts=={0:16,1:16,2:16}
assert min(channel[1])>15 and 7<min(channel[2])<=max(channel[2])<10
assert min(channel[0])>.8 and max(channel[0])<1.25
cal={str(g):dict(configurations=counts[g],windows=2,min_ratio=min(x),median_ratio=statistics.median(x),max_ratio=max(x),
    min_us=min(channel_times[g]),max_us=max(channel_times[g])) for g,x in channel.items()}
# Historical Judge one-group anchor used the same original r30 module.
def r30(s):return s[s.index('// BMMS1230_BEGIN'):s.index('// BMMS1230_END')]
assert r30((v/'v12_r40_probe_r37_unchanged_in_domain.asc').read_text())==r30(baseline.read_text())
summary=dict(baseline='v12_baseline_r41.asc',judge_r55='15/15Pass, Case12 114.51us: complete r54 guard MISS supported',
    synthetic_not_hidden=True,precision=precision,screen=screens,r58_channels=cal,
    decision='Reject r56/r57 as broad Case12 performance candidates; no promotion; deliver r58 diagnostic only',
    holdout_run=False,holdout_reason='Both broad candidates fail screening; do not promote a partial screen-selected subgroup',
    new_sanitizer_run=False,sanitizer_reason='No performance candidate accepted; r58 changes host dispatch only and inherits known r30 limitations',
    historical_single_group_anchor=dict(version='r40',case12_ms=1.42,r30_module_equal=True,limitation='Old nonpaired Judge observation, not a guaranteed current channel threshold'))
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/'SCREEN.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
sha=hashlib.sha256((v/names[58]).read_bytes()).hexdigest()
report=f'''# Case12：r55反馈后的B/NZ实验与r58诊断

## 结论

r55 Judge 15点全部Pass，Case12为114.51μs，没有校准过的压力信号，支持r54完整入口MISS。**主线继续保留r41**。这不单独证明N%128==0，也不能说r54新kernel实际执行但没有收益。

按既定第三方向完成两种B预打包实现。二者保持原r30分块、A路径、K累加顺序和consumer；完整计时包括打包、同步及矩阵计算，不只计Cube阶段。

|版本|改动|32组中位耗时变化|最差耗时变化|决定|
|--|--|--:|--:|--|
|r56|B一次打包成全局NZ，分段读入L1|增加{-screens['r56']['all']['median_reduction_pct']:.2f}%|增加{-screens['r56']['all']['min_pct']:.2f}%|不提交性能版|
|r57|B按K阶段和N宏块连续存放，一次DMA读入|增加{-screens['r57']['all']['median_reduction_pct']:.2f}%|增加{-screens['r57']['all']['min_pct']:.2f}%|不提交性能版|

两版各164组×3次精度通过。N%128==64且TA=true有局部正收益，但N%128==0配置回退明显；没有进行holdout，也没有把局部screen收益作为上线依据。增加B加载的敏感性不能直接证明一次性预打包一定更快。这些结果只否定本轮两种完整实现的泛化收益，不证明B路径再无优化空间。

## 代码与静态检查

- r56/r57各增加4个kernel，未命中条件时逐字保留r41。没有r54新增的N余数及AM256宏块整除门槛。
- r56全部32种N打包覆盖恰好一次，3,888个L1阶段数据与原始ND切片独立比较一致。r57同样覆盖，并验证未写入的N补齐区域从未被读取。
- B数据以raw uint16搬运，FP16/BF16均不做half算术重解释。
- r56 host遍历32,768组M/N/cores，512个资格成立的plan通过空间检查，UB最大149,856字节；r57仅增加最多N补齐量，UB不变。
- 两版使用完整CANN源码编译、同机串行A/B/B/A两个窗口；每窗30次、丢弃前5次，msprof kernel任务时间。实际kernel名确认新分支执行。
- 本轮没有新增sanitizer验收。没有选中的性能代码不建议提交，既有r30的FFTS/同步检查限制仍保留。

## r58：一次提交区分三个状态

完整文件：`v12_r58_probe_case12_nstride_channels.asc`，SHA256 `{sha}`。

r58只保留Case12已知元数据范围、原r30资格、dtype/transpose/pitch/family及r41未抢占等条件，不再附加原pM/pN状态或新AM256整除要求。

1. 原覆盖域内且N%128==0：用1个Cube组完成全部真实计算。
2. 原覆盖域内且N%128==64：用2个Cube组沿M分工完成全部真实计算。
3. 原覆盖域不成立：走原r41路径。

没有新增设备kernel，不跳过计算、不缓存答案、不复用旧输出。32,768组host状态审计了压力plan的M覆盖连续且不重叠、核数不越界以及原workspace容量足够。

本地164组×3次精度通过。48组入口校准，双窗口、每窗12次丢弃3次，结果如下：

|通道|配置数|r58/r41倍数范围|本地绝对时间范围|
|--|--:|--:|--:|
|N%128==0，单核|16|{cal['1']['min_ratio']:.2f}～{cal['1']['max_ratio']:.2f}|{cal['1']['min_us']/1000:.3f}～{cal['1']['max_us']/1000:.3f} ms|
|N%128==64，双核|16|{cal['2']['min_ratio']:.2f}～{cal['2']['max_ratio']:.2f}|{cal['2']['min_us']/1000:.3f}～{cal['2']['max_us']/1000:.3f} ms|
|域外fallback|16|{cal['0']['min_ratio']:.3f}～{cal['0']['max_ratio']:.3f}|各自基线附近|

上述是20 Cube环境的合成校准，**不是Judge固定阈值**。特别是历史r40曾测到Case12单组压力约1.42ms，r30代码已核实相同，说明不能强制要求Judge也慢16倍。旧值只能作辅助锚点，隐藏输入和运行条件仍需可比。收到截图后结合同期约114.5μs基线、旧单组压力和本地两档分离解读；Fail或处于模糊区间时不强行判定N余数。

若高档明确成立，后续优先研究N128对齐输入的直接producer路径，停止反复提交只有N64收益的代码；若低档明确成立，则N余数符合r54条件，转查核数/原plan/新宏块整除门槛；若仍约114.5μs，则应回查Case12范围和路由证据。

## 复现与文件

evidence.tar.gz含源码、构建与精度日志、全部profiler任务记录、测试种子及输入哈希。压缩包SHA256为`6c5e6b9a6b2e0036e3896504a30fe04473b07c593f4018c7844d27b6281244da`。完整15点反馈在`V12_results/2026-10-01_r55_feedback/`。

远端大文件下载曾出现SSH报文损坏，已改用128KiB分块传输；只有完整SHA256核验通过的压缩包才作为最终证据。所有NPU任务均已结束。现在只需提交r58诊断文件，r56/r57不作为冲榜候选。
'''
(out/'REPORT.md').write_text(report,encoding='utf-8')
for n in [56,57]:
 p=v/f'v12_r{n}_manifest.json';m=json.loads(p.read_text());m.update(status='Rejected as broad Case12 candidate after synthetic NPU screening; do not submit',
    numerical_validation=precision[f'r{n}'],screen=screens[f'r{n}'],holdout_run=False,new_sanitizer_run=False,npu_report='../V12_npu_lab/results/case12_bnz_20261001/REPORT.md');p.write_text(json.dumps(m,indent=2)+'\n')
 (v/f'v12_r{n}_README.md').write_text(f'''# v12_r{n}：本地实验，勿提交

完整编译及164组×3次精度通过。但32组筛选中位耗时增加{-screens[f'r{n}']['all']['median_reduction_pct']:.2f}%，未证明可推广收益，不升级r41主线。没有运行holdout或新增sanitizer。详细结果见[报告](../V12_npu_lab/results/case12_bnz_20261001/REPORT.md)。
''',encoding='utf-8')
p=v/'v12_r58_manifest.json';m=json.loads(p.read_text());m.update(status='Calibrated three-state diagnostic ready for one Judge15 run; not a performance candidate',numerical_validation=precision['r58'],calibration=cal,new_sanitizer_run=False,npu_report='../V12_npu_lab/results/case12_bnz_20261001/REPORT.md');p.write_text(json.dumps(m,indent=2)+'\n')
(v/'v12_r58_README.md').write_text(f'''# v12_r58：Case12原覆盖域与N余数一次诊断

**只提交 `v12_r58_probe_case12_nstride_channels.asc` 跑完整15点，回传标注r58。诊断版不能作为冲榜主线。**

r55的Case12为114.51μs，支持r54完整入口MISS。本版在原r30覆盖域内，以真实计算的1/2个Cube组区分N%128=0/64；域外保持r41。全部输出都正常计算。

完整编译及164组×3次精度通过。48组双窗口校准：单核{cal['1']['min_ratio']:.2f}～{cal['1']['max_ratio']:.2f}倍，双核{cal['2']['min_ratio']:.2f}～{cal['2']['max_ratio']:.2f}倍，域外{cal['0']['min_ratio']:.3f}～{cal['0']['max_ratio']:.3f}倍。这是本地校准而非Judge固定阈值；历史Case12单组压力约1.42ms可辅助判断。模糊时间或Fail不解码，收到截图再结合历史判断。

r56/r57的B/NZ性能方案均在本地筛选淘汰，不要提交。主线继续保留r41。r58没有新增设备kernel或sanitizer验收。

SHA256：`{sha}`。

[实验与校准报告](../V12_npu_lab/results/case12_bnz_20261001/REPORT.md)
''',encoding='utf-8')
main=json.loads((v/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_sota']=='v12_baseline_r41.asc'
for n in [56,57]:
 m2=json.loads((v/f'v12_r{n}_manifest.json').read_text())
 assert not any(x['version']==f'v12_r{n}' for x in main['candidates'])
 main['candidates'].append({k:m2[k] for k in ['version','parent','file','sha256','status','npu_report']})
main.update(active_candidate=None,active_diagnostic=dict(version='v12_r58',file=names[58],sha256=sha,status=m['status'],readme='v12_r58_README.md',purpose='Original r30 domain and N%128 residue, real 1/2-group compute channels'),
    latest_experiment_report=m['npu_report'],latest_diagnostic_report=m['npu_report'],next_action='Await single r58 Judge15 diagnostic; keep r41, r56/r57 rejected broadly')
(v/'MAINLINE.json').write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Keep local harness target inventory consistent with the recorded remote build.
(root/'V12_npu_lab/case12_k1_20261001/CMakeLists.txt').write_bytes((e/'CMakeLists.txt').read_bytes())
with zipfile.ZipFile(v/'v12_r58_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [v/names[58],v/'v12_r58_README.md',v/'v12_r58_manifest.json']:z.write(p,p.name)
hashes={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name not in ['SHA256SUMS.json','evidence.retry.tar.gz']}
(out/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n')
print(json.dumps(summary,indent=2))
