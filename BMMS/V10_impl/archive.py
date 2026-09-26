"""Stage reviewed V10 sources and raw offline evidence in the CANN checkout."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    for name,item in checks['runs'].items():
        raw=HERE/'cpu_build'/(name+'_run.stdout.txt')
        if raw.exists():
            data=json.loads(raw.read_text(encoding='utf-8'))
            data['source_sha256']=item['source_sha256']
            (HERE/(name+'_CPU_RESULT.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ref=ROOT/'V10_reference_devkit'
    if (ref/'.git').exists():
        commit=subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()
        files=['include/adv_api/matmul/matmul_client.h',
               'impl/adv_api/detail/matmul/stage/copy_cube_out/copy_cube_out_fixpipe.h',
               'impl/adv_api/detail/matmul/stage/copy_cube_out/copy_cube_out_utils.h']
        info={'repository':'https://gitcode.com/cann/asc-devkit','commit':commit,
              'status':'official development source; NOT the installed competition SDK',
              'files':[{'path':p,'sha256':hashlib.sha256((ref/p).read_bytes()).hexdigest()} for p in files],
              'public_target_docs':[
                  'https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0639.html',
                  'https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0614.html'],
              'findings':['synchronous LocalTensor output uses GM address and CopyToUB on c220',
                          'sequential ND output stride equals actual baseWidth',
                          'ND copies a flat block; only semantic values are consumed by V10'],
              'not_established':['competition CANN compilation','competition runtime tail layout','hardware synchronization','speedup']}
        (HERE/'API_EVIDENCE.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    subprocess.run([sys.executable,str(ROOT/'V9_impl/archive_to_repo.py'),'--repo',str(args.repo.resolve()),'--with-v10'],check=True)

if __name__=='__main__':main()
