#!/usr/bin/env python

import os
from unittest import TestCase, main, mock

from g2p import make_g2p
from g2p.exceptions import MalformedMapping, NeuralDependencyError
from g2p.mappings import Mapping
from g2p.tests.public import PUBLIC_DIR
from g2p.transducer import CompositeTransducer, Transducer, normalize_edges

# Disable the attr-defined mypy error so that we can use setUpClass sanely
# mypy: disable-error-code="attr-defined"


class TransducerTest(TestCase):
    """Basic Transducer Test"""

    @classmethod
    def setUpClass(cls):
        cls.test_mapping_moh = Mapping.find_mapping(
            in_lang="moh-equiv", out_lang="moh-ipa"
        )
        cls.test_mapping = Mapping(
            rules=[{"in": "a", "out": "b"}], in_lang="spam", out_lang="eggs"
        )
        cls.test_mapping_rev = Mapping(
            rules=[{"in": "a", "out": "b"}],
            reverse=True,
            in_lang="eggs",
            out_lang="parrot",
        )
        cls.test_mapping_ordered_feed = Mapping(
            rules=[{"in": "a", "out": "b"}, {"in": "b", "out": "c"}]
        )
        cls.test_mapping_ordered_counter_feed = Mapping(
            rules=[{"in": "b", "out": "c"}, {"in": "a", "out": "b"}]
        )
        cls.test_longest_first = Mapping(
            rules=[{"in": "j", "out": "ʣ"}, {"in": "'y", "out": "jˀ"}]
        )
        cls.test_rules_as_written_mapping = Mapping(
            rules=[{"in": "j", "out": "ʣ"}, {"in": "'y", "out": "jˀ"}],
            rule_ordering="apply-longest-first",
        )
        cls.test_case_sensitive_mapping = Mapping(
            rules=[{"in": "'n", "out": "n̓"}], case_sensitive=True
        )
        cls.test_case_insensitive_mapping = Mapping(
            rules=[{"in": "'n", "out": "n̓"}], case_sensitive=False
        )
        cls.test_case_sensitive_transducer = Transducer(cls.test_case_sensitive_mapping)
        cls.test_case_insensitive_transducer = Transducer(
            cls.test_case_insensitive_mapping
        )
        cls.test_trans_as_written = Transducer(cls.test_longest_first)
        cls.test_trans_longest_first = Transducer(cls.test_rules_as_written_mapping)
        cls.test_trans = Transducer(cls.test_mapping)
        cls.test_trans_ordered_feed = Transducer(cls.test_mapping_ordered_feed)
        cls.test_trans_ordered_counter_feed = Transducer(
            cls.test_mapping_ordered_counter_feed
        )
        cls.test_trans_rev = Transducer(cls.test_mapping_rev)
        cls.test_trans_moh = Transducer(cls.test_mapping_moh)
        cls.test_trans_composite = CompositeTransducer(
            [cls.test_trans, cls.test_trans_rev]
        )
        cls.test_trans_composite_2 = CompositeTransducer(
            [cls.test_trans_rev, cls.test_trans]
        )
        cls.test_regex_set_transducer_sanity = Transducer(
            Mapping(rules=[{"in": "a", "out": "b", "context_before": "c"}])
        )
        cls.test_regex_set_transducer = Transducer(
            Mapping(rules=[{"in": "a", "out": "b", "context_before": "[cd]|[fgh]"}])
        )
        cls.test_deletion_transducer = Transducer(
            Mapping(rules=[{"in": "a", "out": ""}])
        )
        csv_deletion_mapping = Mapping.load_mapping_from_path(
            os.path.join(PUBLIC_DIR, "mappings", "deletion_config_csv.yaml")
        )
        cls.test_deletion_transducer_csv = Transducer(csv_deletion_mapping)
        cls.test_deletion_transducer_json = Transducer(
            Mapping.load_mapping_from_path(
                os.path.join(PUBLIC_DIR, "mappings", "deletion_config_json.yaml")
            )
        )

    def test_no_neural_dependencies(self):
        """This tests what happens if a user tries to create a neural g2p without installing the dependencies. Other neural tests (for when deps are installed are in test_neural.py module.)"""
        with mock.patch("g2p.mappings.utils.has_neural_support", return_value=False):
            with self.assertRaises(NeuralDependencyError):
                make_g2p("foo", "bar", neural=True)
            with self.assertRaises(NeuralDependencyError):
                make_g2p("str", "str-ipa", neural=True)

    def test_properties(self):
        """Test all the basic properties of transducers."""
        self.assertEqual("spam", self.test_trans.in_lang)
        self.assertEqual("eggs", self.test_trans.out_lang)
        self.assertEqual([self.test_trans], self.test_trans.transducers)
        self.assertEqual(
            [self.test_trans, self.test_trans_rev],
            self.test_trans_composite.transducers,
        )
        self.assertEqual("spam", self.test_trans_composite.in_lang)
        self.assertEqual("parrot", self.test_trans_composite.out_lang)

    def test_graph_properties(self):
        """Test all the basic properties of graphs."""
        tg = self.test_trans("abab")
        self.assertEqual("abab", tg.input_string)
        self.assertEqual("bbbb", tg.output_string)
        self.assertEqual(1, len(tg.tiers))
        self.assertEqual([(0, "a"), (1, "b"), (2, "a"), (3, "b")], tg.input_nodes)
        self.assertEqual([(0, "b"), (1, "b"), (2, "b"), (3, "b")], tg.output_nodes)
        self.assertEqual([(0, 0), (1, 1), (2, 2), (3, 3)], tg.edges)
        self.assertEqual(
            [("a", "b"), ("b", "b"), ("a", "b"), ("b", "b")], tg.pretty_edges()
        )
        self.assertEqual(1, len(tg.debugger))
        self.assertEqual(2, len(tg.debugger[0]))
        tg.input_string = "bbbb"
        self.assertEqual([(0, "b"), (1, "b"), (2, "b"), (3, "b")], tg.input_nodes)
        tg.output_string = "baba"
        self.assertEqual([(0, "b"), (1, "a"), (2, "b"), (3, "a")], tg.output_nodes)
        tg.edges = [(0, 1), (1, 0), (2, 3), (3, 2)]
        self.assertEqual([(0, 1), (1, 0), (2, 3), (3, 2)], tg.edges)
        tg.debugger = [["spam", "spam", "spam", "spam"]]
        self.assertEqual(1, len(tg.debugger))
        self.assertEqual(4, len(tg.debugger[0]))
        with self.assertRaises(ValueError):
            tg.input_nodes = ("foo", "bar", "baz")
        with self.assertRaises(ValueError):
            tg.output_nodes = ("foo", "bar", "baz")
        with self.assertRaises(ValueError):
            tg.tiers = ["spam", "spam", "eggs", "spam"]
        tg = self.test_trans("abab")
        tg += tg
        self.assertEqual("abababab", tg.input_string)
        self.assertEqual("bbbbbbbb", tg.output_string)

    def test_composite_graph_properties(self):
        """Test all the basic properties of composite graphs."""
        ctg = self.test_trans_composite("aba")
        self.assertEqual("aba", ctg.input_string)
        self.assertEqual("aaa", ctg.output_string)
        self.assertEqual(2, len(ctg.tiers))
        self.assertEqual([(0, "a"), (1, "b"), (2, "a")], ctg.input_nodes)
        self.assertEqual([(0, "a"), (1, "a"), (2, "a")], ctg.output_nodes)
        self.assertEqual(
            [[(0, 0), (1, 1), (2, 2)], [(0, 0), (1, 1), (2, 2)]], ctg.edges
        )
        self.assertEqual(
            [
                [("a", "b"), ("b", "b"), ("a", "b")],
                [("b", "a"), ("b", "a"), ("b", "a")],
            ],
            ctg.pretty_edges(),
        )
        self.assertEqual(len(ctg.tiers), len(ctg.debugger))
        ctg.input_string = "bbbb"
        self.assertEqual([(0, "b"), (1, "b"), (2, "b"), (3, "b")], ctg.input_nodes)
        ctg.output_string = "baba"
        self.assertEqual([(0, "b"), (1, "a"), (2, "b"), (3, "a")], ctg.output_nodes)
        with self.assertRaises(ValueError):
            ctg.debugger = [["spam", "spam", "spam", "spam"]]
        with self.assertRaises(ValueError):
            ctg.edges = [(0, 1), (1, 0), (2, 3), (3, 2)]
        with self.assertRaises(ValueError):
            ctg.input_nodes = ("foo", "bar", "baz")
        with self.assertRaises(ValueError):
            ctg.output_nodes = ("foo", "bar", "baz")
        with self.assertRaises(ValueError):
            ctg.tiers = ["spam", "spam", "eggs", "spam"]
        ctg = self.test_trans_composite("aba")
        ctg += ctg
        self.assertEqual("abaaba", ctg.input_string)
        self.assertEqual("aaaaaa", ctg.output_string)

    def test_ordered(self):
        transducer_feed = self.test_trans_ordered_feed("a")
        transducer_counter_feed = self.test_trans_ordered_counter_feed("a")
        # These should feed b -> c
        self.assertEqual(transducer_feed.output_string, "c")
        # These should counter-feed b -> c
        self.assertEqual(transducer_counter_feed.output_string, "b")

    def test_forward(self):
        self.assertEqual(self.test_trans("a").output_string, "b")
        self.assertEqual(self.test_trans("b").output_string, "b")

    def test_backward(self):
        self.assertEqual(self.test_trans_rev("b").output_string, "a")
        self.assertEqual(self.test_trans_rev("a").output_string, "a")

    def test_lang_import(self):
        self.assertEqual(self.test_trans_moh("kawenón:nis").output_string, "ɡɑwenṹːnis")

    def test_composite(self):
        self.assertEqual(self.test_trans_composite("aba").output_string, "aaa")
        self.assertEqual(self.test_trans_composite_2("aba").output_string, "bbb")

    def test_rule_ordering(self):
        self.assertEqual(self.test_trans_as_written("'y").output_string, "jˀ")
        self.assertEqual(self.test_trans_longest_first("'y").output_string, "ʣˀ")

    def test_case_sensitive(self):
        self.assertEqual(self.test_case_sensitive_transducer("'N").output_string, "'N")
        self.assertEqual(self.test_case_sensitive_transducer("'n").output_string, "n̓")
        self.assertEqual(self.test_case_insensitive_transducer("'N").output_string, "n̓")
        self.assertEqual(self.test_case_insensitive_transducer("'n").output_string, "n̓")

    def test_regex_set(self):
        # https://github.com/NRC-ILT/g2p/issues/15
        self.assertEqual(
            self.test_regex_set_transducer_sanity("ca").output_string, "cb"
        )
        self.assertEqual(self.test_regex_set_transducer("ca").output_string, "cb")
        self.assertEqual(self.test_regex_set_transducer("fa").output_string, "fb")

    def test_deletion(self):
        tg = self.test_deletion_transducer("a")
        self.assertEqual(tg.output_string, "")
        self.assertEqual(tg.pretty_edges(), [("a", None)])
        self.assertEqual(self.test_deletion_transducer_csv("a").output_string, "")
        self.assertEqual(self.test_deletion_transducer_json("a").output_string, "")

    def test_case_preservation(self):
        mapping = Mapping(
            rules=[
                {"in": "'a", "out": "b"},
                {"in": "e\u0301", "out": "f"},
                {"in": "tl", "out": "λ"},
            ],
            case_sensitive=False,
            preserve_case=True,
            norm_form="NFC",
            case_equivalencies={"λ": "\u2144"},
        )
        transducer = Transducer(mapping)
        self.assertEqual(transducer("'a").output_string, "b")
        self.assertEqual(transducer("'A").output_string, "B")
        self.assertEqual(transducer("E\u0301").output_string, "F")
        self.assertEqual(transducer("e\u0301").output_string, "f")
        # Test what happens in Heiltsuk. \u03BB (λ) should be capitalized as \u2144 (⅄)
        self.assertEqual(transducer("TLaba").output_string, "\u2144aba")
        self.assertEqual(transducer("tlaba").output_string, "λaba")
        # I guess it's arguable what should happen here, but I'll just change case if any of the characters are differently cased
        self.assertEqual(transducer("Tlaba").output_string, "\u2144aba")
        # case equivalencies that are not the same length cause indexing errors in the current implementation
        with self.assertRaises(MalformedMapping):
            Mapping(
                rules=[
                    {"in": "'a", "out": "b"},
                    {"in": "e\u0301", "out": "f"},
                    {"in": "tl", "out": "λ"},
                ],
                case_sensitive=False,
                preserve_case=True,
                norm_form="NFC",
                case_equivalencies={"λ": "\u2144\u2144\u2144"},
            )

        with self.assertRaises(MalformedMapping):
            _ = Mapping(
                rules=[{"in": "a", "out": "b"}],
                case_sensitive=True,
                preserve_case=True,
            )

    def test_normalize_edges(self):
        # Remove non-deletion edges with the same index as deletions
        bad_edges = [
            (0, 0),
            (1, None),
            (1, 1),
            (2, 2),
            (3, None),
            (3, 1),
            (3, 2),
            (4, 4),
        ]
        self.assertEqual(
            normalize_edges(bad_edges), [(0, 0), (1, 0), (2, 2), (3, 2), (4, 4)]
        )
        # Sort edges on inputs and suppress duplicates
        bad_edges = [(4, 0), (1, 3), (1, 2), (2, 5)]
        self.assertEqual(normalize_edges(bad_edges), [(1, 3), (1, 2), (2, 5), (4, 0)])
        bad_edges = [(4, 0), (1, 3), (1, 3), (1, 2), (2, 5)]
        self.assertEqual(normalize_edges(bad_edges), [(1, 3), (1, 2), (2, 5), (4, 0)])
        # Map None to previous if it exists
        bad_edges = [(0, 0), (1, None), (2, 1)]
        self.assertEqual(normalize_edges(bad_edges), [(0, 0), (1, 0), (2, 1)])
        bad_edges = [(0, 0), (1, None), (2, None), (3, None)]
        self.assertEqual(normalize_edges(bad_edges), [(0, 0), (1, 0), (2, 0), (3, 0)])
        bad_edges = [(0, 0), (1, None), (2, None), (3, 1), (4, None), (5, 2)]
        self.assertEqual(
            normalize_edges(bad_edges), [(0, 0), (1, 0), (2, 0), (3, 1), (4, 1), (5, 2)]
        )
        # Map None to next if it exists
        bad_edges = [(0, None), (2, 1)]
        self.assertEqual(normalize_edges(bad_edges), [(0, 1), (2, 1)])
        bad_edges = [(0, None), (1, None), (2, 1)]
        self.assertEqual(normalize_edges(bad_edges), [(0, 1), (1, 1), (2, 1)])
        # Otherwise leave it as None
        bad_edges = []
        self.assertEqual(normalize_edges(bad_edges), bad_edges)
        bad_edges = [(0, None)]
        self.assertEqual(normalize_edges(bad_edges), bad_edges)
        bad_edges = [(0, None), (1, None)]
        self.assertEqual(normalize_edges(bad_edges), bad_edges)


if __name__ == "__main__":
    main()
