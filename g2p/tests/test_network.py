#!/usr/bin/env python

import gzip
import json
import sys
from typing import Any

from pytest import main, raises

from g2p import make_g2p
from g2p.exceptions import InvalidLanguageCode, NoPath
from g2p.log import LOGGER
from g2p.mappings.langs import LANGS_NWORK_PATH
from g2p.mappings.langs.network_lite import DiGraph, node_link_data, node_link_graph
from g2p.transducer import CompositeTransducer, Transducer


class TestNetwork:
    """Basic Test for available networks"""

    def test_not_found(self, caplog):
        with raises(InvalidLanguageCode):
            with caplog.at_level("ERROR", logger=LOGGER.name):
                make_g2p("foo", "eng-ipa")
        with raises(InvalidLanguageCode):
            with caplog.at_level("ERROR", logger=LOGGER.name):
                make_g2p("git", "bar")

    def test_no_path(self, caplog):
        with raises(NoPath), caplog.at_level("ERROR", logger=LOGGER.name):
            make_g2p("hei", "git")

    def test_valid_composite(self):
        transducer = make_g2p("atj", "eng-ipa", tokenize=False)
        assert isinstance(transducer, CompositeTransducer)
        assert "niɡiɡw" == transducer("nikikw").output_string

    def test_valid_transducer(self):
        transducer = make_g2p("atj", "atj-ipa", tokenize=False)
        assert isinstance(transducer, Transducer)
        assert "niɡiɡw" == transducer("nikikw").output_string


class TestNetworkLite:
    data: Any

    @classmethod
    def setup_class(cls):
        with gzip.open(LANGS_NWORK_PATH, "rt", encoding="utf8") as f:
            cls.data = json.load(f)

    def test_has_path(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")  # cycle
        graph.add_edge("a", "c")
        graph.add_edge("c", "d")
        graph.add_edge("e", "f")
        assert graph.has_path("a", "c")
        assert graph.has_path("a", "d")
        assert graph.has_path("b", "a")
        assert not graph.has_path("a", "e")
        assert not graph.has_path("a", "f")
        assert not graph.has_path("c", "a")
        with raises(KeyError):
            graph.has_path("a", "y")
        with raises(KeyError):
            graph.has_path("x", "b")

    def test_g2p_path(self):
        graph = node_link_graph(self.data)
        assert graph.has_path("atj", "eng-ipa")
        assert graph.has_path("atj", "atj-ipa")
        assert not graph.has_path("hei", "git")

    def test_successors(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        graph.add_edge("a", "c")
        assert set(graph.successors("a")) == {"b", "c"}
        assert set(graph.successors("b")) == {"a"}
        assert set(graph.successors("c")) == set()

    def test_descendants(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")  # cycle
        graph.add_edge("a", "c")
        graph.add_edge("c", "d")
        graph.add_edge("e", "f")
        assert graph.descendants("a") == {"b", "c", "d"}
        assert graph.descendants("b") == {"a", "c", "d"}
        assert graph.descendants("c") == {"d"}
        assert graph.descendants("d") == set()
        assert graph.descendants("e") == {"f"}
        assert graph.descendants("f") == set()
        with raises(KeyError):
            graph.descendants("x")

    def test_g2p_descendants(self):
        graph = node_link_graph(self.data)
        assert graph.descendants("atj") == {"eng-ipa", "atj-ipa", "eng-arpabet"}
        assert graph.descendants("eng-ipa") == {"eng-arpabet"}
        assert graph.descendants("atj-ipa") == {"eng-ipa", "eng-arpabet"}
        assert graph.descendants("eng-arpabet") == set()

    def test_ancestors(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("a", "c")
        graph.add_edge("d", "a")  # cycle
        graph.add_edge("c", "d")
        graph.add_edge("e", "f")
        assert graph.ancestors("a") == {"c", "d"}
        assert graph.ancestors("b") == {"a", "d", "c"}
        assert graph.ancestors("c") == {"a", "d"}
        assert graph.ancestors("d") == {"a", "c"}
        assert graph.ancestors("e") == set()
        assert graph.ancestors("f") == {"e"}
        with raises(KeyError):
            graph.ancestors("x")

    def test_g2p_ancestors(self):
        graph: DiGraph = node_link_graph(self.data)
        assert graph.ancestors("atj") == set()
        assert len(graph.ancestors("eng-ipa")) > 50

    def test_shortest_path(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "e")
        graph.add_edge("e", "f")
        graph.add_edge("f", "g")
        graph.add_edge("g", "d")
        graph.add_edge("f", "d")
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")  # Cycle
        graph.add_edge("a", "c")
        graph.add_edge("c", "d")
        graph.add_edge("a", "d")
        graph.add_edge("b", "d")
        assert graph.shortest_path("a", "d") == ["a", "d"]
        assert graph.shortest_path("c", "d") == ["c", "d"]
        assert graph.shortest_path("a", "a") == ["a"]
        with raises(ValueError):
            graph.shortest_path("c", "a")
        with raises(KeyError):
            graph.shortest_path("a", "y")
        with raises(KeyError):
            graph.shortest_path("x", "b")

    def test_g2p_shortest_path(self):
        graph = node_link_graph(self.data)
        assert graph.shortest_path("atj", "eng-arpabet") == [
            "atj",
            "atj-ipa",
            "eng-ipa",
            "eng-arpabet",
        ]

    def test_contains(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        assert "a" in graph
        assert "b" in graph
        assert "c" not in graph

    def test_node_link_data(self):
        graph = node_link_graph(self.data)
        assert node_link_data(graph) == self.data

    def test_node_link_graph_errors(self):
        with raises(ValueError):
            node_link_graph({**self.data, "directed": False})  # type: ignore
        with raises(ValueError):
            node_link_graph({**self.data, "multigraph": True})  # type: ignore
        with raises(ValueError):
            node_link_graph({**self.data, "nodes": "not a list"})  # type: ignore
        with raises(ValueError):
            node_link_graph({**self.data, "links": "not a list"})  # type: ignore
        with raises(ValueError):
            data = self.data.copy()
            del data["nodes"]
            node_link_graph(data)
        with raises(ValueError):
            data = self.data.copy()
            del data["links"]
            node_link_graph(data)

    def test_no_duplicates(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("a", "c")
        graph.add_edge("a", "b")
        assert len(list(graph.edges)) == 3
        assert len(graph.nodes) == 3
        assert len(list(graph.successors("a"))) == 2
        assert len(list(graph.successors("b"))) == 1
        assert len(list(graph.successors("c"))) == 0


if __name__ == "__main__":
    main([__file__, *sys.argv])
