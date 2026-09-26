"""Build two independent R04 descendants: deferred max and full-macro MMAD."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'BMMS_V11_R05_R06'
BASE = ROOT / 'BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc'
BASE_SHA = 'f39d584297451a4ef15d559b67879571e3de86e21007f4a02b0b3552a904a09c'
NAMES = {'R05': 'R05_DEFERRED_MAX', 'R06': 'R06_MACRO_MMAD'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def once(text, old, new):
    assert text.count(old) == 1, (text.count(old), old)
    return text.replace(old, new, 1)


def between(text, start, end):
    a = text.index(start)
    return text[a:text.index(end, a)]


def consumer(text, macro=False):
    start = 'class RowMaxConsumer {' if macro else 'class SmallKConsumer {'
    end = '#ifndef BMMS11R2_CPU_TEST' if macro else 'template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry'
    return between(text, start, end)


def deferred(old):
    # AIV holds one 128-lane maximum vector per owned row, across ALL N panels.
    s = once(old, 'groupBuf,rowBuf,sumBuf;', 'groupBuf,sumBuf;')
    s = once(s, 'pipe->InitBuffer(groupBuf,(TM/2)*TN*4);pipe->InitBuffer(rowBuf,(TM/2)*4);',
             'pipe->InitBuffer(groupBuf,(AM/2)*TN*4);')
    s = once(s, 'auto acc=groupBuf.Get<float>();auto rows=rowBuf.Get<float>();auto run=runningBuf.Get<float>();',
             'auto allMax=groupBuf.Get<float>();auto run=runningBuf.Get<float>();')
    s = once(s, 'AscendC::Duplicate(run,bmmmaxsum_v43::NEG_INF,ar);AscendC::PipeBarrier<PIPE_V>();',
             '''// max over N panels commutes with max over the 128 vector lanes.
                AscendC::Duplicate(allMax,bmmmaxsum_v43::NEG_INF,(ar/2)*TN);AscendC::PipeBarrier<PIPE_V>();''')
    s = once(s, 'AscendC::Duplicate(acc,bmmmaxsum_v43::NEG_INF,vr*TN);AscendC::PipeBarrier<PIPE_V>();',
             'auto acc=allMax[(mo/2)*TN];')
    s = once(s, '''                            AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,vr*TN);
                            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);''', '''                            // A full-width DMA initializes every consumed element.
                            // TQue owns reuse; partial rows still need explicit -inf padding.
                            if(nr<TN){
                                AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,vr*TN);
                                bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
                            }''')
    fold = '''                        AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                        AscendC::Max(acc,acc,acc[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                        AscendC::WholeReduceMax(rows,acc,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                        AscendC::PipeBarrier<PIPE_V>();
                        AscendC::Max(run[mo+sub*vr],run[mo+sub*vr],rows,vr);AscendC::PipeBarrier<PIPE_V>();
'''
    s = once(s, fold, '')
    s = once(s, '                bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);', '''                // Destructive lane reduction happens only after the last N panel.
                for(int mo=0;mo<ar;mo+=TM){
                    const int vr=MinI(TM,ar-mo)/2;
                    auto acc=allMax[(mo/2)*TN];
                    AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                    AscendC::Max(acc,acc,acc[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::WholeReduceMax(run[mo+sub*vr],acc,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                    AscendC::PipeBarrier<PIPE_V>();
                }
                bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);''')
    return s


def macro_mmad(old):
    s = once(old, '// V11 R02: publish a completed 2x2 macro tile using one ring credit.',
             '// V11 R06: full 128x256 MMAD with the existing macro ring publication.')
    load = between(s, '        AscendC::LoadData2DParams la{};', '        AscendC::SetFlag<AscendC::HardEvent::MTE1_M>(l0Ready[s0]);')
    newload = '''        AscendC::LoadData2DParams la{};la.ifTranspose=TA;
        // Pack the whole A macro for Mmad(m=ar,k=kr0), with no per-micro padding.
        if(ar>kr0){
            la.repeatTimes=ar/16;la.srcStride=TA?kr1/16:1;la.dstGap=kr0/16-1;
            for(int j=0;j<kr0/16;++j){
                const int off=TA?(kk+j*16)*16:(kk/16+j)*ar*16;
                AscendC::LoadData(da[j*256],sa[off],la);
            }
        }else{
            la.repeatTimes=kr0/16;la.srcStride=TA?1:ar/16;
            for(int i=0;i<ar/16;++i){
                const int off=TA?i*kr1*16+kk*16:(kk/16)*ar*16+i*256;
                AscendC::LoadData(da[i*kr0*16],sa[off],la);
            }
        }
        AscendC::LoadData2DParams lb{};lb.ifTranspose=!TB;
        // Pack the whole B macro for Mmad(n=br), using the shorter loop axis.
        if(br<kr0){
            lb.repeatTimes=kr0/16;lb.srcStride=TB?br/16:1;lb.dstGap=br/16-1;
            for(int i=0;i<br/16;++i){
                const int off=TB?(kk/16)*br*16+i*256:i*kr1*16+kk*16;
                AscendC::LoadData(db[i*256],sb[off],lb);
            }
        }else{
            lb.repeatTimes=br/16;lb.srcStride=TB?1:kr1/16;
            for(int j=0;j<kr0/16;++j){
                const int off=TB?(kk/16+j)*br*16:(kk+j*16)*16;
                AscendC::LoadData(db[j*br*16],sb[off],lb);
            }
        }
'''
    s = once(s, load, newload)
    compute = between(s, '                for(int mo=0;mo<ar;mo+=TM){', '                // Reused A/B stay owned by M')
    s = once(s, compute, '''                // One instruction covers the complete macro; K accumulation order is unchanged.
                auto cc=cBuf.template Get<float>();
                AscendC::MmadParams q{};q.m=ar;q.n=br;q.k=kr0;q.cmatrixInitVal=(l0Count==0);
                AscendC::Mmad(cc,aa,bb,q);
                if((ar/16)*(br/16)<10)AscendC::PipeBarrier<PIPE_M>();
''')
    s = once(s, '// Reused A/B stay owned by M until all four output MMADs complete.',
             '// Both complete operands stay owned by M until the macro MMAD completes.')
    s = once(s, 'f.nSize=nr;f.mSize=mr;f.srcStride=mr;', 'f.nSize=nr;f.mSize=mr;f.srcStride=ar;')
    s = once(s, 'cBuf.template Get<float>()[ci*TM*TN],f);',
             'cBuf.template Get<float>()[(no/16)*ar*16+mo*16],f);')
    assert consumer(s, True) == consumer(old, True)
    return s


def verify():
    assert sha(BASE) == BASE_SHA
    original = BASE.read_text(encoding='utf-8')
    macro = (ROOT / 'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    assert original.count(macro) == 1
    for version, name in NAMES.items():
        source = (OUT / (name + '.asc')).read_text(encoding='utf-8')
        if version == 'R05':
            for kind, is_macro in [('macro', True), ('micro', False)]:
                new = (HERE / f'r05_{kind}_consumer.asc').read_text(encoding='utf-8')
                source = once(source, new, consumer(original, is_macro))
        else:
            new = (HERE / 'r06_macro_fragment.asc').read_text(encoding='utf-8')
            source = once(source, new, macro)
        assert source.split('\n', 1)[1] == original.split('\n', 1)[1], version
    return {'independent_R04_descendants': True, 'dispatch_and_workspace_unchanged': True,
            'R05_only_two_consumers_changed': True, 'R06_only_macro_producer_changed': True,
            'fallback_other_than_shared_native_consumer_preserved': True}


def main():
    assert sha(BASE) == BASE_SHA
    original = BASE.read_text(encoding='utf-8')
    macro = (ROOT / 'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    r05 = original
    for kind, is_macro in [('macro', True), ('micro', False)]:
        old = consumer(original, is_macro)
        new = deferred(old)
        write(HERE / f'r05_{kind}_consumer.asc', new)
        r05 = once(r05, old, new)
    r06_fragment = macro_mmad(macro)
    write(HERE / 'r06_macro_fragment.asc', r06_fragment)
    r06 = once(original, macro, r06_fragment)
    OUT.mkdir(exist_ok=True)
    entries = []
    for version, source, label in [('R05', r05, 'defer lane max until all N panels are consumed'),
                                  ('R06', r06, 'one full-macro MMAD per K0; packed L0 operands')]:
        name = NAMES[version]
        source = once(source, source.split('\n', 1)[0], '// ' + name + ': independent R04 descendant; ' + label + '.')
        path = OUT / (name + '.asc')
        write(path, source)
        assert source.count('extern "C" void run_kernel(') == 1
        assert '#define ASCENDC_CUBE_ONLY' not in source
        write(HERE / (name + '.diff'), ''.join(difflib.unified_diff(
            original.splitlines(True), source.splitlines(True), fromfile='R04', tofile=name)))
        entries.append({'version': version, 'file': path.name, 'sha256': sha(path), 'change': label,
                        'cann_compiled_locally': False, 'npu_tested_locally': False, 'platform_result_received': False})
    manifest = {'base': BASE.relative_to(ROOT).as_posix(), 'base_sha256': BASE_SHA,
                'base_platform_identity': 'R04 inferred from sole immediately preceding delivery; user said SOTA, no filename',
                'variants': entries, 'proof': verify(), 'known_numerical_limitations_remain': True}
    write(OUT / 'MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
