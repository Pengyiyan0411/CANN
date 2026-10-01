from pathlib import Path
import hashlib,json,shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
package=ROOT/'BMMS_V11_R47_R48'
manifest=json.loads((package/'MANIFEST.json').read_text(encoding='utf-8'))
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,51.62,72.39,74.82,91.20,5.14,5.40,4.05]
records=[
    ('R48_RESIDUAL_BATCH_OWNER',1,'3443fe5c0b72c61248445a51341b9e78.png',
     [2.52,5.65,5.10,6.48,6.51,14.75,9.44,63.79,71.09,84.81,101.49,124.61,17.22,13.74,15.54]),
    ('R48_RESIDUAL_BATCH_OWNER',2,'dc94858d79caec07786f9037d075cfdd.png',
     [2.53,5.68,5.25,6.45,6.39,15.07,9.70,62.30,69.57,84.36,100.82,123.09,16.96,13.61,15.06]),
    ('R47_NATIVE_NARROW_DIRECT',1,'401c7029e242c10288a1d675947d6db6.png',
     [2.50,5.34,5.14,6.50,6.61,15.17,10.80,62.98,70.50,84.57,100.97,123.11,19.23,13.86,15.06]),
]
runs=[]
for variant,rep,pic,values in records:
    source=package/(variant+'.asc')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest==manifest[variant]['sha256']
    origin=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori')/pic
    copied=False
    if origin.is_file():
        shutil.copyfile(origin,HERE/pic);copied=True
    runs.append({'variant':variant,'repetition':rep,'source_sha256':digest,
                 'image_origin':str(origin),'image_copied':copied,
                 'cases':[{'case':i+1,'status':'Pass','displayed_error_percent':0.0,
                           'latency_us':v,'platform_best_us':best[i]} for i,v in enumerate(values)]})
report={'date':'2026-09-28','source':'user-labelled screenshots; manually transcribed displayed values',
        'same_round_R43_control_available':False,'runs':runs,
        'decision':{'baseline':'R43_CASE8_PADDED_MACRO','R48':'retain as promising measured candidate; do not silently replace R43 baseline',
                    'R47':'do not adopt; Case13 regression in supplied run'},
        'observed_summary':{'R48_case7_us':[9.44,9.70],'R48_case7_mean_and_two_sample_median_us':9.57,
                            'R47_case13_us':19.23,'R48_case13_us':[17.22,16.96],
                            'all_45_displayed_checks_pass':True,
                            'non_target_regression_proven':False,'non_regression_guaranteed':False},
        'case13_shape_update':{'user_statement':'这边认为点13的M至少是>256',
                               'source':'user follow-up assessment; not a new raw probe log',
                               'working_constraint':'M>256; with established M%16==0, M>=272',
                               'R47_already_requires_M_gt_256':True,
                               'N_48_or_64_not_independently_confirmed_by_this_update':True},
        'route_execution_instrumented':False,'new_kernel_created':False}
(HERE/'FEEDBACK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert all(len(r['cases'])==15 for r in runs)
print(json.dumps({'runs':len(runs),'cases':45,'screenshots_copied':sum(r['image_copied'] for r in runs)},ensure_ascii=False))
