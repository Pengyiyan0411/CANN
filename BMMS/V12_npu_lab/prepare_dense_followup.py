from pathlib import Path
r=Path(__file__).resolve().parent;h=r/'harness'
s=(h/'generate_c1112_screen.py').read_text(encoding='utf-8')
s=s.replace('cases_c1112_screen','cases_dense_balanced').replace('2092812','2092830')
a=s.index('shapes=');b=s.index('manifest=[];',a)
s=s[:a]+'''shapes=[(1344,3136,1728),(1728,6208,3392)]
for M,N,K in shapes:
 for layout in range(4):
  for dt in [1,2]:
   specs.append(dict(id=len(specs),label='balanced_independent',B=1,M=M,N=N,K=K,dtype=dt,ta=layout//2,tb=layout%2,pattern='random'))
'''+s[b:]
a=s.index('sets=');b=s.index('\nfor name,ids',a)
s=s[:a]+"sets={'manifest':range(len(manifest)),'profile':[0,1,2,3,4,5,6,7], 'sanitize':[0,1], 'screen':range(len(manifest))}"+s[b:]
(h/'generate_dense_balanced.py').write_text(s,encoding='utf-8',newline='\n')
# Used only if r30 survives initial screening. Compiles all instrumentation first.
v=(h/'validate_dense_winner.sh').read_text(encoding='utf-8')
v=v.replace('r26|r27','r30')
v=v.replace("# Heavy instrumented compilation", "python3 generate_dense_balanced.py >results/dense_balanced_generation.log 2>&1\n# Heavy instrumented compilation")
v=v.replace('--target "sanitize_${version}"', '--target "${version}_build" "sanitize_${version}"')
v=v.replace("for pair in 'holdout", "bash profile_dense_variants.sh >results/profile_dense_variants_job.log 2>&1\nfor pair in 'screen cases_c1112_screen' 'values cases_r25_values' 'holdout")
v=v.replace('./build/event_bench_${version} cases_c1112_holdout/aligned.txt 8 "results/${version}_holdout_event.jsonl"', './build/event_bench_${version} cases_c1112_screen/aligned.txt 6 "results/${version}_screen_event.jsonl" >"results/${version}_screen_event.log" 2>&1\n./build/event_bench_${version} cases_c1112_holdout/aligned.txt 8 "results/${version}_holdout_event.jsonl"')
v=v.replace("'gap cases_c12_holdout';", "'gap cases_c12_holdout' 'balanced cases_dense_balanced';")
v=v.replace('python3 - <<\'PY\'', '''./build/event_bench_${version} cases_dense_balanced/manifest.txt 10 "results/${version}_balanced_event.jsonl" >"results/${version}_balanced_event.log" 2>&1
python3 - <<'PY' ''',1)
# Prevent heredoc trailing-space ambiguity.
v=v.replace("<<'PY' \n", "<<'PY'\n")
v=v.replace('python3 analyze_dense_macro.py >"results/${version}_final_event_analysis.log"','true')
(h/'validate_dense_pipeline.sh').write_text(v,encoding='utf-8',newline='\n')
print('Prepared independent balanced holdout and validation script; not launched.')
