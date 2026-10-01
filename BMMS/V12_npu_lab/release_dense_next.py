from pathlib import Path
import json,hashlib,zipfile,statistics,shutil
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';d=r/'V12_npu_lab/results/dense_next_20260928';e=d/'evidence'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(d/'dense_next_evidence.zip') as z:
 assert z.testzip() is None
 inventory=json.loads(z.read('SHA256.json'))
 for name,value in inventory.items():
  assert not Path(name).is_absolute() and '..' not in Path(name).parts
  assert hashlib.sha256(z.read(name)).hexdigest()==value
 z.extractall(e)
s=json.loads((e/'results/dense_next_summary.json').read_text())
assert s['source_sha256']['r33']==sha(o/'v12_r33_shortk_prefetch_allpitch.asc')
assert s['source_sha256']['r30']==sha(o/'v12_baseline_r30.asc')
precision=[x for x in s['precision'] if x['file'].startswith('r33_final_')]
groups=sum(x['groups'] for x in precision);calls=sum(x['calls'] for x in precision)
assert groups==412 and calls==1236
s['verified_evidence_files']=len(inventory);dump(d/'SUMMARY.json',s)
for name in ['prepare_dense_next.py','accept_r30.py','prepare_r33.py','check_dense_next.py','check_r33_host.py','release_dense_next.py']:
 target=d/'local_reproduction'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(r/'V12_npu_lab'/name,target)
for name in ['dense_next_host.json','r33_host.json']:shutil.copyfile(r/'V12_npu_lab/results'/name,d/name)
def evrow(label,key):
 x=s['events'][key];return f"|{label}|{len(x['cases'])}|{x['median_reduction_pct']:.2f}%|{x['min_reduction_pct']:.2f}%～{x['max_reduction_pct']:.2f}%|"
evtable='\n'.join(evrow(a,b) for a,b in [('冻结候选后的新形状，首轮','holdout'),('相同新形状，独立复测','repeat'),('首批全部短K配置复测','all80'),('A/A控制','aa')])
public=s['public']['shortk_public']['summary'];gains=[100*(1-x['candidate_median_us']/x['baseline_median_us']) for x in public]
controls=[]
for label,key in [('11/12域及邻近回退','longk_control'),('Case8族','c8_control'),('Case15/Split-K族','split_control'),('其它旧路径','other_control')]:
 rows=s['public'][key]['summary'];diff=[x['candidate_median_us']-x['baseline_median_us'] for x in rows]
 controls.append(f'|{label}|{len(rows)}|{min(diff):+.2f}～{max(diff):+.2f}μs|')
ctrl='\n'.join(controls)
reverse=s['public'].get('unchanged_reverse',{}).get('summary',[])
smallreverse=s['public'].get('small_reverse',{}).get('summary',[])
reverse_text='\n'.join(f"- 旧R06回退样本{i}：反序复测总体中位数r30={x['baseline_median_us']:.2f}μs，r33={x['candidate_median_us']:.2f}μs，降幅{100*(1-x['candidate_median_us']/x['baseline_median_us']):.2f}%。" for i in [61,63] for x in reverse if x['case'][0]==i)
small_text='\n'.join(f"- 小形状{x['case'][2:5]}：反序复测r30={x['baseline_median_us']:.3f}μs，r33={x['candidate_median_us']:.3f}μs，差值{x['candidate_median_us']-x['baseline_median_us']:+.3f}μs。" for x in smallreverse if x['case'][0] in [0,2,3,8])
sample='\n'.join(f"|{'×'.join(map(str,x['case'][2:5]))} / {'T' if x['case'][6] else 'N'}{'T' if x['case'][7] else 'N'}|{x['baseline_median_us']:.2f}|{x['candidate_median_us']:.2f}|{100*(1-x['candidate_median_us']/x['baseline_median_us']):.2f}%|" for x in public if x['case'][0] in [0,8,24,64,72])
san=s['sanitizer'];santable='\n'.join(f"|{k}|{san[k]['actual_kernel_starts']}|{san[k]['errors']}|" for k in ['memcheck','racecheck','initcheck'])
report=f'''# v12_r33：将r30宏块预取扩展到短K大矩阵

当前已接受主线为r30；本轮交付r33供Judge测试。r31没有有效收益，r32由覆盖更完整的r33替代。所有本地形状均为自建，不能当作隐藏Case9/10的实测。

## 已确认线上基线

用户确认r30有效，15/15 Pass：11=97.09μs、12=115.12μs、8=46.78μs、15=11.37μs。两张图片内容和路径相同，只记录一次独立结果。r30源码冻结为v12_baseline_r30.asc，r19保留回退；Judge通过没有关闭原竞争/初始化告警。

## 排查、实验和取舍

1. r31合并L1→L0的LoadData调用，保持r30分块、K次序与预取。48组普通入口数值通过；18个计时配置中位降幅仅{s['screen']['r31']['median_reduction_pct']:.3f}%，没有有效收益，淘汰。地址模型检查10240种尾块/布局映射，合并前后相同；没有仅凭指令数减少认定加速。
2. r32为B1、M/N至少1024、1024≤K<1536的大矩阵增加宏块预取入口，复用r30设备实现。初筛32配置全部改善，中位{s['screen']['r32']['median_reduction_pct']:.2f}%，范围{s['screen']['r32']['min_reduction_pct']:.2f}%～{s['screen']['r32']['max_reduction_pct']:.2f}%。这是目前Case9/10证据所支持的域，没有使用隐藏case编号或数据内容分派。
3. r32最初保留64元素物理跨度条件。对不满足条件的16个合成配置直接调用同一内核，数值全部通过，耗时降幅1.33%～5.23%。r33因此去掉短K入口的这个性能门槛，保留原R06要求的M/N16对齐、K32对齐。没有放宽11/12原有入口。

LoadData映射使用[CANN9.0 LoadData2D文档](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_00169.html)的分形stride定义。所安装技能未包含其引用的code-gen参考文件；使用已有经过验证的CANN源码与官方API文档核对。本项目为独立Judge C ABI，沿用已有FP64参考、ACL设备事件和msprof公共入口harness，未另建ascend-kernel/PyTorch包。

## 最终代码范围

新增入口：FP16/BF16，B=1，1024≤M,N≤8192，1024≤K<1536，并满足原R06 Eligibility。实现直接调用bmms1230::Entry，原r30模块、planner和其它路径均保留。移除新增模块与一行入口，可逐字节恢复r30。

计算始终先完成整个K的FP32累加，再max N、sum M；不做近似，不缓存输入或结果。L1/L0A/L0B/L0C沿用r30；M=8192时显式UB分配164384字节，最终Max的repeat=128。192条任务链、19936个宏块、107156次装载的离散状态检查通过，不替代硬件同步检查。

## 性能结果

设备与前轮相同：Ascend910_9362、20 Cube、CANN9.0.0、dav-2201。编译全部结束后串行测量；同进程AB/BA，100次预热，每窗32次调用。正数表示1−候选/基线的耗时降幅，基线为r30在对应短K域走的原R06设备路径。

|设备事件测试|配置数|中位降幅|配置范围|
|---|---:|---:|---:|
{evtable}

冻结r33后的独立形状为2048×1536×1408、1168×3216×1120、5120×1280×1216、1104×4096×1472，均遍历4种布局和2种类型。两轮各8窗。80配置复测各6窗，包含M=8192、短K尾部、负数、零和不规则物理跨度。

公共run_kernel入口另以msprof task-time采集，每版2个独立进程、每例60次丢弃15次，A/B与B/A交替；核验实际kernel名和源码哈希。短K的24配置中位降幅{statistics.median(gains):.2f}%，范围{min(gains):.2f}%～{max(gains):.2f}%。下表为合成形状，单位μs，不能映射成Judge点号：

|M×N×K / 布局，FP16|r30基线|r33|降幅|
|---|---:|---:|---:|
{sample}

|旧路径回归集|配置数|r33−r30任务耗时范围|
|---|---:|---:|
{ctrl}

逐窗口数据完整保留。代码未改动的路径仍可能受独立进程计时与编译布局影响；不把源码保留解释为每个隐藏点绝对零退化。

初轮两个旧R06回退样本M1920/N8192/K3936（NT/TT）各窗口方向相反，聚合值分别慢34.39/37.97μs；小形状也有+0.12～0.16μs。为此追加每版4个进程的反序测试，结果如下；原始异常值没有删除：

{reverse_text}
{small_text}

小形状最初的两项+0.12/+0.16μs在复测中变为0/−0.01μs，没有重现同幅度退化。但大形状的多个窗口仍有较大波动，反序复测的两个回退样本聚合值仍略慢，不能据此证明不存在退化。它们不满足r30的物理跨度条件，两版均实际使用旧bmms11r2内核；不是新增短K入口。完整数据交给后续Judge验证，未以“旧代码未变”为由删除不利结果。

## 数值与插桩验证

最终r33普通入口{groups}组×3次={calls}次全部通过，最大误差/容差比{max(x['max_tolerance_ratio'] for x in precision):.6f}。输入实际量化到FP16/BF16，再用CPU FP64计算参考；阈值1e-4+1e-4×abs(ref)，每次输出先填NaN。复用已有测试，加上本轮短K和新独立数据，均为自建用例，非testcase-gen产出。覆盖新入口、长K、Case8族、Split-K、Native等旧路径。

全指令插桩执行4个新增域样本：M8192/N1024/K1024与M1040/N2064/K1056，各FP16/BF16。插桩运行数值通过，工具报告分别统计，不能以退出码0替代报告判读：

|检查|实际kernel运行数|ERROR报告数|
|---|---:|---:|
{santable}

原r30竞争、初始化及冗余同步告警仍未闭环。r33复用同一设备实现，不声称已解决这些问题；本轮也没有把告警直接归为误报。完整原始日志保留。

本轮memcheck另有{san['memcheck']['register_warnings']}条FFTS_BASE_ADDR未复位的寄存器警告。racecheck的8条ERROR均为连续MMAD的L0C RAW/WAW；没有观测到L1预取的新类型报告，但这不构成安全证明。没有将不同数量样本上的告警计数作安全性优劣比较。

## 提交建议与后续

只提交v12_r33_shortk_prefetch_allpitch.asc。目标是Case9/10，同时确认全部15点Pass，11/12保住97/115μs附近的新成果，8/15保住约46/11μs。真实shape仍未知，最终收益以Judge为准；r33尚不替换已接受r30。

本轮结论：减少LoadData指令数没有形成可测收益；复用宏块预取到短K域有跨形状收益；物理跨度差的收益较小但本轮样本仍为正。下一步先看9/10实际命中和收益，避免再次修改已经有效的11/12计划。

候选SHA256：`{s['source_sha256']['r33']}`。基线SHA256：`{s['source_sha256']['r30']}`。证据包CRC与{len(inventory)}个文件SHA256全部校验。
'''
(d/'REPORT.md').write_text(report,encoding='utf-8')
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version']=='v12_r30' and main['accepted_sha256']==s['source_sha256']['r30']
statuses={31:'Rejected locally: 0.013% screen median benefit; no meaningful gain',32:'Superseded by r33 with validated all-pitch short-K coverage',33:'Numerical/performance validated locally; Judge candidate; r30 remains accepted; sanitizer limitations retained'}
for v in [31,32,33]:
 p=o/f'v12_r{v}_manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m.update(status=statuses[v],npu_report='../V12_npu_lab/results/dense_next_20260928/REPORT.md');dump(p,m)
 main['candidates']=[x for x in main['candidates'] if x['version']!=m['version']]+[{k:m[k] for k in ['version','file','sha256','parent','status','npu_report']}]
 (o/f'v12_r{v}_README.md').write_text(f"# v12_r{v}\n\n{m['status']}\n\n[完整报告]({m['npu_report']})。当前基线为[v12_r30](v12_baseline_r30.asc)。\n",encoding='utf-8')
main.update(recommended_candidate='v12_r33_shortk_prefetch_allpitch.asc',next_action='Judge r33 all15: short-K Case9/10 gain and retention of r30 Case11/12, Case8 and Case15. Keep r30 accepted until feedback.')
dump(o/'MAINLINE.json',main)
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r30](v12_baseline_r30.asc)。下一次Judge候选：[r33](v12_r33_shortk_prefetch_allpitch.asc)，将宏块预取扩展到Case9/10所在短K域，保留11/12的r30路径。r31无收益，r32由r33替代。[完整本地报告](../V12_npu_lab/results/dense_next_20260928/REPORT.md)。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(o/'v12_r33_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in ['v12_r33_shortk_prefetch_allpitch.asc','v12_r33_manifest.json','v12_r33_README.md']:z.write(o/name,name)
 z.write(d/'REPORT.md','VALIDATION_REPORT.md')
with zipfile.ZipFile(o/'v12_r33_submission.zip') as z:assert z.testzip() is None
print('release',groups,calls,'sanitizer',san)
print('independent',s['events']['holdout']['median_reduction_pct'],s['events']['repeat']['median_reduction_pct'])
print('public',statistics.median(gains),min(gains),max(gains))
