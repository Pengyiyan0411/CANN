"""Make a single-variable K128 / double-L0C diagnostic from frozen D01."""
from pathlib import Path
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V9_D03'


def once(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new,1)


def main():
    src=(HERE/'dense_fragment.asc').read_text(encoding='utf-8')
    assert hashlib.sha256((HERE/'dense_fragment.asc').read_bytes()).hexdigest()=='e2455c63a4a1da3eed20ab770f73181c14539aa501443b3826fdfd38972d1698'
    new=once(src,'// BMMS V9-D experimental full-K native Cube path.',
             '// BMMS V9-D03: frozen D01 K128 with two independent L0C slots.')
    new=once(new,'l0Free[2],cReady,cFree;','l0Free[2],cReady,cFree[2];')
    new=once(new,'// Single L0C: no new MMAD may reuse it until the preceding Fixpipe\n        // has finished reading it. This is independent of the GM ring credit.\n        if(seq>0)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);',
             '// Two L0C slots: wait only when reusing the same C slot. The\n        // other slot may still be read by Fixpipe while this tile accumulates.\n        const int cSlot=seq&1;\n        if(seq>=2)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[cSlot]);')
    new=once(new,'auto cc=cBuf.template Get<float>();','auto cc=cBuf.template Get<float>()[cSlot*TM*TN];')
    new=once(new,'AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree);','AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree[cSlot]);')
    new=once(new,'cFree=pipe_->AllocEventID<AscendC::HardEvent::FIX_M>();',
             'for(int s=0;s<2;++s)cFree[s]=pipe_->AllocEventID<AscendC::HardEvent::FIX_M>();')
    new=once(new,'pipe->InitBuffer(cBuf,TM*TN*sizeof(float));','pipe->InitBuffer(cBuf,2*TM*TN*sizeof(float));')
    new=once(new,'if(seq>0)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);',
             'for(int s=0;s<bmms83::MinI(2,seq);++s)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[s]);')
    new=once(new,'pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree);',
             'for(int s=0;s<2;++s)pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree[s]);')
    fragment=HERE/'dense_c2_fragment.asc';fragment.write_text(new,encoding='utf-8',newline='\n')
    d01=ROOT/'BMMS_V9_SubmitPack/D01_DENSE_K128.asc'
    assert hashlib.sha256(d01.read_bytes()).hexdigest()=='5b5204fc42ac174de5b30bfc20e03094311d56ffa3de2d5b4e5fe536d7580375'
    parent=d01.read_text(encoding='utf-8')
    output=once(parent,src,new)
    output=once(output,'// D01_DENSE_K128: BMMS V9 experimental candidate.',
                '// D03_DENSE_K128_C2: BMMS V9 experimental candidate.')
    assert '#define BMMS9D_K_BLOCK 128' in output
    assert output.count('extern "C" void run_kernel(')==1
    assert output[output.index('extern "C" void run_kernel('):]==parent[parent.index('extern "C" void run_kernel('):]
    OUT.mkdir(exist_ok=True)
    path=OUT/'D03_DENSE_K128_C2.asc';path.write_text(output,encoding='utf-8',newline='\n')
    diff=''.join(difflib.unified_diff(src.splitlines(True),new.splitlines(True),fromfile='D01/dense_fragment.asc',tofile='D03/dense_c2_fragment.asc'))
    (HERE/'d03_delta.diff').write_text(diff,encoding='utf-8',newline='\n')
    manifest={'variant':'D03_DENSE_K128_C2','file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
              'comparison':'D01_DENSE_K128','comparison_sha256':hashlib.sha256(d01.read_bytes()).hexdigest(),
              'fragment_sha256':hashlib.sha256(fragment.read_bytes()).hexdigest(),
              'single_change':'L0C slots 1 -> 2 with per-slot FIX_M lifetime',
              'k_block':128,'explicit_L0C_bytes':65536,'host_entry_unchanged':True,
              'cann_compiled':False,'npu_tested':False,'known_numeric_counterexamples_remain':True}
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
