"""Independent challenge validation; requires Pillow for image analyses."""
from __future__ import annotations
import base64,codecs,io,json,re,struct,wave,zipfile,math
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'organizer'/'competition-pack'
files=PACK/'assets'
data=json.loads((PACK/'manifest.json').read_text())
flags={i['slug']:i.get('flag') for i in data['challenges']}
def check(slug,result):
 assert result==flags[slug],f'{slug}: decoded {result!r}, expected {flags[slug]!r}'
 print('PASS',slug)

def lsb_read(im,channel):
 raw=im.tobytes();stride=len(im.getbands());one=[(raw[j*stride+channel]&1) for j in range(min((len(raw)//stride),1800))]
 def getbyte(off):return sum(one[off+i]<<(7-i) for i in range(8))
 n=256*getbyte(0)+getbyte(8)
 return bytes(getbyte(16+8*i) for i in range(n))

with Image.open(files/'01_station.png') as im:check('steg-metadata',im.info['Description'].split(' ')[-1])
with Image.open(files/'02_red_channel.png') as im:check('steg-red-lsb',lsb_read(im.convert('RGB'),0).decode())
with Image.open(files/'03_blueprint.png') as im:
 # Blue high-contrast ink is visible when isolating one plane; check ink present.
 blue=im.getchannel('B');assert blue.getextrema()[1]>220
 print('PASS steg-blue (visual blue-plane ink present)')
raw=(files/'04_after_the_end.png').read_bytes();payload=raw.split(b'ARCHIVE PAYLOAD BEGINS\n')[1].split(b'\n')[0]
check('steg-trailer',base64.b64decode(payload).decode())
with wave.open(str(files/'05_carrier.wav'),'rb') as w:
 assert w.getsampwidth()==2 and w.getnchannels()==1
 samples=struct.unpack('<'+'h'*w.getnframes(),w.readframes(w.getnframes()))
 b=[x&1 for x in samples]
 def char_at(off):return sum(b[off+i]<<(7-i) for i in range(8))
 n=char_at(0)*256+char_at(8)
 check('steg-audio-lsb',bytes(char_at(16+8*k) for k in range(n)).decode())
# For Morse inspect temporal on/off runs in a decoded amplitude array.
with wave.open(str(files/'06_beacon.wav'),'rb') as w:
 rate=w.getframerate();s=struct.unpack('<'+'h'*w.getnframes(),w.readframes(w.getnframes()))
 window=320;gates=[max(abs(v) for v in s[i:i+window])>4000 for i in range(0,len(s),window)]
 runs=[]
 for v in gates:
  if runs and runs[-1][0]==v:runs[-1][1]+=1
  else:runs.append([v,1])
 from tools.build_challenges import MORSE
 inv={v:k for k,v in MORSE.items()};message='';pattern=''
 for idx,(val,length) in enumerate(runs):
  if val:pattern+='-' if length>7 else '.'
  elif length>5 and pattern:message+=inv[pattern];pattern=''
 if pattern:message+=inv[pattern]
 check('steg-morse','HUNT{'+message+'}')
with Image.open(files/'07_scanline.png') as im:
 pix=im.convert('RGB').load();n=pix[0,0][0]*256+pix[1,0][0]
 check('steg-scanline',bytes(pix[k+2,0][0] for k in range(n)).decode())
with zipfile.ZipFile(files/'08_casefile.zip') as z:
 with Image.open(io.BytesIO(z.read('case/trace.png'))) as im:check('steg-alpha',lsb_read(im.convert('RGBA'),3).decode())
with Image.open(files/'09_whisper.png') as im:
 b=lsb_read(im.convert('RGB'),2);key=b'ECHO'
 check('steg-xor',bytes(v^key[i%4] for i,v in enumerate(b)).decode())
raw=(files/'10_shift.txt').read_text().splitlines()[1]
check('crypto-caesar',''.join(chr((ord(c)-65-7)%26+65) if 'A'<=c<='Z' else c for c in raw))
raw=(files/'11_orbit.txt').read_text().split('CIPHERTEXT = ')[1].splitlines()[0]
key='ORBIT';out='';j=0
for c in raw:
 if c.isalpha():out+=chr((ord(c)-ord(key[j%5]))%26+65);j+=1
 else:out+=c
check('crypto-vigenere',out)
text=(files/'12_monoalphabet.txt').read_text().splitlines();mapping=dict(zip(text[1][8:],text[0][8:]));check('crypto-substitution',''.join(mapping.get(c,c) for c in text[3].split(': ')[1]))
raw=(files/'13_rails.txt').read_text().split('TRANSPOSED = ')[1].splitlines()[0]
rail_count=3;pos=[];row=0;direction=1
for _ in raw:
 pos.append(row)
 if row==0:direction=1
 elif row==rail_count-1:direction=-1
 row+=direction
out=['']*len(raw);cursor=0
for rail in range(rail_count):
 for i,p in enumerate(pos):
  if p==rail:out[i]=raw[cursor];cursor+=1
check('crypto-rail',''.join(out))
hex_blob=(files/'14_frozen_hex.txt').read_text().splitlines()[1];key=b'ICE';blob=bytes.fromhex(hex_blob)
check('crypto-xor',bytes(v^key[i%3] for i,v in enumerate(blob)).decode())
lines=(files/'15_rsa.txt').read_text().splitlines();n=int(lines[0].split('=')[1]);e=int(lines[1].split('=')[1]);cipher=list(map(int,lines[3].split()))
p=next(x for x in range(2,math.isqrt(n)+1) if n%x==0);q=n//p;d=pow(e,-1,(p-1)*(q-1))
check('crypto-small-rsa',''.join(chr(pow(c,d,n)) for c in cipher))
raw=(files/'16_layers.txt').read_text().splitlines()[1]
check('crypto-layers',codecs.decode(base64.b64decode(bytes.fromhex(raw)).decode(),'rot_13'))
with zipfile.ZipFile(files/'20_final_hunt.zip') as z:
 with Image.open(io.BytesIO(z.read('01-visual.png'))) as im:p1=im.info['First-fragment']
 p2=codecs.decode(z.read('02-radio.txt').decode().split(': ')[1].strip(),'rot_13')
 p3=int(z.read('03-terminal.txt').decode().split(': ')[1].split()[0],2)
 phrase=f'{p1}:{p2}:{p3}'
 assert phrase==data['final_phrase'];print('PASS final-hunt 3-fragment phrase')
assert len(data['challenges'])==20
print('All asset-level puzzle checks passed.')