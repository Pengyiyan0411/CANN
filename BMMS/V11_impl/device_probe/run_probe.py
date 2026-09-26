"""Bounded P01/R01 diagnosis. Default prepares only; no implicit NPU use.

--build-only needs CANN but never runs ACL/NPU. A subsequent --execute reuses
matching binaries. Each invocation has a wall budget including its compilation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np
from precision_gate import assess

HERE=Path(__file__).resolve().parent
SOURCES={'P01':'P01_CONTROL.asc','R01':'R01_REUSE_2X2.asc'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def quantize(x,dt):
    if dt==1:
        q=x.astype(np.float16);return q.view(np.uint16),q.astype(np.float64)
    u=x.astype(np.float32).view(np.uint32)
    q=((u+0x7fff+((u>>16)&1))>>16).astype(np.uint16)
    return q,(q.astype(np.uint32)<<16).view(np.float32).astype(np.float64)

def prepare(out,cores):
    configs=[('macro',(1,128,256,256),1,False,False),
             ('tail',(1,144,272,288),min(cores,4),False,True),
             ('fallback',(1,32,128,64),cores,False,False),
             ('dense512',((cores+7)//8,512,512,512),cores,True,False),
             ('dense1024',((cores+31)//32,1024,1024,1024),cores,True,False)]
    result=[]
    for si,(name,shape,c,profile,negative) in enumerate(configs):
        B,M,N,K=shape
        for dt in (1,2):
            # Two profile shapes retain both dtypes; correctness covers all
            # layouts on the small full-macro and tail cases.
            rng=np.random.default_rng(261100+si*100+dt)
            a=rng.uniform(-1,1,(B,M,K));b=rng.uniform(-1,1,(B,K,N))
            a/=np.linalg.norm(a,axis=2,keepdims=True);b/=np.linalg.norm(b,axis=1,keepdims=True)
            if negative:a=np.abs(a);b=-np.abs(b)
            qa,fa=quantize(a,dt);qb,fb=quantize(b,dt)
            gold=(fa@fb).max(axis=2).sum(axis=1,dtype=np.float64).astype(np.float32)
            for ta,tb in ([(0,0)] if profile or name=='fallback' else [(0,0),(0,1),(1,0),(1,1)]):
                label=f'{name}_dt{dt}_{ta}{tb}';d=out/label;d.mkdir()
                x=np.ascontiguousarray(qa.swapaxes(1,2) if ta else qa)
                z=np.ascontiguousarray(qb.swapaxes(1,2) if tb else qb)
                x.tofile(d/'a.bin');z.tofile(d/'b.bin');gold.tofile(d/'golden.bin')
                macro_count=B*((M+127)//128)*((N+255)//256)
                changed=M>=128 and N>=256 and K>=256 and K%32==0 and macro_count>=c
                result.append(dict(id=label,shape=list(shape),dtype=dt,ta=ta,tb=tb,cores=c,
                    expect_R01=changed,profile=profile and dt==1,
                    a_sha256=sha(d/'a.bin'),b_sha256=sha(d/'b.bin'),golden_sha256=sha(d/'golden.bin')))
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cores',type=int,required=True,help='Actual available AIC groups (not AIV count)')
    mode=ap.add_mutually_exclusive_group();mode.add_argument('--execute',action='store_true');mode.add_argument('--build-only',action='store_true')
    ap.add_argument('--budget-seconds',type=int,default=1200)
    ap.add_argument('--arch',default='dav-2201')
    ap.add_argument('--out',type=Path,default=HERE/'run')
    args=ap.parse_args()
    if not 1<=args.cores<=64 or not 60<=args.budget_seconds<=1800:ap.error('invalid cores or budget')
    if (args.execute or args.build_only) and os.name!='posix':ap.error('CANN execution/build requires Linux')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();deadline=start+args.budget_seconds
    stamp=time.strftime('%Y%m%d_%H%M%S');log=out/('session_'+stamp);log.mkdir(exist_ok=False)
    state={'device_execution_requested':args.execute,'build_only':args.build_only,
        'cores':args.cores,'arch':args.arch,'budget_seconds':args.budget_seconds,'records':[],
        'source_sha256':{k:sha(HERE/v) for k,v in SOURCES.items()}}
    def save():
        state['elapsed_seconds']=time.monotonic()-start
        (log/'results.json').write_text(json.dumps(state,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    def command(cmd,label,allow_failure=False,cap=None):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise RuntimeError('wall budget exhausted; no more commands launched')
        p=subprocess.Popen(cmd,cwd=HERE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                           start_new_session=os.name=='posix')
        limit=min(remaining,cap) if cap else remaining
        try:so,se=p.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            if os.name=='posix':os.killpg(p.pid,signal.SIGKILL)
            else:p.kill()
            so,se=p.communicate()
            (log/(label+'.stdout.txt')).write_text(so,encoding='utf-8');(log/(label+'.stderr.txt')).write_text(se,encoding='utf-8')
            raise RuntimeError('time budget exhausted during '+label)
        (log/(label+'.stdout.txt')).write_text(so,encoding='utf-8');(log/(label+'.stderr.txt')).write_text(se,encoding='utf-8')
        if p.returncode and not allow_failure:raise RuntimeError(f'{label}: exit {p.returncode}; inspect logs')
        return so
    def validate(path,c,reps):
        y=np.fromfile(path,np.float32);ref=np.fromfile(out/c['id']/'golden.bin',np.float32)
        if y.size!=reps*c['shape'][0]:raise RuntimeError('wrong output count')
        y=y.reshape(reps,-1);checks=[assess(row,ref,y[0]) for row in y]
        return dict(strict=all(c['strict'] for c in checks),combined=all(c['combined'] for c in checks),
            repeat=all(c['bitwise_repeat'] for c in checks),finite=all(c['finite'] for c in checks),
            max_abs=max(c.get('max_abs',0) for c in checks),max_rel=max(c.get('max_rel',0) for c in checks))
    try:
        manifest=out/'inputs.json'
        if manifest.exists():
            data=json.loads(manifest.read_text(encoding='utf-8'))
            if data['cores']!=args.cores:raise RuntimeError('existing inputs use different core count; choose new --out')
            cases=data['cases']
            for c in cases:
                for file,key in [('a.bin','a_sha256'),('b.bin','b_sha256'),('golden.bin','golden_sha256')]:
                    if sha(out/c['id']/file)!=c[key]:raise RuntimeError('input/golden digest mismatch')
        else:
            cases=prepare(out,args.cores)
            manifest.write_text(json.dumps({'cores':args.cores,'cases':cases},indent=2)+'\n',encoding='utf-8')
        state['inputs']=cases;save()
        if not(args.execute or args.build_only):
            state['status']='PREPARED_ONLY';save();print(f'Prepared {len(cases)} cases; no NPU/compile commands.');return
        for tool in (['cmake','msprof'] if args.execute else ['cmake']):
            if not shutil.which(tool):raise RuntimeError(tool+' unavailable; source the CANN environment')
        # Capture a bounded, read-only environment record. Do not dump credentials.
        state['environment']={k:os.environ.get(k) for k in ['ASCEND_HOME_PATH','ASCEND_DEVICE_ID']}
        if args.execute and shutil.which('npu-smi'):command(['npu-smi','info'],'npu_smi',allow_failure=True,cap=15)
        if args.execute:command(['msprof','--version'],'msprof_version',allow_failure=True,cap=15)
        command(['cmake','--version'],'cmake_version',cap=15)
        cann=os.environ.get('ASCEND_HOME_PATH')
        if cann:
            for name in ['version.cfg','version.info']:
                f=Path(cann)/name
                if f.is_file():state['environment'][name]=f.read_text(errors='replace')[:12000]
        executables={}
        for v,name in SOURCES.items():
            src=out/(v+'_src');src.mkdir(exist_ok=True);build=out/(v+'_build')
            wanted={'source':sha(HERE/name),'main':sha(HERE/'main.asc'),'cmake':sha(HERE/'CMakeLists.txt'),'arch':args.arch}
            cache=build/'BMMS_BUILD.json';exe=build/'bench';reuse=False
            if cache.exists() and exe.exists():
                prev=json.loads(cache.read_text(encoding='utf-8'));reuse=prev.get('inputs')==wanted and prev.get('executable_sha256')==sha(exe)
            if not reuse:
                for f in ['main.asc','CMakeLists.txt']:shutil.copyfile(HERE/f,src/f)
                shutil.copyfile(HERE/name,src/'kernel_under_test.asc')
                command(['cmake','-S',str(src),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
                         '-DCMAKE_ASC_RUN_MODE=npu','-DCMAKE_ASC_ARCHITECTURES='+args.arch],v+'_configure')
                command(['cmake','--build',str(build),'-j','2'],v+'_build')
                cache.write_text(json.dumps({'inputs':wanted,'executable_sha256':sha(exe)},indent=2)+'\n',encoding='utf-8')
            executables[v]=exe;state.setdefault('executables',{})[v]={'sha256':sha(exe),'reused':reuse};save()
        if args.build_only:
            state['status']='BUILT_ONLY';save();print('Built both sources; no NPU commands.');return
        def app(v,c,reps,dest):
            return [str(executables[v]),*map(str,c['shape']),str(c['dtype']),str(c['ta']),str(c['tb']),
                    str(c['cores']),str(reps),str(out/c['id']/'a.bin'),str(out/c['id']/'b.bin'),str(dest)]
        for i,c in enumerate(cases):
            for v in (('P01','R01') if i%2==0 else ('R01','P01')):
                label='check_'+c['id']+'_'+v;dest=log/(label+'.bin')
                command(app(v,c,3,dest),label,cap=60)
                check=validate(dest,c,3);state['records'].append(dict(stage='correctness',case=c['id'],version=v,**check));save()
                if not(check['strict'] and check['repeat'] and check['finite']):raise RuntimeError('precision/repeat failure; profiling cancelled')
        for c in [c for c in cases if c['profile']]:
            if not c['expect_R01']:raise RuntimeError('profile fixture would not enter R01')
            for i,v in enumerate(['P01','R01','R01','P01']):
                label='profile_'+c['id']+'_'+str(i)+'_'+v;dest=log/(label+'.bin');prof=log/label
                command(['msprof','--application='+shlex.join(app(v,c,20,dest)),
                         '--output='+str(prof),'--aic-metrics=PipeUtilization'],label,cap=120)
                check=validate(dest,c,20);state['records'].append(dict(stage='profile',case=c['id'],version=v,profile_dir=str(prof),**check));save()
                if not(check['strict'] and check['repeat'] and check['finite']):raise RuntimeError('profiled output failed verification')
        # main has one explicit warmup, then 20 measured-output invocations.
        # Exclude explicit warmup plus the first ten sampled calls from profiling.
        summary=log/'task_durations.json'
        command([sys.executable,str(HERE/'profile_summary.py'),str(log),'--contains','bmms','--skip','11','--output',str(summary)],'summary')
        groups=json.loads(summary.read_text(encoding='utf-8'))['groups']
        if not groups:raise RuntimeError('no usable msprof Task Duration; inspect raw profiles')
        for record in [r for r in state['records'] if r['stage']=='profile']:
            matches=[g for g in groups if Path(record['profile_dir']) in Path(g['file']).parents]
            if not matches:raise RuntimeError('profile invocation has no usable kernel tasks: '+record['profile_dir'])
            if any(g['count']!=10 for g in matches):raise RuntimeError('unexpected per-task repetition count; do not infer timings')
            if record['version']=='R01' and not any('bmms11_' in g['kernel'] for g in matches):
                raise RuntimeError('expected R01 kernel not observed; inspect route or profiler naming')
        state['profile_route_and_counts_verified']=True
        state['status']='COMPLETED';save();print('Saved correctness and actual profiler data:',log)
    except Exception as e:
        state['status']='STOPPED';state['error']=str(e);save();raise

if __name__=='__main__':main()
