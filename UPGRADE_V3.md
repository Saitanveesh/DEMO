# Crypto Cyber Hunt v3 — Multiple hints and unified mission board

## What changed

- **One student mission board.** All released challenges appear in a single mixed grid. No steganography/cryptography/web filters or separate student sections. Organizer category labels remain for managing inventory.
- **Multiple, sequential hints.** Each challenge supports up to five clues. Hint 1 is free by default. The provided private pack adds clues 2 and 3 to all 20 existing missions, priced at approximately 10% and 20% of base points (rounded up in 10-point increments). Organizers can edit each text and price.
- **Immediate, permanent team deductions.** Purchasing a paid clue debits the team *whether or not* they later solve it. Debits can make a team score negative. A correct flag awards the full base points but does not refund hint purchases. Repeat clicks never charge twice. Clues cannot be purchased after a correct solve or outside a live round.
- **Transparent live scoring.** The leaderboard displays net points, hint deductions and usage. The score graph includes negative-score steps. Organizer activity shows clue purchases, and CSV exports contain earned, deductions and net score.
- Existing teams, rounds, solves, challenge files, flags and administrator account are preserved. Schema changes use `CREATE TABLE IF NOT EXISTS` and only add new tables.

## Update existing Windows installation (do not reset the database)

First stop the running Crypto Cyber Hunt console using Ctrl+C. Leave MON alone.

```powershell
$root = "$env:USERPROFILE\Desktop\crypto-cyber-hunt"
Set-Location $root
$backup = "$env:USERPROFILE\Desktop\CryptoHunt-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item -LiteralPath .\data -Destination (Join-Path $backup 'data') -Recurse
Copy-Item -LiteralPath .\organizer -Destination (Join-Path $backup 'organizer') -Recurse
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\CRYPTO_HUNT_V3_WINDOWS_PATCH.zip" -DestinationPath $root -Force
python app.py init
python -m unittest tests.test_system -v
python start_hunt.py
```

The patch contains `organizer/hints_v3.json`, which is **private organizer-only content**. Keep it off public GitHub. Do not run `setup_event.py` or `import-pack` again on an existing competition. The first `python app.py init` safely creates hint tables and seeds the optional clues without resetting any scores or registrations.

Open the **exact URL** printed by the conflict-free launcher. The port is intentionally different each time so MON is unaffected.

## Quick browser test

1. Log in as admin, go to **Mission control**, select a challenge and click **Edit**. Verify five configurable clue slots and point costs.
2. Deploy a short round containing that challenge. Keep the timer on the organizer screen.
3. In Incognito, log in using a student/team account. The challenge board has one mixed list, no separate category tabs.
4. Open the challenge, unlock clue 1 (free), clue 2 (points deducted), and optionally clue 3 (further deduction).
5. In another window, confirm the team appears on the live leaderboard with a negative hint adjustment. Repeat clicking a purchased hint: it remains unlocked and does not charge again.
6. Submit the correct flag. Its base award increases your team score, while the deductions remain. Return to the admin panel and verify clue events in the live feed and CSV export.
7. After testing, end the round so teams cannot continue submitting or buying clues.

**Important:** All puzzle files, scoring, login and admin functionality need a running Python server. GitHub Pages cannot run this backend. Use a campus-accessible HTTPS server for the real event.
