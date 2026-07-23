import networkx as nx
from typing import Dict, List, Any

class KnowledgeGraphBuilder:
    """Part 2: Builds software dependency and Knowledge Graphs."""

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_dependency(self, source_module: str, target_module: str, relation_type: str = "IMPORTS"):
        """Adds a directional dependency edge to the graph."""
        self.graph.add_edge(source_module, target_module, relation=relation_type)

    def get_graph_stats(self) -> Dict[str, Any]:
        """Returns structural metrics of the graph."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "is_dag": nx.is_directed_acyclic_graph(self.graph)
        }
