from pathlib import Path
import re,html,json,math,statistics,hashlib,shutil
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'V12_results/2026-09-28_v1201_ranking'
SOURCE=Path('C:/Users/cc/Downloads/CANNJudge.html')
current=[2.24,5.01,5.04,6.47,6.54,14.25,9.09,62.15,69.84,84.30,100.04,121.67,14.74,13.30,15.12]
def clean(s):return ' '.join(html.unescape(re.sub('<[^>]+>',' ',s)).split())
def component(t,b):return 100/(1+math.log(t/b)/math.log(1.5))
def main():
    OUT.mkdir(parents=True,exist_ok=True);raw=SOURCE.read_bytes();s=raw.decode('utf-8');rows=[]
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>',s,re.S):
        cells=[clean(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>',tr,re.S)]
        if cells and cells[0]=='TBest时间':best=[float(x.replace('μs','')) for x in cells[1:]]
        if len(cells)==21 and cells[0].isdigit():
            rows.append(dict(rank=int(cells[0]),team=cells[1],score=float(cells[4]),times=[float(x.replace('μs','')) for x in cells[6:]]))
    assert len(rows)==20 and len(best)==15
    residuals=[]
    for r in rows:
        r['recomputed_score']=sum(component(t,b) for t,b in zip(r['times'],best))/15
        residuals.append(r['recomputed_score']-r['score'])
    table=[]
    for i,(t,b) in enumerate(zip(current,best)):
        times=sorted(r['times'][i] for r in rows);target=times[4]
        table.append(dict(case=i+1,current=t,TBest=b,ratio=t/b,visible_best=times[0],fifth_fastest=target,median=statistics.median(times),
          faster_teams=sum(x<t for x in times),gain_10pct=(component(max(b,t*.9),b)-component(t,b))/15,
          gain_to_fifth=max(0,(component(target,b)-component(t,b))/15)))
    score=sum(component(t,b) for t,b in zip(current,best))/15
    scenarios={}
    for i,target in [(2,2.8),(3,3.0),(4,4.2),(5,4.8),(6,10),(7,7),(8,50),(9,55),(10,79),(11,85),(12,105),(13,10.5),(14,10.5),(15,10),(1,1.8)]:
        scenarios[str(i)]={'target_us':target,'gain':(component(target,best[i-1])-component(current[i-1],best[i-1]))/15}
    data={'source':'user-saved CANNJudge.html page 1 only','visible_rows':20,'total_rows_label':424,'sha256':hashlib.sha256(raw).hexdigest(),
      'formula':'mean(100/(1+ln(time/TBest)/ln(1.5)))','max_score_reconstruction_error':max(map(abs,residuals)),
      'latest_user_screenshot_times':current,'latest_user_screenshot_version':'V12.01 inferred from immediately preceding delivery',
      'user_verdict':'没啥效果','all_15_pass':True,'all_displayed_errors_zero':True,
      'recomputed_current_score':score,'cases':table,'scenarios_not_predictions':scenarios,'ranking':rows}
    (OUT/'ANALYSIS.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    shutil.copyfile(SOURCE,OUT/'CANNJudge_snapshot.html')
    print('score',score,'max score error',max(map(abs,residuals)))
    for r in table:print(f"{r['case']:2} cur={r['current']:6.2f} fifth={r['fifth_fastest']:6.2f} median={r['median']:6.2f} faster={r['faster_teams']:2} gain10={r['gain_10pct']:.3f} gainFifth={r['gain_to_fifth']:.3f}")
    print(json.dumps(scenarios,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
