"""Validate diagnostic data and parsing without consuming an NPU."""
from pathlib import Path
import ast
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PROBE=HERE/'device_probe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for p in list(HERE.glob('*.py'))+list(PROBE.glob('*.py')):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    for name in ['R01_REUSE_2X2.asc','P01_CONTROL.asc']:
        assert (PROBE/name).read_bytes()==(ROOT/'BMMS_V11_SubmitPack'/name).read_bytes()
    cases=json.loads((HERE/'probe_prepare_check/inputs.json').read_text(encoding='utf-8'))['cases']
    assert len(cases)==22
    for case in cases:
        d=HERE/'probe_prepare_check'/case['id'];B,M,N,K=case['shape']
        assert (d/'a.bin').stat().st_size==B*M*K*2 and (d/'b.bin').stat().st_size==B*N*K*2
        for file,key in [('a.bin','a_sha256'),('b.bin','b_sha256'),('golden.bin','golden_sha256')]:assert sha(d/file)==case[key]
        def decode(file,shape,trans):
            u=np.fromfile(file,np.uint16)
            f=u.view(np.float16).astype(np.float64) if case['dtype']==1 else (u.astype(np.uint32)<<16).view(np.float32).astype(np.float64)
            f=f.reshape(shape);return f.swapaxes(1,2) if trans else f
        a=decode(d/'a.bin',(B,K,M) if case['ta'] else (B,M,K),case['ta'])
        b=decode(d/'b.bin',(B,N,K) if case['tb'] else (B,K,N),case['tb'])
        assert np.isfinite(a).all() and np.isfinite(b).all()
        actual=(a@b).max(axis=2).sum(axis=1,dtype=np.float64).astype(np.float32)
        assert np.array_equal(actual.view(np.uint32),np.fromfile(d/'golden.bin',np.uint32))
        if case['profile']:assert case['expect_R01']
    # This synthetic CSV tests parser correctness only. Never archive it as a device measurement.
    with tempfile.TemporaryDirectory(prefix='bmms_parser_') as temp:
        d=Path(temp);f=d/'op_summary_synthetic.csv'
        with f.open('w',encoding='utf-8',newline='') as handle:
            w=csv.writer(handle);w.writerow(['Op Name','Task Type','Op Type','Task Duration(us)','aic_mac_ratio'])
            for typ in ['AI_CORE','AI_VECTOR_CORE']:
                for i in range(21):w.writerow(['bmms11_test',typ,'SyntheticTestOnly',10+i,0.5])
            w.writerow(['unrelated','AI_CORE','Other',999,0])
        p=subprocess.run([sys.executable,str(PROBE/'profile_summary.py'),str(d),'--skip','11'],capture_output=True,text=True,check=True)
        report=json.loads(p.stdout);assert len(report['groups'])==2
        for group in report['groups']:
            assert group['count']==10 and group['median_us']==25.5 and group['op_type']=='SyntheticTestOnly'
            assert group['pipeline_metrics_median']=={'aic_mac_ratio':0.5}
        assert any('multiple kernels/task types' in w for w in report['warnings'])
    result={'prepare_only_inputs_verified':22,'quantized_physical_layout_golden_verified':True,
        'synthetic_parser_separates_task_types':True,'parser_discards_11_warmup_records':True,
        'device_execution_performed':False,'cann_compiled':False,
        'files':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(PROBE.iterdir()) if p.is_file()}}
    (HERE/'PROBE_OFFLINE_CHECKS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))

if __name__=='__main__':main()
