# NeuralLog

![NeuralLog interface overview](examples/neurallog%20screenshot.jpg)

**Keywords:** `Engineering Memory` · `Discord Export Analysis` · `Semantic Search` · `Hybrid Retrieval` · `Timeline Reconstruction` · `Retrieval Evaluation` · `FastAPI`

NeuralLog is a local-first research system for transforming Discord-based engineering discussions into a searchable operational memory layer. The project is oriented toward robotics and embedded-systems workflows, where design rationale, debugging observations, experiment notes, and integration decisions are often distributed across long-lived chat channels rather than formal documentation.

This repository combines two layers:

- `neurallog/`: the Python retrieval application, including ingestion, indexing, search, evaluation, timeline reconstruction, and a local web interface
- `DiscordChatExporter.*`: the upstream Discord export tooling retained as the ingestion substrate for producing compatible JSON exports

The present implementation should be understood as an applied retrieval system rather than a production knowledge platform. Its purpose is to support exploration of how engineering chat archives can be indexed, queried, evaluated, and iteratively improved using lightweight local infrastructure.

## Abstract

Engineering teams generate substantial technical knowledge in conversational systems, yet much of this knowledge remains difficult to recover once it is buried in chat history. NeuralLog investigates whether Discord export archives can be restructured into a usable memory layer through message normalization, chunk-based indexing, configurable embeddings, hybrid retrieval, and query-conditioned timeline reconstruction. The current system supports local experimentation through both a command-line interface and a FastAPI-backed web application, with evaluation utilities for comparing retrieval behavior across embedding configurations.

## Research Motivation

In robotics and embedded software environments, consequential technical decisions are frequently made in informal channels: sensor debugging threads, field-test observations, deployment coordination, estimator tuning discussions, and subsystem integration reviews. These artifacts are valuable, but they are rarely organized for retrospective analysis.

NeuralLog is motivated by the following question:

> Can engineering chat history be transformed into a practical retrieval layer for reconstructing decisions, diagnosing past failures, and recovering design context?

This repository explores that question with a deliberately compact architecture that can be executed locally and extended incrementally.

## Current Capabilities

NeuralLog currently supports:

- ingestion of Discord JSON exports produced in the style of DiscordChatExporter
- normalization of message metadata, authorship, timestamps, attachments, and references
- chunk-based grouping of temporally adjacent discussion windows
- configurable embedding backends:
  - `hash`
  - `sentence-transformers`
  - `openai`
- optional persistent embedding caching in SQLite
- vector search using `inmemory` and optional `faiss` backends
- lightweight hybrid ranking that combines semantic similarity with lexical term coverage
- one-shot search directly over an export file
- timeline reconstruction from retrieved evidence
- retrieval evaluation against labeled query sets
- side-by-side comparison across embedding specifications
- a local web UI for interactive experimentation

## Current Limitations

The present prototype does not yet provide:

- multi-source ingestion from Git, ROS logs, experiment notebooks, or deployment systems
- large-scale persistence and serving infrastructure
- GPU-oriented indexing beyond optional FAISS usage
- LLM-native summarization or agentic reasoning workflows
- formal access control, multi-user deployment, or production hardening

## Repository Structure

```text
neurallog/
  api.py
  cache.py
  chunking.py
  cli.py
  discord_ingest.py
  embeddings.py
  evaluation.py
  index.py
  models.py
  services.py
  web/
frontend/
  src/
  dist/
examples/
  sample-discord-export.json
  sample-evaluation.json
DiscordChatExporter.Cli/
DiscordChatExporter.Core/
DiscordChatExporter.Gui/
```

## System Architecture

The current processing pipeline is:

```text
DiscordChatExporter JSON
        ->
message normalization
        ->
temporal chunking
        ->
embedding generation
        ->
vector indexing
        ->
hybrid retrieval
        ->
timeline reconstruction / evaluation / API responses
```

The retrieval stage combines semantic similarity with lexical evidence. In practice, this hybrid ranking is important for engineering queries containing domain-specific terms such as `EKF`, `AMCL`, `localization`, or `odom drift`, where pure semantic similarity may over-generalize toward nearby concepts such as mapping or SLAM.

## Installation

NeuralLog targets Python `3.11+`.

Install the base package:

```bash
python3 -m pip install -e .
```

Optional extras:

```bash
python3 -m pip install -e ".[faiss]"
python3 -m pip install -e ".[embeddings]"
```

Embedding backends:

- `hash`: dependency-light baseline intended for portability and fast experimentation
- `sentence-transformers`: local semantic embeddings using models such as `all-MiniLM-L6-v2`
- `openai`: hosted embeddings using models such as `text-embedding-3-small`

By default, embedding outputs are cached in `neurallog-embeddings.sqlite3`. The cache path can be overridden with `--embedding-cache-path`, or disabled by passing an empty string.

## Running The Web Application

Start the FastAPI server from the repository root:

```bash
python3 -m uvicorn neurallog.api:app --reload --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

The local web application supports:

- Discord export ingestion
- one-shot search over an export
- timeline reconstruction
- retrieval evaluation
- backend comparison
- direct export creation through the bundled DiscordChatExporter CLI when available

## Interface Preview

The following figures illustrate the current local interface and representative retrieval output.

![NeuralLog workflow interface](examples/mapping-ezgif.com-video-to-gif-converter.gif)

![NeuralLog retrieval results view](examples/ekf-ezgif.com-video-to-gif-converter.gif)

If you want to run the React frontend in development mode:

```bash
cd frontend
npm install
npm run dev
```

The development frontend expects the API at `http://127.0.0.1:8000`.

## Command-Line Usage

### 1. Ingest a Discord export

```bash
PYTHONPATH=. python3 -m neurallog.cli ingest path/to/export.json
```

Installed-script form:

```bash
neurallog ingest path/to/export.json
```

### 2. One-shot search over an export

```bash
PYTHONPATH=. python3 -m neurallog.cli search-export \
  examples/sample-discord-export.json \
  "Why was localization unstable in March?" \
  --limit 3
```

With `sentence-transformers`:

```bash
PYTHONPATH=. python3 -m neurallog.cli \
  --embedding-backend sentence-transformers \
  --embedding-model all-MiniLM-L6-v2 \
  --embedding-batch-size 32 \
  search-export examples/sample-discord-export.json \
  "Why was localization unstable in March?" \
  --limit 3
```

With OpenAI embeddings:

```bash
OPENAI_API_KEY=your_key_here \
PYTHONPATH=. python3 -m neurallog.cli \
  --embedding-backend openai \
  --embedding-model text-embedding-3-small \
  --embedding-batch-size 64 \
  search-export examples/sample-discord-export.json \
  "Why was localization unstable in March?" \
  --limit 3
```

### 3. One-shot timeline reconstruction

```bash
PYTHONPATH=. python3 -m neurallog.cli timeline-export \
  examples/sample-discord-export.json \
  "IMU drift and EKF stability" \
  --limit 4
```

### 4. Search an existing persisted index

```bash
PYTHONPATH=. python3 -m neurallog.cli --index-path neurallog.index.json search \
  "Summarize EKF tuning decisions" \
  --limit 5
```

### 5. Evaluate retrieval quality

```bash
PYTHONPATH=. python3 -m neurallog.cli \
  --embedding-cache-path /private/tmp/neurallog-embeddings.sqlite3 \
  evaluate examples/sample-discord-export.json examples/sample-evaluation.json \
  --limit 3
```

Returned summary metrics include:

- mean precision@k
- mean recall@k
- mean reciprocal rank

### 6. Compare embedding backends

```bash
PYTHONPATH=. python3 -m neurallog.cli \
  --embedding-cache-path /private/tmp/neurallog-embeddings.sqlite3 \
  compare-backends examples/sample-discord-export.json examples/sample-evaluation.json \
  --spec hash \
  --spec sentence-transformers:all-MiniLM-L6-v2 \
  --skip-unavailable \
  --limit 3
```

Each spec may be provided as:

- `hash`
- `sentence-transformers:model_name`
- `openai:model_name`

## Example Query Behavior

Given an export containing discussion fragments such as:

```text
2026-03-10  Maya: IMU drift got much worse after the pool test. EKF position estimate diverges after 90 seconds.
2026-03-12  Alex: We changed the MPU-9250 low-pass filter constants and reduced some of the high-frequency noise.
2026-03-14  Maya: Finished tuning EKF covariance values. Localization is still shaky during turns but much better.
2026-03-17  Jordan: After the covariance tuning and filter changes, localization stayed stable for the full test run.
```

NeuralLog can answer a query such as:

```bash
PYTHONPATH=. python3 -m neurallog.cli search-export \
  examples/sample-discord-export.json \
  "Why was localization unstable in March?" \
  --limit 3
```

Representative output:

```json
{
  "results": [
    {
      "chunk_id": "channel-eng-9f6bf828c801",
      "score": 0.4331988897471611,
      "channel_name": "systems-integration",
      "start_time": "2026-03-14T20:41:00+00:00",
      "end_time": "2026-03-14T20:41:00+00:00",
      "participants": ["Maya"],
      "preview": "[Maya] Finished tuning EKF covariance values. Localization is still shaky during turns but much better.",
      "message_ids": ["1003"]
    },
    {
      "chunk_id": "channel-eng-70b8dcb93382",
      "score": 0.29285113019775794,
      "channel_name": "systems-integration",
      "start_time": "2026-03-17T21:05:00+00:00",
      "end_time": "2026-03-17T21:05:00+00:00",
      "participants": ["Jordan"],
      "preview": "[Jordan] After the covariance tuning and filter changes, localization stayed stable for the full test run.",
      "message_ids": ["1004"]
    }
  ]
}
```

This behavior illustrates the intended retrieval pattern: chunks explicitly containing the target engineering concept are promoted above merely adjacent topics.

## API

Run the API:

```bash
python3 -m uvicorn neurallog.api:app --reload --host 127.0.0.1 --port 8000
```

Primary endpoints:

- `GET /`
- `GET /health`
- `POST /ingest/discord-export`
- `POST /search`
- `POST /timeline`
- `POST /workflow/search-export`
- `POST /workflow/timeline-export`
- `POST /workflow/export-discord`
- `POST /workflow/evaluate`
- `POST /workflow/compare-backends`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/workflow/search-export \
  -H "Content-Type: application/json" \
  -d '{
    "export_path": "examples/sample-discord-export.json",
    "query": "Why was localization unstable in March?",
    "limit": 3,
    "config": {
      "backend": "auto",
      "embedding_backend": "hash",
      "embedding_model": "all-MiniLM-L6-v2",
      "embedding_batch_size": 32,
      "embedding_cache_path": "neurallog-embeddings.sqlite3"
    }
  }'
```

## Data Assumptions

NeuralLog expects Discord exports in the JSON format produced by DiscordChatExporter. The exporter source is retained in this repository because it remains the operational starting point for the current ingestion workflow.

If Discord history is collected from a personal account, note that automating user accounts may violate Discord's Terms of Service. When possible, use a bot token scoped only to channels that your application is authorized to access.

## Provenance

This repository incorporates the upstream DiscordChatExporter codebase as an ingestion dependency and foundation for Discord archive generation. Relevant references to the upstream project remain in the bundled source and build metadata, including links to:

- `https://github.com/Tyrrrz/DiscordChatExporter`

NeuralLog should therefore be interpreted as a downstream research system built on top of that export substrate, rather than as an unrelated implementation from first principles.

## License

This repository includes an MIT license; see [License.txt](/Users/harvardsummer/Library/Mobile%20Documents/com~apple~CloudDocs/GitHub/NeuralLog/License.txt). The bundled DiscordChatExporter-derived components also reference MIT licensing in the retained upstream materials.

## Development Status

NeuralLog is currently best suited for:

- local experimentation
- architecture validation
- retrieval quality studies
- engineering-memory demonstrations
- iterative tuning of chunking, embeddings, and ranking behavior

The `hash` backend remains useful as a portable baseline, but it should be treated as a convenience model rather than the target retrieval ceiling. For higher-quality search behavior, `sentence-transformers` is the recommended default local backend.

## Future Directions

Planned directions include:

- stronger hybrid retrieval and reranking strategies
- more rigorous benchmark datasets for engineering queries
- multi-source ingestion from Git history, deployment logs, ROS artifacts, and experiment records
- narrative summarization and root-cause synthesis
- knowledge graph construction across systems, teams, and decisions
- interactive visualization for long-horizon project reconstruction

## Why This Project Exists

NeuralLog begins from a simple premise: high-value engineering knowledge is frequently produced in chat, but chat systems are poor long-term memory systems. Recovering that knowledge usually requires either individual recollection or time-consuming manual searching through conversational archives.

This project explores whether a lightweight retrieval layer can materially improve that situation. In that sense, NeuralLog is not just a software utility; it is also an applied investigation into how engineering organizations might preserve conversational knowledge as a searchable technical asset.
