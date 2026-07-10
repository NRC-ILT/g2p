#!/usr/bin/env python

import os
import sys
from unittest import mock

from pytest import main, raises

from g2p import make_g2p
from g2p.exceptions import MalformedMapping, NeuralDependencyError
from g2p.mappings import Mapping
from g2p.tests.public import PUBLIC_DIR
from g2p.transducer import CompositeTransducer, Transducer, normalize_edges

# Disable the attr-defined mypy error so that we can use setUpClass sanely
# mypy: disable-error-code="attr-defined"


class TestTransducer:
    """Basic Transducer Test"""

    @classmethod
    def setup_class(cls):
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
            with raises(NeuralDependencyError):
                make_g2p("foo", "bar", neural=True)
            with raises(NeuralDependencyError):
                make_g2p("str", "str-ipa", neural=True)

    def test_properties(self):
        """Test all the basic properties of transducers."""
        assert "spam" == self.test_trans.in_lang
        assert "eggs" == self.test_trans.out_lang
        assert [self.test_trans] == self.test_trans.transducers
        assert [
            self.test_trans,
            self.test_trans_rev,
        ] == self.test_trans_composite.transducers
        assert "spam" == self.test_trans_composite.in_lang
        assert "parrot" == self.test_trans_composite.out_lang

    def test_graph_properties(self):
        """Test all the basic properties of graphs."""
        tg = self.test_trans("abab")
        assert "abab" == tg.input_string
        assert "bbbb" == tg.output_string
        assert 1 == len(tg.tiers)
        assert [(0, "a"), (1, "b"), (2, "a"), (3, "b")] == tg.input_nodes
        assert [(0, "b"), (1, "b"), (2, "b"), (3, "b")] == tg.output_nodes
        assert [(0, 0), (1, 1), (2, 2), (3, 3)] == tg.edges
        assert [("a", "b"), ("b", "b"), ("a", "b"), ("b", "b")] == tg.pretty_edges()
        assert 1 == len(tg.debugger)
        assert 2 == len(tg.debugger[0])
        tg.input_string = "bbbb"
        assert [(0, "b"), (1, "b"), (2, "b"), (3, "b")] == tg.input_nodes
        tg.output_string = "baba"
        assert [(0, "b"), (1, "a"), (2, "b"), (3, "a")] == tg.output_nodes
        tg.edges = [(0, 1), (1, 0), (2, 3), (3, 2)]
        assert [(0, 1), (1, 0), (2, 3), (3, 2)] == tg.edges
        tg.debugger = [["spam", "spam", "spam", "spam"]]
        assert 1 == len(tg.debugger)
        assert 4 == len(tg.debugger[0])
        with raises(ValueError):
            tg.input_nodes = ("foo", "bar", "baz")
        with raises(ValueError):
            tg.output_nodes = ("foo", "bar", "baz")
        with raises(ValueError):
            tg.tiers = ["spam", "spam", "eggs", "spam"]
        tg = self.test_trans("abab")
        tg += tg
        assert "abababab" == tg.input_string
        assert "bbbbbbbb" == tg.output_string

    def test_composite_graph_properties(self):
        """Test all the basic properties of composite graphs."""
        ctg = self.test_trans_composite("aba")
        assert "aba" == ctg.input_string
        assert "aaa" == ctg.output_string
        assert 2 == len(ctg.tiers)
        assert [(0, "a"), (1, "b"), (2, "a")] == ctg.input_nodes
        assert [(0, "a"), (1, "a"), (2, "a")] == ctg.output_nodes
        assert [[(0, 0), (1, 1), (2, 2)], [(0, 0), (1, 1), (2, 2)]] == ctg.edges
        assert [
            [("a", "b"), ("b", "b"), ("a", "b")],
            [("b", "a"), ("b", "a"), ("b", "a")],
        ] == ctg.pretty_edges()
        assert len(ctg.tiers) == len(ctg.debugger)
        ctg.input_string = "bbbb"
        assert [(0, "b"), (1, "b"), (2, "b"), (3, "b")] == ctg.input_nodes
        ctg.output_string = "baba"
        assert [(0, "b"), (1, "a"), (2, "b"), (3, "a")] == ctg.output_nodes
        with raises(ValueError):
            ctg.debugger = [["spam", "spam", "spam", "spam"]]
        with raises(ValueError):
            ctg.edges = [(0, 1), (1, 0), (2, 3), (3, 2)]
        with raises(ValueError):
            ctg.input_nodes = ("foo", "bar", "baz")
        with raises(ValueError):
            ctg.output_nodes = ("foo", "bar", "baz")
        with raises(ValueError):
            ctg.tiers = ["spam", "spam", "eggs", "spam"]
        ctg = self.test_trans_composite("aba")
        ctg += ctg
        assert "abaaba" == ctg.input_string
        assert "aaaaaa" == ctg.output_string

    def test_ordered(self):
        transducer_feed = self.test_trans_ordered_feed("a")
        transducer_counter_feed = self.test_trans_ordered_counter_feed("a")
        # These should feed b -> c
        assert transducer_feed.output_string == "c"
        # These should counter-feed b -> c
        assert transducer_counter_feed.output_string == "b"

    def test_forward(self):
        assert self.test_trans("a").output_string == "b"
        assert self.test_trans("b").output_string == "b"

    def test_backward(self):
        assert self.test_trans_rev("b").output_string == "a"
        assert self.test_trans_rev("a").output_string == "a"

    def test_lang_import(self):
        assert self.test_trans_moh("kawenón:nis").output_string == "ɡɑwenṹːnis"

    def test_composite(self):
        assert self.test_trans_composite("aba").output_string == "aaa"
        assert self.test_trans_composite_2("aba").output_string == "bbb"

    def test_rule_ordering(self):
        assert self.test_trans_as_written("'y").output_string == "jˀ"
        assert self.test_trans_longest_first("'y").output_string == "ʣˀ"

    def test_case_sensitive(self):
        assert self.test_case_sensitive_transducer("'N").output_string == "'N"
        assert self.test_case_sensitive_transducer("'n").output_string == "n̓"
        assert self.test_case_insensitive_transducer("'N").output_string == "n̓"
        assert self.test_case_insensitive_transducer("'n").output_string == "n̓"

    def test_regex_set(self):
        # https://github.com/NRC-ILT/g2p/issues/15
        assert self.test_regex_set_transducer_sanity("ca").output_string == "cb"
        assert self.test_regex_set_transducer("ca").output_string == "cb"
        assert self.test_regex_set_transducer("fa").output_string == "fb"

    def test_deletion(self):
        tg = self.test_deletion_transducer("a")
        assert tg.output_string == ""
        assert tg.pretty_edges() == [("a", None)]
        assert self.test_deletion_transducer_csv("a").output_string == ""
        assert self.test_deletion_transducer_json("a").output_string == ""

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
        assert transducer("'a").output_string == "b"
        assert transducer("'A").output_string == "B"
        assert transducer("E\u0301").output_string == "F"
        assert transducer("e\u0301").output_string == "f"
        # Test what happens in Heiltsuk. \u03BB (λ) should be capitalized as \u2144 (⅄)
        assert transducer("TLaba").output_string == "\u2144aba"
        assert transducer("tlaba").output_string == "λaba"
        # I guess it's arguable what should happen here, but I'll just change case if any of the characters are differently cased
        assert transducer("Tlaba").output_string == "\u2144aba"
        # case equivalencies that are not the same length cause indexing errors in the current implementation
        with raises(MalformedMapping):
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

        with raises(MalformedMapping):
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
        assert normalize_edges(bad_edges) == [(0, 0), (1, 0), (2, 2), (3, 2), (4, 4)]
        # Sort edges on inputs and suppress duplicates
        bad_edges = [(4, 0), (1, 3), (1, 2), (2, 5)]
        assert normalize_edges(bad_edges) == [(1, 3), (1, 2), (2, 5), (4, 0)]
        bad_edges = [(4, 0), (1, 3), (1, 3), (1, 2), (2, 5)]
        assert normalize_edges(bad_edges) == [(1, 3), (1, 2), (2, 5), (4, 0)]
        # Map None to previous if it exists
        bad_edges = [(0, 0), (1, None), (2, 1)]
        assert normalize_edges(bad_edges) == [(0, 0), (1, 0), (2, 1)]
        bad_edges = [(0, 0), (1, None), (2, None), (3, None)]
        assert normalize_edges(bad_edges) == [(0, 0), (1, 0), (2, 0), (3, 0)]
        bad_edges = [(0, 0), (1, None), (2, None), (3, 1), (4, None), (5, 2)]
        assert normalize_edges(bad_edges) == [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 1),
            (4, 1),
            (5, 2),
        ]
        # Map None to next if it exists
        bad_edges = [(0, None), (2, 1)]
        assert normalize_edges(bad_edges) == [(0, 1), (2, 1)]
        bad_edges = [(0, None), (1, None), (2, 1)]
        assert normalize_edges(bad_edges) == [(0, 1), (1, 1), (2, 1)]
        # Otherwise leave it as None
        bad_edges = []
        assert normalize_edges(bad_edges) == bad_edges
        bad_edges = [(0, None)]
        assert normalize_edges(bad_edges) == bad_edges
        bad_edges = [(0, None), (1, None)]
        assert normalize_edges(bad_edges) == bad_edges


if __name__ == "__main__":
    main([__file__, *sys.argv])
