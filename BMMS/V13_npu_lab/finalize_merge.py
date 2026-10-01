from pathlib import Path
import json,hashlib,shutil,tarfile
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V13';lab=root/'V13_npu_lab/c12_merge_20261001'
r=json.loads((lab/'results/VALIDATION.json').read_text());shutil.copyfile(lab/'results/VALIDATION.json',v/'VALIDATION.json')
e=json.loads((v/'evidence/evidence_manifest.json').read_text());assert hashlib.sha256((v/'evidence/evidence.tar.gz').read_bytes()).hexdigest()==e['sha256']
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in v.glob('*.asc')}
assert hashes['v13_r1_baseline_r72.asc']=='7a1c3efec19d4907ae6f1b88a0bb4acbbebfc722555574cd4e8c1b507c0bee6c'
src=(v/'v13_r2_case12_o10.asc').read_bytes().decode();mod=(lab/'c12_module.asc').read_bytes().decode()
hook='    if(bmms12opt::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert src.replace(mod+'\n\n','').replace(hook,'').encode()==(v/'v13_r1_baseline_r72.asc').read_bytes()
assert 'qN' not in mod and 'Strong timing encoder' not in mod
lines=['# V13 r2 本地验证报告','',
'最终提交：`v13_r2_case12_o10.asc`。CANN 9.0 / dav-2201 完整工程编译及链接成功。',
'远端：`/home/developer/bmms_v13_c12_20261001`，Ascend 910，20 AIC / 40 AIV。',
'', '## 精度', '',
'共 93 个合成配置、279 次调用：**92 通过，1 失败**（98.92%）。55 个大矩阵配置与 r1 逐项比较，记录的最大绝对误差全部相同；未发现合并新增的精度失败。',
'', '| 类别 | 配置数 | 结果 |','|---|---:|---|',
'| 入口内 N=4096..6080，步长64 | 32 | 全部通过 |',
'| 特殊值及负值尾块 | 9 | 8 通过，K 完全抵消失败 |',
'| dtype/layout/shape 入口失配 | 11 | 全部通过 |',
'| 其他大矩阵控制 | 3 | 全部通过 |',
'| 小点回归 | 38 | 全部通过 |','',
'标杆：实际 FP16/BF16 量化输入，以 CPU FP64 计算矩阵乘、N 维 max、M 维 sum。阈值 `abs_error <= 1e-4 + 1e-4*abs(reference)`，没有为通过测试而放宽。通过配置中最大的误差/阈值比为 '+str(r['precision']['max_tolerance_ratio_pass'])+'。','',
'失败配置 40037：BF16 TN，(B,M,N,K)=(1,1280,4096,1536)，A 的后半 K 复制前半，B 的后半 K 取前半相反数。FP64 输出约 4.44e-16；r1 与 r2 三次均得到相同的 0.00234625582，超过近零阈值约 23.46 倍。这支持“已有长 K 累加舍入经 max/sum 放大”的解释；没有进一步逐 MMAD 插桩，故不声称已证明全部数值根因。保留失败，不将其计为通过，也不把源码一致当作任意输入精度保证。','',
'## 配对性能', '',
'使用串行 A/B/B/A，每个版本两个独立窗口，各配置100次、丢弃前20次。数值为 msprof kernel task duration 的窗口中位数，再取跨窗口中位数；不是 host wall time。合成数据不能当作 Judge 隐藏输入结果。','',
'| B,M,N,K；BF16 TN | r1 μs | r2 μs | 耗时减少 |','|---|---:|---:|---:|']
for s in r['performance']['c12']['summary']:
    _,B,M,N,K,*_=s['case'];a=s['baseline_median_us'];b=s['candidate_median_us']
    lines.append(f'| {B},{M},{N},{K} | {a:.3f} | {b:.3f} | {(1-b/a)*100:.2f}% |')
lines += ['',
'Profiler 已确认：前七个配置，r1 实际执行 `bmms1230_b16_tn`，r2 执行 `bmms12opt_b16_tn`；后三个大矩阵控制的 kernel 归属不变。',
'',
'**重要边界：本地 N=4096 未复现明显收益，N=4160 与6080分别约14.70%和16.20%。** 用户确认线上分支约20 μs收益，因此本次仍合并其有效路线；不据此否定线上结果，也不拿其他 N 的本地收益冒充真实 Case12 收益。保留原入口的32个N，不加入 exact-N 限制。','',
'小点首轮38配置总体中位变化约 -0.18%；5个配置出现超过3%的小幅回退，绝对量约数十到190ns。针对这5个与3个控制点补做每版本3窗口、100次/窗口的独立复核：8个配置中位耗时减少0.30%，最差0.00%，没有复现回退。结合小点源码逐字节不变，目前没有证据表明合并损失了r72收益；实际隐藏点仍须Judge确认。','',
'## 内存、竞争与同步检测', '',
'针对新增模块构建 sanitizer 版本，producer/consumer 模块文本与提交一致；仅最小化 host 依赖。另对 r1 的旧 r30 模块做相同检测，以区分已有报告。各检查确实运行了目标kernel并通过该次输出校验，但进程返回0不代表没有工具错误。','',
'| 检查，精确形状 | r1 旧路线 | r2 新路线 | 解读 |','|---|---|---|---|',
'| memcheck | 0错误，60警告 | 0错误，60警告 | FFTS_BASE_ADDR未复位警告；未报越界 |',
'| racecheck | 2错误 | 2错误 | 同类L0C MMAD RAW/WAW潜在竞争报告 |',
'| initcheck | 602错误 | 604错误 | ring/partial跨核读及相关读的未初始化报告；新路线多两个N分片合并读 |',
'| synccheck | 0错误，564警告 | 0错误，564警告 | redundant wait_flag |',
'| N=4160尾块 memcheck | 未测 | 0错误，60警告 | 同类寄存器警告 |','',
'上述 race/init 报告**尚未排除，也未证明为误报**。旧版出现同类问题，只能说明它们并非本次才出现的新类别，不能替代修复或认证。故本次代码是保留已获线上反馈路线的性能合并候选，不标记为“全域精度/全套sanitizer已通过”。','',
'## 交付与复现','',
'- 原始输入摘要、模块diff、探针移除diff：`evidence/`。',
'- 本地用例生成与测试工程：`../V13_npu_lab/c12_merge_20261001/`。',
'- 可复现数据种子、输入哈希、precision JSONL、每个profile窗口、原始op_summary CSV与检测日志：`evidence/evidence.tar.gz`。大型输入可由归档内generate_cases.py重新生成。',
'- 没有替用户提交比赛；下一次15点提交使用r2，重点核对2～4和12，并检查其余点正确性。','',
'## 文件校验','']
for name,sha in hashes.items():lines.append(f'- `{name}`：`{sha}`')
lines.append(f'- 验证归档SHA256：`{e["sha256"]}`')
(v/'VALIDATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
m=json.loads((v/'MAINLINE.json').read_text());m['candidate_status']='Merged, CANN full build passed; 92/93 synthetic precision configurations pass with identical inherited cancellation failure; Judge15 pending'
m['validation']='VALIDATION.md';m['analysis']='CASE12_BRANCH_ANALYSIS.md';m['user_case12_feedback']='User reconfirms supplied branch gives approximately 20 us benefit on Judge Case12.';m['shape_evidence']='N=4096 follows conditional on all five probes described by teammate; only NBIT1 source provided; original N%64 range retained.'
(v/'MAINLINE.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
oldpath=root/'BMMS_V12/MAINLINE.json';old=json.loads(oldpath.read_text(encoding='utf-8'))
old['accepted_sota']='v12_r72_small_cases_index_padded.asc';old['accepted_sha256']=hashes['v13_r1_baseline_r72.asc'];old['acceptance_basis']='User explicitly confirms r72 improves Cases2-4 and promotes it as V13 r1.';old['active_candidate']=None;old['continuation']='../BMMS_V13/MAINLINE.json';old['latest_experiment_outcome']='r72 accepted by user; continuing in V13. See V13 MAINLINE.json for Case12 branch merge.'
(oldpath).write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(v/'README.md').write_text('''# BMMS V13

- 已接受基线：[v13_r1_baseline_r72.asc](v13_r1_baseline_r72.asc)，与用户确认的r72完全相同。
- 本次15点提交：[v13_r2_case12_o10.asc](v13_r2_case12_o10.asc)，r72 + 队友Case12 O10路线，已去除NBIT1减速探针。
- [分支与形状分析、下一步优化顺序](CASE12_BRANCH_ANALYSIS.md)
- [编译、精度、配对性能及未解决问题](VALIDATION.md)

r2已在卡上完成本地验证，尚未提交Judge。93个合成配置中92通过；唯一严格抵消用例在旧版也以相同结果失败。race/init检测仍有旧新版共同出现的未排除报告。请保留r1作为回退，不将本地合成结果等同15个隐藏测试点。
''',encoding='utf-8')
print(json.dumps(dict(hashes=hashes,precision=r['precision'],archive_verified=True),indent=2))
