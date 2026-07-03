#!/usr/bin/env python

import io
import json
import os
import re
import sys
import unicodedata as ud
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List
from unittest import TestCase, mock

from pydantic import ValidationError
from pytest import main

from g2p import exceptions, make_g2p
from g2p.exceptions import InvalidNormalization, NeuralDependencyError
from g2p.log import LOGGER
from g2p.mappings import Mapping, Rule
from g2p.mappings.utils import NORM_FORM_ENUM, RULE_ORDERING_ENUM, normalize
from g2p.tests.public import __file__ as public_data
from g2p.transducer import Transducer


def rules_from_strings(*mapping: str) -> List[dict]:
    """Quick pseudo constructor for unit testing of mappings"""
    rules = []
    for rule in mapping:
        key, value = rule.split(":")
        rules.append({"in": key, "out": value})
    return rules


class MappingTest(TestCase):
    """Basic Mapping Test"""

    def setUp(self):
        self.test_mapping_no_norm = Mapping(
            rules=[
                {"in": "\u00e1", "out": "\u00e1"},
                {"in": "\u0061\u0301", "out": "\u0061\u0301"},
            ],
            norm_form="none",
        )
        self.test_mapping_norm = Mapping(rules=[{"in": "\u00e1", "out": "\u00e1"}])
        with open(
            os.path.join(os.path.dirname(public_data), "git_to_ipa.json"),
            encoding="utf8",
        ) as f:
            self.json_map = json.load(f)

    def test_find_mappings(self):
        rules_mapping = make_g2p("str", "str-ipa")
        self.assertIsNone(rules_mapping.transducers[-1].mapping.type)

    def test_neural_not_available_raises_exception(self):
        from g2p.mappings.utils import (
            deep_phonemizer_handler,
            download_huggingface_model,
            has_neural_support,
        )

        # Call things that need neural with a mock context simulating not having
        # installed the dependencies, even when they are actually installed
        with mock.patch("g2p.mappings.utils.has_neural_support", return_value=False):
            with self.assertRaises(NeuralDependencyError):
                make_g2p("str", "str-ipa", neural=True)
            with self.assertRaises(NeuralDependencyError):
                deep_phonemizer_handler(Path(), {}, "foo")
            with self.assertRaises(NeuralDependencyError):
                download_huggingface_model("foo")

        # calling has_neural_support should return a Bool without raising any exception,
        # but we can't assert the value since we don't know if neural deps are installed
        assert isinstance(has_neural_support(), bool)

    def test_normalization(self):
        self.assertEqual(
            ud.normalize("NFD", "\u00e1"), self.test_mapping_norm.rules[0].rule_input
        )
        self.assertNotEqual(self.test_mapping_norm.rules[0].rule_input, "\u00e1")
        self.assertEqual(self.test_mapping_norm.rules[0].rule_input, "\u0061\u0301")
        self.assertEqual(self.test_mapping_no_norm.rules[0].rule_input, "\u00e1")
        self.assertEqual(self.test_mapping_no_norm.rules[0].rule_output, "\u00e1")
        self.assertEqual(self.test_mapping_no_norm.rules[1].rule_input, "\u0061\u0301")
        self.assertEqual(self.test_mapping_no_norm.rules[1].rule_output, "\u0061\u0301")

    def test_utils_normalize(self):
        """Explicitly test our custom normalize function."""
        self.assertEqual(normalize(r"\u0061", None), "a")
        self.assertEqual(normalize("\u010d", "NFD"), "\u0063\u030c")
        self.assertEqual(normalize("\u0063\u030c", "NFC"), "\u010d")
        with self.assertRaises(InvalidNormalization) as cm:
            normalize("FOOBIE", "BLETCH")
        assert "invalid argument" in str(cm.exception)

    def test_json_map(self):
        json_map = Mapping(
            rules=self.json_map["map"],
            **{k: v for k, v in self.json_map.items() if k != "map"},
        )
        self.assertEqual(len(json_map.rules), 34)
        # This is a very old version of the config, I'm not even sure these tests should be in here at all.
        # assert json_map.kwargs["in_metadata"]["case_insensitive"]

    def test_no_mappings_key(self):
        with self.assertRaises(ValidationError):
            Mapping.load_mapping_from_path(
                os.path.join(
                    os.path.dirname(public_data), "mappings", "no_mappings_key.yaml"
                )
            )

    def test_improperly_initialized(self) -> None:
        mapping = Mapping(rules=[Rule(rule_input="a", rule_output="b")])
        mapping.rules = [{"rule_input": "something misguided"}]  # type: ignore
        with self.assertRaises(AttributeError):
            mapping.inventory()

    def test_as_is(self):
        """
        Test deprecated config: as_is.

        This will fail when we release g2p 3.0.0, at which point we can just delete this test.
        """

        # explicitly set as_is=False
        log_output = io.StringIO()
        with redirect_stderr(log_output):
            mapping_sorted = Mapping(
                rules=[{"in": "a", "out": "b"}, {"in": "aa", "out": "c"}], as_is=False
            )
        self.assertTrue(
            mapping_sorted.rule_ordering == RULE_ORDERING_ENUM.apply_longest_first
        )
        self.assertIn(
            "deprecated",
            log_output.getvalue(),
            "it should warn that the feature is deprecated",
        )
        self.assertIn(
            "apply-longest-first",
            log_output.getvalue(),
            "it should show the equivalent rule_ordering setting",
        )

        # explicitly set as_is=True
        log_output = io.StringIO()
        with redirect_stderr(log_output):
            mapping = Mapping(
                rules=[{"in": "a", "out": "b"}, {"in": "aa", "out": "c"}], as_is=True
            )
        self.assertFalse(
            mapping.rule_ordering == RULE_ORDERING_ENUM.apply_longest_first
        )
        self.assertIn(
            "deprecated",
            log_output.getvalue(),
            "it should warn that the feature is deprecated",
        )
        self.assertIn(
            "as-written",
            log_output.getvalue(),
            "it should show the equivalent rule_ordering setting",
        )

        # test the default (rule_ordering="as-written")
        mapping_as_is = Mapping(
            rules=[{"in": "a", "out": "b"}, {"in": "aa", "out": "c"}]
        )
        self.assertFalse(
            mapping.rule_ordering == RULE_ORDERING_ENUM.apply_longest_first
        )

        # test the alternative (rule_ordering="apply-longest-first")
        transducer = Transducer(mapping_sorted)
        transducer_as_is = Transducer(mapping_as_is)
        self.assertEqual(transducer("aa").output_string, "c")
        self.assertEqual(transducer_as_is("aa").output_string, "bb")

    def test_rule_ordering(self):
        """
        Test the config option:

        rule-ordering: 'as-written' (default)

        or

        rule-ordering: 'apply-shortest-first'
        """
        rules = [{"in": "a", "out": "b"}, {"in": "aa", "out": "c"}]

        transducer_longest_first = Transducer(
            Mapping(rules=rules, rule_ordering="apply-longest-first")
        )
        self.assertEqual(transducer_longest_first("aa").output_string, "c")

        transducer_as_written = Transducer(
            Mapping(rules=rules, rule_ordering="as-written")
        )
        self.assertEqual(transducer_as_written("aa").output_string, "bb")

        transducer_default = Transducer(Mapping(rules=rules))
        self.assertEqual(transducer_default("aa").output_string, "bb")

    def test_rule_ordering_with_indices(self):
        """a{1}b{3} should be shorter than abc"""
        rules = [{"in": "a{1}b{2}", "out": "x{1}x{2}"}, {"in": "abc", "out": "y"}]
        mapping = Mapping(rules=rules, rule_ordering="apply-longest-first")
        transducer = Transducer(mapping)
        self.assertEqual(transducer("abc").output_string, "y")

    def test_rule_ordering_given_invalid_value(self):
        """
        It should log an error messages if given an invalid value for
        rule_ordering=...
        """
        rules = [{"in": "a", "out": "b"}, {"in": "aa", "out": "c"}]

        # typo in the valid setting:
        incorrect_value = "apply-longest-frist"

        log_output = io.StringIO()
        with redirect_stderr(log_output) and self.assertRaises(ValidationError):
            Mapping(rules=rules, rule_ordering=incorrect_value)

    def test_case_sensitive(self):
        mapping = Mapping(rules=[{"in": "A", "out": "b"}], case_sensitive=False)
        mapping_case_sensitive = Mapping(rules=[{"in": "A", "out": "b"}])
        transducer = Transducer(mapping)
        transducer_case_sensitive = Transducer(mapping_case_sensitive)
        self.assertEqual(transducer("a").output_string, "b")
        self.assertEqual(transducer_case_sensitive("a").output_string, "a")
        self.assertEqual(transducer("A").output_string, "b")

    def test_case_equivalencies(self):
        with self.assertRaises(exceptions.MalformedMapping):
            Mapping(rules=[{"in": "a", "out": "b"}], case_equivalencies={"a": "AA"})

    def test_escape_special(self):
        mapping = Mapping(rules=[{"in": r"\d", "out": "digit"}])
        mapping_escaped = Mapping(
            rules=[{"in": r"\d", "out": "b"}], escape_special=True
        )
        mapping_input_and_output_special_escaped = Mapping(
            rules=[{"in": "&", "out": "&"}], escape_special=True
        )
        mapping_specific_from_fpcc = Mapping(
            rules=[{"in": r"^", "out": "A"}, {"in": "o", "out": r"."}],
            rule_ordering="apply-longest-first",
            escape_special=True,
        )
        transducer = Transducer(mapping)
        transducer_escaped = Transducer(mapping_escaped)
        transducer_escaped_input_output = Transducer(
            mapping_input_and_output_special_escaped
        )
        transducer_fpcc = Transducer(mapping_specific_from_fpcc)
        self.assertEqual(transducer("1").output_string, "digit")
        self.assertEqual(transducer(r"\d").output_string, r"\d")
        self.assertEqual(transducer_escaped("1").output_string, "1")
        self.assertEqual(transducer_escaped(r"\d").output_string, "b")
        self.assertEqual(transducer_escaped_input_output("&").output_string, "&")
        self.assertEqual(transducer_fpcc("^o").output_string, "A.")

    def test_norm_form(self):
        mapping_nfc = Mapping(rules=[{"in": "a\u0301", "out": "a"}])  # Defaults to NFC
        mapping_nfd = Mapping(rules=[{"in": "a\u0301", "out": "a"}], norm_form="NFD")
        mapping_none = Mapping(rules=[{"in": "a\u0301", "out": "a"}], norm_form=False)

        transducer_nfc = Transducer(mapping_nfc)
        transducer_nfd = Transducer(mapping_nfd)
        transducer_none = Transducer(mapping_none)

        self.assertEqual(transducer_nfc("a\u0301").output_string, "a")
        self.assertEqual(transducer_nfc("\u00e1").output_string, "a")
        self.assertEqual(transducer_nfd("a\u0301").output_string, "a")
        self.assertEqual(transducer_nfd("\u00e1").output_string, "a")
        self.assertEqual(transducer_none("a\u0301").output_string, "a")
        self.assertEqual(transducer_none("\u00e1").output_string, "\u00e1")

    def test_reverse(self):
        mapping = Mapping(rules=[{"in": "a", "out": "b"}])
        mapping_reversed = Mapping(rules=[{"in": "a", "out": "b"}], reverse=True)
        transducer = Transducer(mapping)
        transducer_reversed = Transducer(mapping_reversed)
        self.assertEqual(transducer("a").output_string, "b")
        self.assertEqual(transducer("b").output_string, "b")
        self.assertEqual(transducer_reversed("a").output_string, "a")
        self.assertEqual(transducer_reversed("b").output_string, "a")

    def test_minimal(self):
        mapping = Mapping.load_mapping_from_path(
            os.path.join(
                os.path.dirname(public_data), "mappings", "minimal_config-g2p.yaml"
            )
        )
        transducer = Transducer(mapping)
        self.assertEqual(transducer("abb").output_string, "aaa")
        self.assertEqual(transducer("a").output_string, "a")
        self.assertFalse(
            mapping.rule_ordering == RULE_ORDERING_ENUM.apply_longest_first
        )
        self.assertFalse(mapping.case_sensitive)
        assert mapping.escape_special
        self.assertEqual(mapping.norm_form, NORM_FORM_ENUM.NFD)
        assert mapping.reverse

    def test_abbreviations(self):
        mapping = Mapping.load_mapping_from_path(
            os.path.join(
                os.path.dirname(public_data), "mappings", "abbreviation_config-g2p.yaml"
            )
        )
        self.assertEqual(mapping.rules[0].rule_input, "i|u")
        self.assertEqual(mapping.rules[1].rule_input, "a|e|i|o|u")
        transducer = Transducer(mapping)
        self.assertEqual(transducer("i").output_string, "1")
        self.assertEqual(transducer("e").output_string, "2")

    def test_rule_ordering_from_config(self):
        """
        Same as test_minimal, but uses "rule-ordering" instead of "as-is" in the config.
        """
        mapping = Mapping.load_mapping_from_path(
            os.path.join(os.path.dirname(public_data), "mappings", "rule-ordering.yaml")
        )
        transducer = Transducer(mapping)
        self.assertEqual(transducer("abb").output_string, "aaa")
        self.assertEqual(transducer("a").output_string, "a")
        assert mapping.rule_ordering == RULE_ORDERING_ENUM.apply_longest_first
        self.assertEqual(mapping.rule_ordering, RULE_ORDERING_ENUM.apply_longest_first)
        self.assertFalse(mapping.case_sensitive)
        assert mapping.escape_special
        self.assertEqual(mapping.norm_form, NORM_FORM_ENUM.NFD)
        assert mapping.reverse

    def test_null_input(self):
        with self.assertLogs(LOGGER, "WARNING"):
            Mapping(rules=[{"in": "", "out": "a"}])

    def test_no_escape(self):
        mapping = Mapping(
            rules_path=os.path.join(
                os.path.dirname(public_data), "mappings", "no_escape.csv"
            )
        )
        transducer = Transducer(mapping)
        self.assertEqual(transducer("?").output_string, "ʔ")

    def test_invalid_regex(self):
        rules = [{"in": "fo(o", "out": "bar"}]
        with self.assertLogs(LOGGER, level="ERROR"):
            with self.assertRaises(exceptions.MalformedMapping) as cm:
                _ = Mapping(rules=rules)
        assert "regex" in cm.exception.message

    def test_invalid_rules_json(self):
        rules = [{"in": "a"}, {"out": "c"}]
        with self.assertRaises(ValidationError):
            Mapping(rules=rules)

    def test_invalid_rules_csv(self):
        tf = NamedTemporaryFile(
            prefix="test_invalid_rules_", mode="w", suffix=".csv", delete=False
        )
        tf.write("good-in,good-out\n\ngood-in-no-out\n")
        tf.close()
        with self.assertRaises(exceptions.MalformedMapping):
            Mapping(rules_path=tf.name)
        os.unlink(tf.name)

    def test_invalid_rules_filetype(self):
        tf = NamedTemporaryFile(
            prefix="test_invalid_rules_", mode="w", suffix=".foo", delete=False
        )
        tf.write("good-in,good-out\n\ngood-in-no-out\n")
        tf.close()
        with self.assertRaises(exceptions.IncorrectFileType) as cm:
            Mapping(rules_path=tf.name)
        assert "not a valid mapping filetype" in str(cm.exception)
        os.unlink(tf.name)

    def test_extend_and_deduplicate(self):
        mapping1 = Mapping(rules=rules_from_strings("a:b", "c:d", "g:h"))
        mapping2 = Mapping(rules=rules_from_strings("a:x", "c:d", "e:f"))
        extend_ref = Mapping(
            rules=rules_from_strings("a:b", "c:d", "g:h", "a:x", "c:d", "e:f")
        )
        mapping1.extend(mapping2)
        self.assertEqual(mapping1.rules, extend_ref.rules)
        dedup_ref = Mapping(rules=rules_from_strings("a:b", "c:d", "g:h", "a:x", "e:f"))
        mapping1.deduplicate()
        self.assertEqual(mapping1.rules, dedup_ref.rules)

    def test_g2p_studio_csv(self):
        # Ensure that a single CSV file from Studio works properly
        with self.assertLogs(LOGGER, level="WARNING"):  # silence "" input warnings
            mapping = Mapping(
                rules_path=os.path.join(
                    os.path.dirname(public_data), "mappings", "g2p_studio.csv"
                )
            )
        transducer = Transducer(mapping)
        self.assertEqual(
            transducer("Jouni haluaa juoda kahvia").output_string,
            "Jouni hɑluɑː juodɑ kɑhviɑ",
        )
        # Concatenate them (this is not a good idea) and make sure it works anyway
        tf = NamedTemporaryFile(
            prefix="test_g2p_g2p_",
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf8",
        )
        with open(
            os.path.join(os.path.dirname(public_data), "mappings", "g2p_studio.csv"),
            encoding="utf8",
        ) as fh:
            tf.write(fh.read())
        # In fact you can't concatenate them anyway. They don't end in newline.
        tf.write("\n")
        with open(
            os.path.join(os.path.dirname(public_data), "mappings", "g2p_studio2.csv"),
            encoding="utf8",
        ) as fh:
            tf.write(fh.read())
        tf.close()
        with self.assertLogs(LOGGER, level="WARNING"):  # silence "" input warnings
            mapping = Mapping(rules_path=tf.name)
        transducer = Transducer(mapping)
        self.assertEqual(
            transducer("tee on herkullista").output_string, "teː on herkullistɑ"
        )
        os.unlink(tf.name)

    def test_no_reprocess(self):
        """Ensure that attempting to reprocess a mapping is an error."""
        with self.assertRaises(AssertionError):
            self.test_mapping_norm.process_model_specs()
        with self.assertRaises(ValidationError):
            _ = Mapping(
                rules=[{"in": "a", "out": "b", "match_pattern": re.compile("XOR OTA")}]
            )
        with self.assertRaises(ValidationError):
            _ = Mapping(
                rules=[
                    {
                        "in": "a",
                        "out": "b",
                        "intermediate_form": re.compile("HACKEM MUCHE"),
                    }
                ]
            )


if __name__ == "__main__":
    main([__file__, *sys.argv])
