"""Verify D04 source, model evidence and unmodified fallback; create ZIP."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V9_D04'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    m=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    r=json.loads((OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    assert sha(OUT/m['file'])==m['sha256']
    assert sha(HERE/'dense_m128_fragment.asc')==m['fragment_sha256']==r['runs']['D04']['fragment_sha256']
    assert sha(ROOT/'BMMS_V9_D03/D03_DENSE_K128_C2.asc')==m['comparison_sha256']
    for row in r['runs'].values():assert row['source_runs']==283 and row['strict_misses']==row['combined_misses']==0
    assert r['bounded_output_records_compared_bitwise']
    assert r['runs']['D03']['output_bits_sha256']==r['runs']['D04']['output_bits_sha256']
    assert r['runs']['D03']['logical_input_bytes_fixture']==786432
    assert r['runs']['D04']['logical_input_bytes_fixture']==524288
    assert r['runs']['D04']['small_mmads_checked']==r['runs']['D04']['pipe_m_barriers']==4128
    parent=(ROOT/'BMMS_V9_D03/D03_DENSE_K128_C2.asc').read_text(encoding='utf-8')
    output=(OUT/m['file']).read_text(encoding='utf-8');entry='extern "C" void run_kernel('
    assert output.count(entry)==1
    assert output[output.index(entry):].replace('bmms9r::TryLaunch','bmms9d::TryLaunch')==parent[parent.index(entry):]
    old=(HERE/'dense_c2_fragment.asc').read_text(encoding='utf-8')
    new=(HERE/'dense_m128_fragment.asc').read_text(encoding='utf-8')
    a='static inline bool Eligible(';b='static inline Plan MakePlan('
    assert old[old.index(a):old.index(b)]==new[new.index(a):new.index(b)]
    base=(ROOT/'next_stage/C00_P01_CONTROL.asc').read_text(encoding='utf-8')
    consumer=base[base.index('class SmallKConsumer {'):base.index('template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry')]
    consumer=consumer.replace('SmallKConsumer','RowMaxConsumer').replace('NativePlan','Plan')
    assert consumer in new
    assert '#define ASCENDC_CUBE_ONLY' not in output and '#include "catlass/' not in output
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    archive=ROOT/'BMMS_V9_D04_提交包.zip';names=[m['file'],'MANIFEST.json','CPU_CHECKS.json','README.md']
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            i=zipfile.ZipInfo('BMMS_V9_D04/'+name,date_time=(2026,9,26,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(i,(OUT/name).read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in names:assert z.read('BMMS_V9_D04/'+name)==(OUT/name).read_bytes()
    report={'source_sha256':m['sha256'],'archive_sha256':sha(archive),
            'fallback_entry_unchanged_except_namespace':True,'consumer_body_matches_parameterized_P01':True,
            'source_checks_per_candidate':283,'local_cann_compiled':False,'npu_tested':False}
    (HERE/'d04_package_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
