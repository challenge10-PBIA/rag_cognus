"""Sincronização explícita do catálogo fonético publicado no Medallion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from rag_cognus.config import Settings
from rag_cognus.gold import PHONETICS_VIEW, load_exercises_from_databricks, save_snapshot
from rag_cognus.phonetics import catalog_from_documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--snapshot", type=Path, default=Path(".cache/phonetics.jsonl"))
    args = parser.parse_args()
    load_dotenv(args.env_file) if args.env_file else load_dotenv()
    documents = load_exercises_from_databricks(Settings.from_env())
    catalog_from_documents(documents)
    print(json.dumps(save_snapshot(documents, args.snapshot, PHONETICS_VIEW), indent=2))


if __name__ == "__main__":
    main()
