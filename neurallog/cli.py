from __future__ import annotations

import argparse
import json
from pathlib import Path

from neurallog.evaluation import compare_embedding_backends, evaluate_export
from neurallog.services import NeuralLogService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NeuralLog CLI")
    parser.add_argument(
        "--index-path",
        default="neurallog.index.json",
        help="Path to the persisted vector index JSON file.",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "inmemory", "faiss"],
        default="auto",
        help="Vector index backend to use.",
    )
    parser.add_argument(
        "--embedding-backend",
        choices=["hash", "sentence-transformers", "openai"],
        default="hash",
        help="Embedding backend to use.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Model name for sentence-transformers or OpenAI embeddings.",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=None,
        help="Optional embedding dimensions for OpenAI text-embedding-3 models.",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=None,
        help="Optional embedding batch size for supported backends.",
    )
    parser.add_argument(
        "--embedding-cache-path",
        default="neurallog-embeddings.sqlite3",
        help="Path to the persistent embedding cache database. Use '' to disable caching.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Ingest a Discord JSON export.")
    ingest.add_argument("export_path", help="Path to a DiscordChatExporter JSON file.")

    search = subparsers.add_parser("search", help="Search indexed engineering history.")
    search.add_argument("query", help="Semantic search query.")
    search.add_argument("--limit", type=int, default=5)

    timeline = subparsers.add_parser("timeline", help="Build a timeline from search context.")
    timeline.add_argument("query", help="Timeline reconstruction query.")
    timeline.add_argument("--limit", type=int, default=8)

    search_export = subparsers.add_parser(
        "search-export",
        help="Ingest one Discord export and search it immediately without relying on a saved index.",
    )
    search_export.add_argument("export_path", help="Path to a DiscordChatExporter JSON file.")
    search_export.add_argument("query", help="Semantic search query.")
    search_export.add_argument("--limit", type=int, default=5)

    timeline_export = subparsers.add_parser(
        "timeline-export",
        help="Ingest one Discord export and reconstruct a timeline immediately.",
    )
    timeline_export.add_argument("export_path", help="Path to a DiscordChatExporter JSON file.")
    timeline_export.add_argument("query", help="Timeline reconstruction query.")
    timeline_export.add_argument("--limit", type=int, default=8)

    evaluate = subparsers.add_parser(
        "evaluate",
        help="Evaluate retrieval quality against a labeled query set.",
    )
    evaluate.add_argument("export_path", help="Path to a DiscordChatExporter JSON file.")
    evaluate.add_argument("evaluation_set", help="Path to an evaluation JSON file.")
    evaluate.add_argument("--limit", type=int, default=5)

    compare = subparsers.add_parser(
        "compare-backends",
        help="Compare retrieval quality across multiple embedding backend specs.",
    )
    compare.add_argument("export_path", help="Path to a DiscordChatExporter JSON file.")
    compare.add_argument("evaluation_set", help="Path to an evaluation JSON file.")
    compare.add_argument(
        "--spec",
        action="append",
        required=True,
        help=(
            "Embedding spec in the form backend or backend:model. "
            "Example: hash or sentence-transformers:all-MiniLM-L6-v2"
        ),
    )
    compare.add_argument("--limit", type=int, default=5)
    compare.add_argument(
        "--skip-unavailable",
        action="store_true",
        help="Skip specs that require unavailable packages or credentials.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    backend = args.backend if hasattr(args, "backend") else "auto"
    embedding_backend = args.embedding_backend if hasattr(args, "embedding_backend") else "hash"
    cache_path = args.embedding_cache_path if args.embedding_cache_path != "" else None
    try:
        service = NeuralLogService(
            index_path=Path(args.index_path),
            backend=backend,
            embedding_backend=embedding_backend,
            sentence_transformers_model=args.embedding_model or "all-MiniLM-L6-v2",
            openai_model=args.embedding_model or "text-embedding-3-small",
            openai_dimensions=args.embedding_dimensions,
            embedding_batch_size=args.embedding_batch_size,
            embedding_cache_path=cache_path,
        )
    except RuntimeError as exc:
        parser.exit(status=1, message=f"neurallog: error: {exc}\n")

    if args.command == "ingest":
        result = service.ingest_discord_export(args.export_path)
        print(json.dumps(result, indent=2))
        return

    if args.command == "search":
        results = [result.to_dict() for result in service.search(args.query, limit=args.limit)]
        print(json.dumps({"results": results}, indent=2))
        return

    if args.command == "timeline":
        events = [event.to_dict() for event in service.build_timeline(args.query, limit=args.limit)]
        print(json.dumps({"events": events}, indent=2))
        return

    if args.command == "search-export":
        transient_service = _create_service(
            parser,
            backend=backend,
            embedding_backend=embedding_backend,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            embedding_batch_size=args.embedding_batch_size,
            embedding_cache_path=cache_path,
        )
        transient_service.ingest_discord_export(args.export_path)
        results = [
            result.to_dict()
            for result in transient_service.search(args.query, limit=args.limit)
        ]
        print(json.dumps({"results": results}, indent=2))
        return

    if args.command == "timeline-export":
        transient_service = _create_service(
            parser,
            backend=backend,
            embedding_backend=embedding_backend,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            embedding_batch_size=args.embedding_batch_size,
            embedding_cache_path=cache_path,
        )
        transient_service.ingest_discord_export(args.export_path)
        events = [
            event.to_dict()
            for event in transient_service.build_timeline(args.query, limit=args.limit)
        ]
        print(json.dumps({"events": events}, indent=2))
        return

    if args.command == "evaluate":
        transient_service = _create_service(
            parser,
            backend=backend,
            embedding_backend=embedding_backend,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            embedding_batch_size=args.embedding_batch_size,
            embedding_cache_path=cache_path,
        )
        report = evaluate_export(
            transient_service,
            args.export_path,
            args.evaluation_set,
            limit=args.limit,
        )
        print(json.dumps(report, indent=2))
        return

    if args.command == "compare-backends":
        specs = [_parse_embedding_spec(spec) for spec in args.spec]

        def service_factory(spec: dict[str, object]) -> NeuralLogService:
            return _build_service(
                backend=backend,
                embedding_backend=str(spec["embedding_backend"]),
                embedding_model=spec.get("embedding_model"),
                embedding_dimensions=args.embedding_dimensions,
                embedding_batch_size=args.embedding_batch_size,
                embedding_cache_path=cache_path,
            )

        report = compare_embedding_backends(
            service_factory,
            args.export_path,
            args.evaluation_set,
            specs,
            limit=args.limit,
            skip_unavailable=args.skip_unavailable,
        )
        print(json.dumps(report, indent=2))
        return


def _create_service(
    parser: argparse.ArgumentParser,
    *,
    backend: str,
    embedding_backend: str,
    embedding_model: str | None,
    embedding_dimensions: int | None,
    embedding_batch_size: int | None,
    embedding_cache_path: str | None,
) -> NeuralLogService:
    try:
        return _build_service(
            backend=backend,
            embedding_backend=embedding_backend,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            embedding_batch_size=embedding_batch_size,
            embedding_cache_path=embedding_cache_path,
        )
    except RuntimeError as exc:
        parser.exit(status=1, message=f"neurallog: error: {exc}\n")


def _build_service(
    *,
    backend: str,
    embedding_backend: str,
    embedding_model: str | None,
    embedding_dimensions: int | None,
    embedding_batch_size: int | None,
    embedding_cache_path: str | None,
) -> NeuralLogService:
    return NeuralLogService(
        backend=backend,
        embedding_backend=embedding_backend,
        sentence_transformers_model=embedding_model or "all-MiniLM-L6-v2",
        openai_model=embedding_model or "text-embedding-3-small",
        openai_dimensions=embedding_dimensions,
        embedding_batch_size=embedding_batch_size,
        embedding_cache_path=embedding_cache_path,
    )


def _parse_embedding_spec(spec: str) -> dict[str, object]:
    backend, separator, model = spec.partition(":")
    if backend not in {"hash", "sentence-transformers", "openai"}:
        raise RuntimeError(
            "Invalid embedding spec backend. Use one of: hash, sentence-transformers, openai."
        )
    label = spec
    return {
        "label": label,
        "embedding_backend": backend,
        "embedding_model": model if separator else None,
    }


if __name__ == "__main__":
    main()
