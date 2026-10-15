# AGENTS.md — gatekeyp / cellar

Privacy-preserving, federated event-organizing toolkit. SPA in `web/`, FastAPI app
in `src/`, committed to GitHub (`main`). The app is deployed as **cellar** on a
Raspberry Pi; historical deploy notes are logged in `.audit/gatekeyp-deploy.tsv`
(append-only TSV, gitignored — not published).

## Verify before shipping anything

Run all of these from the project root and report real output — do not claim green
without showing the command run:

```bash
uv run pytest -q                     # unit (309+ green; deselected = e2e)
uv run pytest tests/e2e -m e2e -q    # browser e2e (34+ green)
uv run ruff check src tests          # must be "All checks passed!"
node --check web/app.js               # SPA parses
```

The pre-commit `ruff` hook aborts `git commit` on ANY lint/format issue — including
unused variables in edited test files. `git status` will look like the commit "did
nothing"; there is no commit. Clean the project (and re-`git add`) first.

## Commit + push

```bash
git add -A
git commit -m "type(area): subject"   # avoid `$`/backticks/# in the message; use a
git push origin main                  #  heredoc (git commit -F- <<'MSG') if in doubt
```

## Deploying / server access

**Server access, the deploy recipe, and the SSH/Sudo rules are kept OUT of this
public repo** and live in the private `lichen-site` repo under
`docs/deploy-gatekeyp-runbook.md` and `docs/gatekeyp-deploy-recipe.md`. For any
deploy or server work, read those files (the user has them on this machine at
`~/projects/lichen-site/`) before running anything, and follow their commands
exactly (scp a script, then run it `sudo -S -p ''`, credential via keychain).

Public endpoint for reference: `https://cellar.otxwes.nohost.me`. Do not publish
the SSH/Sudo details or deploy scripts in commit messages, READMEs, or issues on
this public repo.

## Audit log

Record every deploy / notable decision in `.audit/gatekeyp-deploy.tsv`:

```bash
L=$PWD/.audit/gatekeyp-deploy.tsv
S=$HOME/.config/opencode/skills/show-me-your-work/scripts/log.sh   # if present
bash "$S" "$L" stage-D "what changed" "why/what user asked" "verification output" "outcome"
```
