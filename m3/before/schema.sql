-- Module 3: the knowledge base schema.
-- Articles carry the facts you filter on. Chunks carry the text and the embedding.
-- Region, product, and effective dates are copied onto each chunk so a filter and
-- the vector search run against one table, which keeps the HNSW index usable.

DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS articles;

CREATE TABLE articles (
    id              integer PRIMARY KEY,
    title           text        NOT NULL,
    product         text        NOT NULL,
    region          text        NOT NULL,
    effective_from  date        NOT NULL,
    effective_to    date,
    meta            jsonb       NOT NULL DEFAULT '{}',
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id              bigint PRIMARY KEY,
    article_id      integer     NOT NULL REFERENCES articles (id),
    chunk_no        integer     NOT NULL,
    content         text        NOT NULL,
    product         text        NOT NULL,
    region          text        NOT NULL,
    effective_from  date        NOT NULL,
    effective_to    date,
    meta            jsonb       NOT NULL DEFAULT '{}',
    embedding       vector(384) NOT NULL
);
