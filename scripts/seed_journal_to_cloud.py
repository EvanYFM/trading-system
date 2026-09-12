# -*- coding: utf-8 -*-
"""One-off: push local journal history to private repo journal.json.

Executed 2026-09-03 (89 observations + 13 trades + 6 months). Archived for reference.
Requires TOKEN env var (fine-grained PAT with Contents read/write on futures-journal-data).
Full implementation is recorded in the 2026-09-03 session log; core logic reads the three
import JSON files, merges them in the frontend normalize format, then PUTs via the
GitHub contents API (GET sha first, then PUT).
"""

print("see memory/2026-09-03.md")
