"""Independent R04 descendants: conservative macro grid balance and native packets."""
from pathlib import Path
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V11_R07_R08'
BASE=ROOT/'BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc'
BASE_SHA='f39d584297451a4ef15d559b67879571e3de86e21007f4a02b0b3552a904a09c'
NAMES={'R07':'R07_BALANCED_GRID','R08':'R08_NATIVE_PACKETS'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a[:100])
    return s.replace(a,b,1)
def between(s,a,b):
    start=s.index(a)
    return s[start:s.index(b,start)]
def producer(s):return between(s,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer {','class SmallKConsumer {')
def consumer(s):return between(s,'class SmallKConsumer {','template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry')
def plan(s):return between(s,'static inline Plan MakePlan(','static inline uint64_t RingBytes(')
def ring(s):return between(s,'static inline uint64_t NativeRingBytes(','static inline uint64_t NativePartialBytes(')

def packet_producer(old):
    s=once(old,'if(seq>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+slot);',
        '''const int packet=seq/PACKET_TILES,packetSlot=packet&1,tileSlot=seq%PACKET_TILES;
        // Reserve the whole GM packet before its first Fixpipe; L0C still has two independent slots.
        if(tileSlot==0&&packet>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+packetSlot);''')
    s=once(s,'(int64_t(group)*2+slot)*TM*TN',
        '((int64_t(group)*2+packetSlot)*PACKET_TILES+tileSlot)*TM*TN')
    s=once(s,'AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+slot);++seq;',
        '''if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+packetSlot);
        ++seq;''')
    s=once(s,'int64_t(p.blocks)*2*TM*TN','int64_t(p.blocks)*2*PACKET_TILES*TM*TN')
    s=once(s,'''        for(int s=0;s<MinI(2,seq);++s){
            AscendC::CrossCoreWaitFlag<0x2>(FREE+s);''',
        '''        // Publish an incomplete last packet before waiting for any final FREE.
        if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+((seq/PACKET_TILES)&1));
        const int packets=(seq+PACKET_TILES-1)/PACKET_TILES;
        for(int s=0;s<MinI(2,packets);++s)AscendC::CrossCoreWaitFlag<0x2>(FREE+s);
        for(int s=0;s<MinI(2,seq);++s){''')
    return s

def packet_consumer(old):
    s=once(old,'class SmallKConsumer {','class SmallKPacketConsumer {')
    s=once(s,'int64_t(p.blocks)*2*TM*TN','int64_t(p.blocks)*2*PACKET_TILES*TM*TN')
    s=once(s,'const int nr=MinI(TN,br-no),ringSlot=seq&1;',
        'const int nr=MinI(TN,br-no),ringSlot=(seq/PACKET_TILES)&1,tileSlot=seq%PACKET_TILES;')
    s=once(s,'AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);',
        'if(tileSlot==0)AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);')
    s=once(s,'(int64_t(group)*2+ringSlot)*TM*TN+sub*vr*TN',
        '((int64_t(group)*2+ringSlot)*PACKET_TILES+tileSlot)*TM*TN+sub*vr*TN')
    s=once(s,'AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);',
        'if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);')
    s=once(s,'        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();',
        '''        // The final partial packet has no next tile to trigger the normal release.
        if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+((seq/PACKET_TILES)&1));
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();''')
    return s

def verify():
    assert sha(BASE)==BASE_SHA
    assert sha(OUT/'R04_CONTROL.asc')==BASE_SHA
    original=BASE.read_text(encoding='utf-8')
    macro=(ROOT/'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    r7=(OUT/(NAMES['R07']+'.asc')).read_text(encoding='utf-8')
    r7=once(r7,(HERE/'r07_macro_fragment.asc').read_text(encoding='utf-8'),macro)
    r8=(OUT/(NAMES['R08']+'.asc')).read_text(encoding='utf-8')
    r8=once(r8,(HERE/'native_ring.asc').read_text(encoding='utf-8'),ring(original))
    r8=once(r8,(HERE/'packet_producer.asc').read_text(encoding='utf-8'),producer(original))
    r8=once(r8,(HERE/'packet_consumer.asc').read_text(encoding='utf-8'),'')
    r8=once(r8,'if ASCEND_IS_AIV {SmallKPacketConsumer op;', 'if ASCEND_IS_AIV {SmallKConsumer op;')
    for s in [r7,r8]:assert s.split('\n',1)[1]==original.split('\n',1)[1]
    assert once((HERE/'r07_macro_fragment.asc').read_text(encoding='utf-8'),
                (HERE/'balanced_plan.asc').read_text(encoding='utf-8'),plan(macro))==macro
    return {'independent_R04_descendants':True,'R07_only_macro_host_plan_changed':True,
        'R08_only_native_small_K_output_protocol_changed':True,'shared_residual_consumer_preserved':True,
        'all_original_dispatch_guards_preserved':True,'R05_R06_changes_not_included':True}

def main():
    assert sha(BASE)==BASE_SHA
    original=BASE.read_text(encoding='utf-8')
    macro=(ROOT/'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    new_macro=once(macro,plan(macro),(HERE/'balanced_plan.asc').read_text(encoding='utf-8'))
    write(HERE/'r07_macro_fragment.asc',new_macro)
    r7=once(original,macro,new_macro)
    pp=packet_producer(producer(original));pc=packet_consumer(consumer(original))
    nr='constexpr int32_t PACKET_TILES=4;\n'+ring(original).replace('uint64_t(p.blocks)*2*TM*TN*4','uint64_t(p.blocks)*2*PACKET_TILES*TM*TN*4')
    write(HERE/'native_ring.asc',nr);write(HERE/'packet_producer.asc',pp);write(HERE/'packet_consumer.asc',pc)
    r8=once(original,ring(original),nr)
    r8=once(r8,producer(original),pp)
    r8=once(r8,consumer(original),consumer(original)+pc)
    r8=once(r8,'if ASCEND_IS_AIV {SmallKConsumer op;', 'if ASCEND_IS_AIV {SmallKPacketConsumer op;')
    OUT.mkdir(exist_ok=True)
    (OUT/'R04_CONTROL.asc').write_bytes(BASE.read_bytes())
    rows=[]
    for version,s in [('R07',r7),('R08',r8)]:
        name=NAMES[version];s=once(s,s.split('\n',1)[0],'// '+name+': independent R04 descendant; pending platform validation.')
        file=OUT/(name+'.asc');write(file,s)
        assert s.count('extern "C" void run_kernel(')==1 and '#define ASCENDC_CUBE_ONLY' not in s
        write(HERE/(name+'.diff'),''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='R04',tofile=name)))
        rows.append({'version':version,'file':file.name,'sha256':sha(file),'platform_result_received':False})
    manifest={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,
              'control':{'file':'R04_CONTROL.asc','sha256':BASE_SHA},'variants':rows,'proof':verify(),
              'cann_compiled_locally':False,'npu_tested_locally':False,'known_numerical_limitations_remain':True}
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
