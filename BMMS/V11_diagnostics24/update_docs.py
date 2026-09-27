"""Record confirmed R23 screenshots and the new route-specific diagnostic design."""
from pathlib import Path
import csv,importlib.util,json,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
PREVIOUS='9995599ae1ba5e275f49167db6b79f7337f4c6b9'
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
RUNS=[[2.58,5.11,5.08,6.26,7.10,14.38,10.72,90.50,69.01,84.07,101.45,123.22,16.48,13.96,15.18],
      [2.76,5.31,5.25,6.51,7.52,15.01,11.30,91.91,70.81,85.11,101.35,123.32,17.03,14.71,15.18]]
BEST=[1.22,1.58,2.16,2.92,1.89,7.09,3.70,14.88,51.77,72.47,74.82,91.20,5.20,5.40,4.05]

def main():
    b.verify();host=json.loads((HERE/'HOST_CHECKS.json').read_text(encoding='utf-8'));cpu=json.loads((HERE/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    for rel,digest in {**host['source_sha256'],**cpu['artifacts']}.items():assert b.sha(ROOT/rel)==digest,rel
    folder=ROOT/'V11_results/2026-09-27_r23_submission';folder.mkdir(exist_ok=True)
    # Preserve exact screenshot bytes. Paths are not included in the public result metadata.
    source_root=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori')
    images=[]
    for i,name in enumerate(['8660e43cf378b1142324210606093a95.png','0fb0886eeef61f8400f2f1dba0b99725.png'],1):
        source=source_root/name;dest=folder/f'R23_run_{i:02}.png'
        if dest.exists():
            if source.exists():assert dest.read_bytes()==source.read_bytes()
        else:shutil.copyfile(source,dest)
        images.append({'file':dest.name,'sha256':b.sha(dest)})
    historical=list(csv.DictReader((ROOT/'V11_results/2026-09-26_r13_r14_submission/measurements.csv').open(encoding='utf-8')))
    r14=[float(row['R14_us']) for row in historical];speedup=r14[14]/RUNS[0][14];reduction=100*(1-RUNS[0][14]/r14[14])
    with (folder/'measurements.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['case','status_run1','status_run2','error_display_percent','R23_run1_us','R23_run2_us','best_column_us','historical_R14_us'])
        for i in range(15):writer.writerow([i+1,'Pass','Pass','0.00',RUNS[0][i],RUNS[1][i],BEST[i],r14[i]])
    evidence={'version':'R23_SPLIT_K','initial_label':'R14','version_confirmed_by_user':'R23_SPLIT_K',
        'candidate_source_sha256':b.BASE_SHA,'platform_binary_hash_available':False,'screenshots':images,
        'pass_count_per_screenshot':[15,15],'timings_us':RUNS,'best_column_us':BEST,
        'case15':{'historical_R14_us':r14[14],'R23_us':[15.18,15.18],'historical_comparison_speedup':speedup,'historical_comparison_time_reduction_pct':reduction,
            'paired_adjacent_R14_control_available':False,'two_equal_rounded_values_do_not_prove_zero_variance':True},
        'score_or_rank_inferred':False,'zero_error_display_means_bitwise_equal':False,
        'new_user_route_evidence':{'Native_stress_us':{'5':14.11,'13':99.17,'14':43.43},
            'Case7_R03_stress_us':32.83,'Case7_R03_off_us':13.11,
            'Case7_K_less_than_512_inference_withdrawn':True,'probe_source_hashes_verified':False},
        'current_submission_baseline':'R23','historical_reference':'R14','next_action':'D24 route-specific conditional scheduling probes; stop old A-C'}
    b.write(folder/'RESULT.json',json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    b.write(folder/'AUDIT.md',f'''# R23 两轮提交结果及版本纠正

用户最初将截图称作 R14，随后明确确认是 **R23_SPLIT_K**。两张图均 15/15 Pass，
Case15 两次都显示 15.18 μs。逐点转录在 measurements.csv，截图原字节及 hash 保留。

相对历史 R14 的 Case15=36.25 μs，时间减少 {reduction:.2f}%，约 {speedup:.3f} 倍加速。
没有同一轮相邻 R14 控制，因此不把其他点的微小差异算作优化收益；
两个舍入后相同的数不能证明设备没有波动，0.00% 也不代表位级相等。
页面最优列 4.05 μs 得到新截图支持，但不推断官方得分、名次或其更新语义。

代码作用域与 Case15 大幅变化支持新 Split-K 路线有效，后续把 R23 作为冻结的提交基线。
R14 仍保留作历史参考，不覆盖旧源码、ZIP 或报告。

用户同时补充 Native 单组 stress：Case5/13/14 为 14.11/99.17/43.43 μs；
Case7 的 R03 stress=32.83 μs，而 R03_OFF 仅 13.11 μs。
据此撤回 Case7 从旧 C512 null result 推出的 K<512，上界重新未知，改用条件式单组压力。
这批新探针源码/hash 未提供，不与仓库旧同名 probe 混合。
''')
    audit='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
    previous=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+audit],cwd=ROOT/'CANN_archive')
    snapshot=ROOT/'audit_current/AUDIT_R23_DELIVERY.md'
    if snapshot.exists():assert snapshot.read_bytes()==previous
    else:snapshot.write_bytes(previous)
    rows='\n'.join('| '+name+' | '+route+' | `'+predicate+'` |' for name,route,predicate,_ in b.SPECS)
    readme=f'''# D24 诊断包：冻结 R23，分路径提取 shape

这批文件用于诊断，不能替换 R23 作为长期冲榜版。每份 .asc 都是独立完整提交，只选一份。
当前基线是用户确认的 R23：两轮 15/15 Pass，Case15=15.18/15.18 μs。
CONTROL_R23.asc 与它字节一致；原 R14/R23 均未修改。本包不再包含旧 A–C 阈值扫描。

## 建议顺序

1. **N01–N05**：同时观察 Case5/13/14，分别确认 K32、K64、M≤32、N≤32、B=1。
2. **R7_01–R7_05**：观察 Case7，分别确认 M<128、N<256、macro_occ<cores、K≥512、K≥1024。
3. **L00_K1_CONTROL → L05_SPATIAL_EQ1**：观察 Case15。如果 L00 明显变慢且 L05 复现，
   一次联合探针同时确认 B=1、M≤64、N≤128。

第一批不必一次跑完；前两组可以交叉提交以缩短反馈周期。
每张图保留完整 15 点和文件名，Case6 可以同时免费观察响应。
C00/C01 是新包的 Native/R03 无条件单组压力对照，条件结果不清或需要凭阴性排除时再用。
不需要补旧 A–C 的结果。

## 读数规则

- Native K：N01 是→32；N01 否、N02 是→64；两者否且阳性压力对照有效→128。
- family：N03/N04 是/否→ShortM；否/是→ShortN；其余两组相同响应→Dense。
- Case7 K：R7_04/05 否/否→[256,512)，是/否→[512,1024)，是/是→[1024,8192]；均 32 对齐。
- 阳性要求明显脱离相邻控制波动并接近该路径压力对照；阴性需要有效阳性对照。
  小幅差异记“不确定”，不按全局倍数去噪。相互矛盾的位模式、TLE/编译失败/精度失败均不能当 shape 位。
- **撤回 Case7 K<512 的旧推断**：旧 bypass 信号只有约 2 μs，不足以由不变排除条件。
- **Case15 不再用 R03 bypass**：当前路径已经是更早返回的 Split-K。L 系列只在 Split-K 内退为单分片；
  L00 的耗时必须实测，不能直接套用历史 R14 的 37 μs。

## 按结果追加

L05 若可靠阴性，再做 L01/L02/L03 分别拆开三项条件；L04 判断 MN≤4096；L06 判断原 S≥8。
若已拿到所需信息就停止该组，不追精确 M/N/K。
Case6 先看 N/R7/L00 的响应；仍未知时再做 X6_01/X6_02/X6_03，分别破坏 Macro、Tree、最后 fallback 的并行度。
全无响应也不能把路径全排除，原计划可能接近单组。

## 文件作用域

| 文件（省略 .asc） | 仅作用的路径 | 条件 |
|---|---|---|
{rows}

L00_K1_CONTROL.asc 是上轮 K1 文件的原字节副本。
Native/R03/Macro 的压力计划同步设置 pM=pN=1、tasks=B、blocks=1，再分配 workspace。
这保留全部 batch 的真实计算；没有只改 blocks，也没有把 tasks 错写成 1。

## 已完成检查

设备代码逐字保持 R23；全部干预都在 host。
82236 次实际 host 分派记录检查通过，含 69226 次不命中时完整记录相等；漏更新 tasks 的故障注入被拒绝。
原计划/单组计划各 160 次 Native/R03/Macro/Tree 源码模型执行、80 次重复核对，输出逐位一致。
K1 设备检查继承上轮绑定源码 hash 的结果；Fallback 单核参数本轮检查了 host，不声称覆盖其全部 device 子路。
这些新诊断文件尚未由本地 CANN 编译或 NPU 验证；R23 的平台 Pass 不自动覆盖诊断版。

完整推导、状态表和下一轮优化分支见 DESIGN.md；逐文件 SHA256 在 MANIFEST.json。
'''
    b.write(b.OUT/'README.md',readme);shutil.copyfile(HERE/'DESIGN.md',b.OUT/'DESIGN.md')
    b.write(ROOT/audit,f'''# BatchMatmulMaxSum 当前审计：R23 获两轮通过，转入 D24 分路径诊断

2026-09-27。用户已确认两张最新截图实际为 R23_SPLIT_K，均 15/15 Pass，Case15 均 15.18 μs。
R23 保留为当前提交基线，R14 作为冻结历史参考。本轮交付独立诊断包，不修改 SOTA 计算代码。

## 新结果

历史 R14 Case15=36.25 μs，R23=15.18/15.18 μs，约 {speedup:.2f} 倍加速、减少 {reduction:.1f}% 时间。
这不是同轮相邻 A/B；其他点差异保留为波动待辨，不归因为收益，不用实时变化的最优列复算官方名次。
两个舍入结果相等不是零方差证明，0.00% 误差栏不是逐位一致证明。
[两轮逐点数据、截图、版本纠正](V11_results/2026-09-27_r23_submission/AUDIT.md)。

## 证据修正与分组

5/13/14 以用户提供的强 Native stress 响应为依据，工作域为 M/N≥16 且 16 对齐，K32/64/128。
Case6 无可靠 shape 约束，必须先定位路径。
Case7 的 R03 stress=32.83 μs，但 R03_OFF 只有 13.11 μs，因此旧 C512 无明显响应不足以排除 K≥512。
**撤回 Case7 K<512，保留 K≥256 且 32 对齐，上界待探。**
Case15 的 K4096..8192、小 M/N 证据保留，但当前从旧 R03 转入 R23 Split-K；旧 R03 guard 探针不再适用。
新用户 P/A/B/C 的原始文件/hash 未提供，按报告作用域使用，不当作独立复现。

## D24 设计与执行顺序

| 对象 | 第一组诊断 | 如何解释 |
|---|---|---|
| 5 / 13 / 14 | N01 K32，N02 K64，N03 M≤32，N04 N≤32，N05 B1 | 条件命中才执行 Native 单组压力；一次提交读三个点 |
| 7 | R7_01 M<128，02 N<256，03 macro_occ<cores，04 K≥512，05 K≥1024 | 使用强 R03 单组响应，不使用弱 bypass 响应 |
| 15 | L00 K1 对照，再 L05 空间任务数=1 | 阳性联合确认 B1/M≤64/N≤128；否则再拆开 L01–L03 |
| 6 | 先观察前述提交；必要时 X6_01 Macro、02 Tree、03 fallback | 先锁实际路径，阴性不当作排除 |

Native/R03/Macro 的单组计划同时更新 pM、pN、tasks=B、blocks=1，并在此后计算 workspace。
所有探针只改原路径选中后的 host 参数；未命中路径以及全部 device 代码与 R23 相同。
C00/C01 是本包压力校准；其余 L / X6 是按反馈展开的可选文件。
阳性要明显离开相邻控制波动；阴性需要可靠压力阳性对照；模糊结果保留未知。
不用全局缩放消除噪声，不拼接各轮最低值，不要求补旧 A–C。

Case15 当前 consumer 固定 128 列，即使 N 很小也补零并处理这些列。
若联合几何和 S 证据支持，下一性能候选优先考虑紧凑 N 合并与受控 S 消融。
Case7 继续保留已有空间并行，Native 则等待 K/family 后再定资源布局；不统一套用 Split-K。
[完整条件、推理及下一轮路线](V11_diagnostics24/DESIGN.md)。

## 本地检查与边界

21 份独立诊断、2 份冻结控制。82236 次实际 host 分派记录检查通过，
其中 69226 次验证不命中的完整记录相同；每个探针均有阳性/阴性输入，六条顶层路均覆盖。
漏更新 tasks 的故障注入被拒绝，999 组输入核对了空间任务为 1 的联合推论。
原计划与单组计划各 160 次源码模型运行、80 次重复核对，Native/R03/Macro/Tree 普通输出逐位一致。
K1 继承上轮源码 hash 绑定验证；Fallback 单核参数本轮只验证 host，不夸称覆盖全部高层 device 子路。
[host 报告](V11_diagnostics24/HOST_CHECKS.json) / [CPU 模型报告](V11_diagnostics24/CPU_CHECKS.json)。

本地无 CANN/NPU，D24 平台编译、正确性和压力幅度尚待提交；R23 的 15/15 不能替代这些检查。
保留全数值域和真实异步行为未验证的限制。

## 交付

[D24 诊断包](BMMS_V11_D24_诊断包.zip) / [提交说明](BMMS_V11_D24_Diagnostics/README.md)。
上轮状态冻结为[历史审计](audit_current/AUDIT_R23_DELIVERY.md)；R14/R23 源码与旧 ZIP 不覆盖。
归档分支：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
''')
    links=[('D24 诊断包','BMMS_V11_D24_诊断包.zip'),('提交顺序与读数','BMMS_V11_D24_Diagnostics/README.md'),
        ('诊断设计','V11_diagnostics24/DESIGN.md'),('当前 R23 冲榜文件','BMMS_V11_R23/R23_SPLIT_K.asc'),
        ('R23 两轮通过证据','V11_results/2026-09-27_r23_submission/AUDIT.md'),('当前审计',audit),
        ('host 检查','V11_diagnostics24/HOST_CHECKS.json'),('CPU 计划检查','V11_diagnostics24/CPU_CHECKS.json')]
    index='''# BatchMatmulMaxSum：R23 基线，D24 分路径诊断

R23 两轮均 15/15 Pass，Case15=15.18/15.18 μs；用户已纠正最初的 R14 标签。
保留 R14/R23 原源码，D24 只修改各实际分支的 host 计划，用于 Native、R03、Split-K 和 Case6 路径定位。
停止旧 A–C；撤回 Case7 K<512 的推断。D24 是诊断文件，不是新的冲榜版本。

'''+''.join(f'- [{label}]({path})\n' for label,path in links)+'''
```powershell
python V11_diagnostics24/build.py
python V11_diagnostics24/check_host.py
python V11_diagnostics24/check_device_plans.py
python V11_diagnostics24/update_docs.py
python V11_diagnostics24/package.py
```

本地未做 CANN/NPU 验证。历史源码、提交包和报告快照冻结。
审计快照需要历史 commit；截图已归档后不再依赖聊天附件原路径。
'''
    b.write(ROOT/'README.md',index);cann=index
    for _,path in links:cann=cann.replace(']('+path+')','](BMMS/'+path+')')
    b.write(HERE/'CANN_README.md',cann.replace('```powershell\n','```powershell\ncd BMMS\n'))
    status=json.loads((ROOT/'ARCHIVE_STATUS.json').read_text(encoding='utf-8'))
    status.update(working_baseline='R23',historical_reference='R14',R23_platform_result_received=True,R23_pass_counts=[15,15],
        R23_case15_us=[15.18,15.18],R23_screenshot_initial_label_corrected_from='R14',
        selected_baseline_reason='User confirmed R23 screenshots, both 15/15; Case15 substantially improved; freeze R23 for new diagnostic work.',
        latest_feedback='Two screenshots confirmed as R23; Native cases 5/13/14, strong R03 stress for Case7; stop old A-C and build route-specific diagnostics.',
        case7_K_less_than_512_inference_withdrawn=True,case7_K_lower_bound=256,case7_K_upper_bound_exclusive_unknown=True,
        D24_host_dispatch_checks=host['host_dispatch_checks'],D24_platform_results_received=False,
        D24_cann_compiled_locally=False,D24_npu_tested_locally=False,
        next_action='N01-N05 for 5/13/14; R7_01-R7_05 for 7; L00 then L05 for 15; observe Case6 and expand only as needed.')
    b.write(ROOT/'ARCHIVE_STATUS.json',json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'R23_pass_counts':[15,15],'case15_speedup_vs_historical_R14':speedup,'time_reduction_pct':reduction,'next_package':'D24'},ensure_ascii=False))
if __name__=='__main__':main()
