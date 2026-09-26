"""Assemble R01 on the frozen P01 control; verify every fallback byte."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V11_SubmitPack'
BASE=ROOT/'next_stage/C00_P01_CONTROL.asc'
BASE_SHA='138cb8066c437f9373eec4e08340b77367eedc8440ebbfeb078944cba874a969'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b,1)

def main():
    assert sha(BASE)==BASE_SHA
    base=BASE.read_text(encoding='utf-8')
    consumer=base[base.index('class SmallKConsumer {'):base.index('template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry')]
    consumer=consumer.replace('SmallKConsumer','RowMaxConsumer').replace('NativePlan','Plan')
    consumer=once(consumer,'mBegin=mt0*TM,mEnd=MinI(mt1*TM,p.M)','mBegin=mt0*AM,mEnd=MinI(mt1*AM,p.M)')
    consumer=once(consumer,'nBegin=nt0*TN,nEnd=MinI(nt1*TN,p.N)','nBegin=nt0*BN,nEnd=MinI(nt1*BN,p.N)')
    fragment=once((HERE/'reuse_fragment.asc.in').read_text(encoding='utf-8'),'// @ROW_MAX_CONSUMER@',consumer)
    (HERE/'reuse_fragment.asc').write_text(fragment,encoding='utf-8',newline='\n')
    entry='extern "C" void run_kernel('
    hook='    if(bmms11::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    needle='    const int cores=availableCoreNum>0&&availableCoreNum<=64?int(availableCoreNum):1;\n'
    source=once(base,entry,fragment+'\n'+entry)
    source=once(source,needle,needle+hook)
    header='// R01_REUSE_2X2: P01 fallbacks + V11 macro operand reuse. Device validation pending.\n'
    source=header+source
    restored=source[len(header):].replace(fragment+'\n','',1).replace(hook,'',1)
    assert restored==base and source.count(entry)==1
    assert '#define ASCENDC_CUBE_ONLY' not in source
    OUT.mkdir(exist_ok=True)
    dest=OUT/'R01_REUSE_2X2.asc';dest.write_text(source,encoding='utf-8',newline='\n')
    control=OUT/'P01_CONTROL.asc';control.write_bytes(BASE.read_bytes())
    manifest={'variant':'R01_REUSE_2X2','file':dest.name,'sha256':sha(dest),
        'baseline':{'file':control.name,'sha256':sha(control)},
        'fallback_body_restored_exactly':True,'source_template_sha256':sha(HERE/'reuse_fragment.asc.in'),
        'fragment_sha256':sha(HERE/'reuse_fragment.asc'),
        'micro_mnk':[64,128,64],'macro_mnk':[128,256,256],
        'explicit_bytes':{'L1':393216,'L0A':32768,'L0B':65536,'L0C':131072,'max_consumer_UB':131744,'ring_per_group':65536},
        'cann_compiled':False,'npu_tested':False,'known_precision_counterexamples_remain':True}
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
