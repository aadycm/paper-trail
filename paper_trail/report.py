"""Turn the graph into something I can read, paste somewhere, or draw."""

from __future__ import annotations

import json

from .graph import Graph
from .text import shorten


def text_report(papers, graph: Graph, *, top: int = 8) -> str:
    by_id = {p.id: p for p in papers}
    rows = graph.load_bearing()
    known = [r for r in rows if r[2]["known"]]
    out: list[str] = []

    def title(key: str) -> str:
        paper = by_id.get(key)
        return paper.label if paper else f"{key}  [not in folder]"

    out.append("READING LIST")
    out.append(f"  {len(papers)} papers, {sum(len(p.cites) for p in papers)} citations")
    missing = graph.dangling()
    if missing:
        out.append(f"  {len(missing)} cited but not present: {', '.join(missing[:6])}"
                   + (" ..." if len(missing) > 6 else ""))
    loops = graph.cycles()
    if loops:
        out.append(f"  {len(loops)} citation loop(s), check these - papers cannot cite forward:")
        for loop in loops[:3]:
            out.append("    " + " -> ".join(loop))
    out.append("")

    out.append("WHAT EVERYTHING RESTS ON")
    for key, score, detail in known[:top]:
        flag = "  <- sole bridge" if detail["cut_vertex"] else ""
        out.append(f"  {score:.3f}  {title(key)}{flag}")
        out.append(
            f"         {detail['dependents']} paper(s) depend on it, "
            f"cited by {detail['cited_by']}, pagerank {detail['pagerank']:.4f}"
        )
    out.append("")

    out.append("CLAIMS BY PAPER")
    for paper in papers:
        results = paper.claims_of("result")
        limits = paper.claims_of("limitation")
        if not results and not limits:
            continue
        out.append(f"  {paper.label}")
        for claim in results[:2]:
            out.append(f"     result     {shorten(claim.text)}")
        for claim in limits[:1]:
            out.append(f"     limitation {shorten(claim.text)}")
    return "\n".join(out)


def to_json(papers, graph: Graph) -> str:
    rows = {key: detail | {"score": score} for key, score, detail in graph.load_bearing()}
    payload = {
        "papers": [
            {
                "id": p.id,
                "title": p.title,
                "year": p.year,
                "authors": p.authors,
                "cites": p.cites,
                "claims": [{"kind": c.kind, "text": c.text} for c in p.claims],
                "metrics": rows.get(p.id, {}),
            }
            for p in papers
        ],
        "edges": [{"from": s, "to": d} for s, targets in sorted(graph.out.items())
                  for d in sorted(targets)],
        "dangling": graph.dangling(),
        "cycles": graph.cycles(),
    }
    return json.dumps(payload, indent=2)


def to_dot(papers, graph: Graph) -> str:
    by_id = {p.id: p for p in papers}
    rows = {key: (score, detail) for key, score, detail in graph.load_bearing()}
    lines = [
        "digraph paper_trail {",
        '  rankdir=LR;',
        '  bgcolor="#0d1117";',
        '  node [shape=box style="rounded,filled" fontname="Helvetica" '
        'fontsize=10 color="#30363d" fontcolor="#d7dae1" fillcolor="#11161d"];',
        '  edge [color="#3a4250" arrowsize=0.7];',
    ]
    for key in sorted(graph.nodes):
        score, detail = rows.get(key, (0.0, {}))
        paper = by_id.get(key)
        label = (paper.title if paper else key).replace('"', "'")
        if not detail.get("known", True):
            lines.append(f'  "{key}" [label="{label}" style="rounded,dashed" '
                         f'fontcolor="#8f96a4"];')
        elif detail.get("cut_vertex"):
            lines.append(f'  "{key}" [label="{label}\\n{score:.2f}" color="#22d3ee" '
                         f'penwidth=2 fontcolor="#e7eaf0"];')
        else:
            lines.append(f'  "{key}" [label="{label}\\n{score:.2f}"];')
    for src, targets in sorted(graph.out.items()):
        for dst in sorted(targets):
            lines.append(f'  "{src}" -> "{dst}";')
    lines.append("}")
    return "\n".join(lines)
