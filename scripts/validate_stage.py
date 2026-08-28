"""Small, dependency-free validators used by workflow_runner."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


class StageValidationError(ValueError):
    pass


def validate(stage: dict, root: Path) -> None:
    outputs = [root / p for p in stage.get("outputs", [])]
    missing = [str(p) for p in outputs if not p.is_file()]
    if missing:
        raise StageValidationError(f"missing expected output(s): {missing}")
    kind = stage.get("validator", "files_exist")
    if kind in (None, "files_exist"):
        return
    if kind in ("json", "rule_result"):
        for p in outputs:
            if p.suffix.lower() != ".json":
                continue
            try: data = json.loads(p.read_text(encoding="utf-8"))
            except Exception as exc: raise StageValidationError(f"invalid JSON: {p}: {exc}") from exc
            if kind == "rule_result" and not isinstance(data.get("results"), list):
                raise StageValidationError(f"Rule Result results must be a list: {p}")
    elif kind in ("qa", "docx_qa"):
        for p in outputs:
            if p.suffix.lower() != ".json":
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("all_pass") is not True:
                raise StageValidationError(f"QA all_pass is not true: {p}")
    elif kind == "semantic_blocks":
        for p in outputs:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data.get("blocks"), list) or not data["blocks"]:
                raise StageValidationError(f"semantic blocks are empty/invalid: {p}")
    elif kind == "ooxml":
        for p in outputs:
            if p.suffix.lower() != ".docx": continue
            with zipfile.ZipFile(p) as z:
                for name in ("word/document.xml", "word/styles.xml", "word/numbering.xml"):
                    if name not in z.namelist(): raise StageValidationError(f"missing OOXML part {name}: {p}")
    else:
        raise StageValidationError(f"unknown validator: {kind}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    args = ap.parse_args()
    validate(json.loads(args.stage.read_text(encoding="utf-8")), args.root)
    print("PASS")


if __name__ == "__main__": main()
