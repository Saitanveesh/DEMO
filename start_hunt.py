"""Start Crypto Cyber Hunt without conflicting with MON or another local service."""
import argparse
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Launch Crypto Cyber Hunt safely")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        from app import DATA, Handler, HuntServer, connect, initialize
    except ImportError as exc:
        print("ERROR: Use the COMPLETE Crypto Cyber Hunt release, not the old MVP.")
        print("Detail:", exc)
        return 2
    initialize()
    db = connect()
    try:
        admins = db.execute("SELECT COUNT(*) FROM users WHERE is_admin=1").fetchone()[0]
        challenges = db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
    finally:
        db.close()
    print("\nCrypto Cyber Hunt / conflict-free Windows launcher")
    print("Directory:", Path(__file__).resolve().parent)
    print("Database:", DATA / "hunt.sqlite3")
    print("Admins:", admins, "Challenges:", challenges)
    if not admins or not challenges:
        print("First-time setup required: python setup_event.py")
        print("Then run: python start_hunt.py")
        return 2
    with HuntServer(("127.0.0.1", 0), Handler) as server:
        port = server.server_address[1]
        base = "http://127.0.0.1:" + str(port)
        def verify():
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(base + "/healthz", timeout=8) as res:
                    if res.status != 200 or res.read().strip() != b"OK":
                        raise RuntimeError("Wrong health check response")
                with opener.open(base + "/", timeout=8) as res:
                    if res.status != 200 or "<title>Home · Crypto Cyber Hunt</title>" not in res.read().decode("utf-8"):
                        raise RuntimeError("Another application answered")
                print("\n[PASS] Crypto Cyber Hunt responded, MON is unchanged")
                print("WEBSITE:", base + "/")
                print("ADMIN:", base + "/admin")
                print("LOGIN:", base + "/login")
                print("Keep this PowerShell window open.")
                if not args.no_browser:
                    webbrowser.open_new_tab(base + "/")
            except Exception as exc:
                print("[FAIL] Local server verification:", exc)
        threading.Thread(target=verify, daemon=True).start()
        try:
            server.serve_forever(poll_interval=0.15)
        except KeyboardInterrupt:
            print("\nStopped Crypto Cyber Hunt.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
