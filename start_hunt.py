"""Conflict-free local launcher for Crypto Cyber Hunt.

Works with the complete, stdlib-only competition release. The operating system
chooses an unused local TCP port. Verifies the actual app before opening Chrome.
Does not modify competition database, flags or existing MON services.
"""
from __future__ import annotations

import argparse
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description='Start Crypto Cyber Hunt on a free local port')
    parser.add_argument('--no-browser', action='store_true', help='Only print the verified URL')
    args = parser.parse_args()

    try:
        from app import ASSETS, DATA, Handler, HuntServer, connect, initialize
    except (ImportError, ModuleNotFoundError) as exc:
        print('\nERROR: This launcher needs the COMPLETE Crypto Cyber Hunt release, not the old Flask MVP.')
        print('Your folder must contain app.py, setup_event.py, and organizer/competition-pack/.')
        print(f'Detail: {exc}')
        return 2

    initialize()
    db = connect()
    try:
        n_admin = db.execute('SELECT COUNT(*) FROM users WHERE is_admin=1').fetchone()[0]
        n_challenges = db.execute('SELECT COUNT(*) FROM challenges').fetchone()[0]
    finally:
        db.close()

    print('\n' + '=' * 60)
    print('CRYPTO CYBER HUNT | VERIFIED LOCAL LAUNCHER')
    print('=' * 60)
    print('Directory: ', Path(__file__).resolve().parent)
    print('Database:  ', DATA / 'hunt.sqlite3')
    print('Admins:    ', n_admin)
    print('Challenges:', n_challenges)

    if not n_admin or not n_challenges:
        print('\nFIRST-TIME SETUP REQUIRED')
        print('Run: python setup_event.py')
        print('Then run: python start_hunt.py')
        print('No existing competition data was deleted.')
        return 2

    # Port 0 asks Windows to choose an available ephemeral port while binding
    # atomically. This avoids the check-then-bind race of manually picking ports.
    try:
        server = HuntServer(('127.0.0.1', 0), Handler)
    except OSError as exc:
        print(f'Cannot bind the local HTTP server: {exc}')
        return 1

    port = server.server_address[1]
    base = f'http://127.0.0.1:{port}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def verify_and_launch() -> None:
        try:
            with opener.open(base + '/healthz', timeout=8) as response:
                if response.status != 200 or response.read().strip() != b'OK':
                    raise RuntimeError('Unexpected response from the health endpoint')
            with opener.open(base + '/', timeout=8) as response:
                page = response.read().decode('utf-8')
                if response.status != 200 or '<title>Home · Crypto Cyber Hunt</title>' not in page:
                    raise RuntimeError('Another application answered on the selected port')
            print('\n[PASS] Loopback health check: correct Crypto Cyber Hunt service')
            print('[PASS] Homepage response: Crypto Cyber Hunt identified')
            print('\nOPEN THIS ADDRESS:', base + '/')
            print('ADMIN LOGIN:       ', base + '/login')
            print('ADMIN PANEL:       ', base + '/admin')
            print('\nKeep this window open while using the website.')
            if not args.no_browser:
                print('Opening your default browser...')
                webbrowser.open_new_tab(base + '/')
        except Exception as exc:
            print(f'\n[FAIL] Application self-check: {exc}')
            print('Keep the error message and run: python -m unittest tests.test_system -v')

    threading.Thread(target=verify_and_launch, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.15)
    except KeyboardInterrupt:
        print('\nStopping Crypto Cyber Hunt. MON is unchanged.')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
