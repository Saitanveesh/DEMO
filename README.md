# CRYPTO CYBER HUNT — Team Tournament v2.0

Independent, self-hosted cybersecurity competition portal for a campus event with approximately 100 participants. **Not CTFd. No paid dependency.** Server uses Python 3.10+ standard library; browser charts are implemented with SVG, without external JS frameworks.

## What's new in v2

- **Team registration:** team name, 2–4 member names, team login handle and password. Teams have one shared login and one combined score; individual contributions within a team are **not** separately attributable. Organizer can edit team names and rosters after registration.
- **Dynamic rounds:** organizer selects any challenges in Mission Control, enters a round name and duration (1–240 minutes), and clicks **Deploy selected challenges**. There is no need to assign challenges to rounds beforehand. Example: 10 in Round 1, 5 in Round 2, 5 in Round 3.
- **Server-enforced deadline:** the countdown begins at deploy time and is visible throughout participant pages. All unselected and expired challenges, file downloads, flags, and arena puzzles are blocked server-side. Round duration does not depend on the participant's computer clock. No pause/extension mechanism: end a round and deploy another when ready.
- **Live team leaderboard:** automatic five-second updates, top-three podium, top-five score-vs-time SVG, cumulative points, and rank table. Graph data comes from saved solves, not simulation. Freeze makes a scoreboard and graph snapshot.
- **Admin controls:** end an active round early; edit team rosters; export team results CSV; view recent attempts; toggle registration; edit challenges and add evidence files. Previously earned scores remain across rounds.
- **Visual polish:** subtle perspective/depth, restrained gradients, responsive cards and an always-visible countdown strip; supports reduced-motion preference.

### Important upgrade for existing users (including `Test001`)

**Do not run `setup_event.py` or `import-pack` on your existing event.** Those commands are for initial setup and re-importing can reset challenge publication and flags.

1. Stop the existing Crypto Cyber Hunt server (MON is unrelated and does not need to be stopped).
2. Make a private backup of the entire `data/` folder, including `hunt.sqlite3`, `hunt.sqlite3-wal`, `hunt.sqlite3-shm` (if present), and `data/artifacts/`. Also retain the private `organizer/` folder. Keep this backup outside public GitHub.
3. Copy the v2 `app.py`, `static/app.js`, `static/style.css`, and, optionally, `tests/test_system.py` into the existing `crypto-cyber-hunt` folder. Replace the old code files **but not** `data/` or `organizer/`.
4. From PowerShell in that folder, run:

   ```powershell
   python start_hunt.py
   ```

5. Use the exact free-port URL printed by the launcher. Log in with the original admin password. The database migration runs automatically and does not delete scores or passwords.
6. Your existing student logins are migrated to single-member team records, with the same username, password and scores. Use **Mission control → Registered team roster → Edit roster** to add team members and rename an old team as needed. New registrations require 2–4 names.

**Known behavior:** Any pre-v2 event with `Competition live` enabled will be effectively locked until you deploy its first v2 round. This is intentional to prevent accidental early release. Existing solve records remain in the leaderboard.

## First-time deployment (new organizer)

1. Extract the complete private package into `crypto-cyber-hunt/`. Verify `organizer/competition-pack/manifest.json` exists.
2. Run `python setup_event.py` once. Create a strong administrator login/password.
3. Run `python start_hunt.py` (or double-click `start-windows.bat`). This chooses an unused port, so it will not conflict with the MON dashboard.
4. Open the printed URL in your browser and log in. Navigate to `/admin`.
5. Under **Release control**, enter e.g. `Qualifier`, `30` minutes, tick 10 challenge cards, and click **Deploy selected challenges**. A confirmation dialog prevents accidental deployment.
6. Students register their teams at `/register`. They immediately see the selected challenge cards and countdown, and submit flags through each challenge page. Other rounds and challenge files stay hidden.
7. End the round or allow its timer to expire. Select the second set of challenges and deploy the next round, without resetting scores. Repeat as needed.
8. Display `/scoreboard` on a projector; export CSV from Mission Control. Turn off registration or freeze the leaderboard when needed.

## Challenge distribution

| Category | Challenges |
|---|---:|
| Steganography | 9 |
| Cryptography | 7 |
| Web security (simulated isolated arena) | 3 |
| Final multi-stage Cyber Hunt | 1 |

The package contains 17 evidence artifacts, an organizer-only manifest and answer key, and three dynamic web puzzles plus a team-specific final flag. **Do not commit or share `organizer/`, `data/`, or the private ZIP**. Static challenge flags can still be shared or solved with AI; the event is not AI-proof.

## Event semantics

- A **round** is a set of specific challenge IDs and one authoritative server deadline. Only one round runs at a time. First round starts when Deploy is clicked. Ending or expiry immediately locks new submissions and evidence downloads for that round.
- Challenge eligibility toggle (**Enabled/Hidden**) can withdraw a live challenge. Deploying a challenge automatically enables it. A challenge from an earlier round does not remain accessible during the next round unless selected again.
- One team can earn a particular challenge's points **only once across the whole event**, even if an organizer reuses that challenge in another round.
- Previous solves remain recorded and count toward the team's cumulative total. Ties are ordered by the team's earliest final solve.
- Existing solo student accounts become one-member legacy teams; they can be edited by the organizer. New team registrations accept exactly 2–4 members.
- The **team login/password is shared** among that team's members. If separate personal logins or member-level attribution are required in a future version, a multi-account membership model will be needed.

## Security and network deployment

This is a campus-scale threaded Python/SQLite server, **not an internet-hardened service**. Keep it local for development. For the campus network, deploy behind HTTPS and a reverse proxy; never expose plaintext HTTP logins over a shared Wi-Fi network. Arrange secure hosting, access controls, database/artifact backups and a 100-person rehearsal before public launch. Set `HUNT_HTTPS=1` only when TLS is functioning end-to-end behind your reverse proxy.

- Local start: `python start_hunt.py`
- Explicit host/port: `python app.py serve --host 127.0.0.1 --port 8800`
- LAN (only behind appropriate HTTPS gateway): `python app.py serve --host 0.0.0.0 --port 8800`
- Team capacity default: 120 accounts; set `HUNT_CAPACITY` to override.
- Health: `/healthz` must return HTTP 200 and `OK`.
- Server round-state API: `/api/event` returns `active`, round identifier/name, server timestamp, deadline and number of active challenges.
- Leaderboard JSON: `/api/scoreboard` returns team rankings, score history and freeze status.
- Organizer activity: `/api/admin` is restricted to organizer logins.
- SQLite snapshot: `python app.py backup pre-upgrade-backup.sqlite3` (store privately). Also back up `data/artifacts/` separately.

GitHub Pages **cannot** run this Python backend, session authentication or SQLite scoring. GitHub hosts the source; use Windows/Linux hosting or a dynamic application host for the event itself.

## Quality checks

```powershell
python -m unittest discover -s tests -v
```

The private-package tests exercise team creation, score continuity, launch selection, unauthorized challenge access, early termination, automatic deadline expiry, multiple rounds, team-specific flags, leaderboard history, roster editing, migration and admin-only controls.

Artifact generation/evidence checks (Pillow is optional only for generating or verifying artifacts):

```powershell
python -m pip install Pillow
python -m tests.verify_puzzles
python tests/load_probe.py --url http://127.0.0.1:PORT --requests 100
```

A passing integration test is not a substitute for a full on-site load/security rehearsal.
