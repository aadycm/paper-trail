"""the citation graph and the three questions i actually want to ask it

arrows go from the paper doing the citing to the paper being cited
so support flows the way they point
a paper is load bearing when a lot of other work sits on top of it
either directly or further down the chain

i report three numbers instead of one because they disagree
and the disagreement is the interesting part

dependents
how many papers rest on this one in the end
blunt but its the closest thing to what falls over if this is wrong

pagerank
a citation from a paper everyone reads should count for more
than one from a preprint nobody opened

cut vertex
does pulling it out split the graph in two
a paper can have one citation and still be the only way through to a whole
branch and the first two numbers miss that completely
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class Node:
    id: str
    known: bool = True # false means someone cited it but i dont have it


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.out: dict[str, set[str]] = defaultdict(set) # citing -> cited
        self.inn: dict[str, set[str]] = defaultdict(set) # cited  -> citing

    def add_node(self, key: str, known: bool = True) -> None:
        node = self.nodes.get(key)
        if node is None:
            self.nodes[key] = Node(key, known)
        elif known:
            node.known = True

    def add_edge(self, citing: str, cited: str) -> None:
        self.add_node(citing)
        self.add_node(cited, known=False)
        self.out[citing].add(cited)
        self.inn[cited].add(citing)

    @classmethod
    def from_papers(cls, papers) -> "Graph":
        g = cls()
        for p in papers:
            g.add_node(p.id, known=True)
        for p in papers:
            for target in p.cites:
                if target != p.id: # citing yourself doesnt count as a dependency
                    g.add_edge(p.id, target)
        return g

    def dangling(self) -> list[str]:
        """papers that get cited but that i never actually saved"""
        return sorted(k for k, n in self.nodes.items() if not n.known)

    def dependents(self, key: str) -> set[str]:
        """everything that ends up resting on key however far down the chain"""
        seen: set[str] = set()
        queue = deque(self.inn.get(key, ()))
        while queue:
            cur = queue.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            queue.extend(self.inn.get(cur, ()))
        seen.discard(key)
        return seen

    def pagerank(self, damping: float = 0.85, iterations: int = 80,
                 tolerance: float = 1e-10) -> dict[str, float]:
        keys = list(self.nodes)
        n = len(keys)
        if n == 0:
            return {}
        rank = {k: 1.0 / n for k in keys}
        sinks = [k for k in keys if not self.out.get(k)]
        for _ in range(iterations):
            leaked = sum(rank[k] for k in sinks) / n
            nxt = {k: (1.0 - damping) / n + damping * leaked for k in keys}
            for src, targets in self.out.items():
                if not targets:
                    continue
                share = damping * rank[src] / len(targets)
                for dst in targets:
                    nxt[dst] += share
            delta = sum(abs(nxt[k] - rank[k]) for k in keys)
            rank = nxt
            if delta < tolerance:
                break
        return rank

    def cut_vertices(self) -> set[str]:
        """find the papers that hold the graph together

        tarjans articulation points on the graph with the arrows ignored
        written with an explicit stack instead of recursion
        a reading list in one field is one long chain
        and a long chain is exactly what blows the recursion limit
        """
        adj: dict[str, set[str]] = defaultdict(set)
        for src, targets in self.out.items():
            for dst in targets:
                adj[src].add(dst)
                adj[dst].add(src)

        disc: dict[str, int] = {}
        low: dict[str, int] = {}
        parent: dict[str, str | None] = {}
        cuts: set[str] = set()
        timer = 0

        for root in self.nodes:
            if root in disc:
                continue
            parent[root] = None
            stack = [(root, iter(sorted(adj[root])))]
            disc[root] = low[root] = timer
            timer += 1
            root_children = 0
            while stack:
                node, children = stack[-1]
                advanced = False
                for nxt in children:
                    if nxt not in disc:
                        parent[nxt] = node
                        disc[nxt] = low[nxt] = timer
                        timer += 1
                        if node == root:
                            root_children += 1
                        stack.append((nxt, iter(sorted(adj[nxt]))))
                        advanced = True
                        break
                    if nxt != parent.get(node):
                        low[node] = min(low[node], disc[nxt])
                if not advanced:
                    stack.pop()
                    if stack:
                        up = stack[-1][0]
                        low[up] = min(low[up], low[node])
                        if parent.get(up) is not None and low[node] >= disc[up]:
                            cuts.add(up)
            if root_children > 1:
                cuts.add(root)
        return cuts

    def load_bearing(self) -> list[tuple[str, float, dict]]:
        """rank the papers by how much is sitting on them
        gives back id and score and detail"""
        rank = self.pagerank()
        cuts = self.cut_vertices()
        deps = {k: len(self.dependents(k)) for k in self.nodes}
        max_dep = max(deps.values(), default=0) or 1
        max_rank = max(rank.values(), default=0.0) or 1.0

        rows = []
        for key in self.nodes:
            detail = {
                "dependents": deps[key],
                "pagerank": rank[key],
                "cut_vertex": key in cuts,
                "cited_by": len(self.inn.get(key, ())),
                "cites": len(self.out.get(key, ())),
                "known": self.nodes[key].known,
            }
            score = 0.55 * (deps[key] / max_dep) + 0.45 * (rank[key] / max_rank)
            if detail["cut_vertex"]:
                score += 0.15 # it is the only way through to a branch
            rows.append((key, round(min(score, 1.0), 4), detail))
        rows.sort(key=lambda r: (-r[1], r[0]))
        return rows

    def cycles(self) -> list[list[str]]:
        """citation loops

        papers cant cite forward in time so a loop means i typed a key wrong
        somewhere
        better to see it than to quietly walk around it
        """
        # iterative on purpose for the same reason as above
        # one fields reading list is a long chain
        # and a long chain is what kills a recursive walk
        colour: dict[str, int] = {}
        found: list[list[str]] = []

        for start in sorted(self.nodes):
            if colour.get(start, 0) != 0:
                continue
            path: list[str] = []
            stack: list[tuple[str, object]] = [(start, iter(sorted(self.out.get(start, ()))))]
            colour[start] = 1
            path.append(start)
            while stack:
                node, children = stack[-1]
                advanced = False
                for nxt in children: # type: ignore[union-attr]
                    state = colour.get(nxt, 0)
                    if state == 0:
                        colour[nxt] = 1
                        path.append(nxt)
                        stack.append((nxt, iter(sorted(self.out.get(nxt, ())))))
                        advanced = True
                        break
                    if state == 1 and nxt in path:
                        found.append(path[path.index(nxt):] + [nxt])
                if not advanced:
                    colour[node] = 2
                    path.pop()
                    stack.pop()
        return found
