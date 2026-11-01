"""Crypto Cyber Hunt — self-hosted competition server (Python stdlib only).

Do not expose the server on the public internet without HTTPS reverse proxy,
network controls, external monitoring and a load/recovery rehearsal.
"""
from __future__ import annotations
import argparse, base64, csv, hashlib, hmac, html, io, json, mimetypes, os, re, secrets, sqlite3, sys, threading, time, traceback, urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=Path(os.getenv('HUNT_DATA_DIR',str(ROOT/'data'))).resolve()
DB=DATA/'hunt.sqlite3'
ASSETS=DATA/'artifacts'
STATIC=ROOT/'static'
CATEGORIES=('Steganography','Cryptography','Web Security','Final Hunt')
USER_RE=re.compile(r'^[A-Za-z0-9_]{3,32}$')
SLUG_RE=re.compile(r'^[a-z0-9-]{3,65}$')
PBKDF_ITERS=260000
PORT=int(os.getenv('PORT','8000'))
HOST=os.getenv('HOST','127.0.0.1')
SECURE_COOKIE=os.getenv('HUNT_HTTPS','0')=='1'
MAX_PARTICIPANTS=int(os.getenv('HUNT_CAPACITY','120'))
DB_LOCK=threading.Lock()

def now():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def esc(value):return html.escape(str(value if value is not None else ''),quote=True)
def hflag(flag):return hashlib.sha256(flag.strip().encode()).hexdigest()
def random_key():return secrets.token_urlsafe(32)
def password_hash(pw):
 salt=secrets.token_bytes(16); v=hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,PBKDF_ITERS)
 return f'pbkdf2_sha256${PBKDF_ITERS}${salt.hex()}${v.hex()}'
def password_ok(pw,stored):
 try:
  method,n,salt,digest=stored.split('$')
  if method!='pbkdf2_sha256':return False
  candidate=hashlib.pbkdf2_hmac('sha256',pw.encode(),bytes.fromhex(salt),int(n))
  return hmac.compare_digest(candidate,bytes.fromhex(digest))
 except (ValueError,TypeError):return False

def connect():
 db=sqlite3.connect(DB,timeout=20,isolation_level=None)
 db.row_factory=sqlite3.Row
 db.execute('PRAGMA foreign_keys=ON')
 db.execute('PRAGMA busy_timeout=20000')
 return db

def initialize():
 DATA.mkdir(parents=True,exist_ok=True);ASSETS.mkdir(parents=True,exist_ok=True)
 db=connect();db.execute('PRAGMA journal_mode=WAL')
 db.executescript('''
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE COLLATE NOCASE NOT NULL,password_hash TEXT NOT NULL,is_admin INTEGER NOT NULL DEFAULT 0,is_suspended INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,csrf TEXT NOT NULL,created_at INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS challenges(id INTEGER PRIMARY KEY,slug TEXT NOT NULL UNIQUE,title TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,points INTEGER NOT NULL,flag_hash TEXT,flag_mode TEXT NOT NULL DEFAULT 'static',published INTEGER NOT NULL DEFAULT 0,sort_order INTEGER NOT NULL DEFAULT 0,hint TEXT NOT NULL DEFAULT '',asset_name TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),challenge_id INTEGER NOT NULL REFERENCES challenges(id),correct INTEGER NOT NULL,created_at TEXT NOT NULL,created_epoch INTEGER NOT NULL);
 CREATE INDEX IF NOT EXISTS idx_submit_recent ON submissions(user_id,challenge_id,created_epoch);
 CREATE TABLE IF NOT EXISTS solves(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),challenge_id INTEGER NOT NULL REFERENCES challenges(id),created_at TEXT NOT NULL,UNIQUE(user_id,challenge_id));
 CREATE TABLE IF NOT EXISTS auth_attempts(id INTEGER PRIMARY KEY,ip TEXT NOT NULL,ts INTEGER NOT NULL);
 CREATE INDEX IF NOT EXISTS idx_auth_ip_time ON auth_attempts(ip,ts);
 ''')
 for k,v in [('registration','1'),('event_live','0'),('scoreboard_frozen','0'),('announcement','Welcome to Crypto Cyber Hunt. Stand by for the event launch.'),('final_phrase_hash',''),('arena_secret',secrets.token_hex(32))]:
  db.execute('INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)',(k,v))
 db.execute('DELETE FROM sessions WHERE created_at<?',(int(time.time())-86400,))
 db.close()

def setting(db,key,default=''):
 row=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
 return row['value'] if row else default

def set_setting(db,key,value):db.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value)))
def dynamic_flag(db,username,slug):
 secret=bytes.fromhex(setting(db,'arena_secret'))
 token=hmac.new(secret,f'{username.lower()}:{slug}'.encode(),'sha256').hexdigest()[:18].upper()
 return f'HUNT{{{slug.upper().replace("-","_")}_{token}}}'

def rankings(db):
 # Use solve creation time to break ties (earlier last solve ranks first).
 rows=db.execute('''SELECT u.username,COALESCE(SUM(c.points),0) AS score,COUNT(s.id) AS solves,MAX(s.created_at) AS last_solve
 FROM users u LEFT JOIN solves s ON s.user_id=u.id LEFT JOIN challenges c ON c.id=s.challenge_id
 WHERE u.is_admin=0 AND u.is_suspended=0 GROUP BY u.id
 ORDER BY score DESC, CASE WHEN last_solve IS NULL THEN 1 ELSE 0 END, last_solve ASC, u.username COLLATE NOCASE ASC''').fetchall()
 return [dict(rank=i+1,username=r['username'],score=r['score'],solves=r['solves']) for i,r in enumerate(rows)]

def page(title,body,user=None,message='',status='',extra_script=''):
 nav=('<a href="/challenges">Challenges</a><a href="/scoreboard">Leaderboard</a>')
 if user:
  nav+=('<a href="/admin">Mission control</a>' if user['is_admin'] else '')
  nav+=f'<span class="account">{esc(user["username"])}</span><form method="post" action="/logout"><input type="hidden" name="_csrf" value="__CSRF__"><button class="nav-link" type="submit">Log out</button></form>'
 else:nav+='<a href="/login">Sign in</a><a class="button small" href="/register">Join event</a>'
 banner=f'<div class="notice {esc(status)}" role="status">{esc(message)}</div>' if message else ''
 return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>{esc(title)} · Crypto Cyber Hunt</title><link rel="stylesheet" href="/static/style.css"></head><body><div class="app-shell"><header><a href="/" class="brand"><span class="brand-icon">◇</span> CRYPTO<span>CYBER</span>HUNT<small> / 2026</small></a><nav>{nav}</nav></header><main>{banner}{body}</main><footer><span>CRYPTO CYBER HUNT / CYBER SECURITY CLUB</span><span>Evidence over guesses. AI permitted. Fair play required.</span></footer></div>{extra_script}</body></html>'''

def card_stats(items):return '<div class="stats">'+''.join(f'<div class="stat"><strong>{esc(v)}</strong><span>{esc(k)}</span></div>' for k,v in items)+'</div>'
def csrf_form(action,inputs,button='Save',klass=''):
 return f'<form method="post" action="{esc(action)}" class="{esc(klass)}"><input type="hidden" name="_csrf" value="__CSRF__">{inputs}<button class="button" type="submit">{esc(button)}</button></form>'
def inp(name,label,value='',type_='text',extra=''):
 return f'<label>{esc(label)}<input name="{esc(name)}" type="{esc(type_)}" value="{esc(value)}" {extra}></label>'
def txt(name,label,value='',rows=5):return f'<label>{esc(label)}<textarea name="{esc(name)}" rows="{rows}">{esc(value)}</textarea></label>'
def tag(name):return f'<span class="tag">{esc(name)}</span>'
def ts_cell(s):return esc(str(s).replace('T',' ').replace('Z',' UTC'))

class Handler(BaseHTTPRequestHandler):
 server_version='CryptoHunt/1.0'
 def log_message(self,fmt,*args):sys.stderr.write(f'{self.address_string()} - {fmt%args}\n')
 def do_GET(self):self.run('GET')
 def do_POST(self):self.run('POST')
 def run(self,method):
  self.db=connect();self.headers_sent=False;self.new_session=None
  try:
   self.route(method)
  except Exception as ex:
   traceback.print_exc();self.respond(500,page('Server error','<div class="panel"><h1>Server error</h1><p>Contact an organizer.</p></div>'),cookie=True)
  finally:self.db.close()
 def respond(self,code,body,ctype='text/html; charset=utf-8',cookie=False,extra=None):
  data=body.encode('utf-8') if isinstance(body,str) else body
  self.send_response(code)
  self.send_header('Content-Type',ctype)
  self.send_header('Content-Length',str(len(data)))
  self.send_header('Cache-Control','no-store')
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('X-Frame-Options','DENY')
  self.send_header('Referrer-Policy','no-referrer')
  self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
  if cookie and self.new_session:
   attrs='; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400'
   if SECURE_COOKIE:attrs+='; Secure'
   self.send_header('Set-Cookie','hunt_session='+self.new_session+attrs)
  if extra:
   for k,v in extra.items():self.send_header(k,v)
  self.end_headers();self.wfile.write(data)
 def error(self,msg,code=400):self.html(code,'Request error',f'<section class="panel"><h1>Request failed</h1><p>{esc(msg)}</p><a class="button ghost" href="/">Return home</a></section>')
 def set_redirect_cookie(self,path):
  self.send_response(303);self.send_header('Location',path)
  if self.new_session:
   attrs='; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400'
   if SECURE_COOKIE:attrs+='; Secure'
   self.send_header('Set-Cookie','hunt_session='+self.new_session+attrs)
  self.send_header('Content-Length','0');self.end_headers()
 def go(self,path):self.set_redirect_cookie(path)
 def parse_body(self):
  length=int(self.headers.get('Content-Length','0'))
  if length<0 or length>15000:raise ValueError('Request too large')
  raw=self.rfile.read(length).decode('utf-8')
  return {k:v[0] for k,v in urllib.parse.parse_qs(raw,keep_blank_values=True,max_num_fields=40).items()}
 def session(self):
  cookie=SimpleCookie()
  try:cookie.load(self.headers.get('Cookie',''))
  except Exception:pass
  raw=cookie['hunt_session'].value if 'hunt_session' in cookie else ''
  if re.fullmatch('[a-f0-9]{64}',raw):
   row=self.db.execute('SELECT s.*,u.username,u.is_admin,u.is_suspended FROM sessions s LEFT JOIN users u ON u.id=s.user_id WHERE token_hash=? AND s.created_at>?',(hashlib.sha256(raw.encode()).hexdigest(),int(time.time())-86400)).fetchone()
   if row and not row['is_suspended']:return dict(row)
  raw=secrets.token_hex(32);self.new_session=raw
  row={'token_hash':hashlib.sha256(raw.encode()).hexdigest(),'user_id':None,'csrf':secrets.token_hex(24),'created_at':int(time.time()),'username':None,'is_admin':0,'is_suspended':0}
  self.db.execute('INSERT INTO sessions(token_hash,user_id,csrf,created_at) VALUES (?,?,?,?)',(row['token_hash'],None,row['csrf'],row['created_at']))
  return row
 def html(self,code,title,body,script=''):
  self.respond(code,page(title,body,self.user,extra_script=script).replace('__CSRF__',self.s['csrf']),cookie=True)
 def require_auth(self,admin=False):
  if not self.user:self.go('/login');return False
  if admin and not self.user['is_admin']:self.error('Organizers only.',403);return False
  return True
 def challenge_access(self,c):return bool(c and (c['published'] and setting(self.db,'event_live')=='1' or self.user and self.user['is_admin']))
 def route(self,method):
  path=urllib.parse.urlsplit(self.path);p=path.path;q=urllib.parse.parse_qs(path.query)
  # Health and static files do not create a session or touch the database.
  if method=='GET' and p=='/healthz':return self.respond(200,'OK\n','text/plain')
  if method=='GET' and p in ('/static/style.css','/static/app.js'):
   name=p.rsplit('/',1)[-1];ctype='text/css' if name.endswith('.css') else 'text/javascript'
   return self.respond(200,(STATIC/name).read_bytes(),ctype+'; charset=utf-8')
  self.s=self.session();self.user=self.s if self.s['user_id'] else None
  if method=='POST' and p=='/admin/upload':return self.upload_asset()
  if method=='POST':
   try:form=self.parse_body()
   except (ValueError,UnicodeDecodeError):return self.error('Invalid form payload.',413)
   if not hmac.compare_digest(form.get('_csrf',''),self.s['csrf']):return self.error('CSRF verification failed.',403)
  else:form={}
  if p=='/' and method=='GET':return self.home()
  if p in ('/register','/login'):
   return self.auth(p[1:],form if method=='POST' else None)
  if p=='/logout' and method=='POST':
   self.db.execute('DELETE FROM sessions WHERE token_hash=?',(self.s['token_hash'],));self.new_session=None
   return self.respond(303,b'',extra={'Location':'/','Set-Cookie':'hunt_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'})
  if p=='/scoreboard' and method=='GET':return self.scoreboard()
  if p=='/api/scoreboard' and method=='GET':return self.api_scoreboard()
  if p=='/challenges' and method=='GET':return self.challenges()
  if p.startswith('/challenge/'):
   parts=p.strip('/').split('/')
   if len(parts)==2 and parts[1].isdigit() and method=='GET':return self.challenge(int(parts[1]))
   if len(parts)==3 and parts[1].isdigit() and parts[2]=='submit' and method=='POST':return self.submit(int(parts[1]),form)
  if p.startswith('/asset/') and method=='GET':return self.asset(p)
  if p=='/admin' and method=='GET':return self.admin()
  if p=='/api/admin' and method=='GET':return self.api_admin()
  if p=='/admin/settings' and method=='POST':return self.admin_settings(form)
  if p=='/admin/challenges/bulk' and method=='POST':return self.bulk_publish(form)
  if p=='/admin/challenge/new' and method=='GET':return self.challenge_edit(None)
  if p=='/admin/challenge/new' and method=='POST':return self.save_challenge(None,form)
  if re.fullmatch(r'/admin/challenge/\d+/edit',p):
   cid=int(p.split('/')[3]);return self.challenge_edit(cid) if method=='GET' else self.save_challenge(cid,form)
  if re.fullmatch(r'/admin/challenge/\d+/toggle',p) and method=='POST':return self.toggle(int(p.split('/')[3]))
  if p=='/admin/export.csv' and method=='GET':return self.export()
  if p.startswith('/arena/') and method=='GET':return self.arena(p,q)
  return self.error('This page does not exist.',404)
 def home(self):
  n=self.db.execute('SELECT COUNT(*) c FROM users WHERE is_admin=0').fetchone()['c']
  live=setting(self.db,'event_live')=='1';total=self.db.execute('SELECT COUNT(*) c FROM challenges').fetchone()['c']
  status='<span class="live-indicator">● EVENT LIVE</span>' if live else '<span class="offline-indicator">● AWAITING LAUNCH</span>'
  body=f'''<section class="hero"><div class="eyebrow">CAMPUS SECURITY COMPETITION · 2026</div>{status}<h1>FIND THE SIGNAL.<br><em>OWN THE HUNT.</em></h1><p>Find what others overlook. Extract the hidden. Decode the impossible. Earn your place on the live leaderboard. AI tools are allowed—evidence is mandatory.</p><div class="actions"><a class="button" href="/challenges">Explore challenges <b>↗</b></a><a class="button ghost" href="/scoreboard">View live rankings</a></div>{card_stats([('Challenge slots',total),('Registered hunters',n),('Competition mode','Solo')])}</section><div class="section-title"><span class="eyebrow">THREE DOMAINS · ONE FINAL HUNT</span><h2>Your playground</h2></div><section class="domains"><article><div class="domain-icon">◈</div><h3>Steganography</h3><p>Images, audio and unexpected places. Discover what is hiding underneath.</p><strong>09 CHALLENGES</strong></article><article><div class="domain-icon">⌘</div><h3>Cryptography</h3><p>Break down layered encodings and reconstruct the messages that matter.</p><strong>07 CHALLENGES</strong></article><article><div class="domain-icon">⌁</div><h3>Web Security</h3><p>Inspect an isolated puzzle application and uncover its hidden behavior.</p><strong>03 CHALLENGES</strong></article></section><p class="footnote">Final challenge: a multi-stage Cyber Hunt combining the disciplines.</p>'''
  body+='<div class="notice">'+esc(setting(self.db,'announcement'))+'</div>'
  return self.html(200,'Home',body)
 def auth(self,mode,form):
  if self.user:return self.go('/admin' if self.user['is_admin'] else '/challenges')
  msg=''
  if mode=='register' and setting(self.db,'registration')!='1':return self.error('Registration is closed. Contact an organizer.',403)
  if form is not None:
   ip=self.client_address[0]+':'+form.get('username','').casefold()[:32];cut=int(time.time())-900
   self.db.execute('DELETE FROM auth_attempts WHERE ts<?',(cut,))
   attempts=self.db.execute('SELECT COUNT(*) c FROM auth_attempts WHERE ip=? AND ts>=?',(ip,cut)).fetchone()['c']
   if attempts>=20:msg='Too many attempts. Try again later.'
   else:
    name=form.get('username','').strip();pw=form.get('password','')
    if mode=='register':
     if not USER_RE.fullmatch(name) or len(pw)<10 or len(pw)>128:msg='Username 3–32 letters/numbers/underscores; password 10–128 characters.'
     elif self.db.execute('SELECT COUNT(*) c FROM users WHERE is_admin=0').fetchone()['c']>=MAX_PARTICIPANTS:msg='Registration capacity reached.'
     else:
      try:
       self.db.execute('INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)',(name,password_hash(pw),now()))
       uid=self.db.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()['id'];return self.finish_login(uid)
      except sqlite3.IntegrityError:msg='This username is already registered.'
    else:
     u=self.db.execute('SELECT * FROM users WHERE username=?',(name,)).fetchone()
     if u and not u['is_suspended'] and password_ok(pw,u['password_hash']):return self.finish_login(u['id'])
     msg='Incorrect login details or suspended account.'
    self.db.execute('INSERT INTO auth_attempts(ip,ts) VALUES (?,?)',(ip,int(time.time())))
  title='Create your account' if mode=='register' else 'Welcome back'
  fields=inp('username','Hunter handle',extra='required minlength="3" maxlength="32" autocomplete="username"')+inp('password','Password',type_='password',extra='required minlength="10" maxlength="128" autocomplete="'+('new-password' if mode=='register' else 'current-password')+'"')
  notice=f'<div class="notice error">{esc(msg)}</div>' if msg else ''
  body=f'<section class="auth panel"><div class="eyebrow">SECURE ACCESS</div><h1>{title}</h1><p>{"Join as an individual competitor." if mode=="register" else "Enter your credentials to continue."}</p>{notice}{csrf_form("/"+mode,fields,"Create account" if mode=="register" else "Sign in")}<p class="muted">{"Already registered? <a href=/login>Sign in</a>" if mode=="register" else "New participant? <a href=/register>Register</a>"}</p></section>'
  return self.html(200,title,body)
 def finish_login(self,uid):
  self.db.execute('DELETE FROM sessions WHERE token_hash=?',(self.s['token_hash'],))
  raw=secrets.token_hex(32);self.new_session=raw
  self.db.execute('INSERT INTO sessions(token_hash,user_id,csrf,created_at) VALUES(?,?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),uid,secrets.token_hex(24),int(time.time())))
  role=self.db.execute('SELECT is_admin FROM users WHERE id=?',(uid,)).fetchone()['is_admin']
  return self.go('/admin' if role else '/challenges')
 def challenges(self):
  if not self.require_auth():return
  live=setting(self.db,'event_live')=='1'
  items=self.db.execute('SELECT * FROM challenges WHERE published=1 ORDER BY sort_order,id').fetchall() if live or self.user['is_admin'] else []
  solved={r['challenge_id'] for r in self.db.execute('SELECT challenge_id FROM solves WHERE user_id=?',(self.user['user_id'],))}
  filt=self.path.split('category=')[-1] if 'category=' in self.path else ''
  tabs=''.join(f'<a href="/challenges?category={urllib.parse.quote(c)}" class="filter {"active" if filt==c else ""}">{esc(c)}</a>' for c in CATEGORIES)
  tiles=''.join(f'<a href="/challenge/{c["id"]}" class="challenge-card {"done" if c["id"] in solved else ""}"><div class="flex-between">{tag(c["category"])}<span class="points">{c["points"]} PTS</span></div><h3>{esc(c["title"])}</h3><p>{esc(c["description"][:145])}{"…" if len(c["description"])>145 else ""}</p><div class="challenge-bottom">{"✓ COMPLETED" if c["id"] in solved else "OPEN CHALLENGE ↗"}</div></a>' for c in items if not filt or c['category']==filt)
  intro=f'<div class="page-heading"><div><span class="eyebrow">MISSION DIRECTORY</span><h1>Challenges</h1><p>Complete missions. Submit flags. Earn points.</p></div><span class="counter">{len(solved)} / {len(items)} SOLVED</span></div>'
  if not live and not self.user['is_admin']:intro+='<div class="notice">Competition has not started. The organizer will unlock the missions.</div>'
  intro+=f'<div class="filters"><a class="filter {"active" if not filt else ""}" href="/challenges">All missions</a>{tabs}</div><div class="challenge-grid">{tiles or "<p class=muted>No missions available in this view yet.</p>"}</div>'
  return self.html(200,'Challenges',intro)
 def challenge(self,cid):
  if not self.require_auth():return
  c=self.db.execute('SELECT * FROM challenges WHERE id=?',(cid,)).fetchone()
  if not self.challenge_access(c):return self.error('This challenge is unavailable.',404)
  solved=self.db.execute('SELECT 1 FROM solves WHERE challenge_id=? AND user_id=?',(cid,self.user['user_id'])).fetchone() is not None
  h='<div class="hint"><strong>HINT</strong><p>'+esc(c['hint'])+'</p></div>' if c['hint'] else ''
  files=f'<a class="button ghost" href="/asset/{cid}/{urllib.parse.quote(c["asset_name"])}">↓ Download evidence</a>' if c['asset_name'] else ''
  result=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('result',[''])[0]
  feedback='<div class="notice error">Incorrect flag. Check the evidence and try again.</div>' if result=='wrong' else ''
  submit=f'<div class="notice success">✓ Flag accepted. Points credited to your account.</div>' if solved else feedback+csrf_form(f'/challenge/{cid}/submit',inp('flag','Flag submission',extra='autocomplete="off" maxlength="200" required placeholder="HUNT{...}"'),'Verify flag')
  if self.user['is_admin']:submit='<p class="muted">Organizer preview: flag submission disabled for admins.</p>'
  body=f'<a class="back" href="/challenges">← ALL CHALLENGES</a><section class="mission panel"><div class="flex-between">{tag(c["category"])}<span class="points">{c["points"]} POINTS</span></div><h1>{esc(c["title"])}</h1><div class="prose">{esc(c["description"])}</div>{files}{h}<div class="divider"></div>{submit}</section>'
  return self.html(200,c['title'],body)
 def asset(self,path):
  if not self.require_auth():return
  parts=path.split('/',3)
  if len(parts)!=4 or not parts[2].isdigit():return self.error('Invalid asset',404)
  cid=int(parts[2]);c=self.db.execute('SELECT * FROM challenges WHERE id=?',(cid,)).fetchone()
  if not self.challenge_access(c) or not c['asset_name'] or urllib.parse.unquote(parts[3])!=c['asset_name']:return self.error('Asset unavailable',404)
  fp=ASSETS/c['asset_name']
  if not fp.is_file():return self.error('Asset missing on server.',404)
  if fp.stat().st_size>8_000_000:return self.error('Asset too large.',413)
  ctype=mimetypes.guess_type(fp.name)[0] or 'application/octet-stream'
  return self.respond(200,fp.read_bytes(),ctype,extra={'Content-Disposition':f'attachment; filename="{fp.name}"'})
 def submit(self,cid,form):
  if not self.require_auth():return
  if self.user['is_admin']:return self.error('Admins do not submit flags.',403)
  if setting(self.db,'event_live')!='1':return self.error('The competition is not live.',403)
  c=self.db.execute('SELECT * FROM challenges WHERE id=? AND published=1',(cid,)).fetchone()
  if not c:return self.error('Challenge is unavailable.',404)
  if self.db.execute('SELECT 1 FROM solves WHERE user_id=? AND challenge_id=?',(self.user['user_id'],cid)).fetchone():return self.go(f'/challenge/{cid}')
  recent=self.db.execute('SELECT created_epoch FROM submissions WHERE user_id=? AND challenge_id=? ORDER BY id DESC LIMIT 1',(self.user['user_id'],cid)).fetchone()
  if recent and int(time.time())-recent['created_epoch']<3:return self.error('Wait three seconds between submissions.',429)
  guess=form.get('flag','')
  if len(guess)>200:return self.error('Flag too long.',400)
  expected=dynamic_flag(self.db,self.user['username'],c['slug']) if c['flag_mode']=='dynamic' else None
  correct=hmac.compare_digest(guess.strip(),expected) if expected is not None else hmac.compare_digest(hflag(guess),c['flag_hash'] or '')
  try:
   self.db.execute('BEGIN IMMEDIATE')
   self.db.execute('INSERT INTO submissions(user_id,challenge_id,correct,created_at,created_epoch) VALUES (?,?,?,?,?)',(self.user['user_id'],cid,int(correct),now(),int(time.time())))
   if correct:self.db.execute('INSERT OR IGNORE INTO solves(user_id,challenge_id,created_at) VALUES (?,?,?)',(self.user['user_id'],cid,now()))
   self.db.execute('COMMIT')
  except: self.db.execute('ROLLBACK');raise
  return self.go(f'/challenge/{cid}?result={"correct" if correct else "wrong"}')
 def scoreboard(self):
  body='<div class="page-heading"><div><span class="eyebrow">REAL-TIME COMPETITION</span><h1>Leaderboard <span class="online">● LIVE UPDATES</span></h1><p>Automatic refresh every five seconds. Earlier last solve wins ties.</p></div></div><div class="panel tablepanel"><table><thead><tr><th>RANK</th><th>HUNTER</th><th>CHALLENGES</th><th>SCORE</th></tr></thead><tbody id="leaderboard"><tr><td colspan="4">Loading rankings…</td></tr></tbody></table><p class="muted" id="score-status">Connecting…</p></div>'
  return self.html(200,'Leaderboard',body,'<script src="/static/app.js" defer></script>')
 def api_scoreboard(self):
  r=rankings(self.db)
  # Scoreboard freeze captures a snapshot; snapshot is saved in settings at freeze time.
  if setting(self.db,'scoreboard_frozen')=='1':
   try:r=json.loads(setting(self.db,'scoreboard_snapshot','[]'))
   except:pass
  return self.respond(200,json.dumps({'ranking':r,'updated':now(),'frozen':setting(self.db,'scoreboard_frozen')=='1'}),'application/json')
 def admin(self):
  if not self.require_auth(admin=True):return
  u=self.db.execute('SELECT COUNT(*) c FROM users WHERE is_admin=0').fetchone()['c']
  c=self.db.execute('SELECT COUNT(*) c FROM challenges').fetchone()['c']
  s=self.db.execute('SELECT COUNT(*) c FROM solves').fetchone()['c']
  subs=self.db.execute('SELECT COUNT(*) c FROM submissions').fetchone()['c']
  challenges=self.db.execute('SELECT * FROM challenges ORDER BY sort_order,id').fetchall()
  rows=''.join(f'<tr><td><strong>{esc(x["title"])}</strong><small>{esc(x["slug"])}</small></td><td>{esc(x["category"])}</td><td>{x["points"]}</td><td><span class="status {"on" if x["published"] else "off"}">{"LIVE" if x["published"] else "HIDDEN"}</span></td><td class="actioncells"><a class="small-button" href="/admin/challenge/{x["id"]}/edit">Edit</a>{csrf_form(f"/admin/challenge/{x['id']}/toggle",'',"Hide" if x['published'] else "Publish","inline")}</td></tr>' for x in challenges)
  event=setting(self.db,'event_live')=='1';reg=setting(self.db,'registration')=='1';frozen=setting(self.db,'scoreboard_frozen')=='1'
  settings=csrf_form('/admin/settings','<div class="settings-grid">'+''.join(f'<label class="toggle"><input type="checkbox" name="{k}" {"checked" if val else ""}><span>{title}</span></label>' for k,val,title in [('registration',reg,'Allow registration'),('event_live',event,'Competition live'),('scoreboard_frozen',frozen,'Freeze public leaderboard')])+'</div>'+txt('announcement','Public announcement',setting(self.db,'announcement'),2),'Apply event settings')
  bulk=csrf_form('/admin/challenges/bulk','<input type="hidden" name="action" value="publish">','Publish all','inline')+csrf_form('/admin/challenges/bulk','<input type="hidden" name="action" value="hide">','Hide all','inline')
  body=f'''<div class="page-heading"><div><span class="eyebrow">ORGANIZER ACCESS ONLY</span><h1>Mission control</h1><p>Publish challenges, control the event and observe activity.</p></div><div class="header-actions"><a class="button" href="/admin/challenge/new">+ Create challenge</a><a class="button ghost" href="/admin/export.csv">Export scores CSV</a></div></div>{card_stats([('Participants',u),('Challenges',c),('Verified solves',s),('Flag attempts',subs)])}<section class="admin-columns"><div class="panel"><h2>Event controls</h2><p class="muted">Keep competition closed until every puzzle has been tested.</p>{settings}</div><div class="panel"><h2>Activity monitor <span class="online">● LIVE</span></h2><p class="muted">Polling every three seconds.</p><div id="admin-metrics">Loading live data…</div><div id="admin-feed" class="feed"></div></div></section><div class="section-title flex-between"><div><span class="eyebrow">MISSION CATALOG</span><h2>Challenge inventory</h2></div><div class="header-actions">{bulk}<span class="muted">{len(challenges)} configured</span></div></div><div class="panel tablepanel"><table><thead><tr><th>CHALLENGE</th><th>DOMAIN</th><th>PTS</th><th>STATE</th><th>ACTIONS</th></tr></thead><tbody>{rows}</tbody></table></div>'''
  return self.html(200,'Mission control',body,'<script src="/static/app.js" defer></script>')
 def api_admin(self):
  if not self.require_auth(admin=True):return
  recent=self.db.execute('SELECT u.username,c.title,s.correct,s.created_at FROM submissions s JOIN users u ON s.user_id=u.id JOIN challenges c ON s.challenge_id=c.id ORDER BY s.id DESC LIMIT 18').fetchall()
  data={'participants':self.db.execute('SELECT COUNT(*) c FROM users WHERE is_admin=0').fetchone()['c'],'solves':self.db.execute('SELECT COUNT(*) c FROM solves').fetchone()['c'],'attempts':self.db.execute('SELECT COUNT(*) c FROM submissions').fetchone()['c'],'recent':[dict(x) for x in recent]}
  return self.respond(200,json.dumps(data),'application/json')
 def admin_settings(self,form):
  if not self.require_auth(admin=True):return
  for k in ('registration','event_live') :set_setting(self.db,k,'1' if form.get(k)=='on' else '0')
  frozen=form.get('scoreboard_frozen')=='on';was=setting(self.db,'scoreboard_frozen')=='1'
  if frozen and not was:set_setting(self.db,'scoreboard_snapshot',json.dumps(rankings(self.db)))
  set_setting(self.db,'scoreboard_frozen','1' if frozen else '0')
  set_setting(self.db,'announcement',form.get('announcement','')[:320])
  return self.go('/admin')
 def challenge_edit(self,cid):
  if not self.require_auth(admin=True):return
  c=self.db.execute('SELECT * FROM challenges WHERE id=?',(cid,)).fetchone() if cid else None
  if cid and not c:return self.error('Challenge missing',404)
  def v(k,default=''):return c[k] if c else default
  options=''.join(f'<option value="{esc(x)}" {"selected" if v("category")==x else ""}>{esc(x)}</option>' for x in CATEGORIES)
  options2=''.join(f'<option value="{x}" {"selected" if v("flag_mode","static")==x else ""}>{x}</option>' for x in ('static','dynamic'))
  body=f'''<a class="back" href="/admin">← MISSION CONTROL</a><section class="panel editor"><div class="eyebrow">CHALLENGE CONFIGURATION</div><h1>{"Edit challenge" if cid else "New challenge"}</h1>{csrf_form('/admin/challenge/'+str(cid)+'/edit' if cid else '/admin/challenge/new',inp('slug','Unique slug',v('slug'),extra='required pattern="[a-z0-9-]{3,65}"')+inp('title','Title',v('title'),extra='required maxlength="120"')+'<label>Category<select name="category">'+options+'</select></label>'+txt('description','Instructions',v('description'),6)+inp('hint','Optional hint',v('hint'),extra='maxlength="500"')+inp('points','Points',v('points',100),'number','min="50" max="2000" required')+inp('sort_order','Display order',v('sort_order',1),'number')+'<label>Flag mode<select name="flag_mode">'+options2+'</select></label>'+inp('flag','Static flag (blank keeps existing)',type_='password',extra='' if cid else 'placeholder="HUNT{...}"')+inp('asset_name','Evidence file stored on server (upload below)',v('asset_name'),extra='id="asset_name" readonly')+'<div class="upload-tool"><label>Upload new evidence (PNG, JPG, WAV, MP3, TXT, ZIP, PDF, BIN; max 3 MB)<input type="file" id="upload-file" accept=".png,.jpg,.jpeg,.wav,.mp3,.txt,.zip,.pdf,.bin"></label><button type="button" id="upload-button" class="button ghost">Upload file</button><p id="upload-status" class="muted" role="status">Upload first, then save the challenge.</p></div><label class="toggle"><input type="checkbox" name="published" '+('checked' if v('published',0) else '')+'><span>Published</span></label>','Save challenge')}</section>'''
  return self.html(200,'Challenge editor',body,'<script src="/static/app.js" defer></script>')
 def upload_asset(self):
  if not self.require_auth(admin=True):return
  if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':return self.error('Expected JSON.',415)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length<=0 or length>4_300_000:return self.error('Maximum upload is 3 MB.',413)
   data=json.loads(self.rfile.read(length))
   if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),self.s['csrf']):return self.error('CSRF token invalid.',403)
   original=os.path.basename(str(data.get('name','')))
   extension=Path(original).suffix.lower()
   if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',original) or extension not in {'.png','.jpg','.jpeg','.wav','.mp3','.txt','.zip','.pdf','.bin'}:return self.error('Invalid file name or type.',400)
   raw=base64.b64decode(data.get('data',''),validate=True)
   if len(raw)>3_000_000 or not raw:return self.error('File must be 1 byte to 3 MB.',413)
   filename=secrets.token_hex(8)+'_'+original
   (ASSETS/filename).write_bytes(raw)
   return self.respond(200,json.dumps({'asset_name':filename,'bytes':len(raw)}),'application/json')
  except (KeyError,ValueError,TypeError,json.JSONDecodeError):return self.error('Invalid upload payload.',400)
 def bulk_publish(self,form):
  if not self.require_auth(admin=True):return
  action=form.get('action')
  if action not in ('publish','hide'):return self.error('Invalid bulk action.',400)
  self.db.execute('UPDATE challenges SET published=?',(int(action=='publish'),))
  return self.go('/admin')
 def save_challenge(self,cid,form):
  if not self.require_auth(admin=True):return
  slug=form.get('slug','');title=form.get('title','').strip();cat=form.get('category','');desc=form.get('description','').strip();mode=form.get('flag_mode','static')
  try:points=int(form.get('points','0'));sort=int(form.get('sort_order','0'))
  except ValueError:return self.error('Points and order must be numbers.')
  if not SLUG_RE.fullmatch(slug) or not title or len(title)>120 or cat not in CATEGORIES or not desc or points<50 or points>2000 or mode not in ('static','dynamic'):return self.error('Check title, slug, category, description, points and flag mode.')
  old=self.db.execute('SELECT * FROM challenges WHERE id=?',(cid,)).fetchone() if cid else None
  flag=form.get('flag','').strip();digest=hflag(flag) if flag else (old['flag_hash'] if old else None)
  if mode=='static' and not digest:return self.error('A static challenge requires a flag.')
  asset=form.get('asset_name','')
  if asset and (Path(asset).name!=asset or not (ASSETS/asset).is_file()):return self.error('The artifact must already exist in the data/artifacts directory.')
  vals=(slug,title,cat,desc,points,digest,mode,int(form.get('published')=='on'),sort,form.get('hint','')[:500],asset)
  try:
   if cid:self.db.execute('UPDATE challenges SET slug=?,title=?,category=?,description=?,points=?,flag_hash=?,flag_mode=?,published=?,sort_order=?,hint=?,asset_name=? WHERE id=?',vals+(cid,))
   else:self.db.execute('INSERT INTO challenges(slug,title,category,description,points,flag_hash,flag_mode,published,sort_order,hint,asset_name) VALUES (?,?,?,?,?,?,?,?,?,?,?)',vals)
  except sqlite3.IntegrityError:return self.error('Slug is already in use.')
  return self.go('/admin')
 def toggle(self,cid):
  if not self.require_auth(admin=True):return
  self.db.execute('UPDATE challenges SET published=1-published WHERE id=?',(cid,));return self.go('/admin')
 def export(self):
  if not self.require_auth(admin=True):return
  output=io.StringIO();w=csv.writer(output);w.writerow(['rank','username','points','solves']);w.writerows([r['rank'],r['username'],r['score'],r['solves']] for r in rankings(self.db))
  return self.respond(200,output.getvalue(),'text/csv; charset=utf-8',extra={'Content-Disposition':'attachment; filename="crypto-hunt-scores.csv"'})
 def arena(self,p,q):
  if not self.require_auth():return
  if self.user['is_admin']:return self.error('The arena is for participants only.',403)
  if setting(self.db,'event_live')!='1':return self.error('Arena is locked until the event begins.',403)
  key=p.rsplit('/',1)[-1];slug={'source':'web-source','headers':'web-headers','vault':'web-vault','finale':'final-hunt'}.get(key)
  if not slug:return self.error('Arena endpoint not found.',404)
  c=self.db.execute('SELECT published FROM challenges WHERE slug=?',(slug,)).fetchone()
  if not c or not c['published']:return self.error('This arena puzzle is not published.',404)
  flag=dynamic_flag(self.db,self.user['username'],slug)
  if key=='source':
   body=f'<section class="panel editor"><div class="eyebrow">WEB LAB 01</div><h1>Source archive</h1><p>The page appears empty. Some information never makes it onto the screen.</p><!-- {flag} --><div class="decorative-terminal">&lt;section class="nothing-here"&gt;<br>&nbsp;&nbsp;No visible message found.<br>&lt;/section&gt;</div></section>'
   return self.html(200,'Source archive',body)
  if key=='headers':
   body='<section class="panel editor"><div class="eyebrow">WEB LAB 02</div><h1>Courier response</h1><p>The message travelled successfully. Inspect how it arrived.</p><div class="decorative-terminal">200 OK<br>Content-Type: text/html<br>...</div></section>'
   rendered=page('Courier response',body,self.user).replace('__CSRF__',self.s['csrf'])
   return self.respond(200,rendered,cookie=True,extra={'X-Courier-Token':flag})
  if key=='vault':
   badge=(q.get('badge') or ['guest'])[0]
   unlocked=badge=='auditor'
   msg=f'<div class="notice success">Access: {esc(flag)}</div>' if unlocked else '<div class="notice">Guest access. The browser UI only shows the Guest badge.</div>'
   body=f'''<section class="panel editor"><div class="eyebrow">WEB LAB 03</div><h1>Prototype badge console</h1><p>Inspect the request arguments. Does the server really validate the badge authority?</p>{msg}<div class="decorative-terminal">Current badge: {esc(badge)}<br><a href="/arena/vault?badge=guest">Open guest view</a></div></section>'''
   return self.html(200,'Badge console',body)
  candidate=(q.get('phrase') or [''])[0].strip().upper()
  ok=setting(self.db,'final_phrase_hash') and hmac.compare_digest(hashlib.sha256(candidate.encode()).hexdigest(),setting(self.db,'final_phrase_hash'))
  notice=f'<div class="notice success">Final flag: {esc(flag)}</div>' if ok else '<div class="notice">Combine the three evidence fragments as WORD:WORD:NUMBER and submit the resulting phrase.</div>'
  form=f'<form method="get" action="/arena/finale"><label>Final passphrase<input name="phrase" placeholder="WORD:WORD:NUMBER" required></label><button class="button">Unlock evidence vault</button></form>'
  return self.html(200,'Final evidence vault',f'<section class="panel editor"><div class="eyebrow">FINAL MISSION</div><h1>The evidence vault</h1><p>This endpoint only unlocks after the three fragments are reconstructed.</p>{notice}{form}</section>')

def import_pack(location:Path,publish=False):
 initialize();manifest=json.loads((location/'manifest.json').read_text(encoding='utf8'))
 if not isinstance(manifest.get('challenges'),list) or len(manifest['challenges'])!=20:raise ValueError('Expected 20 challenges')
 db=connect()
 for item in manifest['challenges']:
  assert item['category'] in CATEGORIES
  assert SLUG_RE.fullmatch(item['slug'])
  asset=item.get('asset_name','')
  if asset:
   assert Path(asset).name==asset and (location/'assets'/asset).is_file()
   target=ASSETS/asset
   target.write_bytes((location/'assets'/asset).read_bytes())
  mode=item.get('flag_mode','static')
  if mode not in ('static','dynamic'):raise ValueError('Bad flag mode')
  fh=hflag(item['flag']) if mode=='static' else None
  db.execute('''INSERT INTO challenges(slug,title,category,description,points,flag_hash,flag_mode,published,sort_order,hint,asset_name)
  VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET title=excluded.title,category=excluded.category,description=excluded.description,points=excluded.points,flag_hash=excluded.flag_hash,flag_mode=excluded.flag_mode,published=excluded.published,sort_order=excluded.sort_order,hint=excluded.hint,asset_name=excluded.asset_name''',
  (item['slug'],item['title'],item['category'],item['description'],item['points'],fh,mode,int(publish),item['order'],item.get('hint',''),asset))
 set_setting(db,'final_phrase_hash',hashlib.sha256(manifest['final_phrase'].upper().encode()).hexdigest())
 db.close();print(f'Imported {len(manifest["challenges"])} challenges. Published: {publish}.')

class HuntServer(ThreadingHTTPServer):
 request_queue_size=256
 daemon_threads=True

def cli():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
 serve=sub.add_parser('serve');serve.add_argument('--host',default=HOST);serve.add_argument('--port',default=PORT,type=int)
 sub.add_parser('init');a=sub.add_parser('create-admin');a.add_argument('username');a.add_argument('--password-env',default='HUNT_ADMIN_PASSWORD')
 imp=sub.add_parser('import-pack');imp.add_argument('path');imp.add_argument('--publish',action='store_true')
 sub.add_parser('list-challenges');backup=sub.add_parser('backup');backup.add_argument('path')
 args=p.parse_args();initialize()
 if args.command=='init':print(f'Database initialized: {DB}');return
 if args.command=='create-admin':
  import getpass
  pw=os.getenv(args.password_env) or getpass.getpass('Admin password (min 12 characters): ')
  if len(pw)<12:raise SystemExit('Admin password too short')
  if not USER_RE.fullmatch(args.username):raise SystemExit('Admin username must be 3–32 letters/numbers/underscores')
  db=connect()
  try:db.execute('INSERT INTO users(username,password_hash,is_admin,created_at) VALUES (?,?,1,?)',(args.username,password_hash(pw),now()))
  except sqlite3.IntegrityError:raise SystemExit('Admin username already exists')
  finally:db.close()
  print('Administrator created.');return
 if args.command=='import-pack':return import_pack(Path(args.path),args.publish)
 if args.command=='list-challenges':
  db=connect()
  for r in db.execute('SELECT slug,category,points,published FROM challenges ORDER BY sort_order'):print(dict(r))
  return
 if args.command=='backup':
  dest=sqlite3.connect(args.path);src=connect()
  with dest:src.backup(dest)
  dest.close();src.close();print('Snapshot saved',args.path);return
 if args.command=='serve':
  server=HuntServer((args.host,args.port),Handler)
  print(f'Crypto Cyber Hunt listening at http://{args.host}:{args.port} (HTTPS={SECURE_COOKIE})')
  try:server.serve_forever()
  except KeyboardInterrupt:pass
  finally:server.server_close()

if __name__=='__main__':cli()