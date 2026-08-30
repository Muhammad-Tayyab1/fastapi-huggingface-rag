from pathlib import Path
from uuid import uuid4

import pytest

from app.evaluation.metrics import EvaluationCase, build_report, load_cases, score_case
from app.schemas.rag import RAGQueryResponse, RAGSource


def response(*, answer: str, document: str, grounded: bool = True) -> RAGQueryResponse:
    sources = []
    if document:
        sources.append(
            RAGSource(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name=document,
                page_number=1,
                score=0.9,
                excerpt="Policy text",
            )
        )
    return RAGQueryResponse(
        question="Question",
        answer=answer,
        sources=sources,
        grounded=grounded,
        conversation_id=uuid4(),
    )


def test_score_case_normalizes_terms_and_sources() -> None:
    case = EvaluationCase(
        id="refund",
        question="When?",
        expected_answer_terms=["30 DAYS", "receipt required"],
        expected_document_names=["refund-policy.txt"],
    )

    result = score_case(
        case,
        response(
            answer="Returns are accepted within 30 days. Keep your receipt required for review.",
            document="Refund-Policy.txt",
        ),
    )

    assert result.answer_term_recall == 1
    assert result.source_recall == 1
    assert result.grounded_correct is True


def test_report_enforces_quality_thresholds() -> None:
    case = EvaluationCase(
        id="partial", question="When?", expected_answer_terms=["30 days", "receipt"]
    )
    result = score_case(case, response(answer="Within 30 days", document=""))

    report = build_report(
        [result], min_answer_recall=0.8, min_source_recall=1, min_grounded_accuracy=1
    )

    assert report.mean_answer_term_recall == 0.5
    assert report.passed is False


def test_load_cases_rejects_duplicate_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(
        '{"id":"same","question":"One"}\n{"id":"same","question":"Two"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate"):
        load_cases(dataset)
