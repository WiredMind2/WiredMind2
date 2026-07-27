# AGENTS.md

## Cursor Cloud specific instructions

### What this project is
A single-script GitHub profile stats generator. `generate_stats.py` queries the
GitHub GraphQL API for a user and writes `github_stats.svg` (embedded in
`README.md`). Production runs happen in CI via `.github/workflows/update_stats.yml`
(daily cron + on push to `main`), which installs `requirements.txt` and runs
`python generate_stats.py`. There is no application server, test suite, or linter
configured.

### Dev environment
Dependencies are installed into a virtualenv at `.venv` by the startup update
script (`python3 -m venv .venv` + `pip install -r requirements.txt`). Use
`.venv/bin/python` to run the script. `requirements.txt` lists `requests` and
`dotenv` (pulls in `python-dotenv`, which provides `load_dotenv`).

### Running / lint / test
- Run: `GITHUB_TOKEN=<pat> GITHUB_USERNAME=WiredMind2 .venv/bin/python generate_stats.py` (writes `github_stats.svg`).
- Syntax check (no linter is configured): `.venv/bin/python -m py_compile generate_stats.py`.
- No automated tests exist.

### Required credentials (non-obvious gotcha)
`generate_stats.py` needs a **classic Personal Access Token** (`ghp_...`) in
`GITHUB_TOKEN` with read access to public user data (e.g. `public_repo` +
`read:user`). The GraphQL query reads the `stargazers` and `languages` fields on
the `repositories` connection, and those are **not** accessible to either:
- the repo's built-in installation token (`ghs_...`) — returns `FORBIDDEN:
  Resource not accessible by integration`, or
- a **fine-grained** PAT (`github_pat_...`) — returns `FORBIDDEN: Resource not
  accessible by personal access token`.

With either of those tokens the script authenticates and fetches most fields but
then crashes at the `total_stars` aggregation with
`TypeError: 'NoneType' object is not subscriptable`. Only a classic PAT resolves
those GraphQL fields end to end. (In CI, `secrets.GITHUB_TOKEN` runs against the
repo owner's own public data.)

`GITHUB_USERNAME` defaults to the GraphQL viewer if unset; pass it explicitly to
target the repo owner (`WiredMind2`).
