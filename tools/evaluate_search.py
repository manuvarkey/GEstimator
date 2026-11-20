#!/usr/bin/env python3
"""Run the committed retrieval evaluation without AI or optional dependencies."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modern.backend.service import Service
from modern.backend.mcp_workspace import Workspace
from modern.backend.search import search


def evaluate(dataset):
    service = Service()
    reports = []
    try:
        workspace = Workspace(service)
        for name, cases in dataset["databases"].items():
            _, db = workspace.source("bundled:" + name)
            for use_dictionary in (False, True):
                recalls, reciprocal = [], []
                for case in cases:
                    result = search(service, db, case.get("kind", "schedule"), case["query"], 5, use_dictionary=use_dictionary)
                    codes = [row["code"] for row in result["items"]]
                    expected = set(case["expected"])
                    recalls.append(len(expected.intersection(codes)) / len(expected))
                    reciprocal.append(next((1 / (i + 1) for i, code in enumerate(codes) if code in expected), 0))
                reports.append(dict(database=name, setup="FTS5 + dictionary" if use_dictionary else "FTS5", queries=len(cases), recall_at_5=round(sum(recalls) / len(cases), 4), mrr_at_5=round(sum(reciprocal) / len(cases), 4)))
    finally:
        service.close()
    return dict(results=reports, embeddings="Not installed/evaluated. Require a measured improvement before adding ONNX or enriched bundles.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "tests/data/search_eval.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(evaluate(json.loads(args.dataset.read_text())), indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")
