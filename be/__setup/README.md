# `be/__setup` — full-stack assembly (source of truth)

This folder lives **only in the backend repo**. It holds Docker, shell scripts, and docs needed to run **backend + frontend** together. It does **not** contain React source code.

## One-time workspace layout

```text
<any-workspace-name>/          ← not a git repo; assemble target
  be/                          ← clone backend repo
    __setup/                   ← you are here
  fe/                          ← clone frontend repo
```

## Assemble (after cloning both repos)

```bash
cd /path/to/<workspace>
cp .env.example .env    # first time only — edit POSTGRES_PASSWORD
./be/__setup/assemble.sh
```

The script copies everything from `be/__setup/` into the workspace root **without overwriting** files that already exist.

Then run the stack from the workspace root:

```bash
cd /path/to/<workspace>
./run_docker.sh
./check_data.sh
```

PostgreSQL runs in Docker (`db` service). Data persists in the `postgres_data` volume.

## What gets copied

- `docker-compose.yml`, `docker-compose.dev.yml`
- `run_docker.sh`, `stop_docker.sh`, `run_production.sh`, `stop_production.sh`
- `check_data.sh`, `init_modules.sh`, `run.py`
- `docs/`
- `.env.example`, `.env.production.example`, `README_SETUP.md`

Not copied: `assemble.sh`, this `README.md`.

## Updating stack files

1. Edit files in **`be/__setup/`** (in the backend repo).
2. Commit and push the **be** repo.
3. On each machine: pull **be** and **fe**, run `./be/__setup/assemble.sh` again.
   - Existing workspace files are left unchanged; delete a file manually if you need a fresh copy.

## Monorepo note

If you still use the legacy `CompleteBytePOS` monorepo, keep `be/__setup` in sync with root stack files when you change Docker or scripts.
