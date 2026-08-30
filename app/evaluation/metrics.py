import json
import re
from pathlib import Path
from statistics import mean
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.rag import RAGQueryResponse


class EvaluationCase(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=4000)
    expected_answer_terms: list[str] = Field(default_factory=list)
    expected_document_names: list[str] = Field(default_factory=list)
    expected_grounded: bool = True
    document_ids: list[UUID] | None = None


class CaseResult(BaseModel):
    id: str
    question: str
    answer: str
    answer_term_recall: float
    source_recall: float
    grounded_correct: bool
    retrieved_documents: list[str]


class EvaluationReport(BaseModel):
    cases: int
    mean_answer_term_recall: float
    mean_source_recall: float
    grounded_accuracy: float
    passed: bool
    results: list[CaseResult]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _recall(expected: list[str], observed: list[str]) -> float:
    if not expected:
        return 1.0
    normalized_observed = [_normalize(item) for item in observed]
    matches = sum(
        any(_normalize(item) in candidate for candidate in normalized_observed) for item in expected
    )
    return matches / len(expected)


def score_case(case: EvaluationCase, response: RAGQueryResponse) -> CaseResult:
    documents = list(dict.fromkeys(source.document_name for source in response.sources))
    return CaseResult(
        id=case.id,
        question=case.question,
        answer=response.answer,
        answer_term_recall=round(_recall(case.expected_answer_terms, [response.answer]), 4),
        source_recall=round(_recall(case.expected_document_names, documents), 4),
        grounded_correct=response.grounded is case.expected_grounded,
        retrieved_documents=documents,
    )


def build_report(
    results: list[CaseResult],
    *,
    min_answer_recall: float,
    min_source_recall: float,
    min_grounded_accuracy: float,
) -> EvaluationReport:
    if not results:
        raise ValueError("Evaluation requires at least one case")
    answer_recall = mean(result.answer_term_recall for result in results)
    source_recall = mean(result.source_recall for result in results)
    grounded_accuracy = mean(result.grounded_correct for result in results)
    return EvaluationReport(
        cases=len(results),
        mean_answer_term_recall=round(answer_recall, 4),
        mean_source_recall=round(source_recall, 4),
        grounded_accuracy=round(grounded_accuracy, 4),
        passed=(
            answer_recall >= min_answer_recall
            and source_recall >= min_source_recall
            and grounded_accuracy >= min_grounded_accuracy
        ),
        results=results,
    )


def load_cases(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = EvaluationCase.model_validate_json(line)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid evaluation case on line {line_number}: {exc}") from exc
        if case.id in seen:
            raise ValueError(f"Duplicate evaluation case id: {case.id}")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise ValueError("Evaluation dataset is empty")
    return cases
