# Paper Trail

Turn a reading list into a map of what actually depends on what.

Fifty papers leave you with fifty summaries and no structure. This reads a
folder of notes-on-papers, pulls out each one's claims and citations, and
builds the graph — so you can see the single result everything else is
leaning on.

**Python 3.10+ and nothing else.** No database, no packages.

```bash
python -m paper_trail report papers
python -m paper_trail why papers batchnorm2015
python -m paper_trail graph papers --format dot --out trail.dot
```

## Input

A paper is a markdown file with a short front-matter block — something you can
write while you read, not a PDF pipeline.

```markdown
---
id: batchnorm2015
title: Batch Normalization
authors: Ioffe, Szegedy
year: 2015
cites: sgd1998, covariate2009
---

We show that normalising layer inputs allows much higher learning rates.
It also builds on [[backprop1986]].
```

Citations come from the `cites:` field and from `[[key]]` anywhere in the
prose. Claims are sentences matching a small set of patterns, tagged
`result`, `method` or `limitation`.

## What it reports

```
WHAT EVERYTHING RESTS ON
  1.000  Learning representations by back-propagating errors (1986)
         9 paper(s) depend on it, cited by 1, pagerank 0.2173
  1.000  Efficient BackProp (1998)  <- sole bridge
         8 paper(s) depend on it, cited by 3, pagerank 0.2163
```

Three measures, because they disagree in useful ways:

- **dependents** — how many papers transitively rest on this one. The most
  direct reading of *what breaks if this turns out to be wrong*.
- **pagerank** — weighs a citation from a heavily-cited paper above one from a
  paper nobody reads.
- **cut vertex** — whether removing it disconnects the graph. A paper can have
  only one citation and still be the sole bridge to an entire branch. That is
  the case the first two measures miss, and it is why all three are shown.

It also flags citations to papers not in the folder, and citation loops —
papers cannot cite forward in time, so a loop is a data-entry mistake worth
seeing rather than silently ignoring.

## Commands

| | |
|---|---|
| `report <folder> [--top N]` | the summary above, plus claims per paper |
| `why <folder> <id>` | everything that would be undermined if that paper were wrong |
| `graph <folder> --format json\|dot [--out FILE]` | export the graph |

The DOT export is themed dark and marks bridges in cyan:

```bash
python -m paper_trail graph papers --format dot --out trail.dot
dot -Tsvg trail.dot -o trail.svg      # needs graphviz, optional
```

## Tests

```bash
python -m unittest discover -s tests -v
```

31 tests: front-matter parsing, claim classification, graph measures against
hand-checked fixtures (pagerank ordering, bridge detection, transitive
dependents), both exports, and the shipped corpus. Two of them run 2,000- and
3,000-node chains, because a reading list in one field is exactly the long
chain that a recursive traversal would choke on.

## Honest limits

Claim extraction is pattern matching, not comprehension. A sentence starting
"However" is tagged a limitation even when it is really a positive result, and
a claim phrased unusually is missed entirely. Treat the tags as a reading aid,
not a dataset.

The graph is only as good as your `cites:` lines. Nothing here reads a PDF or
queries a citation API.

## Layout

```
paper_trail/
  parse.py   front matter, citations, claim extraction
  graph.py   pagerank, transitive dependents, cut vertices, cycles
  report.py  text report, JSON and DOT exports
  cli.py     argparse front end
papers/      sample corpus (10 papers)
tests/
```
