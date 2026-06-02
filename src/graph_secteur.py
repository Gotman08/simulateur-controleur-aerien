"""
Graphe du secteur aerien (S2) - helpers spatiaux - Semaine 5 (U7)
=================================================================
Charge secteur_graphe.json (S2) et expose : liste des fixes, voisinage,
plus court chemin (Dijkstra sur les distances NM), et un resume textuel de la
topologie pour ancrer le LLM (conscience spatiale, cf. AirTrafficGen / slide 10).

Utilise par atc_llm (validation ADDWPT + contexte) et 16_graph_demo.
"""
import os
import json
import heapq

_HERE = os.path.dirname(os.path.abspath(__file__))


class SectorGraph:
    def __init__(self, path=None):
        path = path or os.path.join(_HERE, "secteur_graphe.json")
        with open(path, encoding="utf-8") as f:
            g = json.load(f)
        self.sep_nm = g.get("separation_nm")
        raw = g.get("noeuds", g.get("nodes", []))
        self.nodes = {n["id"]: n for n in raw}
        self.segments = g.get("segments", [])
        self.adj = {nid: [] for nid in self.nodes}
        for s in self.segments:
            a, b, d = s.get("de"), s.get("vers"), float(s.get("dist_nm", 0))
            self.adj.setdefault(a, []).append((b, d))
            self.adj.setdefault(b, []).append((a, d))

    def fixes(self):
        return list(self.nodes.keys())

    def is_fix(self, name):
        return name in self.nodes

    def neighbors(self, nid):
        return self.adj.get(nid, [])

    def shortest_path(self, src, dst):
        """Plus court chemin (Dijkstra). Renvoie (chemin, distance_nm) ou (None, inf)."""
        if src not in self.nodes or dst not in self.nodes:
            return None, float("inf")
        dist = {src: 0.0}
        prev = {}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == dst:
                break
            if d > dist.get(u, float("inf")):
                continue
            for v, w in self.adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        if dst not in dist:
            return None, float("inf")
        path = [dst]
        while path[-1] != src:
            path.append(prev[path[-1]])
        return list(reversed(path)), dist[dst]

    def topology_text(self):
        ns = ", ".join(f"{nid}({n.get('type')})" for nid, n in self.nodes.items())
        segs = "; ".join(f"{s['de']}-{s['vers']} {s['dist_nm']}NM" for s in self.segments)
        return f"Sector (separation {self.sep_nm} NM). Fixes: {ns}. Segments: {segs}."


if __name__ == "__main__":
    g = SectorGraph()
    print("Fixes :", g.fixes())
    print(g.topology_text())
    p, d = g.shortest_path("ENTRY_W", "EXIT_E")
    print(f"ENTRY_W -> EXIT_E : {p} = {d} NM")
