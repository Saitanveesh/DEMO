# v3: hint deductions + unified challenges

The participant interface now shows **one mission board**. Organizer categories still exist in the database for management purposes, but are not split into student views or domains.

A challenge supports up to **five sequential hints**. The provided organizer-only `organizer/hints_v3.json` includes two additional tailored clues for every original challenge. Hint 1 is free, hint 2 costs roughly 10% of its base points and hint 3 roughly 20% (rounding applies). The admin editor can customize or create hints for future challenges and choose prices. Total configured hint costs cannot exceed the base award.

Purchased hints are stored in the `hint_unlocks` ledger with the actual price paid. Reopening an unlocked hint is free. Changes to a later price do not rewrite earlier purchases. An unsolved team can spend its points into a negative balance, and unlocking is available only during an active round. Correct solves are credited in full; hint deductions are not refunded. This is an intentionally explicit competition rule, not an accidental penalty.

Live leaderboard and exported CSV contain net score, earned points, purchased hints and point deductions. The cumulative history chart includes score decreases when hints are unlocked. Organizer monitoring lists hint events alongside flag attempts.

An existing v2 database is migrated on startup without deleting any records. Hint texts and answer keys are not served as static files. Do not commit the private `organizer/` directory to GitHub.

Refer to [UPGRADE_V3.md](UPGRADE_V3.md) for the ready-to-paste Windows setup, backup and validation commands.
