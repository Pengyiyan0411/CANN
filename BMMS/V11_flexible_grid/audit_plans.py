"""Compile actual host planners into an independent traversal/oracle check."""
from pathlib import Path
import importlib.util,json,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
spec=importlib.util.spec_from_file_location('flex_build',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
def source(mutation=None):
    old=(ROOT/'V11_grid_packets/grid_checks.cpp.in').read_text(encoding='utf-8')
    preamble=old[:old.index('// INSERT_PLANS')];walk=build.between(old,'void need(','int main()')
    parts=[]
    for ns,path in [('baseline',build.OLD_FRAGMENT),('r13',HERE/'R13_macro_fragment.asc'),('r14',HERE/'R14_macro_fragment.asc')]:
        s=build.between(path.read_text(encoding='utf-8'),'namespace bmms11r2 {','static inline uint64_t RingBytes(')
        if mutation and ns=='r13':s=build.once(s,*mutation)
        parts.append(s.replace('namespace bmms11r2 {','namespace '+ns+' {',1)+'}\n')
    return (HERE/'grid_checks.cpp.in').read_text(encoding='utf-8').replace('// INSERT_PREAMBLE_AND_PLANS',preamble+'\n'.join(parts)+walk)
def check(mutation=None,label='grid',expected=None):
    BUILD.mkdir(exist_ok=True);compiler=shutil.which('g++');assert compiler
    cpp=BUILD/(label+'.cpp');exe=BUILD/(label+'.exe');build.write(cpp,source(mutation))
    for stage,args in [('compile',[compiler,'-std=c++20','-O2',str(cpp),'-o',str(exe)]),('run',[str(exe)])]:
        r=subprocess.run(args,cwd=BUILD,capture_output=True,text=True,timeout=120)
        build.write(BUILD/(label+'_'+stage+'.stdout'),r.stdout);build.write(BUILD/(label+'_'+stage+'.stderr'),r.stderr)
        if expected and stage=='run':
            assert r.returncode!=0 and expected in r.stderr,(r.returncode,r.stderr)
            return {'rejected':True,'exit_code':r.returncode,'stderr':r.stderr.strip()}
        assert r.returncode==0,(stage,r.stderr)
    return json.loads(r.stdout)
def main():
    build.verify();data=check();assert min(data['changed'].values())>0
    data['negative_controls']={
        'kept_old_launch_count':check(('candidate.blocks=candidate.tasks;','candidate.blocks=cores;'),'negative_blocks','inconsistent launch/tasks'),
        'dropped_last_task':check(('candidate.tasks=B*pm*pn;','candidate.tasks=B*pm*pn-1;'),'negative_task','inconsistent launch/tasks')}
    data['source_sha256']={p.relative_to(ROOT).as_posix():build.sha(p) for p in [build.OLD_FRAGMENT,HERE/'R13_macro_fragment.asc',HERE/'R14_macro_fragment.asc']}
    build.write(HERE/'GRID_CHECKS.json',json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2))
if __name__=='__main__':main()
