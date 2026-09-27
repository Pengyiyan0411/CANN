"""Archive the latest R26-context screenshot without rewriting prior results."""
from pathlib import Path
import argparse,csv,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'V11_results/2026-09-27_r26_observed'
DATA=[2.55,5.86,5.29,6.57,6.86,15.19,11.48,92.67,71.24,84.93,101.32,124.41,17.26,13.77,15.43]
BEST=[1.22,1.58,2.16,2.92,1.89,7.09,3.70,14.88,51.77,72.47,74.82,91.20,5.19,5.40,4.05]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--image',type=Path);args=ap.parse_args();OUT.mkdir(exist_ok=True)
    dst=OUT/'observation_01.png'
    if not dst.exists():assert args.image;shutil.copyfile(args.image,dst)
    if args.image:assert sha(dst)==sha(args.image)
    source=ROOT/'BMMS_V11_R26/R26_DENSE_PACKET.asc'
    data=dict(date='2026-09-27',working_attribution='R26_DENSE_PACKET',
        attribution_basis='latest delivered candidate and user says no benefit; no explicit repeated filename or platform hash',
        user_explicit_filename_confirmation=False,platform_source_hash_verified=False,
        archived_source=source.relative_to(ROOT).as_posix(),archived_source_sha256=sha(source),
        screenshot=dst.name,screenshot_sha256=sha(dst),pass_count=15,displayed_error_pct=[0.0]*15,
        us=DATA,best_column_us=BEST,decision='do not promote R26; retain R25 working baseline',
        no_demonstrated_Case13_14_benefit=True,Case5_regression_excluded=False,
        performance_root_cause_confirmed=False,statistical_significance_claimed=False)
    (OUT/'RESULT.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['case','status','displayed_error_pct','time_us','best_column_us'])
        for i,t in enumerate(DATA,1):w.writerow([i,'Pass','0.00',f'{t:.2f}',f'{BEST[i-1]:.2f}'])
    (OUT/'AUDIT.md').write_text('''# R26 回传：正确性通过，未证明性能收益

最新截图按上一轮交付上下文归属 R26_DENSE_PACKET，用户没有重述文件名或平台源码 hash。
15/15 Pass、误差栏 0.00%，完整读数及原图 hash 留在本目录。该精度结果只对应平台15点。

| Case | R25 两次观测 μs | 最新 R26 观测 μs | 当前判断 |
|---|---:|---:|---|
| 5 | 6.60 / 6.45 | 6.86 | 高于两次旧值，不能声称已经排除退化 |
| 13 | 16.80 / 16.91 | 17.26 | 没有收益证据 |
| 14 | 13.84 / 13.63 | 13.77 | 落在旧两次观测之间，没有收益证据 |
| 15 | 15.30 / 15.03 | 15.43 | 仅记录，不给小幅变化强加因果解释 |

结论：撤回 R26 升级推荐，继续以冻结 R25 为工作基线。不用全表缩放消除所谓系统波动，
不拼接跨次最低值；也不把两次观测的范围当成置信区间。

1. 在提交文件对应正确、N01–N05 路由解释成立的前提下，13/14 会命中 R26。
   本地真实 host 分派检查支持这一点，但不能代替平台上报源码 hash。
2. R26 减少的是消费者 DMA 调用，未减少有效 C 字节量、Cube 工作量、全局屏障数或跨核 credits。
   新增 look-ahead 标量工作也有成本；净收益为零并不能唯一定位哪个硬件阶段占主导。
3. 每块 M_FIX 约束的是 FIX 等待该块 MMAD 完成；旧双缓冲已允许跨块重叠。
   不能把源码 Set/Wait 紧邻误读成 Scalar 等待，更不能据此证明整条流水完全串行。

R27 从 R25 派生，只对相同 dense 元数据域替换 MMAD→FIX 的块级同步；消费者和 Case5 均为原 R25。
UnitFlag 是待验证的单变量候选，没有 profiler 证据证明它就是 13/14 的主瓶颈。
''',encoding='utf-8')
    print(json.dumps({'screenshots':1,'measurements':15,'all_pass':True,'R26_promoted':False}))
if __name__=='__main__':main()
