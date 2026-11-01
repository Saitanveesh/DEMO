# Crypto Cyber Hunt · Release 1.0

A self-hosted cybersecurity competition system designed for ~100 second-/third-year participants. **This is an independent application, not CTFd.** The web server requires only Python 3.10+ and the Python standard library. No subscription or third-party account is required.

![license](https://img.shields.io/badge/license-MIT-42e4c3) ![challenges](https://img.shields.io/badge/challenges-20-42e4c3) ![mode](https://img.shields.io/badge/mode-individual-42e4c3)

## Included

- Participant accounts, session cookies, password hashing (PBKDF2-HMAC-SHA256), CSRF controls, login throttling
- 20 original challenges: 9 steganography, 7 cryptography, 3 isolated web puzzles, 1 final multi-stage hunt
- 17 original media/file artifacts (PNG, WAV, ZIP and TXT)
- Individual scoreboard with 5-second refresh; rank ties broken by last-solve time
- Organizer dashboard: 3-second activity updates, publish/hide, edit/create challenges, event launch/pause, registration toggle, freeze/unfreeze scoreboard, CSV export
- Static, SHA-256-verified flags and participant-specific HMAC-derived flags for three web challenges and the finale
- Private answer key and challenge manifest in a **separate organizer package** (never upload it to public GitHub)
- Docker Compose and native Windows/Linux starter scripts

## Fastest setup (Windows / Linux)

1. Install Python 3.10 or newer (check with `python --version`).
2. Extract the **complete organizer ZIP** into a private folder. Confirm `organizer/competition-pack/manifest.json` exists.
3. In that folder, run `python setup_event.py` and choose a strong organizer password.
4. Start with `python app.py serve` or double-click `start-windows.bat`.
5. Visit **http://127.0.0.1:8000/login**, sign in as organizer, open **Mission control**.
6. Preview/publish challenges, enable **Competition live**, and distribute the server URL to participants.

Participants register via `/register`. View scoreboard at `/scoreboard`; the organizer panel is at `/admin`. The default participant capacity is 120; override with `HUNT_CAPACITY`.

### Developer installation (without private pack)

```sh
python app.py init
python app.py create-admin organizer
python app.py serve
```

The project runs, but you must import a challenge package before publishing an event. Generate your own pack by running `python -m pip install Pillow` and then `python tools/build_challenges.py organizer/competition-pack`. Generated flags are unique to this generation; **never regenerate a pack mid-event**.

Import a generated pack with `python app.py import-pack organizer/competition-pack`. Import defaults to hidden challenges. The private package contains `ORGANIZER_ANSWER_KEY.txt` and `manifest.json`, which must stay outside version control. A second import resets challenge publish state; use carefully.

## Docker Compose

```sh
docker compose build
docker compose run --rm cyberhunt python app.py import-pack /app/import
docker compose run --rm -it cyberhunt python app.py create-admin organizer
docker compose up -d
```

Visit http://127.0.0.1:8000 (Docker binds to loopback by default). The database and artifacts live in the `hunt_storage` Docker volume. The private challenge pack mounts read-only at `/app/import` for import; it is not web-served.

## Campus network deployment

For local development, host defaults to `127.0.0.1`. To bind to campus LAN, run:

```sh
python app.py serve --host 0.0.0.0 --port 8000
```

Then use the machine's LAN IP, e.g. `http://LAN-IP:8000`. Coordinate the inbound firewall rule with the university IT team. **Plain HTTP exposes participant credentials on the network**; prefer an HTTPS reverse proxy and never let participants reuse important passwords. For public internet exposure, put Caddy/Nginx in front with a valid TLS certificate, network firewall, access logging, and DNS. Set `HUNT_HTTPS=1` *only* behind working HTTPS so session cookies are marked `Secure`. Do not run on an unrestricted internet endpoint without an operational security review.

### Reverse proxy example (Caddy)

```caddy
hunt.example.edu {
  reverse_proxy 127.0.0.1:8000
}
```

This Caddyfile requires a domain with working DNS and a reachable reverse proxy. We do not provide hosting, DNS, certificates, or a public URL.

## Organizer workflow

1. **Before event:** Import pack, test each challenge with throwaway participant accounts, keep `Competition live` disabled. Publish only challenges you intend to release.
2. **Registration:** Enable registration. For ~100 users, set capacity 120 to allow testing and late arrivals. A team-based fallback can use one account per team, although individual attribution will be lost.
3. **Launch:** In `/admin`, enable `Competition live`. Challenge files, static flags and `/arena/*` web puzzles become available only to signed-in participants.
4. **Run:** Display `/scoreboard` for auto-refresh rankings. The `/admin` dashboard refreshes submission activity every three seconds.
5. **Close:** Uncheck `Competition live`, freeze rankings, export `/admin/export.csv`. Make a database backup and retain event evidence according to university policy.

### Backup

```sh
python app.py backup hunt-backup.sqlite3
```

The SQLite backup contains user accounts, password hashes, scores and flag hashes. **Also back up `data/artifacts/` and the private organizer pack**. Store them securely; never put backups in public GitHub.

## Challenge catalog

| # | Domain | Title | Difficulty concept |
|---|---|---|---|
| 1 | Steg | The Forgotten Caption | PNG metadata |
| 2 | Steg | The Red Thread | Red-channel LSB |
| 3 | Steg | Blueprint in Blue | RGB channel analysis |
| 4 | Steg | After the Final Pixel | Bytes after PNG IEND |
| 5 | Steg | A Quiet Bitstream | 16-bit WAV LSB |
| 6 | Steg | Beacon at 720 Hz | Audio Morse |
| 7 | Steg | First Row, First Word | Pixel-value stream |
| 8 | Steg | The Transparent Witness | Alpha channel + decoy |
| 9 | Steg | Whispers in the Blue | LSB + XOR |
| 10 | Crypto | Seven Steps Away | Caesar |
| 11 | Crypto | Orbital Cipher | Vigenère |
| 12 | Crypto | The Keyboard Alphabet | Substitution |
| 13 | Crypto | Three Parallel Tracks | Rail fence |
| 14 | Crypto | The Frozen Hex | XOR |
| 15 | Crypto | Tiny Keys, Big Mistake | Toy RSA |
| 16 | Crypto | Three Locks, One Key | ROT13/Base64/hex |
| 17 | Web | The Invisible Source | HTML comment |
| 18 | Web | The Courier Header | HTTP response header |
| 19 | Web | The Badge That Lied | Simulated client-trust flaw |
| 20 | Final | The Final Evidence Vault | 3-part multi-domain puzzle |

### AI usage policy

AI assistance is permitted. Participants may ask AI to suggest tools and analyze the evidence. **This event is not AI-proof.** The fixed file challenges can be solved by a capable participant with AI and access to the artifacts; the three web challenges and final endpoint use per-account flags so public answer sharing is less useful. Scores should reward observed work, not false claims that a model cannot solve a puzzle. Publish rules stating that attacking the organizer portal, network infrastructure, or other participants is prohibited.

## Testing and load simulation

```sh
python -m unittest tests.test_system -v
# File artifact validation requires Pillow:
python -m pip install Pillow
python -m tests.verify_puzzles
python tests/load_probe.py --url http://127.0.0.1:8000 --requests 100
```

These checks cover core HTTP flows but do not certify internet exposure, resilience under all network conditions or adversarial abuse. Verify with a full 100-person rehearsal and monitoring before public rollout.

## Storage and security boundaries

- `data/`: SQLite + participant evidence (private; ignored by Git)
- `organizer/`: challenge flags, answer key and original assets (private; ignored by Git)
- `static/`: CSS/JS, deliberately no embedded secrets
- `tools/build_challenges.py`: public generator code, produces new random flags when run

SQLite WAL handles a modest single-host event and simplifies deployment. The threaded stdlib server is a practical campus prototype, not a hardened high-traffic internet application. The three `/arena/` pages are deliberately vulnerable *only as isolated educational puzzles*; they cannot mutate organizer accounts or challenge scores.