import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVALUATION_PATH = ROOT / "docs" / "challenge" / "evaluation.jsonl"
MANIFEST_PATH = ROOT / "docs" / "challenge" / "dataset_manifest.json"
REQUIRED_FIELDS = {
    "id",
    "question",
    "ground_truth",
    "expected_source",
    "category",
    "answerable",
}


def load_evaluation_rows():
    return [
        json.loads(line)
        for line in EVALUATION_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_evaluation_dataset_has_required_shape_and_distribution():
    rows = load_evaluation_rows()
    source_ids = {
        item["id"]
        for item in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["documents"]
    }

    assert len(rows) >= 30
    assert [row["id"] for row in rows[:30]] == [f"q{i:03d}" for i in range(1, 31)]
    assert len({row["id"] for row in rows}) == len(rows)
    assert len({row["question"] for row in rows}) == len(rows)

    for row in rows:
        assert REQUIRED_FIELDS <= row.keys()
        assert isinstance(row["answerable"], bool)
        assert row["question"].strip()
        assert row["ground_truth"].strip()
        assert isinstance(row["expected_source"], list)
        assert all(source in source_ids for source in row["expected_source"])
        if row["answerable"]:
            assert row["expected_source"]
        else:
            assert row["expected_source"] == []

    assert sum(row["answerable"] and row["category"] != "multi_document" for row in rows) == 20
    assert sum(row["category"] == "multi_document" for row in rows) == 5
    assert sum(not row["answerable"] for row in rows) == 5

    categories = {row["category"] for row in rows}
    assert {"cultivation", "pest_disease", "livestock", "aquaculture"} <= categories
    assert {"insufficient_context", "out_of_scope"} <= categories
