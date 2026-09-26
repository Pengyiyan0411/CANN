"""Build two standalone contest candidates from one reviewed implementation."""
from pathlib import Path
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tile', choices=['64x128', '64x256', '128x128'], default='64x128')
    args = ap.parse_args()
    tm, tn = map(int, args.tile.split('x'))
    out = ROOT / ('BMMS_V10_SubmitPack' if args.tile == '64x128' else 'BMMS_V10_' + args.tile)
    out.mkdir(exist_ok=True)
    template = (HERE / 'streaming.asc.in').read_text(encoding='utf-8')
    items = []
    for name, split in [('F01_STREAM_M', 0), ('F02_STREAM_MN', 1)]:
        source = template.replace('@SPLIT_N@', str(split)).replace('@TILE_M@', str(tm)).replace('@TILE_N@', str(tn))
        assert '@' not in source and source.count('extern "C" void run_kernel(') == 1
        source = f'// {name}: V10 streaming candidate; {tm}x{tn}, selective Split-N={split}.\n' + source
        path = out / (name + '.asc')
        path.write_text(source, encoding='utf-8', newline='\n')
        items.append({'variant': name, 'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'bytes': path.stat().st_size, 'split_n': bool(split), 'tile_mn': [tm, tn]})
    manifest = {'family': 'V10', 'user_plan': 'V10_impl/USER_PLAN.md',
                'source_template_sha256': hashlib.sha256((HERE / 'streaming.asc.in').read_bytes()).hexdigest(),
                'cann_compiled': False, 'npu_tested': False, 'platform_submitted': False,
                'variants': items}
    (out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({'directory': str(out), **manifest}, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
