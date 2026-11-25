# Module 3: Modeling, indexing, and sizing Azure Database for PostgreSQL

Commands and expected output for the module 3 demos. Timings will vary. Sizes and plans should match.

## Set up

```bash
set +H
bash setup.sh m3            # about 6 minutes, VECTOR not allowed yet
source .venv/bin/activate
```

`m3` leaves `vector` off the allow list because clip 1 turns it on. To go straight to clips 3 and 4, run `bash setup.sh m4` instead. It allows and creates the extension.

## Clip 1, in-clip demo: Allowing and creating the extension

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m3/after/db.py` | an error that `vector` is not allow-listed, then the hint to allow it |
| 2 | Portal: the server, Settings, Server parameters, `azure.extensions`, add VECTOR, Save | saved, no restart needed |
| 3 | `python m3/after/db.py avail` | available, `installed_version None` |
| 4 | `python m3/after/db.py` | `pgvector 0.8.x is installed`, cosine distance 0.0085 between two test vectors |

## Clip 2, in-clip demo: Watching the plan change

This demo needs chunks in the table. Load them first:

```bash
python m3/after/load.py schema && python m3/after/load.py load && python m3/after/plans.py reset
```

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m3/after/plans.py seq` | `Seq Scan on chunks` across all 5,000 rows |
| 2 | `python m3/after/plans.py hnsw` | the HNSW index built in a few seconds, about 9 to 10 MB |
| 3 | `python m3/after/plans.py indexed` | `Index Scan using chunks_embedding_hnsw` |
| 4 | `python m3/after/plans.py l2` | back to a sequential scan (the index is for cosine, not Euclidean) |

## Clip 3, Demo: Creating the schema and loading chunks

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `cat m3/after/schema.sql` | `articles`, `chunks`, the foreign key, `embedding vector(384)` |
| 2 | `python m3/after/load.py schema` | `Created articles and chunks` (drops and recreates both tables) |
| 3 | `python m3/after/load.py wrongdim` | `DataException: expected 384 dimensions, not 1536` |
| 4 | `python m3/after/load.py orphan` | `ForeignKeyViolation` for article 99999 |
| 5 | `python m3/after/load.py load` | `Loaded 512 articles and 5000 chunks` |
| 6 | `python m3/after/load.py counts` | articles and chunks per region: AU 36/360, CA 60/600, EU 30/259, UK 63/622, US 323/3159 |
| 7 | `sed -n '62,72p' m3/after/load.py` | the metadata query with `%s` placeholders |
| 8 | `python m3/after/load.py query` | 15 chunks for a US blender customer |
| 9 | `python m3/after/load.py query EU blender \| tail -1` | 7 chunks |
| 10 | `python m3/after/load.py size` | 1544 bytes per full-precision vector, 776 per half-precision |
| 11 | `python m3/after/load.py tables` | heap about 10 MB, TOAST and indexes small, articles about 150 kB |

## Clip 4, Demo: Indexing and sizing the knowledge base

Clip 3 dropped the tables, so rebuild the HNSW index from clip 2 first:

```bash
python m3/after/plans.py hnsw
```

| Step | Command | You should see |
| --- | --- | --- |
| 1 | `python m3/after/plans.py halfvec` | about 9,100 kB for the full index versus 5,200 kB for half precision |
| 2 | `python m3/after/plans.py halfquery` | `Index Scan using chunks_embedding_half` |
| 3 | `python m3/after/plans.py halfrecall` | the exact top 10 is the same at full and half precision |
| 4 | `python m3/after/plans.py efsearch` | the exact top five, then how many of them HNSW finds at `ef_search` 40, 100, 200, and 400. At the low settings the count changes from build to build. 200 and 400 should find all five |
| 5 | `python m3/after/plans.py filters` | B-tree and GIN indexes created |
| 6 | `python m3/after/plans.py settings` | `shared_buffers`, `maintenance_work_mem`, `work_mem`, `max_connections` |
| 7 | `python m3/after/plans.py fit` | about 24 MB for `chunks` and its indexes, next to 2 GB of `shared_buffers` |
| 8 | Portal: the server, Settings, Compute + storage | General Purpose, 2 vCores, 8 GiB, storage auto-grow on |

To run clip 4 again: `python m3/after/plans.py reset && python m3/after/plans.py hnsw`.

## Before module 4

Step 5 of clip 4 adds a B-tree on region, which changes the module 4 plans. Reset the knowledge base before you start module 4:

```bash
python tools/setup_pg.py m4
```
