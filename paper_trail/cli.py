"""the command line
read the folder and print what is holding up what"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .graph import Graph
from .parse import read_folder
from .report import text_report, to_dot, to_json


def load(folder: str):
    papers = read_folder(folder)
    if not papers:
        print(f"no papers found in {folder}", file=sys.stderr)
        raise SystemExit(2)
    return papers, Graph.from_papers(papers)


def cmd_report(args) -> int:
    papers, graph = load(args.folder)
    print(text_report(papers, graph, top=args.top))
    return 0


def cmd_graph(args) -> int:
    papers, graph = load(args.folder)
    text = to_dot(papers, graph) if args.format == "dot" else to_json(papers, graph)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def cmd_why(args) -> int:
    """everything that falls over if this paper turns out to be wrong"""
    papers, graph = load(args.folder)
    by_id = {p.id: p for p in papers}
    if args.paper not in graph.nodes:
        print(f"no paper with id {args.paper!r}", file=sys.stderr)
        return 2
    dependents = graph.dependents(args.paper)
    target = by_id.get(args.paper)
    print(f"{target.label if target else args.paper}")
    if not dependents:
        print("  nothing in this folder depends on it")
        return 0
    print(f"  {len(dependents)} paper(s) rest on it:")
    for key in sorted(dependents):
        paper = by_id.get(key)
        print(f"    {paper.label if paper else key}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trail",
        description="Turn a reading list into a map of what actually depends on what.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("report", help="print the summary")
    p.add_argument("folder")
    p.add_argument("--top", type=int, default=8)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("graph", help="export the graph")
    p.add_argument("folder")
    p.add_argument("--format", choices=["json", "dot"], default="json")
    p.add_argument("--out")
    p.set_defaults(func=cmd_graph)

    p = sub.add_parser("why", help="what rests on one paper")
    p.add_argument("folder")
    p.add_argument("paper")
    p.set_defaults(func=cmd_why)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
