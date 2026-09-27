"""Snapshot the prior audit; update only the two designated current documents."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent
PREVIOUS='ede443dc2da2ee89a629443d4d8c8fcd7b3fabbc'
AUDIT='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
def main():
    old=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+AUDIT],cwd=ROOT/'CANN_archive')
    p=ROOT/'audit_current/AUDIT_R28.md'
    if p.exists():assert p.read_bytes()==old
    else:p.write_bytes(old)
    for template,target in [('CURRENT_README.md.in','README.md'),('CURRENT_AUDIT.md.in',AUDIT)]:
        (ROOT/target).write_bytes((HERE/template).read_bytes())
    print('Prior audit snapshotted; current README and audit updated.')
if __name__=='__main__':main()
