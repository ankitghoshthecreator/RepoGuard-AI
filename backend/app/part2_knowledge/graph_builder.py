import logging
import networkx as nx
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase

from backend.app.config import settings

logger = logging.getLogger("repoguard.part2.graph_builder")

class KnowledgeGraphBuilder:
    """Part 2: Builds software dependency and Knowledge Graphs using NetworkX and Neo4j."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.driver = None
        self.use_neo4j = False

        # Attempt to establish connection to Neo4j
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            self.use_neo4j = True
            logger.info("Successfully connected to Neo4j graph database.")
        except Exception as e:
            logger.warning(f"Could not connect to Neo4j database ({settings.NEO4J_URI}). "
                           f"Falling back to NetworkX in-memory representation. Detail: {e}")

    def add_dependency(self, source_module: str, target_module: str, relation_type: str = "IMPORTS"):
        """Adds a directional dependency edge to the graph (NetworkX and Neo4j)."""
        # Add to local NetworkX graph
        self.graph.add_edge(source_module, target_module, relation=relation_type)

        # Add to Neo4j if available
        if self.use_neo4j and self.driver:
            try:
                with self.driver.session() as session:
                    # Merge source node, merge target node, and merge relation
                    query = (
                        "MERGE (s:Module {name: $source}) "
                        "MERGE (t:Module {name: $target}) "
                        f"MERGE (s)-[r:{relation_type}]->(t) "
                        "RETURN r"
                    )
                    session.run(query, source=source_module, target=target_module)
            except Exception as e:
                logger.error(f"Failed to add dependency in Neo4j: {e}")

    def sync_to_neo4j(self):
        """Clears existing database contents and synchronizes the entire local NetworkX graph to Neo4j."""
        if not self.use_neo4j or not self.driver:
            logger.info("Neo4j database is offline. Skipping graph synchronization.")
            return

        try:
            with self.driver.session() as session:
                # Clear all Module nodes and relations
                session.run("MATCH (n:Module) DETACH DELETE n")

                # Insert all nodes and edges from NetworkX
                for u, v, data in self.graph.edges(data=True):
                    relation = data.get("relation", "IMPORTS")
                    query = (
                        "MERGE (s:Module {name: $source}) "
                        "MERGE (t:Module {name: $target}) "
                        f"MERGE (s)-[r:{relation}]->(t)"
                    )
                    session.run(query, source=u, target=v)
            logger.info("Successfully synchronized NetworkX graph to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to synchronize graph to Neo4j: {e}")

    def clear_graph(self):
        """Clears local NetworkX graph and deletes database nodes/edges in Neo4j."""
        self.graph.clear()
        if self.use_neo4j and self.driver:
            try:
                with self.driver.session() as session:
                    session.run("MATCH (n:Module) DETACH DELETE n")
            except Exception as e:
                logger.error(f"Failed to clear Neo4j graph: {e}")

    def find_circular_dependencies(self) -> List[List[str]]:
        """Finds all cycles / circular dependency paths in the module graph."""
        try:
            # NetworkX simple_cycles returns an iterator over list of cycles
            return list(nx.simple_cycles(self.graph))
        except Exception as e:
            logger.error(f"Error finding cycles in graph: {e}")
            return []

    def get_shortest_path(self, source: str, target: str) -> List[str]:
        """Calculates the shortest topological path of import relationships between two modules."""
        if source not in self.graph or target not in self.graph:
            return []
        try:
            return nx.shortest_path(self.graph, source=source, target=target)
        except nx.NetworkXNoPath:
            return []
        except Exception as e:
            logger.error(f"Error calculating shortest path: {e}")
            return []

    def get_neighbors(self, node: str, direction: str = "out") -> List[str]:
        """
        Retrieves directly connected nodes (predecessors or successors).
        
        Args:
            node: Node identifier.
            direction: "out" for target dependencies, "in" for dependent nodes.
        """
        if node not in self.graph:
            return []
        if direction == "out":
            return list(self.graph.successors(node))
        elif direction == "in":
            return list(self.graph.predecessors(node))
        return []

    def get_graph_stats(self) -> Dict[str, Any]:
        """Returns structural analysis metrics of the dependency graph."""
        num_nodes = self.graph.number_of_nodes()
        num_edges = self.graph.number_of_edges()
        
        # Calculate avg degree
        avg_degree = 0.0
        if num_nodes > 0:
            avg_degree = sum(dict(self.graph.degree()).values()) / num_nodes

        # Check if DAG
        is_dag = nx.is_directed_acyclic_graph(self.graph)

        # Detect cycle loops
        cycles = self.find_circular_dependencies()

        return {
            "nodes": num_nodes,
            "edges": num_edges,
            "is_dag": is_dag,
            "density": nx.density(self.graph),
            "average_degree": avg_degree,
            "circular_dependencies": cycles,
            "has_circular_deps": len(cycles) > 0
        }

    def close(self):
        """Closes the Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    def __del__(self):
        self.close()
