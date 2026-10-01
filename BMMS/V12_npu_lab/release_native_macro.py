from pathlib import Path
import json,hashlib,zipfile,shutil
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';d=r/'V12_npu_lab/results/native_macro_20260929';e=d/'evidence'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(d/'native_macro_evidence.zip') as z:
 assert z.testzip() is None
 inventory=json.loads(z.read('SHA256.json'))
 for name,value in inventory.items():
  assert not Path(name).is_absolute() and '..' not in Path(name).parts
  assert hashlib.sha256(z.read(name)).hexdigest()==value
 z.extractall(e)
s=json.loads((e/'results/native_macro_summary.json').read_text())
assert s['source_sha256']['r33']==sha(o/'v12_baseline_r33.asc')
names={'r34':'v12_r34_shortk_a_resident.asc','r35':'v12_r35_native_macro256.asc','r36':'v12_r36_native_macro128_pingpong.asc'}
for v,name in names.items():assert s['source_sha256'][v]==sha(o/name)
s['verified_evidence_files']=len(inventory);dump(d/'SUMMARY.json',s)
groups=sum(x['groups'] for x in s['precision']);calls=sum(x['calls'] for x in s['precision'])
assert groups==260 and calls==780
rows=[]
labels={'r34_screen':'r34 / 短K初筛','r35_screen':'r35 / Native初筛','r35_holdout':'r35 / Native留出','r36_screen':'r36 / Native初筛','r36_holdout':'r36 / Native留出','r36_guard':'r36 / 新N64中等分片'}
for key,x in s['events'].items():rows.append(f"|{labels[key]}|{len(x['cases'])}|{x['median_reduction_pct']:.2f}%|{x['min_reduction_pct']:.2f}%～{x['max_reduction_pct']:.2f}%|")
examples=[]
for key,ids in [('r34_screen',[0,8,26]),('r35_holdout',[16,24]),('r36_guard',[24,40,44,46])]:
 for x in s['events'][key]['cases']:
  if x['case'] not in ids:continue
  B,M,N,K,dt,ta,tb=x['dims'];layout=('T' if ta else 'N')+('T' if tb else 'N')
  examples.append(f"|{key.split('_')[0]}|{M}×{N}×{K}|{'FP16' if dt==1 else 'BF16'} / {layout}|{x['baseline_us']:.3f}|{x['candidate_us']:.3f}|{x['reduction_pct']:.2f}%|")
report='''# r34–r36 三轮实测：保持 r33 主线

2026-09-28 开始，2026-09-29 完成。当前主线仍为 **v12_baseline_r33.asc**。本轮没有获得适合全域提交的稳定收益，r34/r35/r36 均不推荐提交，未把某个样本的最好值当成整体改进。

所有形状均为自建数据，不是隐藏Case。对照标杆是在同一NPU实际运行的已接受r33对应设备内核，不是榜单右列最优耗时。沿用独立Judge C ABI、CPU FP64参考和ACL事件harness；没有转换成ascend-kernel/PyTorch包。本轮用例为自行设计，非testcase-gen产出。

## 三轮修改与结果

1. **r34 / 完整A面板驻留**：B1、M/N≥1024、1024≤K<1536，原R06资格、网格和归约；A完整K留在L1，B改为K1=128双缓冲，并保留跨N宏块的B预取。早期r02曾尝试类似驻留但有轻微回退；本轮区别是r33宏块和跨宏块预取基础。先前口头“没试过”已纠正。80组普通入口精度通过，初筛整体显著回退，淘汰。逻辑搬运减少不等于时延降低；不能把回退量全部归因于某条指令。
2. **r35 / Native 256行宏块**：范围与bmms49::Select相同，保持原Native分核；合并最多4个64行块为一轮MMAD/Fixpipe/通知，N48/64紧凑读取，保留完整M的ReduceSum。受L0A容量限制使用单槽，L0C也单槽。82组普通入口精度通过，但收益与回退混合，淘汰。
3. **r36 / Native 128行双槽**：合并最多2个64行块，L0A/B与L0C均双槽，保留下一宏块L1预取，原分核、完整M归约不变。82组普通入口精度通过，整域仍有明显回退。进一步在新N64中等分片形状M=2944/5008、K128、两dtype四布局上验证，16组均改善，但幅度较小。这个窄范围是从前一批结果形成的假说；没有据此修改最终提交分派，也没有将它声称为已冻结、充分验收的规则。

## 性能

设备与前轮相同：Ascend910_9362，20 Cube，CANN9.0.0，dav-2201。编译完成后串行使用NPU；先通过独立CPU FP64精度校验，再同进程AB/BA计时，100次预热、每窗口32次调用。r34为6窗，r35/r36初筛与留出8窗，r36新窄范围10窗。均保留全部窗口，不挑最快值。

这里的设备流耗时含launch间隙，使用预分配workspace；不包含公共入口内host分配/同步/释放，不等于Judge计时。本轮未执行最终公共入口profiler、A/A复测或sanitizer，因为未通过性能晋升门槛。

正数为耗时降低，负数为变慢：

|实验|配置数|中位降幅|范围|
|---|---:|---:|---:|
'''+'\n'.join(rows)+'''

抽样绝对计时（μs，其余见SUMMARY.json）：

|候选|M×N×K|类型/布局|r33标杆|候选|耗时降低|
|---|---|---|---:|---:|---:|
'''+'\n'.join(examples)+f'''

## 正确性与验证边界

累计 **{groups} 个版本×配置组合、{calls} 次普通入口调用全部通过**，不是{groups}个互不重复形状。r34 80×3，r35 82×3，r36 (82+16)×3。输入先量化至实际FP16/BF16，再用CPU FP64执行matmul/max/sum参考；容差为1e-4+1e-4×abs(reference)，每次调用前输出填NaN。最大误差/容差比为{max(x['max_tolerance_ratio'] for x in s['precision']):.8f}。

- r34地址模型检查455040个NZ索引，192条M行流水、1664宏块、17056次B载入；L1最大516096字节。
- r35/r36离散分片模型各覆盖714944个M分片、121385536个真实行归属；r36另验证129条L0/C生命周期链。模型不是硬件异步时序证明。
- 每个新模块和一条入口移除后，可逐字节恢复r33；完整r33文件哈希未变。r34没有合入r35，r35没有合入r36。
- 本轮三个实验都完成真实CANN编译与NPU数值/初筛；没有执行最终全域回归或内存、竞争、初始化检测。准备的validate_r35/r36脚本未运行。历史r33的竞争/初始化告警仍未闭环，不能声称sanitizer通过。
- 独立用例生成首次未加载CANN环境，torch_npu自动加载因libhccl.so缺失退出；加载原set_env.sh后生成成功。未安装或修改环境，失败日志保留。

## 结论与下一方向

1. 9/10的A驻留在r33流水下仍无整体收益；不继续凭A字节量估算加速。
2. Native减少MMAD/通知数量也没有换来普遍收益，说明不能仅以指令条数判断关键路径；N64部分中等分片仅0.5%～2.41%的收益，不足以推荐未知Case13全域替换。精确Case13的N及M分片仍未知。
3. r33继续作为唯一已接受主线，9–12、8和15的线上成果不被本轮失败实验替换。
4. **下一优先项为Case8的NZ生产者跨宏块预取**。源码bmms1219::NzProducer::Macro目前每个宏块都从LoadStage(...,0,slot0)重新启动，未继承r30/r33已验证的跨宏块首段预取。下一轮应保持PackInputs、原planner、padding/尾块消费者、四微块MMAD布局不变，只迁移预取及其事件生命周期，然后用现有Case8独立集测完整pack+compute路径。这个方向尚未实现或验证，不能预报收益。
5. Case6 route仍缺可靠证据，暂不根据约14μs猜shape或盲写专用kernel。

本輪遵循性能优化技能的最多三轮筛选；不把未通过晋升门槛的源码包装为冲榜成果。证据包CRC及{len(inventory)}个文件SHA256已核验；源码、构建日志、输入manifest/种子/哈希、原始事件数据全部归档。
'''
(d/'REPORT.md').write_text(report,encoding='utf-8')
for v in names:
 p=o/f'v12_{v}_manifest.json';j=json.loads(p.read_text());j['status']='not recommended; no robust broad-domain screening benefit'
 j['report']='../V12_npu_lab/results/native_macro_20260929/REPORT.md';dump(p,j)
 (o/f'v12_{v}_README.md').write_text(f'# v12_{v}：本地实验，未采用\n\n当前主线保持r33；不推荐提交本版。[三轮实测报告](../V12_npu_lab/results/native_macro_20260929/REPORT.md)。\n',encoding='utf-8')
main=o/'MAINLINE.json';j=json.loads(main.read_text());assert j['accepted_sota']=='v12_baseline_r33.asc'
for v,name in names.items():
 j['candidates']=[x for x in j['candidates'] if x['version']!='v12_'+v]
 j['candidates'].append(dict(version='v12_'+v,file=name,parent='v12_baseline_r33.asc',sha256=sha(o/name),status='rejected for promotion after synthetic NPU screening',npu_report='../V12_npu_lab/results/native_macro_20260929/REPORT.md'))
j['recommended_candidate']=None;j['next_action']='Keep r33. Next optimization priority: Case8 bmms1219 NZ cross-macro L1 prefetch, preserving packing/planner/tails; no implementation yet. Case6 route remains unknown.'
j['latest_experiment_report']='../V12_npu_lab/results/native_macro_20260929/REPORT.md';dump(main,j)
p=o/'README.md';t=p.read_text(encoding='utf-8');note='\n2026-09-29：r34–r36完成三轮NPU筛选，未获可推荐的整体收益，主线仍为r33。[本轮报告](../V12_npu_lab/results/native_macro_20260929/REPORT.md)。下一优先方向是Case8的NZ跨宏块预取。\n'
idx=t.index('\n');p.write_text(t[:idx+1]+note+t[idx+1:],encoding='utf-8')
lr=d/'local_reproduction';lr.mkdir(exist_ok=True)
for v in names:
 for name in [f'prepare_{v}.py',f'check_{v}_host.py']:
  shutil.copyfile(r/'V12_npu_lab'/name,lr/name)
 shutil.copyfile(r/f'V12_npu_lab/results/{v}_host.json',d/f'{v}_host.json')
shutil.copyfile(Path(__file__),lr/Path(__file__).name)
print(json.dumps(dict(baseline_unchanged=True,precision_groups=groups,precision_calls=calls,verified_files=len(inventory),report=str(d/'REPORT.md'))))
