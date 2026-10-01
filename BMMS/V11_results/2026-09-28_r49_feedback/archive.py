from pathlib import Path
import json,hashlib,shutil
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
package=ROOT/'BMMS_V11_R49'
manifest=json.loads((package/'MANIFEST.json').read_text(encoding='utf-8'))
assert hashlib.sha256((package/manifest['candidate']).read_bytes()).hexdigest()==manifest['sha256']
latency=[2.50,5.92,4.92,6.32,6.52,14.82,9.44,63.25,70.07,84.66,101.81,124.78,15.02,13.85,15.10]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,51.62,72.39,74.82,91.20,5.14,5.40,4.05]
pic=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori/0c7a5c5566d3357e566c81e57f3189a4.png')
if pic.is_file():shutil.copyfile(pic,H/pic.name)
report={'date':'2026-09-28','candidate':'R49_NATIVE_CONSUMER_ONLY',
 'version_attribution':'inferred from immediate R49 submission conversation; image itself has no version label',
 'source_sha256':manifest['sha256'],'image_origin':str(pic),'image_copied':(H/pic.name).exists(),
 'sample_count':1,'same_round_R48_or_R43_control_available':False,
 'cases':[{'case':i+1,'status':'Pass','displayed_error_percent':0.0,'latency_us':v,'platform_best_us':best[i]} for i,v in enumerate(latency)],
 'comparison':{'R48_case13_us':[17.22,16.96],'R48_case13_mean_us':17.09,'R49_case13_us':15.02,
               'case13_latency_reduction_vs_R48_mean_percent':(17.09-15.02)/17.09*100,
               'R48_case7_us':[9.44,9.70],'R49_case7_us':9.44},
 'decision':'retain R49 as measured positive candidate; keep R43 frozen reference and R48 rollback',
 'causal_limit':'supports consumer-only strategy as a whole; does not isolate each consumer change or explain all R47 regression',
 'route_instrumented':False,'non_regression_guaranteed':False,'new_kernel_created':False}
(H/'FEEDBACK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'cases':len(report['cases']),'image_copied':report['image_copied'],'case13_reduction_percent':round(report['comparison']['case13_latency_reduction_vs_R48_mean_percent'],2)}))
