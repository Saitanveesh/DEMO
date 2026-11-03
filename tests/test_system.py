"""Integration regression: timed releases, team identity/scoring, lock enforcement."""
import contextlib, http.cookiejar, json, os, re, socket, sqlite3, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'organizer'/'competition-pack'

def freeport():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

class Client:
 def __init__(self,port):
  self.base=f'http://127.0.0.1:{port}';self.cookies=http.cookiejar.CookieJar()
  self.open=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(self.cookies))
 def get(self,path):
  try:
   with self.open.open(self.base+path,timeout=15) as r:return r.status,r.read().decode(),r.geturl()
  except urllib.error.HTTPError as e:return e.code,e.read().decode(),e.geturl()
 def post(self,path,payload):
  sourcepath=('/admin' if path.startswith('/admin/') else
              ('/challenge/'+path.split('/')[2] if path.startswith('/challenge/') else
               '/challenges' if path=='/logout' else path))
  _,source,_=self.get(sourcepath)
  match=re.search(r'name="_csrf" value="([a-f0-9]+)"',source)
  assert match,f'No CSRF token on {sourcepath}: {source[:200]}'
  data=urllib.parse.urlencode({'_csrf':match.group(1),**payload}).encode()
  req=urllib.request.Request(self.base+path,data=data,method='POST')
  try:
   with self.open.open(req,timeout=15) as r:return r.status,r.read().decode(),r.geturl()
  except urllib.error.HTTPError as e:return e.code,e.read().decode(),e.geturl()

class SystemTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.dir=tempfile.TemporaryDirectory();env=os.environ.copy();env['HUNT_DATA_DIR']=cls.dir.name;cls.env=env
  for command in [['init'],['import-pack',str(PACK)]]:
   subprocess.run([sys.executable,str(ROOT/'app.py'),*command],env=env,check=True,capture_output=True)
  env['HUNT_ADMIN_PASSWORD']='SuperSecureTestPassword-52836'
  subprocess.run([sys.executable,str(ROOT/'app.py'),'create-admin','testorganizer'],env=env,check=True,capture_output=True)
  cls.port=freeport()
  cls.proc=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'serve','--port',str(cls.port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(60):
   try:
    urllib.request.urlopen(f'http://127.0.0.1:{cls.port}/healthz',timeout=.4);break
   except Exception:time.sleep(.1)
  else:raise RuntimeError('HTTP server did not start')
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=10);cls.dir.cleanup()
 def test_01_team_registration_rounds_expiry_and_scores(self):
  admin=Client(self.port)
  status,html,_=admin.post('/login',{'username':'testorganizer','password':'SuperSecureTestPassword-52836'})
  self.assertEqual(status,200);self.assertIn('Mission control',html)
  self.assertIn('Round name',html);self.assertIn('20',html)
  a=Client(self.port)
  status,html,_=a.post('/register',{'team_name':'Cipher Squad','members':'Asha\nNikhil\nRam','username':'cipherteam','password':'TestPassword_456789'})
  self.assertEqual(status,200);self.assertIn('No active round',html)
  b=Client(self.port)
  status,html,_=b.post('/register',{'team_name':'Blue Circuit','members':'Priya\nAman','username':'bluecircuit','password':'TestPassword_456789'})
  self.assertEqual(status,200);self.assertIn('No active round',html)
  bad=Client(self.port)
  status,html,_=bad.post('/register',{'team_name':'Cipher Squad','members':'Xyz\nPqr','username':'newteam','password':'TestPassword_456789'})
  self.assertIn('already registered',html)
  status,html,_=a.get('/challenge/1');self.assertEqual(status,404)
  status,html,_=a.get('/api/event');self.assertFalse(json.loads(html)['active'])
  # Exactly the three selected challenges are published in the live round.
  status,html,_=admin.post('/admin/rounds/launch',{'round_name':'Qualifier','duration_minutes':'30','pick_1':'on','pick_2':'on','pick_10':'on'})
  self.assertEqual(status,200);self.assertIn('ACTIVE ROUND',html)
  status,data,_=a.get('/api/event');state=json.loads(data)
  self.assertEqual(state['active_challenges'],3);self.assertEqual(state['end_epoch']-state['start_epoch'],1800)
  status,html,_=a.get('/challenges');self.assertIn('The Forgotten Caption',html);self.assertNotIn('Blueprint in Blue',html)
  self.assertEqual(a.get('/challenge/1')[0],200);self.assertEqual(a.get('/challenge/3')[0],404)
  self.assertEqual(a.get('/asset/3/03_blueprint.png')[0],404)
  self.assertEqual(a.get('/arena/source')[0],404)
  self.assertEqual(admin.post('/admin/rounds/launch',{'round_name':'Overlapping','duration_minutes':'10','pick_3':'on'})[0],409)
  self.assertIn('Incorrect flag',a.post('/challenge/1/submit',{'flag':'HUNT{WRONG}'} )[1])
  self.assertEqual(a.post('/challenge/1/submit',{'flag':'HUNT{WRONG}'} )[0],429)
  time.sleep(3.1)
  flag=json.loads((PACK/'manifest.json').read_text())['challenges'][0]['flag']
  status,html,_=a.post('/challenge/1/submit',{'flag':flag});self.assertEqual(status,200);self.assertIn('Points credited to your team',html)
  status,body,_=a.get('/api/scoreboard');payload=json.loads(body)
  self.assertEqual(payload['ranking'][0]['team'],'Cipher Squad');self.assertEqual(payload['ranking'][0]['score'],100)
  self.assertEqual(payload['ranking'][0]['members'],3);self.assertEqual(payload['history'][0]['points'][-1]['score'],100)
  status,html,_=admin.get('/api/admin');self.assertEqual(json.loads(html)['recent'][0]['team'],'Cipher Squad')
  self.assertEqual(a.get('/api/admin')[0],403)
  # Freeze leaderboard, then unfreeze without touching rounds.
  admin.post('/admin/settings',{'registration':'on','scoreboard_frozen':'on'})
  self.assertTrue(json.loads(a.get('/api/scoreboard')[1])['frozen'])
  admin.post('/admin/settings',{'registration':'on'})
  self.assertFalse(json.loads(a.get('/api/scoreboard')[1])['frozen'])
  # Ending round locks challenge GET and POST while retaining scores.
  status,html,_=admin.post('/admin/rounds/end',{});self.assertEqual(status,200)
  self.assertEqual(a.get('/challenge/1')[0],404);self.assertEqual(a.post('/challenge/2/submit',{'flag':'HUNT{X}'})[0],403)
  self.assertEqual(json.loads(a.get('/api/scoreboard')[1])['ranking'][0]['score'],100)
  # Second round has an entirely different selection, including live arena puzzle.
  status,html,_=admin.post('/admin/rounds/launch',{'round_name':'Semifinal','duration_minutes':'15','pick_3':'on','pick_17':'on','pick_20':'on'})
  self.assertEqual(status,200);self.assertEqual(a.get('/challenge/1')[0],404)
  self.assertEqual(a.get('/challenge/3')[0],200);self.assertEqual(a.get('/arena/source')[0],200)
  flagA=re.search(r'HUNT\{WEB_SOURCE_[A-F0-9]+\}',a.get('/arena/source')[1]).group()
  flagB=re.search(r'HUNT\{WEB_SOURCE_[A-F0-9]+\}',b.get('/arena/source')[1]).group()
  self.assertNotEqual(flagA,flagB)
  # Fake browser timer cannot extend access: change authoritative DB end time.
  with sqlite3.connect(Path(self.dir.name)/'hunt.sqlite3') as db:
   db.execute('UPDATE rounds SET end_epoch=? WHERE id=(SELECT MAX(id) FROM rounds)',(int(time.time())-1,))
  state=json.loads(a.get('/api/event')[1]);self.assertFalse(state['active']);self.assertEqual(state['state'],'expired')
  self.assertEqual(a.get('/challenge/3')[0],404);self.assertEqual(a.get('/arena/source')[0],403)
  self.assertEqual(a.post('/challenge/3/submit',{'flag':'HUNT{X}'})[0],403)
  # Third round deploys dynamically, no reset of previous score.
  status,html,_=admin.post('/admin/rounds/launch',{'round_name':'Final','duration_minutes':'40','pick_19':'on'})
  self.assertEqual(status,200);self.assertIn('Final',html)
  self.assertEqual(a.get('/arena/vault?badge=auditor')[0],200)
  self.assertEqual(a.get('/arena/source')[0],404)
  self.assertEqual(json.loads(a.get('/api/scoreboard')[1])['ranking'][0]['score'],100)
  status,body,_=admin.get('/admin/export.csv');self.assertEqual(status,200)
  self.assertIn('Cipher Squad',body);self.assertIn('members',body)
  # Correct a team roster without changing the login account or earned score.
  with sqlite3.connect(Path(self.dir.name)/'hunt.sqlite3') as db:
   team_id=db.execute('SELECT id FROM teams WHERE name=?',('Cipher Squad',)).fetchone()[0]
  status,html,_=admin.get(f'/admin/team/{team_id}/edit');self.assertEqual(status,200);self.assertIn('Asha',html)
  status,html,_=admin.post(f'/admin/team/{team_id}/edit',{'team_name':'Cipher Unit','members':'Asha\nNikhil\nRam\nUma'})
  self.assertEqual(status,200);self.assertIn('Cipher Unit',html)
  self.assertEqual(json.loads(a.get('/api/scoreboard')[1])['ranking'][0]['team'],'Cipher Unit')
  self.assertEqual(json.loads(a.get('/api/scoreboard')[1])['ranking'][0]['members'],4)
  self.assertEqual(a.get('/challenges')[0],200)
  self.assertEqual(a.get('/admin/team/1/edit')[0],403)
  print('PASS: team registration, selective rounds, live timer, expiry, team score continuity, roster editing and dynamic flags')

 def test_02_legacy_member_migration(self):
  with tempfile.TemporaryDirectory() as directory:
   env=os.environ.copy();env['HUNT_DATA_DIR']=directory
   subprocess.run([sys.executable,str(ROOT/'app.py'),'init'],env=env,check=True,capture_output=True)
   db=sqlite3.connect(Path(directory)/'hunt.sqlite3')
   db.execute('INSERT INTO users(username,password_hash,is_admin,created_at) VALUES (?,?,0,?)',('old_student','hash','2026-10-01T00:00:00Z'))
   db.commit();db.close()
   subprocess.run([sys.executable,str(ROOT/'app.py'),'init'],env=env,check=True,capture_output=True)
   db=sqlite3.connect(Path(directory)/'hunt.sqlite3')
   team=db.execute('SELECT name,members_json FROM teams').fetchone()
   self.assertEqual(team[0],'old_student');self.assertEqual(json.loads(team[1]),['old_student'])
   db.close()
if __name__=='__main__':unittest.main(verbosity=2)
