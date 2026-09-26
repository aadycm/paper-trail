"""Tests for Paper Trail. Run: python -m unittest discover -s tests -v"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paper_trail.graph import Graph                                   # noqa: E402
from paper_trail.parse import Paper, parse_text, read_folder, split_list  # noqa: E402
from paper_trail.report import text_report, to_dot, to_json           # noqa: E402

SAMPLE = """---
id: bn2015
title: Batch Normalization
authors: Ioffe, Szegedy
year: 2015
cites: sgd1998, covariate2009
---

We show that normalising layer inputs allows higher learning rates. The method
achieves the same accuracy with far fewer steps. However, it behaves
differently at inference time. It also builds on [[backprop1986]].
"""


def chain(*edges) -> Graph:
    g = Graph()
    for src, dst in edges:
        g.add_edge(src, dst)
    for key in list(g.nodes):
        g.nodes[key].known = True
    return g


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.paper = parse_text(SAMPLE)

    def test_front_matter_fields(self):
        self.assertEqual(self.paper.id, "bn2015")
        self.assertEqual(self.paper.title, "Batch Normalization")
        self.assertEqual(self.paper.year, 2015)
        self.assertEqual(self.paper.authors, "Ioffe, Szegedy")

    def test_citations_from_front_matter_and_inline(self):
        self.assertIn("sgd1998", self.paper.cites)
        self.assertIn("covariate2009", self.paper.cites)
        self.assertIn("backprop1986", self.paper.cites)   # the [[key]] one, written mid-sentence

    def test_citations_are_deduplicated(self):
        doubled = parse_text("---\nid: x\ncites: a, a, b\n---\nSee [[a]].")
        self.assertEqual(doubled.cites, ["a", "b"])

    def test_claims_are_classified(self):
        kinds = {c.kind for c in self.paper.claims}
        self.assertIn("result", kinds)
        self.assertIn("limitation", kinds)

    def test_result_claim_text_is_captured(self):
        results = self.paper.claims_of("result")
        self.assertTrue(any("higher learning rates" in c.text for c in results))

    def test_missing_front_matter_falls_back_to_filename(self):
        paper = parse_text("Just prose, no metadata.", fallback_id="loose-note")
        self.assertEqual(paper.id, "loose-note")
        self.assertEqual(paper.cites, [])

    def test_split_list_handles_brackets_and_spacing(self):
        self.assertEqual(split_list("[a, b   c]"), ["a", "b", "c"])
        self.assertEqual(split_list(""), [])

    def test_read_folder_reads_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text(SAMPLE, encoding="utf-8")
            (Path(tmp) / "skip.png").write_bytes(b"\x89PNG")
            papers = read_folder(tmp)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].id, "bn2015")


class GraphTests(unittest.TestCase):
    def test_edges_point_from_citing_to_cited(self):
        g = chain(("b", "a"))
        self.assertIn("a", g.out["b"])
        self.assertIn("b", g.inn["a"])

    def test_self_citation_is_ignored(self):
        g = Graph.from_papers([Paper(id="a", title="A", cites=["a", "b"])])
        self.assertEqual(g.out["a"], {"b"})

    def test_dependents_are_transitive(self):
        g = chain(("c", "b"), ("b", "a"))
        self.assertEqual(g.dependents("a"), {"b", "c"})
        self.assertEqual(g.dependents("c"), set())

    def test_dangling_lists_papers_not_in_the_folder(self):
        g = Graph.from_papers([Paper(id="a", title="A", cites=["ghost"])])
        self.assertEqual(g.dangling(), ["ghost"])

    def test_pagerank_sums_to_one(self):
        g = chain(("b", "a"), ("c", "a"), ("c", "b"))
        self.assertAlmostEqual(sum(g.pagerank().values()), 1.0, places=6)

    def test_pagerank_favours_the_widely_cited(self):
        g = chain(("b", "a"), ("c", "a"), ("d", "a"), ("c", "b"))
        rank = g.pagerank()
        self.assertGreater(rank["a"], rank["b"])
        self.assertGreater(rank["a"], rank["d"])

    def test_cut_vertex_found_on_a_bridge(self):
        # x - bridge - y, so pulling out "bridge" splits the thing in two
        g = chain(("x", "bridge"), ("bridge", "y"))
        self.assertIn("bridge", g.cut_vertices())
        self.assertNotIn("x", g.cut_vertices())

    def test_no_cut_vertex_in_a_triangle(self):
        g = chain(("a", "b"), ("b", "c"), ("c", "a"))
        self.assertEqual(g.cut_vertices(), set())

    def test_cycles_are_detected(self):
        g = chain(("a", "b"), ("b", "c"), ("c", "a"))
        self.assertTrue(g.cycles())

    def test_acyclic_graph_reports_no_cycles(self):
        g = chain(("c", "b"), ("b", "a"))
        self.assertEqual(g.cycles(), [])

    def test_load_bearing_ranks_the_foundation_first(self):
        g = chain(("d", "c"), ("c", "b"), ("b", "a"))
        top = g.load_bearing()[0][0]
        self.assertEqual(top, "a")

    def test_cycle_detection_survives_a_deep_chain(self):
        # ids sorted so the first node visited has to walk the entire chain,
        # which is exactly what a recursive version chokes on
        g = chain(*[(f"a{i:05d}", f"a{i+1:05d}") for i in range(3000)])
        self.assertEqual(g.cycles(), [])

    def test_cycle_found_at_the_end_of_a_deep_chain(self):
        edges = [(f"b{i:05d}", f"b{i+1:05d}") for i in range(2000)]
        edges.append(("b02000", "b00000"))
        self.assertTrue(chain(*edges).cycles())

    def test_deep_chain_does_not_blow_the_stack(self):
        g = chain(*[(f"p{i+1}", f"p{i}") for i in range(2000)])
        self.assertIn("p1", g.cut_vertices())
        self.assertEqual(len(g.dependents("p0")), 2000)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.papers = [
            parse_text("---\nid: a\ntitle: Foundation\nyear: 1990\n---\nWe show a thing."),
            parse_text("---\nid: b\ntitle: Follow up\nyear: 2000\ncites: a\n---\nIt improves things."),
            parse_text("---\nid: c\ntitle: Later\nyear: 2010\ncites: b, ghost\n---\nHowever it fails."),
        ]
        self.graph = Graph.from_papers(self.papers)

    def test_text_report_names_the_foundation(self):
        out = text_report(self.papers, self.graph)
        self.assertIn("Foundation", out)
        self.assertIn("WHAT EVERYTHING RESTS ON", out)

    def test_text_report_warns_about_missing_papers(self):
        self.assertIn("ghost", text_report(self.papers, self.graph))

    def test_json_export_is_valid_and_complete(self):
        data = json.loads(to_json(self.papers, self.graph))
        self.assertEqual(len(data["papers"]), 3)
        self.assertEqual(data["dangling"], ["ghost"])
        self.assertTrue(all("metrics" in p for p in data["papers"]))

    def test_dot_export_is_well_formed(self):
        dot = to_dot(self.papers, self.graph)
        self.assertTrue(dot.startswith("digraph paper_trail {"))
        self.assertTrue(dot.rstrip().endswith("}"))
        self.assertIn('"b" -> "a"', dot)

    def test_dot_marks_unknown_papers_differently(self):
        self.assertIn("dashed", to_dot(self.papers, self.graph))


class SampleCorpusTests(unittest.TestCase):
    """The papers/ folder I ship should still make sense as a set."""

    def setUp(self):
        folder = Path(__file__).resolve().parent.parent / "papers"
        if not folder.exists():
            self.skipTest("sample corpus not present")
        self.papers = read_folder(folder)
        self.graph = Graph.from_papers(self.papers)

    def test_every_citation_resolves(self):
        self.assertEqual(self.graph.dangling(), [])

    def test_no_paper_cites_forward_in_time(self):
        self.assertEqual(self.graph.cycles(), [])

    def test_the_oldest_paper_carries_the_most(self):
        self.assertEqual(self.graph.load_bearing()[0][0], "backprop1986")

    def test_sgd_is_the_sole_bridge(self):
        self.assertIn("sgd1998", self.graph.cut_vertices())
