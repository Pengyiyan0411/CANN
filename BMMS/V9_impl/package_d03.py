"""Validate the frozen D03 source/evidence pairing and package one candidate."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V9_D03'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    m=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks=json.loads((OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    assert sha(OUT/m['file'])==m['sha256']
    assert sha(HERE/'dense_c2_fragment.asc')==m['fragment_sha256']==checks['runs']['D03']['fragment_sha256']
    assert sha(ROOT/'BMMS_V9_SubmitPack/D01_DENSE_K128.asc')==m['comparison_sha256']
    assert checks['runs']['D01']['output_digest']==checks['runs']['D03']['output_digest']
    assert all(r['source_runs']==240 and r['strict_misses']==0 and r['combined_misses']==0 for r in checks['runs'].values())
    old=(HERE/'dense_fragment.asc').read_text(encoding='utf-8')
    new=(HERE/'dense_c2_fragment.asc').read_text(encoding='utf-8')
    for start,end in [('static inline bool Eligible','template<class T,bool TA,bool TB>'),
                      ('    __aicore__ inline void LoadStage','    __aicore__ inline void Emit'),
                      ('        for(int ki=0;ki<kCount;','        // Drain exactly'),
                      ('    __aicore__ inline void Process(){','        for(int s=0;s<bmms83::MinI(2,seq);++s)AscendC::CrossCoreWaitFlag'),
                      ('#define BMMS9D_KERNEL','} // namespace bmms9d\n#endif')]:
        assert old[old.index(start):old.index(end,old.index(start))]==new[new.index(start):new.index(end,new.index(start))]
    d01=(ROOT/'BMMS_V9_SubmitPack/D01_DENSE_K128.asc').read_text(encoding='utf-8')
    d03=(OUT/m['file']).read_text(encoding='utf-8')
    entry='extern "C" void run_kernel('
    assert d03.count(entry)==1 and d01[d01.index(entry):]==d03[d03.index(entry):]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    archive=ROOT/'BMMS_V9_D03_提交包.zip'
    names=[m['file'],'MANIFEST.json','CPU_CHECKS.json','README.md']
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            item=zipfile.ZipInfo('BMMS_V9_D03/'+name,date_time=(2026,9,26,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED;z.writestr(item,(OUT/name).read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in names:assert z.read('BMMS_V9_D03/'+name)==(OUT/name).read_bytes()
    report={'source_sha256':m['sha256'],'archive_sha256':sha(archive),
            'host_entry_and_input_k_loop_unchanged':True,'source_checks_per_candidate':240,
            'local_cann_compiled':False,'npu_tested':False}
    (HERE/'d03_package_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
