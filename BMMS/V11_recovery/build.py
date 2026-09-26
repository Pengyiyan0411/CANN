"""Independent R08 descendants: residual packets and bounded one-wave macro planning."""
from pathlib import Path
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R09_R10'
BASE=ROOT/'BMMS_V11_R07_R08/R08_NATIVE_PACKETS.asc'
BASE_SHA='bc0e6c895ddcec2ca743204f221d6b0d6967b8944cec7b49dd0946775a103b27'
NAMES={'R09':'R09_RESIDUAL_PACKETS','R10':'R10_SINGLE_WAVE_GRID'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a[:120])
    return s.replace(a,b,1)
def between(s,a,b):
    start=s.index(a);return s[start:s.index(b,start)]
def plan(s):return between(s,'static inline Plan MakePlan(','static inline uint64_t RingBytes(')

def make_residual(old):
    s=once(old,'constexpr uint16_t READY=4, FREE=6;',
        'constexpr uint16_t READY=4, FREE=6;\nconstexpr int32_t PACKET_TILES=bmms83::PACKET_TILES;')
    s=once(s,'uint64_t(p.blocks)*2*TM*TN*4ULL','uint64_t(p.blocks)*2*PACKET_TILES*TM*TN*4ULL')
    s=once(s,'int64_t(p.blocks)*2*TM*TN','int64_t(p.blocks)*2*PACKET_TILES*TM*TN')
    s=once(s,'''        const int slot=seq&1;
        if(seq>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+slot);''',
        '''        const int packet=seq/PACKET_TILES,slot=packet&1,tileSlot=seq%PACKET_TILES;
        // GM packet ownership is independent of this producer's single L0C buffer.
        if(tileSlot==0&&packet>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+slot);''')
    s=once(s,'(int64_t(group)*2+slot)*TM*TN','((int64_t(group)*2+slot)*PACKET_TILES+tileSlot)*TM*TN')
    s=once(s,'AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+slot);',
        'if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+slot);')
    s=once(s,'        for(int s=0;s<bmms83::MinI(2,seq);++s)AscendC::CrossCoreWaitFlag<0x2>(FREE+s);',
        '''        // Publish the final short packet before waiting for its consumer credits.
        if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+((seq/PACKET_TILES)&1));
        const int packets=(seq+PACKET_TILES-1)/PACKET_TILES;
        for(int s=0;s<bmms83::MinI(2,packets);++s)AscendC::CrossCoreWaitFlag<0x2>(FREE+s);''')
    s=once(s,'if ASCEND_IS_AIV {bmms83::SmallKConsumer op;',
        'if ASCEND_IS_AIV {bmms83::SmallKPacketConsumer op;')
    s=s.replace('match bmms83::SmallKConsumer for every task and tail.',
                'match bmms83::SmallKPacketConsumer for every task and tail.')
    return s

def verify():
    assert sha(BASE)==BASE_SHA and sha(OUT/'R08_CONTROL.asc')==BASE_SHA
    original=BASE.read_text(encoding='utf-8')
    old_res=(ROOT/'V11_merge/residual_dense_fragment.asc').read_text(encoding='utf-8')
    old_macro=(ROOT/'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    r9=(OUT/(NAMES['R09']+'.asc')).read_text(encoding='utf-8')
    r10=(OUT/(NAMES['R10']+'.asc')).read_text(encoding='utf-8')
    res=(HERE/'residual_packet_fragment.asc').read_text(encoding='utf-8')
    macro=(HERE/'one_wave_macro_fragment.asc').read_text(encoding='utf-8')
    assert res==make_residual(old_res)
    assert once(macro,(HERE/'one_wave_plan.asc').read_text(encoding='utf-8'),plan(old_macro))==old_macro
    assert once(r9,res,old_res).split('\n',1)[1]==original.split('\n',1)[1]
    assert once(r10,macro,old_macro).split('\n',1)[1]==original.split('\n',1)[1]
    return {'independent_R08_descendants':True,'R08_native_packet_path_unchanged':True,
            'all_original_dispatch_guards_preserved':True,'R09_only_residual_output_protocol_changed':True,
            'R10_only_macro_host_plan_changed':True,'R07_multi_wave_search_not_included':True,
            'R10_macro_producer_consumer_unchanged':True}

def main():
    assert sha(BASE)==BASE_SHA
    original=BASE.read_text(encoding='utf-8')
    old_res=(ROOT/'V11_merge/residual_dense_fragment.asc').read_text(encoding='utf-8')
    old_macro=(ROOT/'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    res=make_residual(old_res)
    macro=once(old_macro,plan(old_macro),(HERE/'one_wave_plan.asc').read_text(encoding='utf-8'))
    write(HERE/'residual_packet_fragment.asc',res);write(HERE/'one_wave_macro_fragment.asc',macro)
    OUT.mkdir(exist_ok=True);(OUT/'R08_CONTROL.asc').write_bytes(BASE.read_bytes())
    rows=[]
    for v,s in [('R09',once(original,old_res,res)),('R10',once(original,old_macro,macro))]:
        s=once(s,s.split('\n',1)[0],'// '+NAMES[v]+': independent R08 descendant; pending platform validation.')
        path=OUT/(NAMES[v]+'.asc');write(path,s)
        assert s.count('extern "C" void run_kernel(')==1 and '#define ASCENDC_CUBE_ONLY' not in s
        write(HERE/(NAMES[v]+'.diff'),''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='R08',tofile=NAMES[v])))
        rows.append({'version':v,'file':path.name,'sha256':sha(path),'platform_result_received':False})
    manifest={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,
              'control':{'file':'R08_CONTROL.asc','sha256':BASE_SHA},'variants':rows,'proof':verify(),
              'R07_TLE_root_cause_confirmed':False,'cann_compiled_locally':False,'npu_tested_locally':False,
              'known_numerical_limitations_remain':True}
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
