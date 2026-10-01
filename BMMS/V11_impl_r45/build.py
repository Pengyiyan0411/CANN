"""Derive one packing-only candidate from the byte-frozen R43 source."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'V11_analysis_r43/R43_CASE8_PADDED_MACRO.asc'
OUT = ROOT / 'BMMS_V11_R45'
NAME = 'R45_CASE8_PACK_TAIL_ZERO.asc'
EXPECTED = '15e2c9a0f73e7534c26400107389dcd8e5cf685b5f6f477c7a3684ad3991df2d'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(s, old, new):
    assert s.count(old) == 1, repr(old)
    return s.replace(old, new, 1)


def function_span(s):
    start = s.index('__aicore__ inline void PackInputs(')
    end = s.index('\nclass MaskedRowMaxConsumer', start)
    return start, end


def main():
    raw = BASE.read_bytes()
    assert sha(raw) == EXPECTED
    source = raw.decode('utf-8')
    start, end = function_span(source)
    original_region = source[start:end]
    region_eol = '\r\n' if '\r\n' in original_region else '\n'
    old = original_region.replace('\r\n', '\n')
    # Retain every original pipeline fence, slot credit, and cross-core flag.
    new = once(old,
        '        const int realRows=MinI(rows,d.srcRows-row0);',
        '        const int remainingRows=d.srcRows-row0;\n'
        '        const int realRows=remainingRows>0?MinI(rows,remainingRows):0;')
    new = once(new,
        '        AscendC::Duplicate(x,half(0.0f),rows*d.dstCols);\n'
        '        if(realRows>0){\n'
        '            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe);\n'
        '            const int copiedPitch=(d.srcCols+15)/16*16;',
        '''        const int copiedPitch=(d.srcCols+15)/16*16;
        const int rowGap=d.dstCols-copiedPitch;
        // R45: DMA writes every real word and its explicit <=15-word suffix.
        // Only the extra 16-word row gap (K%32 == 8 or 16) needs vector zero.
        // One strided Duplicate covers all real rows; no per-row scalar loop.
        if(realRows>0&&rowGap>0){
            AscendC::Duplicate(x[copiedPitch],half(0.0f),uint64_t(rowGap),
                static_cast<uint8_t>(realRows),uint16_t(1),
                static_cast<uint8_t>(d.dstCols/16));
        }
        if(realRows<rows)
            AscendC::Duplicate(x[realRows*d.dstCols],half(0.0f),
                (rows-realRows)*d.dstCols);
        if(realRows>0){
            // Keep this even when no zeroing is needed: slot reuse still
            // requires MTE3 -> V -> MTE2 ordering before the next overwrite.
            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe);''')
    new = once(new,
        '            // to 32 requires a further 16 words, the pre-zeroed row gap keeps',
        '            // to 32 requires a further 16 words, the strided zero above keeps')
    new = new.replace('\n', region_eol)
    header = ('// R45_CASE8_PACK_TAIL_ZERO: independent packing-only ablation of frozen R43.\r\n'
              '// Baseline Case8: user-reported 62.45 us. Device validation is pending.\r\n')
    candidate = header + source[:start] + new + source[end:]
    assert candidate[len(header):start+len(header)] == source[:start]
    assert candidate[start+len(header)+len(new):] == source[end:]
    OUT.mkdir(exist_ok=True)
    dest = OUT / NAME
    encoded = candidate.encode('utf-8')
    if dest.exists():
        previous = dest.read_bytes().decode('utf-8')
        assert previous.startswith(header), 'Refusing to overwrite an unrelated file'
        previous = previous[len(header):]
        ps, pe = function_span(previous)
        assert previous[:ps] == source[:start] and previous[pe:] == source[end:]
    dest.write_bytes(encoded)
    control = OUT / 'CONTROL_R43.asc'
    if control.exists():
        assert control.read_bytes() == raw
    control.write_bytes(raw)
    diff = ''.join(difflib.unified_diff(source.splitlines(keepends=True),
        candidate.splitlines(keepends=True), fromfile='R43_CASE8_PADDED_MACRO.asc', tofile=NAME))
    (OUT/'R45_vs_R43.diff').write_text(diff, encoding='utf-8', newline='')
    manifest = {
        'candidate': NAME, 'candidate_sha256': sha(encoded),
        'baseline_sha256': sha(raw), 'change_scope': 'PackInputs only, plus identification comments',
        'source_outside_PackInputs_unchanged': True,
        'guard_planner_Cube_consumer_dispatch_unchanged': True,
        'all_original_event_and_cross_core_calls_retained': True,
        'CANN_compiled': False, 'NPU_tested': False,
        'user_baseline_case8_us': 62.45, 'candidate_case8_us': None,
        'sequence': ['R45 PACK_TAIL_ZERO (this candidate)',
                     'C_INTERIOR_FAST (pending R45 feedback)',
                     'PACK_IDENTITY_SKIP (pending earlier feedback)'],
    }
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
