"""Offline audit of new Case12 claims against the frozen r41 host planner."""
from pathlib import Path
import collections
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'V12_results/2026-10-01_case12_offline_review'
SOURCE = ROOT / 'BMMS_V12/v12_baseline_r41.asc'
REPORT = Path('C:/Users/cc/Downloads/最重要的是第一条：Case12 的 K 已经精确确定为 1536.md')


def extract_planner(source):
    start = source.index('namespace bmms11r2 {')
    end = source.index('template<class T,bool TA,bool TB>', start)
    return source[start:end]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw = SOURCE.read_bytes()
    source = raw.decode('utf-8')
    planner = extract_planner(source)
    assert planner == extract_planner((ROOT / 'BMMS_V12/v12_baseline_r33.asc').read_text(encoding='utf-8'))
    mainline = json.loads((ROOT / 'BMMS_V12/MAINLINE.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(raw).hexdigest() == mainline['accepted_sha256']
    pre = '''#include <cstdint>
#include <cstdio>
#include <cassert>
namespace bmms83 {
struct NativePlan { int32_t B,M,N,K,mTiles,nTiles,pM,pN,tasks,blocks; };
inline int UpH(int a,int b){return (a+b-1)/b;}
inline int MinH(int a,int b){return a<b?a:b;}
inline int MaxH(int a,int b){return a>b?a:b;}
inline int MinI(int a,int b){return a<b?a:b;}
}
'''
    harness = '''}
int main(){
 printf("cores,M,N,TA,pM,pN,mTiles,nTiles,tasks,blocks,peak_tiles,peak_cells,min_mtiles_per_task,max_mtiles_per_task\\n");
 for(int cores=1;cores<=64;++cores)
 for(int M=1280;M<1536;M+=16)
 for(int N=4096;N<6144;N+=64)
 for(int ta=0;ta<2;++ta){
   const int K=1536;
   if(!bmms11r2::Eligible(1,M,N,K,cores))continue;
   if(ta && M%64)continue; // AlignedPitch with TB=false; N%64 already holds.
   auto p=bmms11r2::MakePlan(1,M,N,K,cores);
   auto peak=bmms11r2::ExistingPeak(p);
   auto flat=(p.mTiles*p.nTiles+cores-1)/cores;
   if(p.pN!=2||p.pM<8||p.tasks!=cores||p.blocks!=cores||flat!=peak.tiles)continue;
   int minM=100,maxM=0;
   for(int task=0;task<p.tasks;++task){
     int ms=task/p.pN;
     int span=(ms+1)*p.mTiles/p.pM-ms*p.mTiles/p.pM;
     if(span<minM)minM=span;if(span>maxM)maxM=span;
   }
   printf("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%llu,%llu,%d,%d\\n",cores,M,N,ta,
       p.pM,p.pN,p.mTiles,p.nTiles,p.tasks,p.blocks,
       (unsigned long long)peak.tiles,(unsigned long long)peak.cells,minM,maxM);
 }
}
'''
    cpp = OUT / 'planner_from_r41.cpp'
    exe = OUT / 'planner_from_r41.exe'
    cpp.write_text(pre + planner + harness, encoding='utf-8')
    run = subprocess.run(['g++', '-O2', '-std=c++17', str(cpp), '-o', str(exe)], capture_output=True, text=True)
    (OUT / 'compile.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    run.check_returncode()
    result = subprocess.check_output([str(exe)], text=True)
    (OUT / 'compatible_plans.csv').write_text(result, encoding='utf-8')
    rows = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(io.StringIO(result))]
    assert rows
    states = collections.Counter((r['cores'], r['pM'], r['mTiles']) for r in rows)
    assert all(r['min_mtiles_per_task'] == r['max_mtiles_per_task'] == 1 for r in rows)
    by_core = {}
    for core in sorted(set(r['cores'] for r in rows)):
        part = [r for r in rows if r['cores'] == core]
        by_core[core] = {'M': sorted(set(r['M'] for r in part)),
                         'N': sorted(set(r['N'] for r in part)),
                         'TA': sorted(set(r['TA'] for r in part)),
                         'configurations': len(part),
                         'MN_pairs': len(set((r['M'], r['N']) for r in part))}
    assert by_core[20]['M'] == [1280]

    stages = []
    for k1 in [192, 256, 320, 384]:
        chunks = [min(k1, 1536-k) for k in range(0, 1536, k1)]
        k0_order = [k+kk for k in range(0, 1536, k1) for kk in range(0, min(k1, 1536-k), 64)]
        assert k0_order == list(range(0, 1536, 64))
        l1 = 2*k1*(128+256)*2
        stages.append({'K1': k1, 'chunks': chunks, 'stage_count': len(chunks),
                       'load_stage_calls_per_macro': len(chunks),
                       'A_plus_B_nd2nz_calls_per_macro': 2*len(chunks),
                       'K0_mmad_count_per_macro': len(k0_order),
                       'L1_A_plus_B_bytes': l1, 'L1_KiB': l1/1024,
                       'fits_recorded_512KiB_budget': l1 <= 512*1024,
                       'L1_start_slot_changes_between_macros': bool(len(chunks)%2),
                       'full_macro_A_logical_bytes': 128*1536*2,
                       'full_macro_B_logical_bytes': 256*1536*2})
    stats20 = []
    for N in by_core[20]['N']:
        nt = (N+255)//256
        stats20.append({'N': N, 'nTiles': nt, 'macro_count': 10*nt,
                        'A_GM_to_L1_requested_bytes': 1280*1536*2*nt,
                        'B_GM_to_L1_requested_bytes': 10*1536*N*2,
                        'B_distinct_input_bytes': 1536*N*2,
                        'partial_bytes': 2*1280*4,
                        'n_tiles_per_task_min': nt//2,
                        'n_tiles_per_task_max': (nt+1)//2})
    summary = {
        'status': 'offline CPU planner/resource analysis only; no SSH, NPU build or timing',
        'assumptions': ['New report probes use the frozen r41/r30 planner and correctly calibrated encoders.',
                        'B=1, K=1536, TB=false, 1280<=M<1536, 4096<=N<6144, M%16=N%64=0.',
                        'pN=2, pM>=8, tasks=blocks=cores, flatPeak=oldPeak.'],
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'new_report_sha256': hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        'actual_planner_extracted': True, 'same_host_planner_as_r33': True,
        'enumeration_input_count': 64*16*32*2,
        'compatible_count_with_TA': len(rows),
        'states': [{'cores': k[0], 'pM': k[1], 'mTiles': k[2], 'count': v} for k,v in sorted(states.items())],
        'by_core': by_core,
        'all_compatible_plans_have_one_M_macro_per_task': True,
        'K1_analysis': stages,
        'cores20_traffic_models_not_HBM_measured_traffic': stats20,
        'reported_sensitivity_deltas_us': {'A_LOAD_X2': round(135.58-113.67, 2),
                                           'B_LOAD_X2': round(146.66-113.67, 2),
                                           'RINGREAD_X2': round(118.39-113.67, 2)},
    }
    (OUT / 'ANALYSIS.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    shutil.copyfile(REPORT, OUT / 'user_report.md')
    print(json.dumps({k: summary[k] for k in ['status','enumeration_input_count','compatible_count_with_TA','states','by_core','K1_analysis']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
