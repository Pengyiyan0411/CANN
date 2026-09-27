"""Snapshot previous audit from git, then update the two mutable root guides."""
from pathlib import Path
import subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
PREVIOUS='862907825fd4e688d514752146f23a32c2cd246b'
AUDIT='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
def main():
    prior=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+AUDIT],cwd=ROOT/'CANN_archive')
    snapshot=ROOT/'audit_current/AUDIT_D24_L00_L05.md'
    if snapshot.exists():assert snapshot.read_bytes()==prior
    else:snapshot.write_bytes(prior)
    for new,old in [('CURRENT_README.md','README.md'),('CURRENT_AUDIT.md',AUDIT)]:
        (ROOT/old).write_bytes((HERE/new).read_bytes())
    print('Previous audit snapshotted; current README and audit updated.')
if __name__=='__main__':main()
