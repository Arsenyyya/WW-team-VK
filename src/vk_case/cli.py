"""Local CLI. No network required to inspect, calculate, export, or verify."""

import argparse
import json
import sys
from pathlib import Path

from .ingest import DataError, load, locate


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vk-case", description="Воспроизводимый анализ VK Case Champ")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["inspect", "run"]:
        p = sub.add_parser(name)
        p.add_argument("--input-dir", type=Path, default=Path("data/raw"))
        p.add_argument("--workbook", type=Path)
        if name == "run":
            p.add_argument("--output-dir", type=Path, default=Path("outputs"))
            p.add_argument("--config", type=Path)
    p = sub.add_parser("verify")
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument("--latest", action="store_true")
    choice.add_argument("--run-dir", type=Path)
    p.add_argument("--output-dir", type=Path, default=Path("outputs"))
    p = sub.add_parser("demo")
    p.add_argument("--store", type=Path, default=Path("data/demo/runtime.sqlite"))
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            bundle = load(locate(args.input_dir, args.workbook))
            result = {"sha256": bundle.source_hash, "period": bundle.period, "sheets": bundle.schema}
        elif args.command == "run":
            from .pipeline import run, verify
            path = run(args.input_dir, args.output_dir, args.workbook, args.config)
            result = {"run_dir": str(path), **verify(path)}
        elif args.command == "verify":
            from .pipeline import latest, verify
            result = verify(args.run_dir or latest(args.output_dir))
        else:
            from .demo import CATALOG, DemoStore
            store = DemoStore(args.store)
            result = {"mode": "demo", "is_demo": True, "products": CATALOG, "local_orders": len(store.list_orders()),
                      "app": ".venv/bin/streamlit run app/streamlit_app.py -- --demo"}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (DataError, ValueError, FileNotFoundError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
