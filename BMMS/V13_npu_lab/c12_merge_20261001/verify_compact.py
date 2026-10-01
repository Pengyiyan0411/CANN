from pathlib import Path
import subprocess,hashlib,json,shutil,re
root=Path(__file__).resolve().parent
stage=root/'compact_verify';stage.mkdir(exist_ok=True)
main=(root/'main.asc').read_text()
(stage/'main.asc').write_text(main)
report={}
for mode in ('host','aicore'):
    results={}
    for version,filename in [('original','r2.asc'),('compact','r2_compact.asc')]:
        shutil.copyfile(root/filename,stage/'input.asc')
        cmd=['bisheng','--asc-aicore-lang','--npu-arch=dav-2201',f'--cce-{mode}-only','-E','-P',
             '-DBMMS_KERNEL_HEADER="input.asc"','-DBMMS_VARIANT="r2"',str(stage/'main.asc')]
        run=subprocess.run(cmd,cwd=stage,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        (stage/f'{mode}_{version}.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr[:4000]
        data=run.stdout;assert len(data)>1000000
        (stage/f'{mode}_{version}.ii').write_bytes(data)
        tokens=re.findall(rb'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^\s"\']+',data)
        canonical=b'\0'.join(tokens)
        (stage/f'{mode}_{version}.canonical').write_bytes(canonical)
        results[version]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'canonical_sha256':hashlib.sha256(canonical).hexdigest(),'token_chunks':len(tokens)}
    a=(stage/f'{mode}_original.ii').read_bytes();b=(stage/f'{mode}_compact.ii').read_bytes()
    ca=(stage/f'{mode}_original.canonical').read_bytes();cb=(stage/f'{mode}_compact.canonical').read_bytes()
    report[mode]={'byte_equal':a==b,'preprocessed_tokens_equal':ca==cb,'outputs':results}
    if ca!=cb:
        aa=ca.split(b'\0');bb=cb.split(b'\0')
        for i,(x,y) in enumerate(zip(aa,bb)):
            if x!=y:
                print('First token difference',mode,i,aa[max(0,i-3):i+4],bb[max(0,i-3):i+4]);break
(root/'results/compact_preprocess.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
