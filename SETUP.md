# SETUP.md - new PC setup, step by step (Windows)

## Before you start
- Windows 10 or 11, signed in as yourself (no admin rights needed).
- Internet access (downloads git/uv if missing, Python packages, one test link).
- About 3-10 minutes and ~1 GB of disk.
- Optional: VS Code (add `-InstallVSCode` to install it), a GitHub token (`-AskGithubToken`).

## Run
1. Open **Windows PowerShell** (Start -> type "PowerShell").
2. Go to the folder where you want the project, e.g. `cd D:\Work` (it will be created as
   `D:\Work\CHAINAIM-TEAM-RESEARCH`). If you skip this, it goes in your home folder
   (`C:\Users\<you>\CHAINAIM-TEAM-RESEARCH`). If you `cd` into an existing clone of this repo, that clone is used.
3. Paste:
```powershell
irm https://raw.githubusercontent.com/chainaim3003/CHAINAIM-TEAM-RESEARCH/main/ops/setup.ps1 -OutFile $env:TEMP\setup.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File $env:TEMP\setup.ps1
```
Want to see the plan first? Add ` -DryRun` at the end: nothing is changed.

## What you will see

| Step | Screen shows | Means |
|---|---|---|
| [1/10] Check this PC | `Windows OK, PowerShell 5.1...` | supported |
| [2/10] Tools | `git found` / `uv found`, or an install | git + uv ready |
| [3/10] Code | `git clone ...` (first time) or `git pull` | repo in `<your folder>\CHAINAIM-TEAM-RESEARCH` |
| [4/10] Packages | `uv sync --frozen`, then the transcript tool's help text | packages installed |
| [5/10] Knowledge base | (quiet) | `Transcript` + `links.txt` created |
| [6/10] .env | `.env created` | optional keys file (empty is fine) |
| [7/10] Tests | `== EVAL SUMMARY ==  N/N checks passed` + `ALL PASS` | code works on this PC |
| [8/10] Scheduled tasks | `registered: ChainAIM-Research-Nightly` / `-Weekly` | automation on |
| | or `already belong to another copy ... Kept them unchanged` | this PC already has another copy with tasks; add `-ReplaceTasks` to move them here |
| [9/10] End-to-end test | `nightly/add link ... OK`, `OK: 1 prompt file(s), INDEX.md written` | a real link went all the way through |
| [10/10] VS Code | VS Code opens on the repo | ready to use |

It ends with **SETUP COMPLETE** and a result table. The log is saved in `<repo>\logs\setup-<time>.log`.

If it shows **SETUP STOPPED**, read the red line, fix it (see CMD.md -> Troubleshooting) and run the same
command again; steps already done are skipped.

## After setup
1. VS Code: `Ctrl+Shift+P` -> **Tasks: Run Task** -> **Research: add link** -> paste a YouTube/GitHub/arXiv/article link.
2. VS Code: **Tasks: Run Task** -> **Research: open app** -> Library -> copy the prompt -> paste into any AI ->
   copy the answer -> **Save summary**.
3. Leave the PC on (or let it catch up): new links in `Transcript\links.txt` are processed nightly; a weekly
   digest is written on Sunday.

All commands: [CMD.md](CMD.md).
