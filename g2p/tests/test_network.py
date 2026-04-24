#!/usr/bin/env python

import gzip
import json
import sys
from typing import Any
from unittest import TestCase

from pytest import main

from g2p import make_g2p
from g2p.exceptions import InvalidLanguageCode, NoPath
from g2p.log import LOGGER
from g2p.mappings.langs import LANGS_NWORK_PATH
from g2p.mappings.langs.network_lite import DiGraph, node_link_data, node_link_graph
from g2p.transducer import CompositeTransducer, Transducer


class NetworkTest(TestCase):
    """Basic Test for available networks"""

    def setUp(self):
        pass

    def test_not_found(self):
        with self.assertRaises(InvalidLanguageCode):
            with self.assertLogs(LOGGER, level="ERROR"):
                make_g2p("foo", "eng-ipa")
        with self.assertRaises(InvalidLanguageCode):
            with self.assertLogs(LOGGER, level="ERROR"):
                make_g2p("git", "bar")

    def test_no_path(self):
        with self.assertRaises(NoPath), self.assertLogs(LOGGER, level="ERROR"):
            make_g2p("hei", "git")

    def test_valid_composite(self):
        transducer = make_g2p("atj", "eng-ipa", tokenize=False)
        self.assertTrue(isinstance(transducer, CompositeTransducer))
        self.assertEqual("niɡiɡw", transducer("nikikw").output_string)

    def test_valid_transducer(self):
        transducer = make_g2p("atj", "atj-ipa", tokenize=False)
        self.assertTrue(isinstance(transducer, Transducer))
        self.assertEqual("niɡiɡw", transducer("nikikw").output_string)


class NetworkLiteTest(TestCase):
    data: Any

    @classmethod
    def setUpClass(cls):
        with gzip.open(LANGS_NWORK_PATH, "rt", encoding="utf8") as f:
            cls.data = json.load(f)

    def test_has_path(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")  # cycle
        graph.add_edge("a", "c")
        graph.add_edge("c", "d")
        graph.add_edge("e", "f")
        self.assertTrue(graph.has_path("a", "c"))
        self.assertTrue(graph.has_path("a", "d"))
        self.assertTrue(graph.has_path("b", "a"))
        self.assertFalse(graph.has_path("a", "e"))
        self.assertFalse(graph.has_path("a", "f"))
        self.assertFalse(graph.has_path("c", "a"))
        with self.assertRaises(KeyError):
            graph.has_path("a", "y")
        with self.assertRaises(KeyError):
            graph.has_path("x", "b")

    def test_g2p_path(self):
        graph = node_link_graph(self.data)
        self.assertTrue(graph.has_path("atj", "eng-ipa"))
        self.assertTrue(graph.has_path("atj", "atj-ipa"))
        self.assertFalse(graph.has_path("hei", "git"))

    def test_successors(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        graph.add_edge("a", "c")
        self.assertEqual(set(graph.successors("a")), {"b", "c"})
        self.assertEqual(set(graph.successors("b")), {"a"})
        self.assertEqual(set(graph.successors("c")), set())

    def test_descendants(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")  # cycle
        graph.add_edge("a", "c")
        graph.add_edge("c", "d")
        graph.add_edge("e", "f")
        self.assertEqual(graph.descendants("a"), {"b", "c", "d"})
        self.assertEqual(graph.descendants("b"), {"a", "c", "d"})
        self.assertEqual(graph.descendants("c"), {"d"})
        self.assertEqual(graph.descendants("d"), set())
        self.assertEqual(graph.descendants("e"), {"f"})
        self.assertEqual(graph.descendants("f"), set())
        with self.assertRaises(KeyError):
            graph.descendants("x")

    def test_g2p_descendants(self):
        graph = node_link_graph(self.data)
        self.assertEqual(
            graph.descendants("atj"), {"eng-ipa", "atj-ipa", "eng-arpabet"}
        )
        self.assertEqual(graph.descendants("eng-ipa"), {"eng-arpabet"})
        self.assertEqual(graph.descendants("atj-ipa"), {"eng-ipa", "eng-arpabet"})
        self.assertEqual(graph.descendants("eng-arpabet"), set())

    def test_ancestors(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("a", "c")
        graph.add_edge("d", "a")  # cycle
        graph.add_edge("c", "d")
        graph.add_edge("e", "f")
        self.assertEqual(graph.ancestors("a"), {"c", "d"})
        self.assertEqual(graph.ancestors("b"), {"a", "d", "c"})
        self.assertEqual(graph.ancestors("c"), {"a", "d"})
        self.assertEqual(graph.ancestors("d"), {"a", "c"})
        self.assertEqual(graph.ancestors("e"), set())
        self.assertEqual(graph.ancestors("f"), {"e"})
        with self.assertRaises(KeyError):
            graph.ancestors("x")

    def test_g2p_ancestors(self):
        graph: DiGraph = node_link_graph(self.data)
        self.assertEqual(graph.ancestors("atj"), set())
        self.assertGreater(len(graph.ancestors("eng-ipa")), 50)

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
        self.assertEqual(graph.shortest_path("a", "d"), ["a", "d"])
        self.assertEqual(graph.shortest_path("c", "d"), ["c", "d"])
        self.assertEqual(graph.shortest_path("a", "a"), ["a"])
        with self.assertRaises(ValueError):
            graph.shortest_path("c", "a")
        with self.assertRaises(KeyError):
            graph.shortest_path("a", "y")
        with self.assertRaises(KeyError):
            graph.shortest_path("x", "b")

    def test_g2p_shortest_path(self):
        graph = node_link_graph(self.data)
        self.assertEqual(
            graph.shortest_path("atj", "eng-arpabet"),
            ["atj", "atj-ipa", "eng-ipa", "eng-arpabet"],
        )

    def test_contains(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        self.assertTrue("a" in graph)
        self.assertTrue("b" in graph)
        self.assertFalse("c" in graph)

    def test_node_link_data(self):
        graph = node_link_graph(self.data)
        self.assertEqual(node_link_data(graph), self.data)

    def test_node_link_graph_errors(self):
        with self.assertRaises(ValueError):
            node_link_graph({**self.data, "directed": False})  # type: ignore
        with self.assertRaises(ValueError):
            node_link_graph({**self.data, "multigraph": True})  # type: ignore
        with self.assertRaises(ValueError):
            node_link_graph({**self.data, "nodes": "not a list"})  # type: ignore
        with self.assertRaises(ValueError):
            node_link_graph({**self.data, "links": "not a list"})  # type: ignore
        with self.assertRaises(ValueError):
            data = self.data.copy()
            del data["nodes"]
            node_link_graph(data)
        with self.assertRaises(ValueError):
            data = self.data.copy()
            del data["links"]
            node_link_graph(data)

    def test_no_duplicates(self):
        graph: DiGraph = DiGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("a", "c")
        graph.add_edge("a", "b")
        self.assertEqual(len(list(graph.edges)), 3)
        self.assertEqual(len(graph.nodes), 3)
        self.assertEqual(len(list(graph.successors("a"))), 2)
        self.assertEqual(len(list(graph.successors("b"))), 1)
        self.assertEqual(len(list(graph.successors("c"))), 0)


if __name__ == "__main__":
    main([__file__, *sys.argv])
