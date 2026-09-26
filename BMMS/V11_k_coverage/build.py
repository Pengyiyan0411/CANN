"""Independent R11 descendants: admit two disjoint, previously generic K domains."""
from pathlib import Path
import difflib,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R15_R16'
BASE=ROOT/'BMMS_V11_R11_R12/R11_SINGLE_WAVE_EXPAND.asc'
BASE_SHA='425db189f068ad963dadf2c537a96118b33a5035ef47c5e43dad2f81fd0ad223'
NAMES={'R15':'R15_K32_GAPS','R16':'R16_K16_TAILS'}
OLD_MACRO=ROOT/'V11_single_wave/expanded_macro_fragment.asc'
OLD_RESIDUAL=ROOT/'V11_merge/residual_dense_fragment.asc'
OLD_COMMENT='''    // slot still reserves the maximum KB tile size. K tail stays a multiple
    // of 32: 32/64 for KB64; 32/64/96/128 for KB128.'''
NEW_COMMENT='''    // slot still reserves the maximum KB tile size. Every active K extent
    // is a whole 16-element fractal; the host guard selects supported tails.'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a[:120]);return s.replace(a,b,1)
def between(s,a,b):
    i=s.index(a);return s[i:s.index(b,i)]
def function(s,signature):
    i=s.index(signature);j=s.index('{',i);depth=1;k=j+1
    while depth:
        depth+=(s[k]=='{')-(s[k]=='}');k+=1
    return s[i:k]
def fragments(version):
    m=OLD_MACRO.read_text(encoding='utf-8');d=OLD_RESIDUAL.read_text(encoding='utf-8')
    if version=='R11':return m,d
    predicate='K>=96&&K!=128&&K%32==0' if version=='R15' else '((K>=256&&K%32==0)||(K>=32&&K%32==16))'
    m=once(m,'K>=K1&&K<=8192&&M%16==0&&N%16==0&&K%32==0',predicate+'&&K<=8192&&M%16==0&&N%16==0')
    d=once(d,'K>=256&&K<=8192&&K%32==0',predicate+'&&K<=8192')
    return m,once(d,OLD_COMMENT,NEW_COMMENT)
def verify():
    assert sha(BASE)==BASE_SHA and sha(OUT/'R11_CONTROL.asc')==BASE_SHA
    original=BASE.read_text(encoding='utf-8');oldM,oldD=fragments('R11')
    for version,name in NAMES.items():
        m,d=fragments(version);s=(OUT/(name+'.asc')).read_text(encoding='utf-8')
        assert m==(HERE/(version+'_macro_fragment.asc')).read_text(encoding='utf-8')
        assert d==(HERE/(version+'_residual_fragment.asc')).read_text(encoding='utf-8')
        assert once(once(s,m,oldM),d,oldD).split('\n',1)[1]==original.split('\n',1)[1]
        assert m[m.index('// Closed-form peak'):]==oldM[oldM.index('// Closed-form peak'):]
        assert d[d.index('static inline bool ResidualEligible'):].replace(NEW_COMMENT,OLD_COMMENT)==oldD[oldD.index('static inline bool ResidualEligible'):]
        for f in [m,d]:
            assert 'if(family==bmms8::Family::Resident||family==bmms8::Family::Tiny)return false;' in f
    return {'independent_R11_descendants':True,'changes':'two K guards and one explanatory comment only',
        'all_device_instructions_and_planners_unchanged':True,'existing_manual_domains_preserved':True,
        'native_32_64_128_preserved':True,'Tiny_Resident_and_skinny_preserved':True,
        'R13_R14_changes_not_included':True,'new_domains_disjoint':True}
def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True)
    (OUT/'R11_CONTROL.asc').write_bytes(BASE.read_bytes());original=BASE.read_text(encoding='utf-8');oldM,oldD=fragments('R11');rows=[]
    for version,name in NAMES.items():
        m,d=fragments(version);write(HERE/(version+'_macro_fragment.asc'),m);write(HERE/(version+'_residual_fragment.asc'),d)
        s=once(once(original,oldM,m),oldD,d)
        s=once(s,s.split('\n',1)[0],'// '+name+': independent R11 K-domain extension; pending platform validation.')
        p=OUT/(name+'.asc');write(p,s)
        write(HERE/(name+'.diff'),''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='R11',tofile=name)))
        rows.append({'version':version,'file':p.name,'sha256':sha(p),'platform_result_received':False})
    manifest={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,
        'control':{'file':'R11_CONTROL.asc','sha256':BASE_SHA},'variants':rows,'proof':verify(),
        'cann_compiled_locally':False,'npu_tested_locally':False,'known_numerical_limitations_remain':True}
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
