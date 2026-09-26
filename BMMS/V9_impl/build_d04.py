"""Build M128/N128 B-reuse producer and its matching row-max consumer."""
from pathlib import Path
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V9_D04'


def once(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b,1)


def main():
    oldfile=HERE/'dense_c2_fragment.asc'
    assert hashlib.sha256(oldfile.read_bytes()).hexdigest()=='c21fe8f9c88b60dcd1e5c716fcf77569dfe08c2702a4dfd9c0577262b8c8631d'
    old=oldfile.read_text(encoding='utf-8')
    base=(ROOT/'next_stage/C00_P01_CONTROL.asc').read_text(encoding='utf-8')
    consumer=base[base.index('class SmallKConsumer {'):base.index('template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry')]
    consumer=consumer.replace('SmallKConsumer','RowMaxConsumer').replace('NativePlan','Plan')
    src=old.replace('bmms9d','bmms9r').replace('BMMS9D','BMMS9R')
    src=once(src,'// BMMS V9-D03: frozen D01 K128 with two independent L0C slots.',
             '// BMMS V9-D04: M128/N128/K128 blocks reuse B across more output rows.')
    src=once(src,'// Uses the existing bmms83 row-max consumer and its exact tile traversal.',
             '// Uses a matching M128 row-max consumer; no external CATLASS dependency.')
    src=once(src,'constexpr int32_t TM=64, TN=128, AM=256, BN=512, KB=BMMS9R_K_BLOCK;',
             'constexpr int32_t TM=128, TN=128, AM=256, BN=512, KB=BMMS9R_K_BLOCK;')
    src=once(src,'static_assert(KB==64||KB==128,"BMMS9R_K_BLOCK must be 64 or 128");',
             'static_assert(KB==128,"D04 freezes K stage at 128");')
    src=once(src,'using Plan=bmms83::NativePlan;','using Plan=bmms83::NativePlan;\nusing bmms83::MinI;')
    src=once(src,'            AscendC::Mmad(cc,aa,bb,q);',
             '            AscendC::Mmad(cc,aa,bb,q);\n            // Small output tiles need an explicit dependency between K MMADs.\n            // See official Mmad documentation and CATLASS v1.4 tile_mmad.hpp.\n            if((mr/16)*(nr/16)<10)AscendC::PipeBarrier<PIPE_M>();')
    src=once(src,'#ifndef BMMS9_CPU_TEST',consumer+'\n#ifndef BMMS9_CPU_TEST')
    src=once(src,'bmms83::SmallKConsumer op;','RowMaxConsumer op;')
    src=src.replace('it must match bmms83::SmallKConsumer for every task and tail.',
                    'it must match this namespace\'s RowMaxConsumer for every task and tail.')
    fragment=HERE/'dense_m128_fragment.asc';fragment.write_text(src,encoding='utf-8',newline='\n')
    parent_path=ROOT/'BMMS_V9_D03/D03_DENSE_K128_C2.asc'
    assert hashlib.sha256(parent_path.read_bytes()).hexdigest()=='17351577d7a4928d3777c29a547631e52ddf3cf4667528d7a1b4c99be6153fd9'
    parent=parent_path.read_text(encoding='utf-8')
    output=once(parent,old,src)
    output=once(output,'#define BMMS9D_K_BLOCK 128','#define BMMS9R_K_BLOCK 128')
    output=once(output,'// D03_DENSE_K128_C2: BMMS V9 experimental candidate.',
                '// D04_DENSE_M128_N128: BMMS V9 experimental candidate.')
    output=once(output,'if(bmms9d::TryLaunch(a,b,y,','if(bmms9r::TryLaunch(a,b,y,')
    entry='extern "C" void run_kernel('
    assert output.count(entry)==1
    assert output[output.index(entry):].replace('bmms9r::TryLaunch','bmms9d::TryLaunch')==parent[parent.index(entry):]
    OUT.mkdir(exist_ok=True)
    dest=OUT/'D04_DENSE_M128_N128.asc';dest.write_text(output,encoding='utf-8',newline='\n')
    (HERE/'d04_delta.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),src.splitlines(True),
        fromfile='D03/dense_c2_fragment.asc',tofile='D04/dense_m128_fragment.asc')),encoding='utf-8')
    manifest={'variant':'D04_DENSE_M128_N128','file':dest.name,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
        'fragment_sha256':hashlib.sha256(fragment.read_bytes()).hexdigest(),'comparison':'D03_DENSE_K128_C2',
        'comparison_sha256':hashlib.sha256(parent_path.read_bytes()).hexdigest(),
        'tile':[128,128,128],'C_slots':2,'public_domain_unchanged':True,
        'changes':['M tile 64 -> 128 for B reuse','matching producer/consumer and plan geometry','small-tile PIPE_M dependency'],
        'explicit_bytes':{'L1':131072,'L0A':65536,'L0B':65536,'L0C':131072,'max_consumer_UB':165152,'ring_per_group':131072},
        'cann_compiled':False,'npu_tested':False,'known_numeric_counterexamples_remain':True}
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
