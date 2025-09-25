"""
Graph analysis utilities for pipeline definitions.
"""

from typing import Any, Dict, List, Optional, Tuple

from aws_lambda_powertools import Logger

logger = Logger()


class GraphAnalyzer:
    """
    Analyzes the graph structure of a pipeline definition.

    This class provides utilities for finding root nodes, leaf nodes,
    and analyzing the connectivity of the pipeline graph.
    """

    def __init__(self, pipeline: Any):
        """
        Initialize the GraphAnalyzer.

        Args:
            pipeline: Pipeline definition object
        """
        self.pipeline = pipeline
        self.nodes = pipeline.configuration.nodes
        self.edges = pipeline.configuration.edges

        # Will be populated during analysis
        self.node_id_to_data_id = {}
        self.data_id_to_node_id = {}
        self.node_id_to_node = {}
        self.graph = {}  # node_id -> [node_id]
        self.data_id_graph = {}  # data_id -> [data_id]
        self.root_nodes = set()
        self.leaf_nodes = set()

    def analyze(self) -> None:
        """
        Analyze the pipeline graph structure.

        This method builds the graph representation and identifies
        root and leaf nodes.
        """
        logger.info("Analyzing pipeline graph structure")

        # Build node mappings
        self._build_node_mappings()

        # Build graph representation
        self._build_graph()

        # Find root and leaf nodes
        self._find_root_and_leaf_nodes()

        logger.info(
            f"Graph analysis complete. Found {len(self.root_nodes)} root nodes and {len(self.leaf_nodes)} leaf nodes"
        )

    def _build_node_mappings(self) -> None:
        """Build mappings between different node ID formats."""
        for node in self.nodes:
            if node.id and node.data and node.data.id:
                self.node_id_to_data_id[node.id] = node.data.id
                self.data_id_to_node_id[node.data.id] = node.id
                self.node_id_to_node[node.id] = node
                logger.debug(
                    f"Node mapping: {node.id} -> {node.data.id} ({node.data.type})"
                )

    def _build_graph(self) -> None:
        """Build graph representations of the pipeline."""
        # Build node.id -> node.id graph
        for edge in self.edges:
            # Handle both dictionary and object structures
            if isinstance(edge, dict):
                source_id = edge.get("source")
                target_id = edge.get("target")
            else:
                source_id = edge.source
                target_id = edge.target

            if source_id not in self.graph:
                self.graph[source_id] = []
            self.graph[source_id].append(target_id)

            # Also build data.id -> data.id graph
            source_data_id = self.node_id_to_data_id.get(source_id)
            target_data_id = self.node_id_to_data_id.get(target_id)

            if source_data_id and target_data_id:
                if source_data_id not in self.data_id_graph:
                    self.data_id_graph[source_data_id] = []
                self.data_id_graph[source_data_id].append(target_data_id)
                logger.debug(
                    f"Added edge to data_id_graph: {source_data_id} -> {target_data_id}"
                )

    def _find_root_and_leaf_nodes(self) -> None:
        """Find root nodes (no incoming edges) and leaf nodes (no outgoing edges)."""
        all_nodes = set(node.id for node in self.nodes)
        target_nodes = set()

        for edge in self.edges:
            # Handle both dictionary and object structures
            if isinstance(edge, dict):
                target_nodes.add(edge.get("target"))
            else:
                target_nodes.add(edge.target)

        # Root nodes have no incoming edges
        self.root_nodes = all_nodes - target_nodes

        # Leaf nodes have no outgoing edges
        self.leaf_nodes = set(
            node_id for node_id in all_nodes if node_id not in self.graph
        )

        logger.info(f"Root nodes: {self.root_nodes}")
        logger.info(f"Leaf nodes: {self.leaf_nodes}")

    def get_root_node(self) -> Optional[str]:
        """
        Get the primary root node for the pipeline.

        If multiple root nodes exist, prefer trigger nodes.
        If no root nodes exist, return the first node.

        Returns:
            Node ID of the root node, or None if no nodes exist
        """
        if not self.root_nodes:
            logger.warning("No root node found in the graph. Using first node as root.")
            return self.nodes[0].id if self.nodes else None

        # Prefer trigger nodes as root
        trigger_roots = [
            node.id
            for node in self.nodes
            if node.id in self.root_nodes and node.data.type.lower() == "trigger"
        ]

        root_node_id = (
            trigger_roots[0] if trigger_roots else next(iter(self.root_nodes))
        )
        logger.info(f"Selected root node: {root_node_id}")
        return root_node_id

    def find_execution_path(
        self, start_node: str, state_names: Dict[str, str]
    ) -> List[str]:
        """
        Find the execution path through the state machine starting from a given node.

        Args:
            start_node: Node ID to start from
            state_names: Mapping from node IDs to state names

        Returns:
            List of state names in execution order
        """
        visited = set()
        path = []

        def dfs(node_id):
            if node_id in visited:
                return

            visited.add(node_id)
            state_name = state_names.get(node_id)

            if state_name:
                path.append(state_name)

            for next_node in self.graph.get(node_id, []):
                dfs(next_node)

        dfs(start_node)
        return path

    def find_special_edges(
        self,
    ) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, List[str]]]:
        """
        Find special edge types in the pipeline.

        Returns:
            Tuple of (
                          choice_true_targets,
                          choice_false_targets,
                          choice_fail_targets,
                          map_processor_chains
                      )
            where map_processor_chains maps Map node IDs to lists of node IDs in their processor chains
        """
        choice_true_targets = {}  # Maps Choice node ID to its "true" target node ID
        choice_false_targets = {}  # Maps Choice node ID to its "false" target node ID
        choice_fail_targets = {}  # Maps Choice node ID to its "fail" target node ID
        map_processor_chains = (
            {}
        )  # Maps Map node ID to a list of node IDs in its processor chain

        # First identify the initial processor nodes for each Map
        initial_processor_targets = (
            {}
        )  # Maps Map node ID to its initial processor node ID

        for edge in self.edges:
            # Extract source, target, and sourceHandle
            if isinstance(edge, dict):
                source_id = edge.get("source")
                target_id = edge.get("target")
                source_handle = edge.get("sourceHandle")
            else:
                source_id = edge.source
                target_id = edge.target
                source_handle = getattr(edge, "sourceHandle", None)

            source_node = self.node_id_to_node.get(source_id)
            if not source_node:
                continue

            # Handle Choice node edges
            if (
                source_node.data.type.lower() == "flow"
                and source_node.data.id == "choice"
            ):
                if source_handle == "Completed":
                    choice_true_targets[source_id] = target_id
                    logger.info(
                        f"Identified Choice true path: {source_id} -> {target_id}"
                    )
                elif source_handle == "In Progress":
                    choice_false_targets[source_id] = target_id
                    logger.info(
                        f"Identified Choice false path: {source_id} -> {target_id}"
                    )
                elif source_handle == "Fail":
                    choice_fail_targets[source_id] = target_id
                    logger.info(
                        f"Identified Choice fail path: {source_id} -> {target_id}"
                    )

            # Handle Map node edges
            if source_node.data.type.lower() == "flow" and source_node.data.id == "map":
                if source_handle == "Processor":
                    initial_processor_targets[source_id] = target_id
                    logger.info(
                        f"Identified initial Map processor: {source_id} -> {target_id}"
                    )

        # Now build the complete processor chains
        for map_id, initial_target in initial_processor_targets.items():
            chain = [initial_target]
            current_node = initial_target

            # Follow the chain of nodes connected to the initial processor
            while current_node in self.graph and self.graph[current_node]:
                next_node = self.graph[current_node][0]  # Take the first outgoing edge
                chain.append(next_node)
                current_node = next_node

            map_processor_chains[map_id] = chain
            logger.info(f"Built processor chain for Map {map_id}: {chain}")

        return (
            choice_true_targets,
            choice_false_targets,
            choice_fail_targets,
            map_processor_chains,
        )

    def find_first_and_last_lambdas(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Find the first and last non-trigger, non-flow nodes in the execution path.

        Returns:
            Tuple of (first_node_id, last_node_id)
        """
        # Get the root node
        root_node_id = self.get_root_node()
        if not root_node_id:
            return None, None

        # Find the first non-trigger, non-flow node
        first_node_id = None
        current_id = root_node_id
        visited = set()

        # BFS to find the first lambda node
        queue = [current_id]
        while queue and not first_node_id:
            current_id = queue.pop(0)
            if current_id in visited:
                continue

            visited.add(current_id)
            current_node = self.node_id_to_node.get(current_id)

            if not current_node:
                continue

            # Skip trigger and flow nodes
            if (
                current_node.data.type.lower() != "trigger"
                and current_node.data.type.lower() != "flow"
            ):
                first_node_id = current_id
                break

            # Add children to queue
            if current_id in self.graph:
                queue.extend(self.graph[current_id])

        # Find the last lambda node by traversing the entire graph
        last_node_id = None
        all_lambda_nodes = []

        for node_id, node in self.node_id_to_node.items():
            if node.data.type.lower() != "trigger" and node.data.type.lower() != "flow":
                all_lambda_nodes.append(node_id)

        # If there are no lambda nodes, return None, None
        if not all_lambda_nodes:
            return None, None

        # If there's only one lambda node, it's both first and last
        if len(all_lambda_nodes) == 1:
            return all_lambda_nodes[0], all_lambda_nodes[0]

        # Find the last lambda node (one with no outgoing edges to other lambdas)
        set(all_lambda_nodes)
        for node_id in all_lambda_nodes:
            has_lambda_children = False
            if node_id in self.graph:
                for child_id in self.graph[node_id]:
                    child_node = self.node_id_to_node.get(child_id)
                    if (
                        child_node
                        and child_node.data.type.lower() != "trigger"
                        and child_node.data.type.lower() != "flow"
                    ):
                        has_lambda_children = True
                        break

            if not has_lambda_children:
                last_node_id = node_id
                break

        # If we couldn't find a last node, use the last one in the list
        if not last_node_id and all_lambda_nodes:
            last_node_id = all_lambda_nodes[-1]

        logger.info(f"Identified first lambda node: {first_node_id}")
        logger.info(f"Identified last lambda node: {last_node_id}")

        return first_node_id, last_node_id
