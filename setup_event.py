"""Organizer's first-time setup: imports the private pack and creates an admin."""
import getpass, json, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PACK=ROOT/'organizer'/'competition-pack'

def run(*args):
 return subprocess.run([sys.executable,str(ROOT/'app.py'),*args],check=True)

if __name__=='__main__':
 print('\nCRYPTO CYBER HUNT — FIRST-TIME SETUP\n')
 if not (PACK/'manifest.json').is_file():
  sys.exit('Organizer pack missing. Unzip competition-pack under organizer/competition-pack first.')
 run('init');run('import-pack',str(PACK))
 print('\nCreate the organizer account. This password will NOT be displayed or saved in source files.')
 username=input('Administrator username [organizer]: ').strip() or 'organizer'
 pw=getpass.getpass('Administrator password (12+ characters): ')
 check=getpass.getpass('Repeat password: ')
 if pw!=check or len(pw)<12:sys.exit('Passwords do not match or are too short.')
 os.environ['HUNT_ADMIN_PASSWORD']=pw
 try:run('create-admin',username)
 finally:os.environ.pop('HUNT_ADMIN_PASSWORD',None)
 print('\nSETUP COMPLETE\nRun: python app.py serve\nOpen http://127.0.0.1:8000/admin and sign in.\n20 challenges were imported but are HIDDEN. Publish and start them from Mission control after testing.\n')