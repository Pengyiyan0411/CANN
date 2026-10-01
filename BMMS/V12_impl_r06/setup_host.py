import build as b
for name in ['check_host.py','host_checks.cpp.in']:
    s=(b.ROOT/'V12_impl_r04'/name).read_text().replace('1204','1206').replace('r04','r06')
    s=s.replace('4ULL*128*256*2+2ULL*256*256*2','2ULL*128*256*2+2ULL*256*256*2')
    b.write(b.H/name,s)
print('Prepared host dispatch checks for same probed domain.')
