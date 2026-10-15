# AGENTS.md — gatekeyp / cellar

Privacy-preserving, federated event-organizing toolkit, deployed as **cellar** on a
Raspberry Pi (YunoHost). SPA in `web/`, FastAPI app in `src/`, committed to GitHub at
`https://github.com/otxwes/gatekeyp` (`main`). Full deployment history is logged in
`.audit/gatekeyp-deploy.tsv` (append-only TSV).

## Verify before shipping anything

Run all of these from `/Users/jackhuang/projects/gatekeyp` and report real output —
do not claim green without showing the command run:

```bash
uv run pytest -q                     # unit (309+ green; deselected = e2e)
uv run pytest tests/e2e -m e2e -q    # browser e2e (34+ green)
uv run ruff check src tests          # must be "All checks passed!"
node --check web/app.js               # SPA parses
```

The pre-commit `ruff` hook aborts `git commit` on ANY lint/format issue —
including unused variables in edited test files. `git status` will look like the
commit "did nothing"; there is no commit. Clean the project (and re-`git add`) first.

## Commit + push

```bash
git add -A
git commit -m "type(area): subject"   # avoid `$`/backticks/# in the message; use a
git push origin main                  #  heredoc (git commit -F- <<'MSG') if in doubt
```

## Deploy to the Pi

Public URL: `https://cellar.otxwes.nohost.me`. On the server the app runs as the
`gatekeyp` service in `/opt/gatekeyp`, loopback-only on `127.0.0.1:8000`, behind
nginx. The deploy scripts live in `tmp/deploy/`.

The one reliable command (deploy, then verify the commit + service + health):

```bash
scp -q tmp/deploy/gkp_app_update.sh otxwes@otxwes.nohost.me:/tmp/gkp_app_update.sh && \
PW=$(security find-generic-password -s webapp_ssh -w 2>/dev/null) && \
printf '%s\n' "$PW" | ssh otxwes@otxwes.nohost.me "sudo -S -p '' bash /tmp/gkp_app_update.sh"
```

`gkp_app_update.sh` does `git fetch/reset --hard origin/main` in `/opt/gatekeyp`
(the untracked `.env` and `keys.db` survive), `chown`, then restarts the service and
prints the deployed commit, service state, and `/health`. Confirm it shows
`deployed commit: <your hash>` and `active`.

### SSH / sudo rules (these save a lot of pain)

- SSH is key-based to `otxwes@otxwes.nohost.me`; the sudo password comes from the
  macOS keychain item named **`webapp_ssh`**.
- **Always scp a script to `/tmp`, then run one `sudo -S -p '' bash /tmp/xxx.sh`.**
  Never chain multiple commands/scripts inside one `sudo` (a chained second command
  runs as the unprivileged user and fails for no visible reason).
- Verify server state with a read-only probe script:
  `scp tmp/deploy/gkp_state_probe.sh ...:/tmp/` then run it `sudo -S -p ''`.
- Schema migrations run automatically on the Pi via the app's `_migrate_schema`
  (`PRAGMA table_info(events)` etc. can confirm a new column landed).
- The SSH port-forward for loopback service access (tunnel) dies on remote-host
  timeouts; re-establish with:
  `ssh -o BatchMode=yes -N -L 8000:127.0.0.1:8000 otxwes@otxwes.nohost.me`

## Audit log

Record every deploy / notable decision in `.audit/gatekeyp-deploy.tsv`:

```bash
L=$PWD/.audit/gatekeyp-deploy.tsv
S=$HOME/.config/opencode/skills/show-me-your-work/scripts/log.sh   # if present
bash "$S" "$L" stage-D "what changed" "why/what user asked" "verification output" "outcome"
```
