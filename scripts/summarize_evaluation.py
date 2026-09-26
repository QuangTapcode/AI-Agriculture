"""Package evaluator JSONL into a reproducible JSON report with metrics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return round(ordered[index], 1)


def _verdict(row: dict) -> str:
    return (row.get("human_review") or {}).get("verdict") or row.get("result", {}).get("verdict", "fail")


def summarize(rows: list[dict], *, chunk_size: int, overlap: int, source_jsonl: str) -> dict:
    answerable = [row for row in rows if row.get("expected_doc_ids")]
    no_answer = [row for row in rows if not row.get("expected_doc_ids")]

    answer_quality = Counter(
        "correct" if _verdict(row) == "pass" else
        "acceptable" if _verdict(row) == "needs_review" else
        "wrong"
        for row in rows
    )

    retrieved_refs = sum(
        len(set(row.get("expected_doc_ids", [])) & set(row.get("retrieved_doc_ids", [])))
        for row in answerable
    )
    expected_refs = sum(len(row.get("expected_doc_ids", [])) for row in answerable)
    hit_rows = sum(
        bool(set(row.get("expected_doc_ids", [])) & set(row.get("retrieved_doc_ids", [])))
        for row in answerable
    )
    all_expected_rows = sum(
        set(row.get("expected_doc_ids", [])) <= set(row.get("retrieved_doc_ids", []))
        for row in answerable
    )

    citation_correct = 0
    citation_missing = 0
    citation_wrong_only = 0
    citation_extra = 0
    citation_exact = 0
    for row in answerable:
        expected = set(row.get("expected_doc_ids", []))
        cited = {item.get("doc_id") for item in row.get("citations", []) if item.get("doc_id")}
        if not cited:
            citation_missing += 1
        elif cited & expected:
            citation_correct += 1
            if cited <= expected:
                citation_exact += 1
            else:
                citation_extra += 1
        else:
            citation_wrong_only += 1

    latency = {}
    for field in ("retrieval_ms", "generation_ms", "total_ms"):
        values = [float(row["timings"][field]) for row in rows if field in row.get("timings", {})]
        latency[field] = {
            "n": len(values),
            "p50_ms": _percentile(values, 0.50),
            "p95_ms": _percentile(values, 0.95),
            "max_ms": max(values) if values else None,
        }

    failures = {
        "retrieval": sum(
            bool(set(row.get("expected_doc_ids", [])) - set(row.get("retrieved_doc_ids", [])))
            for row in answerable
        ),
        "chunking_or_top_k": sum(
            bool(set(row.get("expected_doc_ids", [])) - set(row.get("retrieved_doc_ids", [])))
            and bool(set(row.get("expected_doc_ids", [])) & set(row.get("retrieved_doc_ids", [])))
            for row in answerable
        ),
        "prompt_or_grounding_gate": sum(
            row in no_answer and _verdict(row) != "pass" for row in rows
        ),
        "model_or_content_review": sum(
            row in answerable and _verdict(row) == "needs_review" for row in rows
        ),
        "request_error": sum(bool(row.get("error")) for row in rows),
    }

    no_answer_by_category = {}
    for category in sorted({row.get("original_category", row.get("category")) for row in no_answer}):
        subset = [row for row in no_answer if row.get("original_category", row.get("category")) == category]
        no_answer_by_category[category] = {
            "correct_refusal": sum(_verdict(row) == "pass" for row in subset),
            "total": len(subset),
        }

    return {
        "schema_version": "1.0",
        "experiment": {
            "type": "chunk_size",
            "chunk_size": chunk_size,
            "chunk_overlap": overlap,
            "source_jsonl": source_jsonl,
        },
        "dataset": {"questions": len(rows), "answerable": len(answerable), "no_answer": len(no_answer)},
        "answer_quality": {
            "correct": answer_quality["correct"],
            "acceptable_needs_review": answer_quality["acceptable"],
            "wrong": answer_quality["wrong"],
            "definition": "pass=machine checks passed; needs_review=acceptable form but human content review remains; fail=machine check failed",
        },
        "retrieval_quality": {
            "hit_at_k": {"hits": hit_rows, "total": len(answerable), "rate": round(hit_rows / len(answerable), 4) if answerable else None},
            "recall_at_k": {"retrieved_expected_references": retrieved_refs, "expected_references": expected_refs, "rate": round(retrieved_refs / expected_refs, 4) if expected_refs else None},
            "all_expected_sources": {"hits": all_expected_rows, "total": len(answerable), "rate": round(all_expected_rows / len(answerable), 4) if answerable else None},
            "k": "RAG_TOP_K at runtime; source list is capped by the configured top-k",
        },
        "citation_quality": {
            "correct_source_present": citation_correct,
            "missing": citation_missing,
            "wrong_only": citation_wrong_only,
            "extra_out_of_target_source": citation_extra,
            "exact_expected_source_set": citation_exact,
            "denominator": len(answerable),
        },
        "no_answer_accuracy": {
            "strict_correct_refusal": sum(_verdict(row) == "pass" for row in no_answer),
            "total": len(no_answer),
            "rate": round(sum(_verdict(row) == "pass" for row in no_answer) / len(no_answer), 4) if no_answer else None,
            "by_category": no_answer_by_category,
        },
        "latency_ms": latency,
        "failure_analysis": failures,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--chunk-size", type=int, required=True)
    parser.add_argument("--overlap", type=int, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = summarize(rows, chunk_size=args.chunk_size, overlap=args.overlap, source_jsonl=str(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("answer_quality", "retrieval_quality", "citation_quality", "no_answer_accuracy", "latency_ms", "failure_analysis")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
