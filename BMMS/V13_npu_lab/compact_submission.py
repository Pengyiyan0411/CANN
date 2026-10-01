"""Create a smaller plaintext ASC without changing code or literal contents."""
from pathlib import Path
import hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
def strip_comments(src):
    # Translation phase 2 precedes comment recognition in C++.
    src=src.replace('\r\n','\n').replace('\r','\n')
    src=src.replace('\\\n','')
    assert not re.search(r'(?:u8|u|U|L)?R"',src),'Raw strings need explicit handling'
    out=[];i=0
    while i<len(src):
        if src.startswith('//',i):
            j=src.find('\n',i+2);i=len(src) if j<0 else j
            out.append(' ')
        elif src.startswith('/*',i):
            j=src.find('*/',i+2);assert j>=0,'Unclosed comment'
            out.append(' '+ '\n'*src[i:j+2].count('\n'));i=j+2
        elif src[i] in ('"',"'"):
            quote=src[i];j=i+1
            while j<len(src):
                if src[j]=='\\':j+=2;continue
                if src[j]==quote:break
                j+=1
            assert j<len(src),'Unclosed literal'
            out.append(src[i:j+1]);i=j+1
        else:out.append(src[i]);i+=1
    return ''.join(out)

def compact(src):
    src=strip_comments(src)
    # Collapse horizontal whitespace only outside string/character literals.
    out=[];i=0
    while i<len(src):
        if src[i] in ('"',"'"):
            quote=src[i];j=i+1
            while j<len(src):
                if src[j]=='\\':j+=2;continue
                if src[j]==quote:break
                j+=1
            out.append(src[i:j+1]);i=j+1
        elif src[i] in ' \t\v\f':
            out.append(' ')
            while i<len(src) and src[i] in ' \t\v\f':i+=1
        else:out.append(src[i]);i+=1
    return '\n'.join(line.strip() for line in ''.join(out).splitlines() if line.strip())+'\n'

def lexical_lines(src):
    # Keep directive/logical-line boundaries and all literal spellings.
    tok=re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^\s"\']+')
    return [tok.findall(line) for line in strip_comments(src).splitlines() if line.strip()]

if __name__=='__main__':
    original=ROOT/'BMMS_V13/v13_r2_case12_o10.asc'
    source=original.read_bytes().decode('utf-8')
    assert not re.search(r'\b__(?:LINE|FILE|COUNTER|DATE|TIME)__\b',strip_comments(source))
    result=compact(source)
    assert lexical_lines(source)==lexical_lines(result)
    dst=ROOT/'BMMS_V13/v13_r2_submit_compact.asc'
    dst.write_bytes(result.encode('utf-8'))
    data=dict(original=original.name,submission=dst.name,original_bytes=original.stat().st_size,
              submission_bytes=dst.stat().st_size,reduction_pct=100*(1-dst.stat().st_size/original.stat().st_size),
              original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),submission_sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),
              transformation='remove comments and redundant whitespace; splice backslash-newline before parsing comments; preserve literal contents and directive boundaries',
              lexical_lines_equal=True,compiler_preprocessing_equivalence='pending')
    (ROOT/'BMMS_V13/evidence/r2_compact_manifest.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(data,indent=2))
