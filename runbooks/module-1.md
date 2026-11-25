# Module 1: Querying Azure Cosmos DB for NoSQL efficiently

Commands and expected output for the module 1 demos. Your RU numbers will be a little different from mine.

## Set up

```bash
set +H
bash setup.sh m1            # about 6 minutes; leaves the tickets container empty
source .venv/bin/activate
```

The clip 1 and clip 2 demos read ticket t7, so load the tickets first if you are following in course order:

```bash
python m1/after/tickets.py load
```

`load` is an upsert, so running it again in clip 3 is fine.

## Clip 1, in-clip demo: Reading the bill on a point read

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m1/after/tickets.py read` | `t7 \| c7 \| open \| Refund not received for order A100259` and about 1.14 RU |
| 2 | `python m1/after/tickets.py wrongpk` | `CosmosResourceNotFoundError: status 404` |

## Clip 2, in-clip demo: Asking for more than the account allows

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m1/after/consistency.py` | Eventual allowed; Strong rejected with status 400; the account default (Session) allowed |
| 2 | Portal: the Cosmos DB account, Settings, Default consistency | five levels, Session selected (don't change it) |

## Clip 3, Demo: Connecting and querying support tickets

| Step | Command | You should see |
| --- | --- | --- |
| 1 | Scroll back to the `setup.sh` output | the account, the `support` database, the `tickets` container |
| 2 | `sed -n '24,40p' m1/after/tickets.py` | `CosmosClient`, `get_database_client`, `get_container_client`, and `charge()` reading `x-ms-request-charge` |
| 3 | `python m1/after/tickets.py load` | `Loaded 500 tickets`, about 35,000 RU in total |
| 4 | `python m1/after/tickets.py read` | t7 for c7, 1.14 RU |
| 5 | `python m1/after/tickets.py wrongpk` | status 404 |
| 6 | `python m1/after/tickets.py open c7` | 4 open tickets (t7, t257, t357, t457), about 3 RU |
| 7 | `python m1/after/tickets.py open c12` | 2 open tickets, about 3 RU |
| 8 | `python m1/after/tickets.py billing` | 126 billing tickets across partitions, about 9.35 RU |
| 9 | `python m1/after/tickets.py mine c7` | 5 tickets in one partition, about 3.1 RU |
| 10 | `python m1/after/tickets.py page` | 20 rows, about 3.5 RU, and a continuation token |
| 11 | `python m1/after/tickets.py next` | page 2: 20 more rows |
| 12 | `python m1/after/consistency.py` | Eventual allowed, Strong rejected (400), Session allowed |

## Clip 4, Demo: Cutting Request Unit cost

Needs the 500 tickets from clip 3.

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m1/after/cost.py star` | 126 rows, about 23.6 RU, and a line showing the 384-number embedding came back |
| 2 | `python m1/after/cost.py project` | about 9.3 RU, roughly 60 percent less |
| 3 | `python m1/after/cost.py point` | point read 1.14; query with the partition key about 3; without it about 3 |
| 4 | `python m1/after/cost.py metrics` | utilized single indexes on `/category/?` and `/createdAt/?`; a potential composite index on category and createdAt, impact High |
| 5 | `python m1/after/cost.py policies` | `sessions_default` indexes `/*`; `sessions_narrow` indexes only `/updatedAt/?` |
| 6 | `python m1/after/cost.py sessions` | about 13.1 versus 5.9 RU per write |
| 7 | `python m1/after/cost.py composite` | index transformation progress climbing to 100 percent |
| 8 | `python m1/after/cost.py project` | about 8.4 RU |
| 9 | `python m1/after/cost.py metrics` | the composite index now in the utilized list |

To run clip 4 again: `python m1/after/cost.py uncomposite` removes the composite index.
