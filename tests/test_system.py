"""Real HTTP functional checks with temporary SQLite storage (stdlib)."""
import contextlib, http.cookiejar, json, os, re, shutil, socket, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'organizer'/'competition-pack'

def freeport():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

class Client:
 def __init__(self,port):
  self.base=f'http://127.0.0.1:{port}'
  self.cookies=http.cookiejar.CookieJar();self.open=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
 def get(self,path):
  try:
   with self.open.open(self.base+path,timeout=10) as r:return r.status,r.read().decode(),r.geturl()
  except urllib.error.HTTPError as e:return e.code,e.read().decode(),e.geturl()
 def post(self,path,payload):
  # Obtain CSRF token from a GET form page via a session cookie.
  page={'/register':'/register','/login':'/login','/admin/settings':'/admin', '/challenge/1/submit':'/challenge/1','/logout':'/challenges'}.get(path,path)
  _,source,_=self.get(page)
  match=re.search(r'name="_csrf" value="([a-f0-9]+)"',source)
  assert match,f'Missing CSRF token on {page}: {source[:100]}'
  data=urllib.parse.urlencode({'_csrf':match.group(1),**payload}).encode()
  req=urllib.request.Request(self.base+path,data=data,method='POST')
  try:
   with self.open.open(req,timeout=20) as r:return r.status,r.read().decode(),r.geturl()
  except urllib.error.HTTPError as e:return e.code,e.read().decode(),e.geturl()

class SystemTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.dir=tempfile.TemporaryDirectory();env=os.environ.copy();env['HUNT_DATA_DIR']=cls.dir.name
  cls.env=env
  subprocess.run([sys.executable,str(ROOT/'app.py'),'init'],check=True,env=env,capture_output=True)
  subprocess.run([sys.executable,str(ROOT/'app.py'),'import-pack',str(PACK)],check=True,env=env,capture_output=True)
  env['HUNT_ADMIN_PASSWORD']='SuperSecureTestPassword-52836'
  subprocess.run([sys.executable,str(ROOT/'app.py'),'create-admin','testorganizer'],check=True,env=env,capture_output=True)
  cls.port=freeport();cls.proc=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'serve','--port',str(cls.port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  for _ in range(50):
   try:
    urllib.request.urlopen(f'http://127.0.0.1:{cls.port}/healthz',timeout=.3);break
   except Exception:time.sleep(.1)
  else:raise RuntimeError('HTTP server never started')
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=10);cls.dir.cleanup()
 def test_01_admin_start_and_participant_lifecycle(self):
  admin=Client(self.port)
  code,body,_=admin.post('/login',{'username':'testorganizer','password':'SuperSecureTestPassword-52836'})
  self.assertEqual(code,200);self.assertIn('Mission control',body)
  code,body,_=admin.get('/admin');self.assertEqual(code,200)
  self.assertIn('20 configured',body)
  # Toggle a challenge and start competition from the admin panel.
  code,body,_=admin.post('/admin/challenge/1/toggle',{})
  self.assertEqual(code,200);self.assertIn('Mission control',body)
  code,body,_=admin.post('/admin/settings',{'registration':'on','event_live':'on','announcement':'Welcome, hunters'})
  self.assertEqual(code,200)
  u=Client(self.port)
  code,body,_=u.post('/register',{'username':'hunter_01','password':'TestPassword_456789'})
  self.assertEqual(code,200);self.assertIn('Challenges',body)
  self.assertIn('The Forgotten Caption',body)
  code,body,_=u.get('/challenge/1');self.assertEqual(code,200)
  self.assertIn('Download evidence',body)
  code,body,_=u.post('/challenge/1/submit',{'flag':'HUNT{BAD_GUESS}'})
  self.assertEqual(code,200);self.assertIn('Incorrect flag',body)
  # A second submit within three seconds must be throttled.
  code,body,_=u.post('/challenge/1/submit',{'flag':'HUNT{SOMETHING}'})
  self.assertEqual(code,429)
  time.sleep(3.1)
  manifest=json.loads((PACK/'manifest.json').read_text())
  flag=manifest['challenges'][0]['flag']
  code,body,_=u.post('/challenge/1/submit',{'flag':flag})
  self.assertEqual(code,200);self.assertIn('Flag accepted',body)
  code,body,_=u.get('/api/scoreboard');self.assertEqual(code,200)
  ranking=json.loads(body)['ranking'];self.assertEqual(ranking[0]['username'],'hunter_01');self.assertEqual(ranking[0]['score'],100)
  # Dynamic challenge accessible only to authenticated accounts after publish.
  db=__import__('sqlite3').connect(Path(self.dir.name)/'hunt.sqlite3');db.execute('UPDATE challenges SET published=1 WHERE slug IN ("web-source","web-headers","web-vault","final-hunt")');db.commit();db.close()
  code,body,_=u.get('/arena/source');self.assertEqual(code,200);self.assertRegex(body,r'HUNT\{WEB_SOURCE_[A-F0-9]+\}')
  code,body,_=u.get('/arena/vault?badge=auditor');self.assertEqual(code,200);self.assertRegex(body,r'HUNT\{WEB_VAULT_[A-F0-9]+\}')
  phrase=manifest['final_phrase']
  code,body,_=u.get('/arena/finale?phrase='+urllib.parse.quote(phrase));self.assertEqual(code,200);self.assertIn('Final flag:',body)
  # Admin API should be forbidden to regular participants.
  code,body,_=u.get('/api/admin');self.assertEqual(code,403)
  # Scoreboard freeze preserves published rankings.
  code,body,_=admin.post('/admin/settings',{'registration':'on','event_live':'on','scoreboard_frozen':'on'})
  self.assertEqual(code,200);code,body,_=u.get('/api/scoreboard');self.assertTrue(json.loads(body)['frozen'])
  # Missing CSRF is rejected.
  req=urllib.request.Request(u.base+'/logout',data=b'',method='POST')
  with self.assertRaises(urllib.error.HTTPError) as resp:u.open.open(req)
  self.assertEqual(resp.exception.code,403)
  code,body,_=admin.get('/admin/export.csv');self.assertEqual(code,200);self.assertIn('hunter_01',body)
  with u.open.open(u.base+'/asset/1/01_station.png') as resp:
   self.assertEqual(resp.status,200);self.assertTrue(resp.read(8).startswith(b'\x89PNG'))
  print('Validated admin, launch, registration, flag rejection, throttling, solve, scoreboard, arena, freeze, CSRF and score export')

if __name__=='__main__':unittest.main(verbosity=2)