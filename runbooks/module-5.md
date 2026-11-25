# Module 5: Integrating Azure Managed Redis in AI solutions

Commands and expected output for the module 5 demos. Latency will vary. Hits and misses should match.

## Set up

```bash
set +H
bash setup.sh m5            # Azure Managed Redis Balanced_B0 with RediSearch, plus the module 4 knowledge base
source .venv/bin/activate
nohup python stub_model.py > /dev/null 2>&1 &
```

- If Balanced_B0 has no capacity in your region (`AllocationFailed`), `setup.sh` tries the next region.
- The answer path goes through PgBouncer on port 6432. On a new server, turn it on in the portal (PostgreSQL server, Server parameters, `pgbouncer.enabled` = TRUE, Save) or use the command in the module 4 runbook.
- Before clip 2, start with an empty index: `python m5/after/semcache.py drop && python m5/after/semcache.py create`. Before clip 4, run `drop` (clip 4 creates the index).

To clear cached answers and start clip 3 again:

```bash
python -c "import sys; sys.path.insert(0,'m5/after'); from cache import connect; r=connect(); n=[r.delete(k) for k in r.scan_iter('answer:v*')]; r.delete('policy_version:US'); print(len(n),'answer keys cleared')"
```

## Clip 1, in-clip demo: Watching a key expire

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m5/after/cache.py ttl` | `PING -> True`, TTL counting 5, 3, 2, 0, then `None` after expiry |
| 2 | `python m5/after/cache.py nottl` | TTL -1 (no expiry), -2 (no such key), then 60 after `EXPIRE` |

## Clip 2, in-clip demo: Measuring a paraphrase

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m5/after/semcache.py store` | sc:0 and sc:1 stored for US, TTL 1 hour |
| 2 | `python m5/after/semcache.py ask "can I send back a broken item?"` | nearest "How do I return a damaged item?", distance 0.224, threshold 0.25: HIT |
| 3 | `python m5/after/semcache.py ask "how do I turn on two-step verification?"` | distance about 0.95: miss |
| 4 | step 2 with `--region EU` | no cached answer tagged EU, miss |
| 5 | `python m5/after/semcache.py info`, then `outside` | 2 documents indexed both times |

## Clip 3, Demo: Caching, expiring, and invalidating answers

| Step | Command | You should see |
| --- | --- | --- |
| 1 | Portal: the Azure Managed Redis resource, Overview | Running, Balanced B0, non-TLS access disabled, RediSearch module |
| 2 | `sed -n '34,41p;60,70p' m5/after/cache.py` | the versioned key and the cache-aside `answer` function |
| 3 | `python m5/after/cache.py aside` | a miss (under a second), then a hit (a few ms). The answer cites the 30-day US return policy |
| 4 | run `aside` again | hits only |
| 5 | `python m5/after/cache.py normalize` | the first two lines share a key, the third gets its own |
| 6 | `python m5/after/cache.py bump` | `INCR policy_version`, a miss, then a hit on the new `answer:v4:` key |
| 7 | `python m5/after/cache.py keys` | the old v3 key and the new v4 key, each with a TTL near 24 hours |
| 8 | `python m5/after/cache.py delete` | `DEL -> 1`, then the next read misses |
| 9 | `python m5/after/cache.py memory` | used memory a few MB, `maxmemory_policy` noeviction, the answer key count |

## Clip 4, Demo: Building a semantic cache

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m5/after/semcache.py create` | index `semcache` on hashes with prefix `sc:` |
| 2 | `sed -n '39,64p' m5/after/semcache.py` | the schema, `store`, and the KNN query in `ask` |
| 3 | `python m5/after/semcache.py store`, then `info` | 2 documents indexed |
| 4 | `ask "can I send back a broken item?"` | 0.224: HIT |
| 5 | `ask "my refund still is not in my account"` | 0.290: miss at 0.25 |
| 6 | the same with `--threshold 0.30` | HIT |
| 7 | `ask "I changed my mind, can I return it?"` | 0.525: miss |
| 8 | the same with `--threshold 0.6` | HIT (returns the damaged-item answer) |
| 9 | `ask "how do I turn on two-step verification?"` | about 0.95: miss |
| 10 | `ask "can I send back a broken item?" --region EU` | no EU answer cached: miss |
| 11 | `python m5/after/semcache.py outside` | still 2 documents |
| 12 | `sed -n '60,70p' m5/after/cache.py` | where the semantic check fits in the answer path |

Every `ask` above is `python m5/after/semcache.py ask ...`.
