"""Non-destructive 100-request read-only concurrency probe for event readiness."""
import argparse, concurrent.futures, statistics, time, urllib.request

def hit(url):
 t=time.monotonic()
 try:
  with urllib.request.urlopen(url+'/api/scoreboard',timeout=15) as r:
   assert r.status==200
   result='ok'
 except Exception as ex:result=repr(ex)
 return result,time.monotonic()-t

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8000');p.add_argument('--requests',type=int,default=100);p.add_argument('--workers',type=int,default=30);a=p.parse_args()
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:out=list(pool.map(lambda _:hit(a.url),range(a.requests)))
 good=[t for status,t in out if status=='ok'];bad=[s for s,t in out if s!='ok']
 print(f'Requests: {len(out)}  OK: {len(good)}  Failed: {len(bad)}')
 if good:
  ordered=sorted(good);print(f'Median: {statistics.median(good):.3f}s  p95: {ordered[min(len(ordered)-1,int(len(ordered)*.95))]:.3f}s  Max: {max(good):.3f}s')
 if bad:print('Error samples:',bad[:4]);raise SystemExit(1)