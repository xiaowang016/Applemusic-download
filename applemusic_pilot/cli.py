from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from applemusic_pilot.resolver import AppleMusicResolver


URL_RE = re.compile(r"https?://[^\s]+")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve Apple Music song metadata into JSON"
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Text file containing Apple Music URLs",
    )
    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument(
        "--output",
        type=Path,
        help="Where to write one combined JSON file",
    )
    output_group.add_argument(
        "--output-dir",
        type=Path,
        help="Directory where one JSON file per song will be written",
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="Apple Music URLs to resolve",
    )
    return parser


def extract_urls_from_text(text: str) -> list[str]:
    return URL_RE.findall(text)


def load_urls(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[str]:
    urls: list[str] = []
    if args.input_file is not None:
        urls.extend(extract_urls_from_text(args.input_file.read_text(encoding="utf-8")))
    urls.extend(args.urls)
    if not urls:
        parser.error("Provide Apple Music URLs as arguments or via --input-file")
    return urls


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    urls = load_urls(args, parser)
    resolver = AppleMusicResolver()
    records = resolver.resolve_many(urls)

    if args.output is not None:
        payload = [record.to_dict() for record in records]
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote={len(payload)} output={args.output}")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        output_path = args.output_dir / f"{record.song_id}.json"
        output_path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"wrote={len(records)} output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
