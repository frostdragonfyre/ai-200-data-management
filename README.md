# AI-200: Developing AI Solutions by Using Azure Data Management Services

Exercise files for the course.

The code is the data layer for a customer support answer API. It uses three Azure data stores:

| Store | What it holds | Modules |
|---|---|---|
| Azure Cosmos DB for NoSQL | Support tickets and chat sessions, with embeddings for finding similar resolved tickets | 1, 2 |
| Azure Database for PostgreSQL | The knowledge base (policy and product articles split into chunks, with pgvector embeddings) | 3, 4 |
| Azure Managed Redis | An answer cache and a semantic cache | 5 |

## What you need

- An Azure subscription or a Pluralsight Azure sandbox
- Azure Cloud Shell (Bash). I built and ran everything from Cloud Shell.

You don't need a model endpoint. Embeddings come from `all-MiniLM-L6-v2` (384 dimensions), which runs on the CPU. The RAG demo sends its prompt to `stub_model.py`, which returns the top source with a citation and marks its output as STUB.

## Getting started

Open Cloud Shell (Bash) in the Azure portal and run:

```bash
set +H
git clone https://github.com/frostdragonfyre/ai-200-data-management.git
cd ai-200-data-management
bash setup.sh m1          # or m2, m3, m4, m5, all
source .venv/bin/activate
python m1/after/tickets.py load
python m1/after/tickets.py read
```

If you'd rather not use git, download the zip (Code, Download ZIP), upload it with Manage files > Upload in Cloud Shell, and run `unzip ai-200-data-management-main.zip && cd ai-200-data-management-main`. Then start at `bash setup.sh`.

`setup.sh` finds your resource group and region, creates what the module needs, builds a Python virtual environment, downloads the embedding model, and writes endpoints and keys to `.env`. The scripts read `.env` but never print it. The first run takes 10 to 15 minutes. PostgreSQL and Redis take the longest.

The `runbooks/` folder has one file per module with the setup, every demo command in order, and the output to expect.

## What's in here

```
setup.sh             creates each module's resources (safe to run again)
requirements.txt     azure-cosmos, psycopg, psycopg_pool, redis, numpy, fastembed
.env.example         the settings setup.sh writes
common/              settings loader and the embedding model
data/                500 tickets, knowledge base articles, 5,000 chunks
tools/               make_seed.py rebuilds the data, check_retrieval.py checks distances offline
stub_model.py        stand-in model endpoint for the RAG demo
m1/ ... m5/          before/ is the starting code, after/ is the finished code
m2/functions/        the change feed processor (Azure Functions, Python)
runbooks/            commands and expected output for every demo
```

In each `before/` folder, the code written in the demos is replaced with a `NotImplementedError` or a `# TODO`. In `after/`, the same code sits between `# >>> demo` and `# <<< demo`. Diff the two folders to see what each demo adds. The runbooks use `after/`.

## Gotchas

- Vector search on Cosmos DB has to be turned on when you create the account. `setup.sh` does this. When I tried adding it to an existing account, it never took effect.
- Create PostgreSQL at General Purpose. Burstable doesn't have the built-in PgBouncer, and scaling up later takes about 10 minutes.
- pgvector is a two-step setup. Allow `VECTOR` in the `azure.extensions` server parameter, then run `CREATE EXTENSION vector` in each database.
- PgBouncer is off on a new server. Turn on `pgbouncer.enabled` before modules 4 and 5. The module 4 runbook shows the portal steps and a CLI command.
- PgBouncer runs in transaction mode on port 6432, so the scripts connect with `prepare_threshold=None` (no server-side prepared statements).
- Azure Managed Redis uses port 10000 with TLS. With Enterprise clustering there's one endpoint, so a plain `redis.Redis` client works.
- The function app runs on the Linux Consumption plan. After you deploy, `m2/functions/deploy.sh` syncs triggers and calls `/api/ping`. I had to add that step, because without it the trigger never started.
- In Cloud Shell, a `!` inside a string triggers bash history expansion. Run `set +H` first. `setup.sh` does.

## Cleaning up

Delete the resource group or let the sandbox expire. Everything `setup.sh` creates goes in that resource group.
