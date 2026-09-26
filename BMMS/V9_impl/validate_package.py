"""Check packaging provenance and score handling using explicitly synthetic inputs."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import zipfile
import record_results as recorder

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PACK=ROOT/'BMMS_V9_SubmitPack'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((PACK/'MANIFEST.json').read_text(encoding='utf-8'))
    baseline=ROOT/'next_stage/C00_P01_CONTROL.asc'
    assert baseline.read_bytes()==(PACK/manifest['control']['file']).read_bytes()
    assert digest(baseline)==manifest['baseline_sha256']==manifest['control']['sha256']
    assert manifest['cann_compiled'] is False and manifest['npu_tested'] is False
    cpu=json.loads((HERE/'cpu_checks.json').read_text(encoding='utf-8'))
    for kind,file in [('dense','dense_fragment.asc'),('splitk','splitk_fragment.asc')]:
        assert digest(HERE/file)==manifest['fragments'][kind]
        assert digest(HERE/file)==cpu['source_manifest'][kind]['source_sha256']
    for v in manifest['variants']:
        p=PACK/v['file'];source=p.read_text(encoding='utf-8')
        assert p.stat().st_size==v['bytes'] and digest(p)==v['sha256']
        assert source.count('extern "C" void run_kernel(')==1
        for hook in v['entry_hooks']:assert hook.strip() in source
        assert '#include "catlass/' not in source
        assert '#define ASCENDC_CUBE_ONLY' not in source
    with zipfile.ZipFile(ROOT/'BMMS_V9_提交实验包.zip') as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==11
        for entry in archive.namelist():
            assert archive.read(entry)==(PACK/Path(entry).name).read_bytes()
    for source in HERE.glob('*.py'):ast.parse(source.read_text(encoding='utf-8'),filename=str(source))
    # These synthetic fixtures verify result processing only. They are not
    # written to the submission results directory or presented as device runs.
    fixture={'variant':'D01_DENSE_K128','rows':[
        {'case':i+1,'status':'Pass','latency_us':latency} for i,latency in enumerate(recorder.P01)]}
    baseline_score=recorder.analyze(copy.deepcopy(fixture),manifest)
    assert abs(baseline_score['computed_score']-34.0598926624)<1e-7
    assert baseline_score['score_basis']=='frozen_historical_T_not_current_ranking'
    failed=copy.deepcopy(fixture);failed['rows'][3]['status']='WA'
    assert recorder.analyze(failed,manifest)['computed_score'] is None
    error=recorder.analyze({'variant':'D01_DENSE_K128','compile_error':'synthetic'},manifest)
    assert error['score_basis']=='compile_failed' and error['computed_score'] is None
    duplicate=copy.deepcopy(fixture);duplicate['rows'][2]['case']=1
    invalid=copy.deepcopy(fixture);invalid['rows'][2]['latency_us']=float('nan')
    for bad in (duplicate,invalid):
        try:recorder.analyze(bad,manifest)
        except ValueError:pass
        else:raise AssertionError('invalid result accepted')
    stale=copy.deepcopy(fixture);stale['rows'][0]['latency_us']=1.0
    assert recorder.analyze(stale,manifest)['computed_score'] is None
    current=copy.deepcopy(fixture)
    for row in current['rows']:row['best_us']=row['latency_us']
    current_score=recorder.analyze(current,manifest)
    assert current_score['computed_score']==100 and current_score['score_basis']=='provided_current_T'
    summary={'package_verified':True,'baseline_unchanged':True,'variants':len(manifest['variants']),
             'archive_entries':11,'synthetic_recorder_cases':7,
             'cann_compiled':False,'npu_tested':False,
             'archive_sha256':digest(ROOT/'BMMS_V9_提交实验包.zip')}
    (HERE/'package_checks.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
