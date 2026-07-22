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
`generate_stats.py` needs a **classic or fine-grained Personal Access Token** in
`GITHUB_TOKEN` with read access to public user data. The repo's built-in
`gh`/git installation token (`ghs_...`, a GitHub App token) authenticates and
returns most fields, but GitHub returns `FORBIDDEN: Resource not accessible by
integration` for the GraphQL `stargazers` and `languages` fields. With that token
the script fails at the `total_stars` aggregation with
`TypeError: 'NoneType' object is not subscriptable`. Provide a real PAT (a repo
Actions secret works in CI) to run end to end. `GITHUB_USERNAME` defaults to the
GraphQL viewer if unset, but an installation token cannot resolve `/user`, so pass
`GITHUB_USERNAME` explicitly (the repo owner is `WiredMind2`).
