from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parent
small=(root/'cases/small_regression.txt').read_text().splitlines()
dense=(root/'cases/all.txt').read_text().splitlines()
# Exercise launch order and buffer reuse across old/new Vector/MIX routes.
# Exclude the independently recorded cancellation failure so it does not stop
# the legacy harness before later launch-order combinations can execute.
sequence=[]
for i in range(32):
    sequence += [small[-(i%6)-1],small[i%32],dense[i],small[(i+16)%32],dense[52+i%3],dense[32],dense[i],small[(i+7)%32]]
p=root/'cases/mixed_order.txt';p.write_text('\n'.join(sequence)+'\n')
report={}
for version in ('r1','r2'):
    output=root/f'results/mixed_order_{version}.jsonl'
    with (root/f'results/mixed_order_{version}.log').open('w') as f:
        run=subprocess.run([str(root/f'build/bench_{version}'),str(p),'2',str(output)],cwd=root,stdout=f,stderr=subprocess.STDOUT,timeout=240)
    results=[json.loads(x) for x in output.read_text().splitlines()]
    report[version]={'returncode':run.returncode,'configurations_with_repeats':len(results),'kernel_calls':sum(r['repeats'] for r in results),'failed':[r for r in results if not r['pass']]}
(root/'results/mixed_order_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
