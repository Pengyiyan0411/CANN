from pathlib import Path
import json,hashlib,statistics,zipfile,re,shutil
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';d=r/'V12_npu_lab/results/dense_pipeline_20260928'
s=json.loads((d/'SUMMARY.json').read_text(encoding='utf-8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert s['candidate_sha256']==sha(o/'v12_r30_dense_macro_prefetch.asc')
assert all(c['improvement_pct']>0 for k in ['holdout','holdout_repeat','balanced'] for c in s['events'][k]['cases'])
assert s['sanitizer']['memcheck']['error_reports']==0
assert s['sanitizer']['racecheck']['error_reports']==4 and s['sanitizer']['initcheck']['error_reports']==3310
checks=sum(x['cases'] for x in s['precision'] if x['version']=='r30');calls=sum(x['calls'] for x in s['precision'] if x['version']=='r30')
assert (checks,calls)==(372,1116)
screen='\n'.join(f"|{x['version']}|{x['median_improvement_pct']:.2f}%|{x['min_improvement_pct']:.2f}%～{x['max_improvement_pct']:.2f}%|" for x in s['screen'])
ind='\n'.join(f"|{name}|{len(s['events'][key]['cases'])}|{s['events'][key]['median_improvement_pct']:.2f}%|{s['events'][key]['min_improvement_pct']:.2f}%～{s['events'][key]['max_improvement_pct']:.2f}%|" for key,name in [('holdout','独立形状首轮'),('holdout_repeat','独立形状复测'),('balanced','新形状×全部布局×两种类型')])
ctl=[]
for key,label in [('c8_control','Case8族'),('split_control','Case15/Split-K族'),('c910_control','Case9/10范围'),('other_control','小形状、Native等')]:
 rows=s['public'][f'r30_{key}_summary.json'];dd=[x['candidate_median_us']-x['baseline_median_us'] for x in rows]
 ctl.append(f'|{label}|{len(rows)}|{min(dd):+.2f}～{max(dd):+.2f}μs|')
control='\n'.join(ctl)
bal=s['events']['balanced']['cases']
medshort=statistics.median(x['improvement_pct'] for x in bal[:8]);medlong=statistics.median(x['improvement_pct'] for x in bal[8:])
report=f'''# v12_r30：跨宏块预取的实测结果

本轮可交付候选为 **v12_r30_dense_macro_prefetch.asc**，供下一次Judge全15点测试。**已接受主线仍是r19**，不以合成测试替代隐藏点评分。r28/r29淘汰，不建议提交。r30数值与性能验证通过，但竞争、初始化和同步冗余报告尚未完全闭环，不能称为完整sanitizer通过。

**依据与改动**

r24已确认11/12走R06且物理跨度条件为 `(!ta || M%64==0) && ((tb?K:N)%64==0)`。仍不知道精确shape和布局。本轮全部样本都是自建数据。

先采集r19/r26的PipeUtilization。以M1536/N4096/K1664、FP16 NN为例：r26将标量忙碌时间85.84→53.45μs，Fixpipe 12.57→8.27μs，但MAC约78μs、MTE2约72μs基本不变，task-time只从125.42降至123.37μs。各流水可重叠，忙碌时间不能相加成关键路径。

r28尝试128×128、K0=128/K1=512，增加A重复搬运，实测MTE2上升至108.95μs，整体退化。r29尝试256×128、K0=64/K1=256并合并LoadData；部分配置微增益，大尾块明显退化。LoadData的srcStride/dstGap按[CANN 9.0接口定义](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_00169.html)使用512字节分形单位，并做地址模型校验。

r30恢复128×256、K0=64/K1=256及原R06 planner，在当前宏块最后一个K1段计算期间，向另一个已释放L1槽预取下一宏块的首段。下一宏块接管对应READY；任务结束排空标志。保留r26完整宏块MMAD/写回/消费者，并给最终Max使用显式完整向量与尾部掩码。完整K的FP32累加之后才max N、sum M；没有输入缓存、答案缓存或近似计算。

r30同一采样点的task-time为118.71μs，MAC77.89μs、MTE2 71.92μs。K3072的NN样本208.46→202.06μs。这与减少宏块交界等待的设计一致；没有把流水占比解释为严格的关键路径测量。

作用域：FP16/BF16，B1、1024≤M<2048、2048≤N≤8192、1536≤K<4096，且原R06 eligibility与上述物理跨度条件成立。范围外沿用r19分派。删除新增模块和一行入口即可逐字节恢复r19。显式L1/L0A/L0B/L0C容量为384/32/64/128KiB，AIV显式缓冲区最大90464字节；workspace与原计划相同。

**计时结果**

设备Ascend910_9362、20 Cube、CANN9.0.0、dav-2201。编译结束后串行测试。降幅=1−候选/基线，负值为退化。设备事件是同进程AB/BA、100次预热、每窗32次调用，不含公共入口分配/同步的host时间。

|初筛版本，18配置×6窗|耗时降幅中位数|各配置范围|
|---|---:|---:|
{screen}

|冻结r30后的复验|配置数|降幅中位数|各配置范围|
|---|---:|---:|---:|
{ind}

两轮独立形状各8窗；新增双类型样本各10窗。新样本形状为1344×3136×1728和1728×6208×3392，每个覆盖NN/NT/TN/TT及FP16/BF16：较短K组中位降幅{medshort:.2f}%，较长K组仅{medlong:.2f}%。收益并非所有长K都一样；Case12区间样本更值得期待，Case11仍应看实际反馈。A/A对照中位降幅{s['events']['aa']['median_improvement_pct']:.3f}%。

另以公共run_kernel入口进行轻量task-time profiler交替进程测试，每版2进程、每例60次丢弃15次，核验真实kernel名和源码哈希。命中的样本保留正收益；域外仍使用原kernel。

|旧路径控制|配置数|r30−r19 task-time差值|
|---|---:|---:|
{control}

域外M1920/N8192/K3936的NT/TT在首轮一个窗口分别变慢约6%/11%，另一个窗口基本持平。追加6配置、每版4进程的反序复测后，两版都出现明显窗口波动；这两个域外点的总体中位数r30分别快0.83%/0.92%，没有重现稳定退化方向。原始异常窗口完整保留，未删除或称其绝对无风险。小形状控制也有+0.13μs、Native有+0.26μs等变化，不能宣称所有隐藏点绝无退化。

**数值和检查边界**

最终源码372组×3次，共1116次普通入口数值检查全部通过。包括原合成集、11/12初筛和独立集、新双类型集、Case8、Split-K及其他路径。FP16/BF16量化输入由CPU FP64计算参考，阈值1e-4+1e-4×abs(ref)，每次输出先填NaN。最大误差/容差比为0.01250。覆盖零、全负、动态范围、相同列与M/N/K尾部。

host状态模型检查960条任务链、99680个宏块、1133860次L1装载，验证奇偶K段、尾块、跨行预取以及任务末尾标志排空。它不模拟真实硬件时序，不能代替racecheck。

相同M1040/N2064/K1600、NT、FP16/BF16两例，全指令插桩构建，两版各项实际执行且数值均通过。退出码均为0，但工具报告必须单独判读：

|ERROR报告数|r19|r30|
|---|---:|---:|
|memcheck|192|0|
|racecheck|16|4|
|initcheck|3694|3310|

r30的4条竞争报告均为连续MMAD的L0C RAW/WAW；未发现新增L1预取的竞争报告。initcheck仍在环缓冲读取和后续计算等处报告未初始化。r30 synccheck为0条ERROR、496条WARNING，主要为AIV的冗余wait_flag。未将这些报告认定为误报或通过；报告数下降也不等于安全性定量提升。官方工具说明强调初始化检查依赖竞争问题先解决，见[msSanitizer用户指南](https://github.com/Ascend/mssanitizer/blob/master/docs/en/user_guide/mssanitizer_user_guide.md)。

**交付与下一步**

只把r30作为待Judge验证的性能候选，r19继续作为回退基线。下一次对比11/12，并检查全部15点Pass、Case8约46μs和Case15约11μs的成果。若隐藏点改善也被噪声淹没，不晋升；下一轮不继续微调K1，优先处理已有竞争/初始化报告的最小复现，或转向另一个有明确瓶颈的点。

最终SHA256：`{s['candidate_sha256']}`。初筛早期r30在加入显式Max尾部前的源码与结果单独保存，最终所有独立复验均对应以上哈希。

`dense_pipeline_evidence.zip`的CRC和283个文件SHA256均已校验；包含源码、构建日志、数据生成元信息、全部原始计时、profile CSV和插桩日志。SUMMARY.json保留逐配置数据。主线r19哈希保持`27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021`。
'''
(d/'REPORT.md').write_text(report,encoding='utf-8')
for name in ['prepare_r28.py','prepare_r29.py','prepare_r30.py','check_square_host.py','check_r29_host.py','check_r30_host.py','prepare_dense_followup.py','finalize_dense_pipeline.py','release_r30.py']:
 dst=d/'local_reproduction'/name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(r/'V12_npu_lab'/name,dst)
for name in ['r28_host.json','r29_host.json','r30_host.json']:shutil.copyfile(r/'V12_npu_lab/results'/name,d/name)
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version']=='v12_r19'
for v in [28,29,30]:
 p=o/f'v12_r{v}_manifest.json';m=json.loads(p.read_text(encoding='utf-8'))
 if v==30:m['status']='Performance/precision validated locally; Judge trial candidate; race/init/sync warnings unresolved; r19 remains accepted'
 m['npu_report']='../V12_npu_lab/results/dense_pipeline_20260928/REPORT.md';dump(p,m)
 item={k:m[k] for k in ['version','file','sha256','parent','status','npu_report']}
 main['candidates']=[x for x in main['candidates'] if x['version']!=m['version']]+[item]
 (o/f'v12_r{v}_README.md').write_text(f"# v12_r{v}\n\n{m['status']}\n\n[完整实测报告]({m['npu_report']})。r19保持主线。\n",encoding='utf-8')
main.update(recommended_candidate='v12_r30_dense_macro_prefetch.asc',next_action='Judge r30 all15 with special attention to11/12 and retention of8/15; keep r19 accepted. Race/init/sync reports remain open.')
dump(o/'MAINLINE.json',main)
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r19](v12_baseline_r19.asc)。下一次Judge候选：[r30](v12_r30_dense_macro_prefetch.asc)，跨宏块预取，独立合成形状复测中位降幅约3.9%，372组数值全通过；竞争/初始化/同步冗余报告仍未闭环。r28/r29淘汰。[完整报告](../V12_npu_lab/results/dense_pipeline_20260928/REPORT.md)。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(o/'v12_r30_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [o/'v12_r30_dense_macro_prefetch.asc',o/'v12_r30_README.md',o/'v12_r30_manifest.json']:z.write(p,p.name)
 z.write(d/'REPORT.md','VALIDATION_REPORT.md')
with zipfile.ZipFile(o/'v12_r30_submission.zip') as z:assert z.testzip() is None
assert sha(o/'v12_baseline_r19.asc')==main['accepted_sha256']
print('RELEASED r30 trial package; r19 unchanged. No running jobs are required for this artifact.')
