from pathlib import Path
import argparse,csv,hashlib,json,zipfile
p=argparse.ArgumentParser();p.add_argument('--winner',choices=['none','r26','r27'],default='none');args=p.parse_args()
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';d=r/'V12_npu_lab/results/dense_macro_20260928';e=d/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with zipfile.ZipFile(d/'dense_macro_evidence.zip') as z:
 assert z.testzip() is None
 inv=json.loads(z.read('INVENTORY_SHA256.json'))
 for name,digest in inv.items():
  assert not Path(name).is_absolute() and '..' not in Path(name).parts
  assert hashlib.sha256(z.read(name)).hexdigest()==digest
 z.extractall(e)
assert sha(e/'r19.asc')==sha(o/'v12_baseline_r19.asc')=='27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021'
records=[]
for v in [25,26,27]:
 manifest=json.loads((o/f'v12_r{v}_manifest.json').read_text(encoding='utf-8'))
 assert manifest['sha256']==sha(o/manifest['file'])==sha(e/f'r{v}.asc')
 checks=[]
 for f in sorted(e.glob(f'results/r{v}_*_correctness.jsonl')):
  data=[json.loads(x) for x in f.read_text().splitlines()]
  assert data and all(x['pass'] for x in data)
  checks.append(dict(file=f.name,cases=len(data),calls=sum(x['repeats'] for x in data),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in data)))
 screen=json.loads((e/f'results/r{v}_screen_analysis.json').read_text())
 record=dict(version=f'r{v}',source=manifest['file'],sha256=manifest['sha256'],precision=checks,screen=screen)
 for name in ['holdout','holdout_repeat']:
  f=e/f'results/r{v}_{name}_analysis.json'
  if f.exists():record[name]=json.loads(f.read_text())
 for f in e.glob(f'results/r{v}_*_summary.json'):
  q=json.loads(f.read_text());assert q['source_sha256'][f'r{v}']==manifest['sha256']
  record.setdefault('public_profiles',{})[f.name]=q['summary']
 if f'r{v}'==args.winner:
  assert 'holdout' in record and 'holdout_repeat' in record and record.get('public_profiles')
  assert sum(x['cases'] for x in checks)==356
  status=e/f'results/r{v}_sanitizer_status.txt';assert status.exists()
  record['sanitizer_status']=status.read_text()
 records.append(record)
summary=dict(accepted='r19',recommended_candidate=args.winner,screen_synthetic_not_hidden=True,records=records,
             verified_evidence_files=len(inv),feedback='../V12_results/2026-09-28_r24_feedback/RESULTS.json')
dump(d/'SUMMARY.json',summary)
table='\n'.join(f"|{x['version']}|{sum(a['cases'] for a in x['precision'])} / {sum(a['calls'] for a in x['precision'])}|{x['screen']['median_improvement_pct']:.2f}%|{x['screen']['min_improvement_pct']:.2f}%～{x['screen']['max_improvement_pct']:.2f}%|" for x in records)
decision=('三轮初筛均未获得足够大的整体收益；不推荐提交这三份实验版本，r19保持主线。' if args.winner=='none' else f"推荐 {args.winner} 进行 Judge 全15点验证；r19仍为已接受主线，待真实测评后再晋升。")
report=f'''# r24 结论与对齐跨度 R06 的三轮实验

## 确认的事实

r24 全15点 Pass，Case11 显示1.16ms、Case12显示1.50ms；结合r23正常通道101.79/123.57μs，完整互补条件明确命中。按前序唯一候选推定源码归属，截图无平台哈希。

两点满足原r22 Eligible / ValidPlan / 分配条件且 Prefer=false。物理跨度约束为 `(!ta || M%64==0) && ((tb?K:N)%64==0)`。这不等于M/N/K全部64对齐，也未确定具体形状和布局。覆盖探针结束。

## 本轮实现与隔离

- r25：从r19派生，采用早期r06的完整宏块MMAD布局，将四次Fixpipe写回合成一次128×256 ND宏块写回；消费者对应修改GM源行距。
- r26：在r25结构上，每个AIV一次读取半宏块，将256列通过三次64列Max及WholeReduceMax归约，保持完整K后maxN再sumM。
- r27：在r26结构上将K1从256调为320，继续使用L1/L0双缓冲；K0=64及FP32完整K累加顺序不变。L1为491520字节，L0A/B/C分别为32/64/128KiB，显式AIV UB峰值约90464字节。

三版都保持原R06任务planner，并只覆盖r24确认的对齐跨度区域。没有放开NZ门槛，没有输入/答案缓存。删除新增模块与一行入口即可逐字节恢复r19；Case8/15等旧路径实现保留。

整宏块写回按 [CANN 9.0 Fixpipe参数](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0251.html) 使用源NZ行距ar、目标ND行距BN；参数检查不能替代实际设备验证。

## 测试结果

设备 Ascend910_9362 / CANN 9.0.0。三版完整编译通过，先数值验证后计时。初筛为18组对齐跨度合成配置、6个交替AB/BA窗口、每窗32次设备流调用。基线是r19；这不是隐藏11/12的测评耗时，也不包含Judge未知的host计时范围。改善百分比=1−候选/基线，负值表示变慢。

|版本|数值组数 / 调用数，全通过|初筛中位降幅|初筛各配置降幅范围|
|---|---:|---:|---:|
{table}

数值用实际FP16/BF16量化输入的CPU FP64参考，阈值1e-4+1e-4×abs(ref)。新增8组对齐物理跨度且M/N双尾块的零、全负、动态范围和相同列用例。另用索引模型穷举256个宏块尾部/消费者组合，检查2506752个实际单元的写入/读取与负值max结果；模型不宣称模拟硬件同步或精度。

## 决策

{decision}

从r25/r26对照可见，当前合成族仅合并MMAD/写回和输出读取，整体改善有限，不能据此声称已找到隐藏11/12的主瓶颈。r27单独改变输入分块，其效果见原始数据。下一阶段应取得MTE1/MTE2/Cube各流水耗时，再围绕输入搬运与Cube供数设计改动；无需重新做覆盖探针。

不把这轮合成结果当作榜单成绩，也不以小幅改善保证隐藏点提升。未推荐版本只完成本轮初筛与相关数值验证；不声称已经通过全域回归或完整sanitizer。历史race/init检测问题仍保留。

全部源码、生成脚本、数据集元信息、事件原始JSONL和日志在evidence目录；ZIP CRC及{len(inv)}个文件SHA256已核验。详细分配置数据见SUMMARY.json。
'''
if args.winner!='none':
 selected=next(x for x in records if x['version']==args.winner)
 report+='\n## 候选独立复验\n\n'+json.dumps({k:selected[k] for k in ['version','holdout','holdout_repeat','sanitizer_status']},ensure_ascii=False,indent=2)+'\n'
(d/'REPORT.md').write_text(report,encoding='utf-8')
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version']=='v12_r19'
for record in records:
 version='v12_'+record['version'];status=('locally validated; Judge pending' if record['version']==args.winner else 'experimental; insufficient overall screening benefit; not recommended or promoted')
 item=dict(version=version,file=record['source'],sha256=record['sha256'],parent='v12_baseline_r19.asc',status=status,npu_report='../V12_npu_lab/results/dense_macro_20260928/REPORT.md')
 main['candidates']=[c for c in main['candidates'] if c['version']!=version]+[item]
 p=o/f'{version}_manifest.json';q=json.loads(p.read_text(encoding='utf-8'));q.update(status=status,npu_report=item['npu_report']);dump(p,q)
 (o/f'{version}_README.md').write_text(f"# {version}\n\n{status}\n\n主线保持r19。本版实验及验证结果见[报告](../V12_npu_lab/results/dense_macro_20260928/REPORT.md)。\n",encoding='utf-8')
main.update(recommended_candidate=None if args.winner=='none' else next(x['source'] for x in records if x['version']==args.winner),
 next_action='Coverage resolved. Preserve r19. Profile aligned R06 input/Cube pipeline before another algorithm round.' if args.winner=='none' else f'Judge {args.winner} all15; r19 remains accepted')
dump(o/'MAINLINE.json',main)
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r19](v12_baseline_r19.asc)。r24确认11/12均命中互补守卫，覆盖诊断结束。'+decision+' [本轮实验报告](../V12_npu_lab/results/dense_macro_20260928/REPORT.md)。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
p=o/'v12_r24_README.md';t=p.read_text(encoding='utf-8');notice='> Judge反馈：11=1.16ms、12=1.50ms，两点均HIT，全部Pass。覆盖诊断已结束；以下为提交前说明。\n\n'
if not t.startswith(notice):p.write_text(notice+t,encoding='utf-8')
if args.winner!='none':
 record=next(x for x in records if x['version']==args.winner)
 with zipfile.ZipFile(o/f'v12_{args.winner}_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in [o/record['source'],o/f'v12_{args.winner}_README.md',o/f'v12_{args.winner}_manifest.json']:z.write(p,p.name)
print(table);print(decision)
