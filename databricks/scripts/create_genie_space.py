"""Create (or update) the Genie space "Ask Portugal's public contracts" with the Databricks CLI.

Reads genie/instructions.md (instructions + sample questions) and genie/example_queries.sql (trusted SQL, each
query preceded by a "-- question" comment) and calls the Genie API through `databricks api`, so it uses the
same login as `databricks bundle`. The space id is kept in .genie_space_id; running the script again updates
the same space instead of creating a second one.

    export BUNDLE_VAR_warehouse_id=...      # same variable as the bundle
    python3 scripts/create_genie_space.py   # --dry-run prints the request
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENIE = ROOT / "genie"
ID_FILE = ROOT / ".genie_space_id"
TITLE = "Ask Portugal's public contracts"
DESCRIPTION = (
    "1.5 million public contracts from Portal BASE (2019 to date), gold layer of the procurement lakehouse. "
    "Ask in Portuguese or English."
)
TABLES = [
    "contracts_enriched", "dim_cpv", "dim_supplier",
    "mart_supplier_concentration", "mart_threshold_summary", "mart_top_suppliers",
]

_counter = 0


def new_id() -> str:
    """32 hex characters, increasing, so every list stays in creation order when sorted by id."""
    global _counter
    _counter += 1
    return f"{_counter:08x}{uuid.uuid4().hex[8:]}"


def read_instructions() -> tuple[str, list[str]]:
    text = (GENIE / "instructions.md").read_text(encoding="utf-8")
    body, _, sample = text.partition("Sample questions:")
    questions = [re.sub(r"^\d+\.\s*", "", line).strip() for line in sample.splitlines() if line.strip()]
    return body.strip(), questions


def read_queries(catalog: str) -> list[tuple[str, str]]:
    text = (GENIE / "example_queries.sql").read_text(encoding="utf-8")
    pairs = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("--"):
            continue
        question = lines[0].lstrip("- ").strip()
        sql = "\n".join(lines[1:]).strip().rstrip(";").replace("workspace.", f"{catalog}.")
        pairs.append((question, sql))
    return pairs


def as_lines(text: str) -> list[str]:
    """The API stores long text as an array of lines, each ending in a newline except the last."""
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def build_space(catalog: str) -> dict:
    instructions, questions = read_instructions()
    queries = read_queries(catalog)
    return {
        "version": 2,
        "config": {"sample_questions": [{"id": new_id(), "question": [q]} for q in questions]},
        "data_sources": {"tables": [{"identifier": f"{catalog}.gold.{t}"} for t in sorted(TABLES)]},
        "instructions": {
            "text_instructions": [{"id": new_id(), "content": as_lines(instructions)}],
            "example_question_sqls": [
                {"id": new_id(), "question": [q], "sql": as_lines(sql)} for q, sql in queries
            ],
        },
    }


def cli(method: str, path: str, payload: dict) -> dict:
    result = subprocess.run(
        ["databricks", "api", method, path, "--json", json.dumps(payload)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"databricks api {method} {path} failed:\n{result.stderr or result.stdout}")
    return json.loads(result.stdout or "{}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse-id", default=os.environ.get("BUNDLE_VAR_warehouse_id"))
    parser.add_argument("--catalog", default="workspace")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    space = build_space(args.catalog)
    payload = {
        "warehouse_id": args.warehouse_id or "<warehouse_id>",
        "title": TITLE,
        "description": DESCRIPTION,
        "serialized_space": json.dumps(space, ensure_ascii=False),
    }
    if args.dry_run:
        print(json.dumps({**payload, "serialized_space": space}, indent=2, ensure_ascii=False))
        return
    if not args.warehouse_id:
        sys.exit("Set BUNDLE_VAR_warehouse_id or pass --warehouse-id.")

    space_id = ID_FILE.read_text().strip() if ID_FILE.exists() else ""
    if space_id:
        cli("patch", f"/api/2.0/genie/spaces/{space_id}", payload)
        print(f"Updated Genie space {space_id}")
    else:
        space_id = cli("post", "/api/2.0/genie/spaces", payload)["space_id"]
        ID_FILE.write_text(space_id + "\n")
        print(f"Created Genie space {space_id}")
    host = subprocess.run(["databricks", "auth", "describe", "--output", "json"], capture_output=True, text=True)
    try:
        url = json.loads(host.stdout)["details"]["host"].rstrip("/")
        print(f"Open it: {url}/genie/rooms/{space_id}")
    except (ValueError, KeyError):
        print("Open it from the Genie menu in the workspace.")


if __name__ == "__main__":
    main()
