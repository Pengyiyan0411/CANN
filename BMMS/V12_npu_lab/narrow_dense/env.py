import os,json,platform,subprocess,torch,torch_npu
from pathlib import Path
r=dict(platform=platform.platform(),python=platform.python_version(),torch=torch.__version__,torch_npu=torch_npu.__version__,device_name=torch_npu.npu.get_device_name(0),device_count=torch_npu.npu.device_count(),cann=os.environ.get('ASCEND_HOME_PATH'))
Path('results/environment.json').write_text(json.dumps(r,indent=2))
Path('results/npu_smi.txt').write_text(subprocess.check_output(['npu-smi','info'],text=True))
print(r)
