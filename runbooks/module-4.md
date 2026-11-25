# Module 4: Retrieving context and optimizing connections in PostgreSQL

Commands and expected output for the module 4 demos. Connection times depend on your region. Direct should always be the slowest and the app pool the fastest.

## Set up

```bash
set +H
bash setup.sh m4            # schema, 5,000 chunks, HNSW and GIN indexes (PgBouncer stays off)
source .venv/bin/activate
nohup python stub_model.py > /dev/null 2>&1 &     # the stub model on 127.0.0.1:8000
```

If you just finished module 3 in the same Cloud Shell, run `python tools/setup_pg.py m4` instead of `setup.sh`.

`setup.sh m4` doesn't create a B-tree on region. If one exists, the planner uses an exact scan for the EU filter and the starvation step in clip 1 won't show anything.

PgBouncer is off on a new server. Clip 2 turns it on in the portal. If you skip clip 2, run this instead:

```bash
PG=$(grep '^PG_HOST=' .env | cut -d= -f2 | cut -d. -f1); RG=$(az group list --query [0].name -o tsv)
az postgres flexible-server parameter set -g $RG -s $PG -n pgbouncer.enabled -v true -o none && echo PGBOUNCER_ON
```

## Clip 1, in-clip demo: Filtering by region

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m4/after/rag.py unfiltered` | the top matches are US chunks |
| 2 | `python m4/after/rag.py filtered` | chunk 1042 first (the EU 14-day right of withdrawal) |
| 3 | `python m4/after/rag.py nodate` | the expired 2025 EU version (chunk 1001) comes back too |
| 4 | `python m4/after/rag.py starve` | a password question with the EU filter: 0 rows with iterative scan off, 5 with `relaxed_order` |

## Clip 2, in-clip demo: Turning on PgBouncer

| Step | Command | You should see |
| --- | --- | --- |
| 1 | Portal: the server, Compute + storage | General Purpose (Burstable has no built-in PgBouncer) |
| 2 | Portal: Server parameters, `pgbouncer.enabled` = TRUE, Save | saved in about 30 seconds; `pgbouncer.pool_mode` is transaction |
| 3 | `python m4/after/connections.py version` | `Connected through PgBouncer on 6432` |
| 4 | Open `m4/after/connections.py`, the `connect` function | `prepare_threshold=None` |
| 5 | Portal: `pgbouncer.default_pool_size` | the pool size |
| 6 | `python m4/after/connections.py limits` | `max_connections` and the client backends in use |

## Clip 3, Demo: Retrieving context for a grounded answer

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m4/after/rag.py answer` | the prompt instructions, then sources [1] 1042, [2] 1044, [3] 1043, [4] 1012, [5] 1011 |
| 2 | (same output, last line) | `STUB (returns source [1]): EU customers may return any item within 14 days of delivery ... [1]` |
| 3 | `python m4/after/rag.py nofilter` | [1] is 1017, a US refund chunk, and the stub cites it |
| 4 | `sed -n '23p;64,86p' m4/after/rag.py` | `MAX_DISTANCE = 0.7`, `build_prompt`, and the distance check in `answer` |
| 5 | `python m4/after/rag.py answer --q "How do I reset my password?"` | best distance about 0.80, so it declines |
| 6 | `python m4/after/rag.py offtopic` | best distance about 0.86, declines |
| 7 | `python m4/after/rag.py answer --q "will it rain tomorrow?"` | best distance about 0.88, declines |
| 8 | `python m4/after/rag.py answer --q "can I send back a blender I opened?"` | passes the threshold, but [1] is chunk 4007, a cleaning guide |

## Clip 4, Demo: Measuring connection strategies

Needs PgBouncer on.

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `sed -n '28,54p' m4/after/connections.py` | `median_ms` and `measure` |
| 2 | `python m4/after/connections.py measure` | direct a few dozen ms, PgBouncer about a third less, the app pool a millisecond or two |
| 3 | run `measure` again | similar numbers, same order |
| 4 | `python m4/after/connections.py burst` | 40 clients: about 44 backends direct versus about 5 through PgBouncer |
| 5 | `python m4/after/connections.py burst 80` | 80 clients: about 85 direct versus 8 or 9 through PgBouncer |
| 6 | `python m4/after/connections.py poolstats` | 200 requests served by 2 connections |
| 7 | `python m4/after/connections.py limits` | `max_connections` 859 on this tier, and the backends in use |
| 8 | `python m4/after/rag.py answer --port 6432` | the same cited EU answer, through PgBouncer |
