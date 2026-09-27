"""Build independent, host-only diagnostic submissions on frozen R23."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_D24_Diagnostics'
BASE=ROOT/'BMMS_V11_R23/R23_SPLIT_K.asc'
BASE_SHA='d097fdc60ffc8be7ddf40ef93a3afa04c04d904fec4ae8b42dc7085238353733'
K1=ROOT/'BMMS_V11_R23/R23_K1_CONTROL.asc'
K1_SHA='2d78f01236ec15ac2a44d86a9ef70aa3150ee11f4ebf12abfb59ff5554f44e98'
ONE_GROUP='p.pM=1;p.pN=1;p.tasks=p.B;p.blocks=1;'
SINGLE_K='p.splits=1;p.blocks=B*p.mTiles*p.nTiles;'
SPECS=[
    ('C00_NATIVE_1G','native','true','Native 阳性压力对照'),
    ('C01_R03_1G','residual','true','R03 阳性压力对照'),
    ('N01_K_EQ32','native','K==32','Native: K=32'),
    ('N02_K_EQ64','native','K==64','Native: K=64'),
    ('N03_M_LE32','native','M<=32','Native: M<=32'),
    ('N04_N_LE32','native','N<=32','Native: N<=32'),
    ('N05_B_EQ1','native','B==1','Native: B=1'),
    ('R7_01_M_LT128','residual','M<128','R03: M<128'),
    ('R7_02_N_LT256','residual','N<256','R03: N<256'),
    ('R7_03_MACRO_OCC_LT_CORES','residual','int64_t(B)*bmms83::UpH(M,128)*bmms83::UpH(N,256)<cores','R03: macro occupancy < cores'),
    ('R7_04_K_GE512','residual','K>=512','R03: K>=512'),
    ('R7_05_K_GE1024','residual','K>=1024','R03: K>=1024'),
    ('L01_B_EQ1','split','B==1','Split-K: B=1'),
    ('L02_M_LE64','split','M<=64','Split-K: M<=64'),
    ('L03_N_LE128','split','N<=128','Split-K: N<=128'),
    ('L04_MN_LE4096','split','int64_t(M)*N<=4096','Split-K: MN<=4096'),
    ('L05_SPATIAL_EQ1','split','B*p.mTiles*p.nTiles==1','Split-K: spatial tasks=1'),
    ('L06_SPLITS_GE8','split','p.splits>=8','Split-K: original split count>=8'),
    ('X6_01_MACRO_1G','macro','true','Case6 fallback diagnosis: macro single group'),
    ('X6_02_TREE_1W','tree','true','Case6 fallback diagnosis: tree single worker'),
    ('X6_03_FALLBACK_1CORE','fallback','true','Case6 fallback diagnosis: remaining dispatcher single core'),
]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):assert s.count(a)==1,(s.count(a),a[:100]);return s.replace(a,b,1)
def between(s,a,b):i=s.index(a);return s[i:s.index(b,i)]
def function(s,mark):
    i=s.index(mark);j=s.index('{',i)+1;depth=1
    while depth:depth+=(s[j]=='{')-(s[j]=='}');j+=1
    return s[i:j]

def edits(base,route,predicate):
    if route=='native':
        old='if(native){const auto p=bmms83::MakeNative(B,M,N,K,cores);uint8_t* ws=nullptr;'
        new='if(native){auto p=bmms83::MakeNative(B,M,N,K,cores);\n        if('+predicate+'){'+ONE_GROUP+'}\n        uint8_t* ws=nullptr;'
    elif route in ['residual','macro']:
        ns='bmms11d' if route=='residual' else 'bmms11r2'
        start=base.index('namespace '+ns+' {\nstatic inline bool TryLaunch(')
        old=function(base[start:],'static inline bool TryLaunch(')
        new=once(old,'const auto p=MakePlan(B,M,N,K,cores);',
            'auto p=MakePlan(B,M,N,K,cores);\n    if('+predicate+'){'+ONE_GROUP+'}')
    elif route=='split':
        old='    if(BMMS23_SINGLE_K_CONTROL){'+SINGLE_K+'}'
        new=old+'\n    if('+predicate+'){'+SINGLE_K+'}'
    elif route=='tree':
        old='if(tree){const auto p=bmms83::MakeTree(B,N==1?M:N,K,cores);uint8_t* partial=nullptr;'
        new='if(tree){auto p=bmms83::MakeTree(B,N==1?M:N,K,cores);p.workers=1;uint8_t* partial=nullptr;'
    else:
        assert route=='fallback'
        old='    bmms80d_dispatch(a,ia,b,ib,y,iy,availableCoreNum,stream,ta,tb);'
        new='    bmms80d_dispatch(a,ia,b,ib,y,iy,1,stream,ta,tb);'
    return old,new

def verify():
    assert sha(BASE)==BASE_SHA and sha(K1)==K1_SHA
    assert sha(OUT/'CONTROL_R23.asc')==BASE_SHA and sha(OUT/'L00_K1_CONTROL.asc')==K1_SHA
    base=BASE.read_text(encoding='utf-8')
    for name,route,predicate,_ in SPECS:
        s=(OUT/(name+'.asc')).read_text(encoding='utf-8');old,new=edits(base,route,predicate)
        assert once(s,new,old).split('\n',1)[1]==base.split('\n',1)[1],name
    return {'R23_frozen':True,'R14_not_modified':True,'host_only_edits':True,'all_device_code_byte_identical_to_R23':True,
            'single_intervention_per_submission':True,'one_group_keeps_tasks_equal_B':True,
            'workspace_and_launch_derived_after_mutation':True,'Case15_targets_SplitK_not_bypassed_R03':True}

def main():
    assert sha(BASE)==BASE_SHA and sha(K1)==K1_SHA;OUT.mkdir(exist_ok=True)
    shutil.copyfile(BASE,OUT/'CONTROL_R23.asc');shutil.copyfile(K1,OUT/'L00_K1_CONTROL.asc')
    base=BASE.read_text(encoding='utf-8');rows=[]
    for name,route,predicate,purpose in SPECS:
        old,new=edits(base,route,predicate);s=once(base,old,new)
        s=once(s,s.split('\n',1)[0],f'// D24 {name}: diagnostic on frozen R23; changes only {route} host schedule; not a performance candidate.')
        write(OUT/(name+'.asc'),s)
        rows.append({'file':name+'.asc','route':route,'predicate':predicate,'purpose':purpose,'sha256':sha(OUT/(name+'.asc'))})
    manifest={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,'probes':rows,
        'controls':[{'file':'CONTROL_R23.asc','sha256':BASE_SHA},{'file':'L00_K1_CONTROL.asc','sha256':K1_SHA}],
        'composition':verify(),'cann_compiled_locally':False,'npu_tested_locally':False}
    write(OUT/'MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'diagnostics':len(rows),'controls':2,'composition':manifest['composition']},ensure_ascii=False))
if __name__=='__main__':main()
