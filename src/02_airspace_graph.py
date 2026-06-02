"""
Preuve - Semaine 2 : modélisation de l'espace aérien sous forme de graphe
=========================================================================
Inspiré d'AirTrafficGen : on discrétise le secteur en noeuds (points de report,
balises) séparés par les distances de séparation réglementaires OACI, plutôt que
de fournir au LLM des coordonnées brutes (cf. rapport S2).

Sépration latérale réglementaire retenue : 5 NM (en-route radar).

Exécution :  python 02_airspace_graph.py
Sorties   :  fig_secteur_graphe.png, secteur_graphe.json
"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

SEP_NM = 5.0   # séparation latérale minimale (NM)


def build_sector():
    """Construit un secteur fictif : balises + segments de route + une intersection."""
    G = nx.Graph()
    # (nom, x_NM, y_NM, type)
    nodes = [
        ("ENTRY_W", 0,   20, "entry"),
        ("BALMO",   25,  20, "fix"),
        ("CROSS",   50,  25, "fix"),
        ("DELTA",   75,  20, "fix"),
        ("EXIT_E",  100, 20, "exit"),
        ("ENTRY_S", 50,  0,  "entry"),
        ("NORTH",   50,  50, "exit"),
    ]
    for name, x, y, kind in nodes:
        G.add_node(name, pos=(x, y), kind=kind)

    edges = [
        ("ENTRY_W", "BALMO"), ("BALMO", "CROSS"), ("CROSS", "DELTA"),
        ("DELTA", "EXIT_E"), ("ENTRY_S", "CROSS"), ("CROSS", "NORTH"),
    ]
    for a, b in edges:
        (xa, ya), (xb, yb) = G.nodes[a]["pos"], G.nodes[b]["pos"]
        dist = float(np.hypot(xb - xa, yb - ya))
        G.add_edge(a, b, dist_nm=round(dist, 1),
                   segments=max(1, int(dist // SEP_NM)))
    return G


def to_json(G, path="secteur_graphe.json"):
    data = {
        "separation_nm": SEP_NM,
        "noeuds": [{"id": n, "pos_nm": G.nodes[n]["pos"], "type": G.nodes[n]["kind"]}
                   for n in G.nodes],
        "segments": [{"de": a, "vers": b, "dist_nm": G[a][b]["dist_nm"],
                      "creneaux_5nm": G[a][b]["segments"]} for a, b in G.edges],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {path}  ({G.number_of_nodes()} noeuds, {G.number_of_edges()} segments)")


def plot(G, path="fig_secteur_graphe.png"):
    pos = nx.get_node_attributes(G, "pos")
    colors = {"entry": "#16a34a", "exit": "#dc2626", "fix": "#1f4ed8"}
    node_colors = [colors[G.nodes[n]["kind"]] for n in G.nodes]

    fig, ax = plt.subplots(figsize=(9, 5))
    nx.draw_networkx_edges(G, pos, width=2, edge_color="#64748b", ax=ax)
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=900,
                           edgecolors="black", ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=7, font_color="white",
                            font_weight="bold", ax=ax)
    elabels = {(a, b): f"{G[a][b]['dist_nm']} NM" for a, b in G.edges}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=elabels, font_size=7, ax=ax)

    handles = [plt.Line2D([0], [0], marker="o", ls="", markersize=10,
                          markerfacecolor=c, markeredgecolor="k", label=k)
               for k, c in colors.items()]
    ax.legend(handles=handles, loc="upper left", fontsize=9)
    ax.set_title(f"Secteur aérien discrétisé en graphe (séparation {SEP_NM:.0f} NM)")
    ax.set_xlabel("x (NM)"); ax.set_ylabel("y (NM)")
    ax.grid(True, alpha=0.25); ax.set_aspect("equal")
    ax.set_xlim(-12, 112); ax.set_ylim(-12, 62)   # marges : évite le rognage des labels en bordure
    fig.tight_layout(); fig.savefig(path, dpi=150)
    print(f"[OK] {path}")


def main():
    G = build_sector()
    plot(G)
    to_json(G)
    # exemple de requête de plus court chemin (proof of usefulness for the LLM)
    route = nx.shortest_path(G, "ENTRY_W", "EXIT_E", weight="dist_nm")
    total = sum(G[route[i]][route[i+1]]["dist_nm"] for i in range(len(route) - 1))
    print("Route ENTRY_W -> EXIT_E :", " -> ".join(route), f"({total:.0f} NM)")


if __name__ == "__main__":
    main()
