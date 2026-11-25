# Module 2: Building semantic retrieval and change processing on Azure Cosmos DB

Commands and expected output for the module 2 demos. Here `VectorDistance` returns cosine similarity, so higher means closer.

## Set up

```bash
set +H
bash setup.sh m2            # account with vector search, 500 tickets with embeddings, function app
source .venv/bin/activate
```

The function app is created but not deployed; clip 4 deploys it.

## Clip 1, in-clip demo: Querying by meaning

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m2/after/similar.py "my blender arrived cracked"` | top match t86 "Damaged item on delivery" at about 0.54, then other damage tickets, about 30 RU |
| 2 | add `--filter` to the same command | resolved returns tickets only, about 8.4 RU |
| 3 | Data Explorer: support, tickets, Settings | vector policy `/embedding`, float32, cosine, 384 dimensions; diskANN index |

## Clip 2, in-clip demo: Resuming from a continuation token

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m2/after/pull.py start` | `Read 500 items from the beginning. Token saved.` |
| 2 | `python m2/after/pull.py touch t7` then `python m2/after/pull.py next` | `1 changed ['t7']` |
| 3 | `python m2/after/pull.py token` | the saved token, a few hundred characters long |
| 4 | `python m2/after/pull.py ghost` then `python m2/after/pull.py next` | `0 changed` (deletes don't appear in latest version mode) |

## Clip 3, Demo: Finding similar tickets with vector search

| Step | Command | You should see |
| --- | --- | --- |
| 1 | Portal: the Cosmos DB account, Settings, Features | Vector Search for NoSQL API: On |
| 2 | Data Explorer: support, tickets, Settings | the vector policy and the diskANN index |
| 3 | `python -m common.embed` | `Model ready: 384 dimensions` in under a second |
| 4 | `python m2/after/similar.py cracked --keyword` | 0 tickets |
| 5 | `python m2/after/similar.py damaged --keyword \| tail -3` | 20 tickets, about 4.4 RU |
| 6 | `python m2/after/similar.py "my blender arrived cracked"` | t86 at about 0.54, t452 "Glass carafe shattered", t460 (still open), t21, t201; about 30 RU |
| 7 | add `--filter` | five resolved tickets, about 8.4 RU; the last line shows how the closest match was resolved |
| 8 | `python m2/after/similar.py "my blender arrived cracked" --top 10` | 10 results, all about damage |
| 9 | `python m2/after/similar.py "the jug on my blender has a split down the side" --filter` | a weaker best match, about 0.39 |
| 10 | `python m2/after/similar.py "how do I reset my password"` | account tickets at about 0.71 |

## Clip 4, Demo: Processing changes with a change feed processor

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m2/after/pull.py start` | 500 items read, token saved |
| 2 | `python m2/after/pull.py touch t7`, then `python m2/after/pull.py next` | `1 changed ['t7']` |
| 3 | `python m2/after/pull.py token` | the token length |
| 4 | `touch t9`, `touch t7`, then `next` | `2 changed ['t9', 't7']` |
| 5 | `python m2/after/pull.py ghost`, then `next` | `0 changed` |
| 6 | `sed -n '18,40p' m2/functions/function_app.py` | the trigger on `tickets`, the `leases` container, the output binding to `events`, IDs `evt-{id}` |
| 7 | `bash m2/functions/deploy.sh` | deploy, `Syncing triggers...`, `Waking the host...`, `{"status": "awake"}` |
| 8 | `python m2/after/resolve.py --leases` | 2 lease documents: one lease and the `.info` store metadata |
| 9 | `python m2/after/resolve.py t12 t13 t14`, wait about 15 seconds, then `python m2/after/resolve.py --events` | evt-t12, evt-t13, evt-t14, each processed a few seconds after the update |
| 10 | `python m2/after/resolve.py t12`, wait, then `--events` | still 3 events; evt-t12 has a newer processed time |

You can run `deploy.sh` again if you need to.
