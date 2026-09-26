"""Assemble standalone Judge experiment files without modifying P01."""
from pathlib import Path
import hashlib
import json
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V9_SubmitPack'
BASE=ROOT/'next_stage/C00_P01_CONTROL.asc'
VARIANTS=[
    ('D01_DENSE_K128',128,False,'First dense experiment: full-K native producer; original P01 elsewhere.'),
    ('D02_DENSE_K64',64,False,'Same dense routing/consumer as D01; only K block changes to 64.'),
    ('S01_SMALL_NT_PAIR',None,True,'NT small-output Vector/K-shard path, hi/lo through Max and Sum; P01 elsewhere.'),
    ('M01_DENSE128_PLUS_SMALL',128,True,'Combined experiment; use only after independent D01/S01 assessment.'),
]


def sha(data): return hashlib.sha256(data).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    original=BASE.read_bytes()
    parent=original.decode('utf-8').replace('\r\n','\n')
    entry='extern "C" void run_kernel('
    assert parent.count(entry)==1
    offset=parent.index(entry)
    prefix,body=parent[:offset],parent[offset:]
    anchor='    const int cores=availableCoreNum>0&&availableCoreNum<=64?int(availableCoreNum):1;\n'
    assert body.count(anchor)==1
    dense=(HERE/'dense_fragment.asc').read_text(encoding='utf-8')
    small=(HERE/'splitk_fragment.asc').read_text(encoding='utf-8')
    manifest={'purpose':'User-authorized platform experiments; not a certified replacement baseline',
              'cann_compiled':False,'npu_tested':False,
              'precision_state':'KNOWN_NUMERICAL_COUNTEREXAMPLES; see README and precision review',
              'baseline_sha256':sha(original),
              'fragments':{'dense':sha((HERE/'dense_fragment.asc').read_bytes()),
                           'splitk':sha((HERE/'splitk_fragment.asc').read_bytes())},'variants':[]}
    baseline_name='P00_CONTROL_P01.asc'
    (OUT/baseline_name).write_bytes(original)
    for name,block,use_small,description in VARIANTS:
        definitions=''
        fragments=[]
        hooks=''
        if block:
            definitions+=f'#define BMMS9D_K_BLOCK {block}\n'
            fragments.append(dense)
        if use_small:
            definitions+='#define BMMS9S_MAX_MN 256\n'
            fragments.append(small)
            hooks+='    if(bmms9s::TryLaunch(a,ia,b,ib,y,iy,availableCoreNum,stream,ta,tb))return;\n'
        if block:
            hooks+='    if(bmms9d::TryLaunch(a,b,y,int32_t(B),int32_t(M),int32_t(N),int32_t(K),x.dtype,ta,tb,cores,stream))return;\n'
        patched_body=body.replace(anchor,anchor+hooks,1)
        assert patched_body.replace(hooks,'',1)==body
        banner=f'// {name}: BMMS V9 experimental candidate. Replace only official code/kernel.asc.\n'
        banner+='// CPU models checked; CANN compilation and NPU validation NOT performed.\n'
        banner+='// Known adversarial precision limitations are documented; no performance claim.\n'
        result=banner+definitions+'\n'+prefix+'\n'+'\n'.join(fragments)+'\n'+patched_body
        assert result.count(entry)==1
        assert '#include "catlass/' not in result
        assert '#define ASCENDC_CUBE_ONLY' not in result
        path=OUT/(name+'.asc')
        path.write_text(result,encoding='utf-8',newline='\n')
        manifest['variants'].append(dict(id=name,file=path.name,k_block=block,small_nt=use_small,
            bytes=path.stat().st_size,sha256=sha(path.read_bytes()),description=description,
            entry_hooks=hooks.strip().splitlines()))
    manifest['control']={'file':baseline_name,'bytes':len(original),'sha256':sha(original)}
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for source,name in [('submission_README.md','README_提交顺序.md'),
                        ('results_template.md','RESULTS_TEMPLATE.md'),('record_results.py','record_results.py'),
                        ('precision_review.md','PRECISION_REVIEW.md'),('cpu_checks.json','CPU_CHECKS.json')]:
        (OUT/name).write_bytes((HERE/source).read_bytes())
    include=[baseline_name]+[x['file'] for x in manifest['variants']]+[
        'MANIFEST.json','README_提交顺序.md','RESULTS_TEMPLATE.md','record_results.py',
        'PRECISION_REVIEW.md','CPU_CHECKS.json']
    archive=ROOT/'BMMS_V9_提交实验包.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in include:
            info=zipfile.ZipInfo('BMMS_V9_SubmitPack/'+name,date_time=(2026,9,26,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,(OUT/name).read_bytes())
    print(json.dumps({'archive':str(archive),'archive_bytes':archive.stat().st_size,
                      'variants':[{k:x[k] for k in ('id','bytes','sha256')} for x in manifest['variants']]},indent=2))


if __name__=='__main__': main()
