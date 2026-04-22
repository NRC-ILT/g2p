from collections import deque
from typing import (
    Any,
    Deque,
    Dict,
    Generic,
    Hashable,
    Iterable,
    Iterator,
    List,
    Set,
    Tuple,
    TypeVar,
    Union,
)

from typing_extensions import TypedDict

T = TypeVar("T", bound=Hashable)


class DiGraph(Generic[T]):
    """A simple directed graph class

    Most functions raise KeyError if called with a node u or v not in the graph.
    """

    def __init__(self) -> None:
        """Contructor, empty if no data, else load from data"""
        self._edges: Dict[T, List[T]] = {}

    def clear(self) -> None:
        """Clear the graph"""
        self._edges.clear()

    def update(self, edges: Iterable[Tuple[T, T]], nodes: Iterable[T]):
        """Update the graph with new edges and nodes"""
        for node in nodes:
            self.add_node(node)
        for u, v in edges:
            self.add_edge(u, v)

    def add_node(self, u: T):
        """Add a node to the graph"""
        if u not in self._edges:
            self._edges[u] = []

    def add_edge(self, u: T, v: T):
        """Add a directed edge from u to v"""
        self.add_node(u)
        self.add_node(v)
        if v not in self._edges[u]:
            self._edges[u].append(v)

    def add_edges_from(self, edges: Iterable[Tuple[T, T]]):
        """Add edges from a list of tuples"""
        for u, v in edges:
            self.add_edge(u, v)

    @property  # read-only
    def nodes(self):
        """Return the nodes"""
        return self._edges.keys()

    @property  # read-only
    def edges(self) -> Iterator[Tuple[T, T]]:
        """Iterate over all edges"""
        for u, neighbours in self._edges.items():
            for v in neighbours:
                yield u, v

    def __contains__(self, u: T) -> bool:
        """Check if a node is in the graph"""
        return u in self._edges

    def has_path(self, u: T, v: T) -> bool:
        """Check if there is a path from u to v"""
        if v not in self._edges:
            raise KeyError(f"Node {v} not in graph")
        visited: Set[T] = set()
        return self._has_path(u, v, visited)

    def _has_path(self, u: T, v: T, visited: Set[T]) -> bool:
        """Helper function for has_path"""
        visited.add(u)
        if u == v:
            return True
        for neighbour in self._edges[u]:
            if neighbour not in visited:
                if self._has_path(neighbour, v, visited):
                    return True
        return False

    def successors(self, u: T) -> Iterator[T]:
        """Return the successors of u"""
        return iter(self._edges[u])

    def descendants(self, u: T) -> Set[T]:
        """Return the descendants of u"""
        visited: Set[T] = set()
        self._descendants(u, visited)
        visited.remove(u)
        return visited

    def _descendants(self, u: T, visited: Set[T]):
        """Helper function for descendants"""
        visited.add(u)
        for neighbour in self._edges[u]:
            if neighbour not in visited:
                self._descendants(neighbour, visited)

    def ancestors(self, u: T) -> Set[T]:
        """Return the ancestors of u"""
        reversed_graph: DiGraph[T] = DiGraph()
        reversed_graph.add_edges_from((v, u) for u, v in self.edges)
        for node in self.nodes:
            reversed_graph.add_node(node)
        return reversed_graph.descendants(u)

    def shortest_path(self, u: T, v: T) -> List[T]:
        """Return the shortest path from u to v

        Algorithm: Dijsktra's algorithm for unweighted graphs, which is just BFS

        Returns:
            list: the shortest path from u to v
        Raises:
            KeyError: if u or v is not in the graph
            ValueError: if there is no path from u to v
        """

        if v not in self._edges:
            raise KeyError(f"Node {v} not in graph")
        visited: Dict[T, Union[T, None]] = {
            u: None
        }  # dict of {node: predecessor on shortest path from u}
        queue: Deque[T] = deque([u])
        while queue:
            u = queue.popleft()
            if u == v:
                rev_path: List[T] = []
                nextu: Union[T, None] = u
                while nextu is not None:
                    rev_path.append(nextu)
                    nextu = visited[nextu]
                return list(reversed(rev_path))
            for neighbour in self._edges[u]:
                if neighbour not in visited:
                    visited[neighbour] = u
                    queue.append(neighbour)
        raise ValueError(f"No path from {u} to {v}")


class NodeDict(TypedDict):
    id: Any


class NodeLinkDict(TypedDict, Generic[T]):
    source: T
    target: T


class NodeLinkDataDict(TypedDict, Generic[T]):
    directed: bool
    graph: Dict
    links: List[NodeLinkDict[T]]
    multigraph: bool
    nodes: List[NodeDict]


def node_link_graph(data: NodeLinkDataDict[T]) -> DiGraph[T]:
    """Replacement for networkx.node_link_graph"""
    if not data.get("directed", False):
        raise ValueError("Graph must be directed")
    if data.get("multigraph", True):
        raise ValueError("Graph must not be a multigraph")
    if not isinstance(data.get("nodes", None), list):
        raise ValueError('data["nodes"] must be a list')
    if not isinstance(data.get("links", None), list):
        raise ValueError('data["links"] must be a list')

    graph: DiGraph[T] = DiGraph()
    for node in data["nodes"]:
        graph.add_node(node["id"])
    for edge in data["links"]:
        graph.add_edge(edge["source"], edge["target"])
    return graph


def node_link_data(graph: DiGraph[T]) -> NodeLinkDataDict[T]:
    """Replacement for networkx.node_link_data"""
    nodes: List[NodeDict] = [{"id": node} for node in graph.nodes]
    links: List[NodeLinkDict[T]] = [{"source": u, "target": v} for u, v in graph.edges]
    return {
        "directed": True,
        "graph": {},
        "links": links,
        "multigraph": False,
        "nodes": nodes,
    }
