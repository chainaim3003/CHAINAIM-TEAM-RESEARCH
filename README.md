# CHAINAIM-TEAM-RESEARCH

A free, AI-free research agent for Windows: give it YouTube, GitHub, arXiv or web-article links and it
saves the transcript / text plus a ready-to-paste prompt. You paste the prompt into any AI and save the
answer with a small local app. Nightly and weekly runs are automatic.

## Set up on a new PC (one command, Windows PowerShell)

```powershell
irm https://raw.githubusercontent.com/chainaim3003/CHAINAIM-TEAM-RESEARCH/main/ops/setup.ps1 -OutFile $env:TEMP\setup.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File $env:TEMP\setup.ps1
```

Installs what is missing, clones to `C:\ChainAIM\CHAINAIM-TEAM-RESEARCH`, runs the tests, registers the
scheduled tasks, tests one link end to end and opens VS Code. Details and options: [SETUP.md](SETUP.md).

## Use it

- VS Code: `Ctrl+Shift+P` -> **Tasks: Run Task** -> **Research: add link** (paste a URL) or **Research: open app**
- Every command: [CMD.md](CMD.md)
- How the agent works: [chainaim-deep-research/README.md](chainaim-deep-research/README.md)
