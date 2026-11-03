# Safe Windows upgrade — Solo v1 → Team Tournament v2

No reinstall, no database reset, no challenge regeneration, no MON changes.

1. **Stop only Crypto Cyber Hunt** (`Ctrl+C` in its terminal). Leave MON running if you need it.
2. In `C:\Users\saita\Desktop\crypto-cyber-hunt`, copy the complete `data` directory somewhere private as a backup. Copy the private `organizer` directory as well. Never upload either to GitHub.
3. Extract the small `CRYPTO_HUNT_V2_WINDOWS_PATCH.zip` into that exact folder, replacing the included source files. **Never replace `data/` or `organizer/`.**
4. Open PowerShell in that directory and run:

   ```powershell
   python start_hunt.py
   ```

5. Use the exact URL displayed by PowerShell. Sign in as your existing admin and open Mission Control.
6. Under **Release control**, select your Round 1 challenges, set `30` minutes and click **Deploy selected challenges**.
7. Open an Incognito window and register a new team with a team name, two to four member names, a team login and a strong password.
8. Verify that only Round 1 challenges are visible, the countdown decreases, and solving one challenge adds points to the *team* leaderboard and score graph.
9. Return to Mission Control and use **End current round now** for a short test. The challenge pages should lock while earlier scores remain visible. Deploy Round 2 with a different set.

**Already registered as `Test001`?** That account remains usable. It is converted to a legacy one-member team and can be renamed/expanded by the admin in **Registered team roster → Edit roster**.

**One credential per team:** multiple members can use the same login and share the score, but the platform cannot identify which member submitted a flag. Share credentials privately; do not reuse institutional passwords.

**No external access by default:** the conflict-free launcher binds to local loopback only. For ~100 on-campus participants use an IT-approved HTTPS deployment, and rehearse the full event before launch.
