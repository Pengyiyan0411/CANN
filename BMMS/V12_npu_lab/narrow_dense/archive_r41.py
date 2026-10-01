from pathlib import Path
import json,hashlib,zipfile
root=Path('.').resolve()
precision=[]
for tag in ['correctness','extra_correctness','holdout_correctness']:
 precision += [json.loads(s) for s in (root/f'results/r41_{tag}.jsonl').read_text().splitlines()]
assert len(precision)==230 and all(r['pass'] for r in precision)
san=root/'san_r41';log=(san/'memcheck.log').read_text(errors='replace') if (san/'memcheck.log').exists() else ''
launch=(root/'logs/r41_memcheck_retry_launcher.log').read_text(errors='replace')
checked=[json.loads(s) for s in (san/'precision.jsonl').read_text().splitlines()] if (san/'precision.jsonl').exists() else []
summary=dict(precision_configurations=len(precision),precision_calls=sum(r['repeats'] for r in precision),all_pass=True,
 max_tolerance_ratio=max(r['max_tolerance_ratio'] for r in precision),sanitizer=dict(mode='memcheck on ordinary full-source binary; not instrumented race/init',
 exit_code=int((san/'status.txt').read_text()),completed_cases=len(checked),all_completed_pass=all(r['pass'] for r in checked),errors=log.count('====== ERROR:'),warnings=log.count('====== WARNING:'),
 register_warnings=log.count('[mssanitizer] Warning:'),actual_kernel_starts=log.count('Start memcheck sanitizer on kernel'),completed_kernels=log.count('Sanitizer finished on kernel'),launch_errors=launch.count('[mssanitizer] ERROR:'),log_bytes=len(log)))
(root/'results/r41_validation_summary.json').write_text(json.dumps(summary,indent=2))
files=[]
for pattern in ['*.asc','CMakeLists.txt','generate*.py','representatives.json','run_screen.py','check_r41.sh','finish_r41.sh','memcheck_r41.sh','plan_sweep.sh','archive_r41.py',
 'results/r41*','results/plan_sweep*','results/environment.json','logs/r41*','logs/plan_sweep*','cases/*.txt','cases/*.jsonl','san_r41/*']:
 files += [p for p in root.glob(pattern) if p.is_file()]
files += list(root.glob('profiles/r41_*/PROF_*/mindstudio_profiler_output/op_summary*.csv'))
files=sorted(set(files));manifest=dict(files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},binary_sha256={name:hashlib.sha256((root/'build'/name).read_bytes()).hexdigest() for name in ['bench_r33','bench_r41','sweep_plans']})
with zipfile.ZipFile(root/'r41_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,p.relative_to(root))
 z.writestr('manifest.json',json.dumps(manifest,indent=2))
print(json.dumps(summary))
