from pathlib import Path
h=Path(__file__).resolve().parent/'harness'
s=(h/'archive_c8.py').read_text(encoding='utf-8').replace('Case8','Case12').replace('case8_evidence','case12_evidence')
a=s.index("for pat in ['results/");b=s.index(':\n    for p in r.glob(pat)',a)
s=s[:a]+"for pat in ['results/c12*','logs/c12*','profiles/c12*/**/*','cases_c12*/*','cases/*.txt','cases/*.jsonl','cases_c8*/*.txt','cases_c8*/*.jsonl','cases_split/*.txt','cases_split/*.jsonl','cases_split_controls/*.txt','cases_split_controls/*.jsonl','build/CMakeFiles/*r19*/*.make','build/CMakeFiles/*r20*/*.make']"+s[b:]
s=s.replace("['*.asc','*.py','*.sh','CMakeLists.txt']","['r19.asc','r20.asc','main.asc','event_c12_plan.asc','event_bench_r20.asc','c12_plans.h','*c12*.py','*c12*.sh','generate_cases.py','generate_c8*.py','generate_split*.py','run_screen.py','CMakeLists.txt']")
(h/'archive_c12.py').write_text(s,encoding='utf-8',newline='\n')
s=(h/'review_c8_sanitizers.py').read_text(encoding='utf-8').replace("['r12','r18','r19']","['r19','r20']").replace('c8_','c12_')
(h/'review_c12_sanitizers.py').write_text(s,encoding='utf-8',newline='\n')
