import argparse
import asyncio
import os
from pathlib import Path

import httpx

from app.evaluation.metrics import build_report, load_cases, score_case
from app.schemas.rag import RAGQueryResponse


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a deployed RAG API against JSONL cases")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--base-url", default=os.getenv("RAG_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("RAG_API_TOKEN"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-answer-recall", type=float, default=0.8)
    parser.add_argument("--min-source-recall", type=float, default=1.0)
    parser.add_argument("--min-grounded-accuracy", type=float, default=1.0)
    return parser.parse_args()


async def evaluate(args: argparse.Namespace) -> int:
    if not args.token:
        raise SystemExit("Provide --token or set RAG_API_TOKEN")
    thresholds = (
        args.min_answer_recall,
        args.min_source_recall,
        args.min_grounded_accuracy,
    )
    if any(value < 0 or value > 1 for value in thresholds):
        raise SystemExit("Evaluation thresholds must be between 0 and 1")

    cases = load_cases(args.dataset)
    results = []
    headers = {"Authorization": f"Bearer {args.token}"}
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=120) as client:
        for case in cases:
            payload: dict[str, object] = {"question": case.question}
            if case.document_ids:
                payload["document_ids"] = [str(document_id) for document_id in case.document_ids]
            response = await client.post("/api/v1/rag/query", headers=headers, json=payload)
            response.raise_for_status()
            results.append(score_case(case, RAGQueryResponse.model_validate(response.json())))

    report = build_report(
        results,
        min_answer_recall=args.min_answer_recall,
        min_source_recall=args.min_source_recall,
        min_grounded_accuracy=args.min_grounded_accuracy,
    )
    rendered = report.model_dump_json(indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(evaluate(arguments())))
