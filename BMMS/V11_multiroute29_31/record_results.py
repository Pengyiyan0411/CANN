"""Preserve the latest user screenshot without upgrading contextual attribution to proof."""
from pathlib import Path
import csv,hashlib,io,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'V11_results/2026-09-27_r28_observed'
IMAGE=Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori\17aca8f417cdcc2b0d3b84f074baa117.png')
TIMES=[2.60,5.55,5.23,6.65,6.43,13.58,10.60,90.98,69.64,83.79,100.21,122.56,16.70,13.35,15.49]
BEST=[1.22,1.58,2.16,2.92,1.89,7.09,3.69,14.88,51.62,72.47,74.82,91.20,5.17,5.40,4.05]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data):
    if p.exists():assert p.read_bytes()==data,p
    else:p.write_bytes(data)
def main():
    OUT.mkdir(exist_ok=True,parents=True);img=OUT/'R28_context_attributed.png';save(img,IMAGE.read_bytes())
    source=ROOT/'BMMS_V11_R28/R28_COMPACT_SPLITK.asc';assert sha(source)=='05aaa79b31f6b9315b338f9ee455157ef6da9f3e115e1e0ebf3e2ddcbcb1ec74'
    data={'date':'2026-09-27','contextual_version':'R28_COMPACT_SPLITK','user_explicit_version_label':False,
        'attribution':'Context only: image follows R28 delivery; screenshot has no source hash or explicit version label.',
        'platform_source_hash_verified':False,'delivered_source':source.relative_to(ROOT).as_posix(),'delivered_source_sha256':sha(source),
        'screenshot':img.name,'original_screenshot_filename':IMAGE.name,'screenshot_sha256':sha(img),
        'pass_count':15,'displayed_error_pct':[0.0]*15,'time_us':TIMES,'best_column_us':BEST,
        'adjacent_R25_control_received':False,'R28_performance_improvement_established':False,
        'Case15_us':15.49,'Case5_us':6.43,'measured_baseline_retained':'R25_NATIVE_TARGETED',
        'next_candidates':['R29_SHORTK_L1','R30_NATIVE_M128','R31_MACRO_K128'],
        'CANN_compiled_locally':False,'NPU_tested_locally':False}
    save(OUT/'RESULT.json',(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())
    buf=io.StringIO(newline='');w=csv.writer(buf);w.writerow(['contextual_version','case','status','displayed_error_pct','time_us','best_column_us'])
    for case,t in enumerate(TIMES,1):w.writerow(['R28',case,'Pass','0.00',f'{t:.2f}',f'{BEST[case-1]:.2f}'])
    save(OUT/'measurements.csv',buf.getvalue().encode())
    save(OUT/'AUDIT.md','''# 最新截图记录（上下文归属 R28）

用户没有在这张截图旁重写版本号。按上一轮交付归到 R28，保留“上下文推定”标记；没有平台源码哈希证明。

15/15 Pass，显示误差均 0.00%。Case5 6.43 μs，Case15 15.49 μs。
Case15 未显示相对此前约 15 μs 的明确改善；Case6 13.58、Case14 13.35 等小幅变化缺少相邻 R25 对照，不能认定优化收益。
R28 不晋升，R25 继续为冻结性能基线。平台“最优用时”列单独保存，不用它计算版本间的优化幅度。

按用户要求扩展到三个独立方向：短 K 的 R03 加载、Native 的 M128 计算块、Macro 的 K128 计算块。
不把 Case6/8/9/12 的未定位路径按耗时猜成某一种路径，也不把 Case13/14 的 M>=128 当作已确定事实。
'''.encode())
    print(json.dumps({'measurements':15,'Case15_us':15.49,'R28_promoted':False,'attribution':'contextual'}))
if __name__=='__main__':main()
