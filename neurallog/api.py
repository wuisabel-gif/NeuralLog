from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Literal

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - depends on local installation state
    raise RuntimeError(
        "FastAPI dependencies are not installed. Install the project dependencies first, "
        "for example with `python3 -m pip install -e .`."
    ) from exc

from neurallog.evaluation import compare_embedding_backends, evaluate_export
from neurallog.services import NeuralLogService


DEFAULT_INDEX_PATH = Path("neurallog.index.json")
DEFAULT_EXPORT_DIR = Path("exports")
EXPORTER_CLI_PATH = Path("DiscordChatExporter.Cli/bin/Debug/net10.0/DiscordChatExporter.Cli")
WEB_DIR = Path(__file__).with_name("web")
FRONTEND_DIST_DIR = Path("frontend/dist")
DEFAULT_BACKEND = os.getenv("NEURALLOG_INDEX_BACKEND", "auto")
DEFAULT_EMBEDDING_BACKEND = os.getenv("NEURALLOG_EMBEDDING_BACKEND", "hash")
DEFAULT_EMBEDDING_MODEL = os.getenv("NEURALLOG_EMBEDDING_MODEL")
DEFAULT_EMBEDDING_DIMENSIONS = os.getenv("NEURALLOG_EMBEDDING_DIMENSIONS")
DEFAULT_EMBEDDING_BATCH_SIZE = os.getenv("NEURALLOG_EMBEDDING_BATCH_SIZE")
DEFAULT_EMBEDDING_CACHE_PATH = os.getenv(
    "NEURALLOG_EMBEDDING_CACHE_PATH",
    "neurallog-embeddings.sqlite3",
)
# Required by the bundled DiscordChatExporter CLI for non-interactive export execution.
DISCORD_EXPORTER_ENV_FLAG = "FUCK_RUSSIA"
app = FastAPI(title="NeuralLog", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = NeuralLogService(
    index_path=DEFAULT_INDEX_PATH,
    backend=DEFAULT_BACKEND,
    embedding_backend=DEFAULT_EMBEDDING_BACKEND,
    sentence_transformers_model=DEFAULT_EMBEDDING_MODEL or "all-MiniLM-L6-v2",
    openai_model=DEFAULT_EMBEDDING_MODEL or "text-embedding-3-small",
    openai_dimensions=int(DEFAULT_EMBEDDING_DIMENSIONS) if DEFAULT_EMBEDDING_DIMENSIONS else None,
    embedding_batch_size=int(DEFAULT_EMBEDDING_BATCH_SIZE) if DEFAULT_EMBEDDING_BATCH_SIZE else None,
    embedding_cache_path=DEFAULT_EMBEDDING_CACHE_PATH or None,
)

if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")


class ServiceConfig(BaseModel):
    backend: Literal["auto", "inmemory", "faiss"] = "auto"
    embedding_backend: Literal["hash", "sentence-transformers", "openai"] = "hash"
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    embedding_batch_size: int | None = None
    embedding_cache_path: str | None = DEFAULT_EMBEDDING_CACHE_PATH


class IngestRequest(BaseModel):
    export_path: str = Field(description="Path to a DiscordChatExporter JSON file.")
    config: ServiceConfig | None = None


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=25)
    min_score: float = 0.0
    require_results: bool = False
    config: ServiceConfig | None = None


class SearchExportRequest(SearchRequest):
    export_path: str = Field(description="Path to a DiscordChatExporter JSON file.")


class DiscordExportRequest(BaseModel):
    token: str = Field(min_length=1)
    token_kind: Literal["bot", "user"] = "bot"
    channel_id: str = Field(min_length=1)
    output_path: str | None = None
    config: ServiceConfig | None = None


class EvaluateRequest(BaseModel):
    export_path: str
    evaluation_set_path: str
    limit: int = Field(default=5, ge=1, le=50)
    config: ServiceConfig | None = None


class CompareBackendsRequest(BaseModel):
    export_path: str
    evaluation_set_path: str
    specs: list[str]
    limit: int = Field(default=5, ge=1, le=50)
    skip_unavailable: bool = True
    config: ServiceConfig | None = None


@app.get("/")
def root() -> FileResponse:
    if (FRONTEND_DIST_DIR / "index.html").exists():
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.css")
def app_css() -> FileResponse:
    return FileResponse(WEB_DIR / "app.css", media_type="text/css")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "index_size": service.index.size,
        "backend": service.index.backend_name,
        "faiss_available": service.index.faiss_available,
        "embedding_backend": service.embedder.name,
        "embedding_dimensions": service.embedder.dimensions,
        "embedding_cache_enabled": bool(DEFAULT_EMBEDDING_CACHE_PATH),
    }


@app.post("/ingest/discord-export")
def ingest_discord_export(request: IngestRequest) -> dict[str, int | str]:
    path = Path(request.export_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Export file not found: {path}")
    active_service = _service_for_config(request.config, persistent=True)
    return active_service.ingest_discord_export(path)


@app.post("/search")
def search(request: SearchRequest) -> dict[str, object]:
    active_service = _service_for_config(request.config, persistent=True)
    results = active_service.search(request.query, limit=request.limit, min_score=request.min_score)
    if not results and request.require_results:
        raise HTTPException(status_code=404, detail="No matching results found.")
    return {"results": [result.to_dict() for result in results]}


@app.post("/timeline")
def timeline(request: SearchRequest) -> dict[str, object]:
    active_service = _service_for_config(request.config, persistent=True)
    events = active_service.build_timeline(request.query, limit=request.limit, min_score=request.min_score)
    if not events and request.require_results:
        raise HTTPException(status_code=404, detail="No matching results found.")
    return {"events": [event.to_dict() for event in events]}


@app.post("/workflow/search-export")
def search_export(request: SearchExportRequest) -> dict[str, object]:
    active_service = _service_for_config(request.config, persistent=False)
    export_path = _validated_path(request.export_path)
    active_service.ingest_discord_export(export_path)
    results = active_service.search(request.query, limit=request.limit, min_score=request.min_score)
    if not results and request.require_results:
        raise HTTPException(status_code=404, detail="No matching results found.")
    return {"results": [result.to_dict() for result in results]}


@app.post("/workflow/timeline-export")
def timeline_export(request: SearchExportRequest) -> dict[str, object]:
    active_service = _service_for_config(request.config, persistent=False)
    export_path = _validated_path(request.export_path)
    active_service.ingest_discord_export(export_path)
    events = active_service.build_timeline(request.query, limit=request.limit, min_score=request.min_score)
    if not events and request.require_results:
        raise HTTPException(status_code=404, detail="No matching results found.")
    return {"events": [event.to_dict() for event in events]}


@app.post("/workflow/export-discord")
def export_discord(request: DiscordExportRequest) -> dict[str, object]:
    output_path = Path(request.output_path) if request.output_path else DEFAULT_EXPORT_DIR / f"{request.channel_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exporter_path = EXPORTER_CLI_PATH
    if not exporter_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Discord exporter binary not found at {exporter_path}",
        )

    command = [
        str(exporter_path),
        "export",
        "--token",
        request.token,
        "--channel",
        request.channel_id,
        "--output",
        str(output_path),
        "--format",
        "Json",
    ]

    environment = os.environ.copy()
    environment[DISCORD_EXPORTER_ENV_FLAG] = "1"
    environment["DOTNET_CLI_HOME"] = "/private/tmp"
    environment["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1"

    try:
        completed = subprocess.run(
            command,
            cwd=Path.cwd(),
            env=environment,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Discord export timed out.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start exporter: {exc}") from exc

    if completed.returncode != 0:
        error_text = (completed.stderr or completed.stdout or "Unknown exporter error").strip()
        raise HTTPException(status_code=500, detail=error_text)

    return {
        "status": "ok",
        "channel_id": request.channel_id,
        "token_kind": request.token_kind,
        "output_path": str(output_path),
        "stdout": (completed.stdout or "").strip(),
    }


@app.post("/workflow/evaluate")
def evaluate(request: EvaluateRequest) -> dict[str, object]:
    active_service = _service_for_config(request.config, persistent=False)
    export_path = _validated_path(request.export_path)
    evaluation_set_path = _validated_path(request.evaluation_set_path)
    return evaluate_export(
        active_service,
        export_path,
        evaluation_set_path,
        limit=request.limit,
    )


@app.post("/workflow/compare-backends")
def compare_backends(request: CompareBackendsRequest) -> dict[str, object]:
    export_path = _validated_path(request.export_path)
    evaluation_set_path = _validated_path(request.evaluation_set_path)
    config = request.config or ServiceConfig()

    def service_factory(spec: dict[str, object]) -> NeuralLogService:
        return NeuralLogService(
            backend=config.backend,
            embedding_backend=str(spec["embedding_backend"]),
            sentence_transformers_model=str(spec.get("embedding_model") or "all-MiniLM-L6-v2"),
            openai_model=str(spec.get("embedding_model") or "text-embedding-3-small"),
            openai_dimensions=config.embedding_dimensions,
            embedding_batch_size=config.embedding_batch_size,
            embedding_cache_path=config.embedding_cache_path,
        )

    return compare_embedding_backends(
        service_factory,
        export_path,
        evaluation_set_path,
        [_parse_embedding_spec(spec) for spec in request.specs],
        limit=request.limit,
        skip_unavailable=request.skip_unavailable,
    )


def _validated_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return path


def _service_for_config(config: ServiceConfig | None, *, persistent: bool) -> NeuralLogService:
    if config is None:
        return service if persistent else NeuralLogService()

    index_path = DEFAULT_INDEX_PATH if persistent else None
    return NeuralLogService(
        index_path=index_path,
        backend=config.backend,
        embedding_backend=config.embedding_backend,
        sentence_transformers_model=config.embedding_model or "all-MiniLM-L6-v2",
        openai_model=config.embedding_model or "text-embedding-3-small",
        openai_dimensions=config.embedding_dimensions,
        embedding_batch_size=config.embedding_batch_size,
        embedding_cache_path=config.embedding_cache_path,
    )


def _parse_embedding_spec(spec: str) -> dict[str, object]:
    backend, separator, model = spec.partition(":")
    if backend not in {"hash", "sentence-transformers", "openai"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid embedding spec backend. Use hash, sentence-transformers, or openai.",
        )
    return {
        "label": spec,
        "embedding_backend": backend,
        "embedding_model": model if separator else None,
    }
