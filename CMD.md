# CMD.md - every command to set up and run the ChainAIM research agent (Windows, no AI)

All commands are for **Windows PowerShell** (5.1 or newer). Run them in a normal (non-admin) window.
The agent never uses AI: it fetches transcripts/text and builds prompts. You paste a prompt into
any AI you like (Claude, Gemini, ChatGPT) and save its answer with the app.

`<repo>` below means your install folder (default `C:\ChainAIM\CHAINAIM-TEAM-RESEARCH`).

---

## 1. Set up a new PC (one command)

```powershell
irm https://raw.githubusercontent.com/chainaim3003/CHAINAIM-TEAM-RESEARCH/main/ops/setup.ps1 -OutFile $env:TEMP\setup.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File $env:TEMP\setup.ps1
```

What it does (about 3-10 minutes the first time):
installs git + uv if missing -> clones the repo to `C:\ChainAIM\CHAINAIM-TEAM-RESEARCH` -> installs
packages -> creates `Transcript` + `links.txt` -> runs all tests -> registers the nightly and weekly
tasks -> adds one test link end to end -> opens VS Code. It ends with **SETUP COMPLETE** and a table.
If it stops, fix the message shown and run the same command again (finished steps are skipped).

Options (add after `setup.ps1`):

| Option | Meaning |
|---|---|
| `-InstallDir D:\Work\research` | install somewhere else |
| `-NightlyAt 23:00 -WeeklyDay Saturday -WeeklyAt 10:00` | other run times |
| `-AskGithubToken` | store a GitHub token in `.env` (hidden input; never paste tokens into chat) |
| `-InstallVSCode` | install VS Code too if it is missing |
| `-DryRun` | show what would happen, change nothing |
| `-SkipTests` / `-SkipTasks` / `-SkipSmokeTest` / `-NoVSCode` | skip a step |
| `-Uninstall` | remove the scheduled tasks (files and data are kept) |

Already cloned the repo yourself? From the repo folder:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ops\setup.ps1
```

---

## 2. Daily use

**Add a link (VS Code):** `Ctrl+Shift+P` -> **Tasks: Run Task** -> **Research: add link** -> paste one or
more links (YouTube, GitHub repo/account, arXiv, web article; separate with spaces).

**Add a link (terminal):**
```powershell
cd <repo>; powershell -NoProfile -ExecutionPolicy Bypass -File ops\add_link.ps1 -Link "https://www.youtube.com/watch?v=<id>"
```

**Open the app** (add links, library, copy prompts, save AI answers, digest, task status):
VS Code task **Research: open app**, or
```powershell
cd <repo>; powershell -NoProfile -ExecutionPolicy Bypass -File ops\run_app.ps1
```
Then open http://127.0.0.1:8501 (it opens by itself). Stop with `Ctrl+C`.

**Make a summary:** app -> **Library** -> copy the prompt -> paste into any AI -> copy its answer ->
app -> **Save summary** -> paste -> **Save summary**. It is saved in `Transcript\kb\highlights\`.

**Where files are:** `<repo>\Transcript\kb\`
- `full\` extracted transcripts/text - `prompts\` ready-to-paste prompts - `highlights\` your saved summaries
- `INDEX.md` list with summary status (OK / CHECK / missing) - `digests\` weekly digests

---

## 3. Automation (already set up by step 1)

| Task | When | Does |
|---|---|---|
| ChainAIM-Research-Nightly | daily 02:30 | processes new links in `Transcript\links.txt`, refreshes prompts + INDEX |
| ChainAIM-Research-Weekly | Sunday 09:00 | writes `Transcript\kb\digests\<year>-W<week>.md` |

If the PC is off at that time, the task runs as soon as it is back on (you must be logged in).

Check status:
```powershell
Get-ScheduledTask -TaskName 'ChainAIM-Research-*' | Get-ScheduledTaskInfo | Select-Object TaskName, LastRunTime, LastTaskResult, NextRunTime
```
`LastTaskResult` 0 = OK; 267011 = has not run yet.

Run them now: VS Code tasks **Research: run nightly now** / **Research: weekly digest now**.

Logs: `<repo>\logs\` (one file per run).

---

## 4. Update, repair, remove

**Update to the latest version** (keeps your data):
```powershell
cd <repo>; git pull --ff-only origin main; powershell -NoProfile -ExecutionPolicy Bypass -File ops\setup.ps1 -SkipSmokeTest
```

**Repair** (re-run setup; finished steps are skipped):
```powershell
cd <repo>; powershell -NoProfile -ExecutionPolicy Bypass -File ops\setup.ps1
```

**Run the tests:**
```powershell
cd <repo>\chainaim-deep-research; uv run evals/run_evals.py
```

**Remove the scheduled tasks** (data kept):
```powershell
cd <repo>; powershell -NoProfile -ExecutionPolicy Bypass -File ops\setup.ps1 -Uninstall
```

---

## 5. Troubleshooting

| Message | Fix |
|---|---|
| `installed but is not on PATH yet` | close PowerShell, open a new window, run the setup command again |
| `git is missing and winget is not available` | install git from https://git-scm.com/download/win, run setup again |
| `exists and is not empty` | choose another `-InstallDir` |
| `Local changes found - not updating` | your edits are kept; commit or discard them, then re-run |
| add link exits with code 2 | another run is active; wait and try again |
| file names with `[ID]` not found in PowerShell | use `-LiteralPath` (e.g. `Get-Content -LiteralPath "...[id].txt" -Encoding UTF8`) |

Security: keep keys only in `<repo>\.env` (git-ignored). Never paste keys or `.env` contents into a chat.
