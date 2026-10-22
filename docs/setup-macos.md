# macOS setup (verified on 22 October 2026)

Verified on an Apple M3 MacBook Pro with 16 GB RAM, macOS 26.6.2. Each tool comes from its official source and is installed once per computer. Nothing here is stored in Git.

| Tool | Version verified | Purpose |
|---|---|---|
| uv | 0.13.5 | Installs Python 3.13 and the backend packages; runs commands in the project environment |
| Node.js (LTS) + npm | v24.22.1 / 11.19.1 | Builds and tests the React dashboard |
| GitHub CLI (`gh`) | 2.103.0 | Browser-based GitHub login; creates the repository |
| Ollama | 0.40.8 | Runs the Qwen3 4B language model locally on `127.0.0.1:11434` |

## 1. uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Official docs: https://docs.astral.sh/uv/getting-started/installation/. The tool is installed to `~/.local/bin`; open a new Terminal window afterwards. Check it with `uv --version`.

## 2. Node.js 24 LTS
Download the macOS installer (.pkg) from https://nodejs.org/en/download, then check:
```bash
node --version
```
Optionally verify the download against the `SHASUMS256.txt` published for that version, using `shasum -a 256`.

## 3. GitHub CLI
In this release the universal `.pkg` was **unsigned**, so macOS Gatekeeper blocked it. We used the release's arm64 `.zip` instead. Its `gh` binary is signed with GitHub's Apple Developer ID.
```bash
cd ~/Downloads
curl -LO https://github.com/cli/cli/releases/download/v2.103.0/gh_2.103.0_macOS_arm64.zip
shasum -a 256 gh_2.103.0_macOS_arm64.zip   # compare with gh_2.103.0_checksums.txt
unzip -q gh_2.103.0_macOS_arm64.zip
codesign -dv --verbose=2 gh_2.103.0_macOS_arm64/bin/gh   # Authority=Developer ID Application: GitHub
cp gh_2.103.0_macOS_arm64/bin/gh ~/.local/bin/gh
gh --version
```
This copy does not update itself. For a newer version, repeat these steps with the new version number.

Log in with `gh auth login`, choosing GitHub.com, HTTPS and **No** for "Authenticate Git with your GitHub credentials", then a web browser. Answering No keeps the global Git configuration unchanged. This repository connects Git to `gh` through its local configuration instead (see below).

## 4. Ollama
Download `Ollama.dmg` from https://ollama.com/download/mac, drag it to Applications, open it, and accept the command-line tool install. Check it:
```bash
ollama --version
curl http://127.0.0.1:11434/api/version
```

## 5. Project-only Git settings
These are set inside the repository (`.git/config`), not globally:
```bash
git config --local user.name "<github-username>"
git config --local user.email "<id>+<github-username>@users.noreply.github.com"
git config --local credential.https://github.com.helper ''
git config --local --add credential.https://github.com.helper '!gh auth git-credential'
```
Use `gh`'s full path in the last line if it is not on the PATH Git sees, e.g. `~/.local/bin/gh`.

If a push fails with `RPC failed; HTTP 400` (large commits such as screenshots), raise the HTTP buffer for this repository only:
```bash
git config --local http.postBuffer 157286400
```

## 6. Project dependencies
```bash
uv sync                    # creates .venv with Python 3.13 and locked packages
npm ci --prefix frontend   # installs locked dashboard packages
```
