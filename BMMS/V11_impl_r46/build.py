"""R46: original-stride SDK fast body + overlapping full-width N tail.

Only an isolated module and a guarded dispatch hook are added to frozen R43.
The original R43 implementation is recoverable byte-for-byte by removing them.
"""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'V11_analysis_r43/R43_CASE8_PADDED_MACRO.asc'
OUT = ROOT / 'BMMS_V11_R46'
NAME = 'R46_CASE8_FAST_MAIN_TAIL.asc'
EXPECTED = '15e2c9a0f73e7534c26400107389dcd8e5cf685b5f6f477c7a3684ad3991df2d'
HEADER = ('// R46_CASE8_FAST_MAIN_TAIL: original-stride fast body + overlapping N tail.\r\n'
          '// Based on frozen R43. Candidate only: real CANN/NPU validation pending.\r\n')
HOOK = '    if(bmms_c8f46::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
MODULE_BEGIN = '// BMMS_C8F46_BEGIN\n'
MODULE_END = '// BMMS_C8F46_END\n\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(s, old, new):
    assert s.count(old) == 1, repr(old)
    return s.replace(old, new, 1)


def function(s, marker):
    start = s.index(marker)
    brace = s.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (s[end] == '{') - (s[end] == '}')
        end += 1
    return s[start:end]


def make_module(original):
    src = original.replace('\r\n', '\n')
    start = src.index('template <typename T, bool TA, bool TB>\nclass FastFusedDevice')
    end = src.index('// BMMS_HOST_PLAN_BEGIN', start)
    device = src[start:end]
    device = once(device, 'const Plan& plan', 'const MainTailPlan& plan')
    device = once(device, '        p = plan;', '        p = plan.grid;\n        realN = plan.realN;')
    device = device.replace('int64_t(p.B)*p.K*p.N', 'int64_t(p.B)*p.K*realN')
    device = device.replace('int64_t(batch)*p.K*p.N', 'int64_t(batch)*p.K*realN')
    device = once(device, 'mm.SetOrgShape(p.M, p.N, p.K, p.K);',
                  'mm.SetOrgShape(p.M, realN, p.K, p.K);')
    device = once(device,
                  '''            // Fast-plan invariant: p.nTiles is exactly divisible by p.pN.
            const int32_t nTilesLocal = p.nTiles/p.pN;
            const int32_t n0 = ns*p.nPitch;
            const int32_t cols = p.nPitch;''',
                  '''            // Partition full-width tiles; shard lengths may differ by one
            // tile. The last shard shifts left by (virtualN-realN), so it
            // ends at realN without reading or reducing a padded column.
            // At most vecN-1 real columns overlap the preceding shard.
            // Max is idempotent, so the normal row-max merge removes overlap.
            const int32_t nTileBegin = (ns*p.nTiles)/p.pN;
            const int32_t nTileEnd = ((ns+1)*p.nTiles)/p.pN;
            const int32_t nTilesLocal = nTileEnd-nTileBegin;
            const int32_t cols = nTilesLocal*p.vecN;
            const int32_t n0 = MinI(nTileBegin*p.vecN, realN-cols);''')
    device = once(device, '    Plan p;', '    Plan p;\n    int32_t realN;')
    device = once(device, 'TCubeTiling td, Plan p)', 'TCubeTiling td, MainTailPlan p)')
    device = device.replace('execute ONE FP32 ReduceSum over all M rows. No full C reaches GM.',
                            'execute ONE FP32 ReduceSum over all M rows. SDK may stage C in GM.')
    tiler = function(src, 'static inline bool GetFastTiling(')
    tiler = once(tiler, 'static inline bool GetFastTiling(', 'static inline bool GetTiling(')
    tiler = once(tiler, 'const Plan& p, int32_t dtype, bool ta, bool tb, TCubeTiling& td)',
                 'const MainTailPlan& plan, int32_t dtype, bool ta, bool tb, TCubeTiling& td)')
    tiler = once(tiler, '{\n    if (p.blocks', '{\n    const Plan& p=plan.grid;\n    if (p.blocks')
    tiler = once(tiler, 't.SetOrgShape(p.M, p.N, p.K);',
                 't.SetOrgShape(p.M, plan.realN, p.K); // original physical B stride')
    tiler = once(tiler, 'return FlatFastStream(p, td)', 'return ValidStream(p, td)')
    tiler = tiler.replace('SetSingleShape only shrinks M on the final uneven M-shard.',
                          'SetSingleShape shrinks M and N for uneven partitions; N stays a full tile multiple.')
    model = (HERE/'host.inc').read_text(encoding='utf-8')
    launch = (HERE/'launch.inc').read_text(encoding='utf-8')
    module = MODULE_BEGIN + '''// R46 is confined to the existing R43 metadata domain with ragged N.
// No whole-input padded copies. Each worker uses one registered SDK object and
// one Matmul call for its full-width shard. The last N shard overlaps the body.
// No claim of hardware L0C->UB direct output: the SDK may stage through GM.
namespace bmms_c8f46 {
using bmmmaxsum_v43::Plan;
using bmmmaxsum_v43::MinI;
using bmmmaxsum_v43::Fence;
using bmmmaxsum_v43::NEG_INF;
using bmmmaxsum_v43::CeilDiv;
using bmmmaxsum_v43::MinH;
using bmmmaxsum_v43::BuildPlan;
using bmmmaxsum_v43::FastPlanCost;
using bmmmaxsum_v43::FastAppUbBytes;
using bmmmaxsum_v43::PartialBytes;
using bmmmaxsum_v43::FAST_C_FLOATS;
using bmmmaxsum_v43::SYSTEM_WORKSPACE_BYTES;

struct MainTailPlan {
    Plan grid; // logical N is the virtual tile extent, NOT the physical stride
    int32_t realN;
};

''' + model + '\n' + device + '\n' + tiler + '\n} // namespace bmms_c8f46\n\n' + launch + MODULE_END
    return module


def strip_additions(candidate):
    assert candidate.startswith(HEADER)
    stripped = candidate[len(HEADER):]
    start = stripped.index(MODULE_BEGIN)
    end = stripped.index(MODULE_END, start) + len(MODULE_END)
    stripped = stripped[:start] + stripped[end:]
    return once(stripped, HOOK, '')


def main():
    raw = BASE.read_bytes()
    assert sha(raw) == EXPECTED, 'R43 baseline hash changed'
    original = raw.decode('utf-8')
    module = make_module(original)
    candidate = once(original, 'extern "C" void run_kernel(', module + 'extern "C" void run_kernel(')
    r43_hook = '    if(bmms_c8p43::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
    candidate = HEADER + once(candidate, r43_hook, HOOK + r43_hook)
    assert strip_additions(candidate).encode('utf-8') == raw
    OUT.mkdir(exist_ok=True)
    dest = OUT/NAME
    if dest.exists():
        assert strip_additions(dest.read_bytes().decode('utf-8')).encode('utf-8') == raw
    encoded = candidate.encode('utf-8')
    dest.write_bytes(encoded)
    (OUT/'CONTROL_R43.asc').write_bytes(raw)
    (OUT/'R43_to_R46.diff').write_text(''.join(difflib.unified_diff(
        original.replace('\r\n','\n').splitlines(True),
        candidate.replace('\r\n','\n').splitlines(True),
        fromfile='R43_CASE8_PADDED_MACRO.asc',tofile=NAME)),encoding='utf-8',newline='\n')
    manifest = {
        'candidate': NAME, 'candidate_sha256': sha(encoded),
        'baseline': BASE.name, 'baseline_sha256': EXPECTED,
        'baseline_case8_us_user_reported': 62.45,
        'baseline_restored_byte_identically_after_removing_R46_additions': True,
        'R45_PACK_TAIL_ZERO_included': False,
        'dispatch_guard': 'R43 Eligible && N % 16 != 0',
        'CANN_compiled': False, 'NPU_tested': False,
        'candidate_case8_us': None,
    }
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
