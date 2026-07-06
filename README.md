# Freshdex

A RAG system built around one invariant: **the vector index should never silently drift from the source of truth**. Most RAG systems re-index on a batch schedule, so a document can change in Postgres and the answer engine keeps citing stale content indefinitely, with no signal that anything is wrong.

Freshdex closes that gap with CDC: every insert/update/delete in Postgres flows through Debezium, Kafka, an embedding worker, and into pgvector automatically. A document change is queryable within seconds, not the next batch run. The full architecture rationale and decisions live in the project's design doc (`freshdex-design-doc.md`, kept outside this repo alongside project notes).

## Architecture

```
Postgres (documents + outbox, wal_level=logical)
   -> Debezium (Outbox Event Router, CDC via WAL)
   -> Redpanda (Kafka-API compatible)
   -> transform layer (checksum-gated dedup, splits into requests/tombstones)
   -> embedding worker (sentence-transformers, pluggable)
   -> pgvector (vector store, checksum stored alongside)
   -> query API (retrieval + rerank + Gemini generation)
   -> Redis answer cache (CDC-invalidated, not generation-invalidated)
```

Freshness, checksum miss-rate, and cache invalidation are all measured, not assumed -- see the Prometheus/Grafana stack below.

## Services

| Service | Port | What it's for |
|---|---|---|
| `postgres` | 5432 | Source of truth: `documents`, `outbox`, `indexed_documents` (pgvector store) |
| `redpanda` | 19092 (Kafka), 18081 (schema registry) | Kafka-API broker |
| `redpanda-console` | [8080](http://localhost:8080) | Browse raw Kafka topics/messages |
| `connect` | [8083](http://localhost:8083/connectors) | Kafka Connect / Debezium REST API |
| `transform-layer` | 9100 (metrics) | Checksum-gated dedup, topic splitting |
| `embedding-worker` | -- | Embeds + upserts into pgvector |
| `query-api` | [8000](http://localhost:8000) | `POST /query` -- retrieval, rerank, generation |
| `redis` | 6379 | Answer cache |
| `cache-invalidator` | 9101 (metrics) | Evicts cache entries on source change |
| `prometheus` | [9090](http://localhost:9090) | Metrics |
| `pushgateway` | 9091 | Receives the eval flow's freshness benchmark |
| `grafana` | [3001](http://localhost:3001) | Dashboards (admin / freshdex) |
| `eval-flow` | -- | Scheduled Prefect flow: freshness benchmark + RAGAS eval |

## Running it

**Prerequisites:** Docker Desktop running, a `.env` file (copy `.env.example` and fill in `GEMINI_API_KEY` -- free key from [aistudio.google.com](https://aistudio.google.com/apikey)).

```bash
cd freshdex
docker compose up -d --build   # first run, or after pulling changes
docker compose ps              # confirm everything is healthy
```

Startup order is handled by `depends_on`/healthchecks: Postgres and Redpanda come up first, then Kafka Connect registers the Debezium connector (`connect-init`), then everything downstream. First boot takes a few minutes (model downloads are baked into the embedding-worker and query-api images at build time, so runtime startup itself is fast).

To stop: `docker compose down`. Add `-v` only if you intentionally want to wipe the Postgres volume (deletes all indexed data).

## Using it

**Add, edit, or delete a document** -- any write to `documents` triggers the full pipeline automatically:

```bash
docker compose exec postgres psql -U freshdex -d freshdex -c \
  "INSERT INTO documents (title, content) VALUES ('My Doc', 'some text to index');"
```

**Query it:**

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "your question", "top_k": 3}'
```

Response includes the generated answer, cited `doc_id`s, whether it was served from cache, and the retrieved chunks (on a cache miss).

**Verify freshness end-to-end:** edit a row's `content` in Postgres, then re-run the same query a few seconds later -- the answer should reflect the new content, no restart or cache clear needed.

**Watch it work:**
- Redpanda Console ([localhost:8080](http://localhost:8080)) -- see raw CDC events land on `freshdex.outbox.document`, and the split topics `freshdex.embedding.requests` / `freshdex.embedding.tombstones`.
- Grafana ([localhost:3001](http://localhost:3001)) -- "Freshdex Overview" dashboard: checksum match/mismatch rate, cache invalidations by trigger, live query-result freshness (P95), and the freshness-benchmark latency from the scheduled eval flow.
- `docker compose logs -f <service>` for any service's live logs.

## Bulk-loading a corpus (e.g. a textbook)

Any script that inserts rows into `documents` works -- there's no special ingestion API, since the CDC pipeline picks up ordinary writes automatically. For a PDF or similar source: extract text, split into paragraph/section-sized chunks (not whole chapters -- the correctness invariants assume one vector per doc/chunk), and bulk-insert. Ask for a hand writing that script if you have a specific source in mind.

## Configuration

All service config is environment variables set in `docker-compose.yml`, with secrets in `.env` (gitignored). Key ones:

| Variable | Where used | Default |
|---|---|---|
| `POSTGRES_USER` / `PASSWORD` / `DB` | postgres, all consumers | `freshdex` |
| `GEMINI_API_KEY` | query-api, eval-flow | *(required, put in `.env`)* |
| `EMBEDDER_MODEL` | embedding-worker, query-api | `sentence-transformers/all-MiniLM-L6-v2` -- **must match across both** |
| `GEMINI_MODEL` | query-api, eval-flow | `gemini-2.5-flash-lite` |
| `SCHEDULE_INTERVAL_SECONDS` | eval-flow | `1800` (30 min) |

## Repo layout

```
services/
  transform-layer/      Checksum-gated dedup + topic split (Kafka consumer)
  embedding-worker/     Consumes embedding.requests/tombstones, writes pgvector
  query-api/            FastAPI: retrieval + rerank + generation + cache
  cache-invalidator/    Consumes raw CDC topic, evicts stale cache entries
connectors/             Debezium connector config + registration script
db/init/                Postgres schema (documents, outbox, indexed_documents)
observability/          Prometheus config, Grafana provisioning + dashboard
evals/                  Prefect flow: freshness benchmark + RAGAS eval
```

## Known limitations

- No ordering guarantee between `embedding.requests` and `embedding.tombstones` for the same `doc_id` -- a delete immediately after create can race with its embed (see design doc for details).
- Gemini's free tier is rate-limited (both per-minute and per-day); the eval flow retries on the next scheduled interval if it hits a quota wall.
