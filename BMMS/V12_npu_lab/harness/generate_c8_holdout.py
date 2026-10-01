from pathlib import Path
s=Path('generate_followup.py').read_text();a=s.index('specs=[]');b=s.index('manifest=[];records=[]')
s=s[:a]+'''specs=[]
for M,N,K in [(1024,1024,1032),(1041,1152,1152),(1152,1169,1184)]:
    for dt,ta,tb in itertools.product([1,2],[0,1],[0,1]):
        specs.append(dict(id=len(specs),label='c8_one_axis_ragged',B=1,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern='random'))
for i,(M,N,K) in enumerate([(1025,2047,1040),(2039,1027,1056),(1137,1283,1088),(1281,1135,1120),
                          (1200,1696,1096),(1791,1425,1144),(1467,1867,1216),(1561,1927,1240),
                          (1985,1953,1264),(1079,2001,1048),(1921,1095,1208),(1777,1305,1176),
                          (1433,1527,1168),(1695,1855,1112),(1233,1743,1136),(1311,1583,1256)]):
    specs.append(dict(id=len(specs),label='c8_holdout',B=1,M=M,N=N,K=K,dtype=1+(i//4)%2,ta=(i//2)%2,tb=i%2,pattern='random'))
for i,pattern in enumerate(['negative','last_column','last_row','zero','equal_columns','wide_scale','negative','last_column']):
    for dt in [1,2]:
        specs.append(dict(id=len(specs),label='c8_values',B=1,M=1041,N=1105,K=1032,dtype=dt,ta=(i//2)%2,tb=i%2,pattern=pattern))
'''+s[b:]
s=s.replace("default='cases_followup'","default='cases_c8_holdout'").replace('720928','1430928')
s=s.replace("    elif s['pattern']=='equal_columns':", "    elif s['pattern']=='last_column':\n        a=a.abs();b=-b.abs();b[:,:,-1]=b[:,:,-1].abs()*2\n    elif s['pattern']=='last_row':\n        a.zero_();a[:,-1,:]=1;b.fill_(0.125)\n    elif s['pattern']=='equal_columns':")
a=s.index('sets={');b=s.index('for name,ids in sets.items():',a)
s=s[:a]+"sets={'manifest':range(len(manifest)), 'screen':[0,1,2,3,8,9,10,11,16,17,18,19,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39], 'sanitize':[40,53]}\n"+s[b:]
exec(compile(s,'generate_c8_holdout_expanded.py','exec'))
