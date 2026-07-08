#!/usr/bin/env python

"""Test Mapping utility functions"""

import doctest
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from unittest import TestCase

import yaml
from pep440.core import is_canonical
from pytest import main

import g2p
import g2p.exceptions
from g2p import get_arpabet_langs
from g2p._version import VERSION, version_tuple
from g2p.log import LOGGER
from g2p.mappings import Mapping, utils
from g2p.mappings.utils import RULE_ORDERING_ENUM, Rule
from g2p.tests.public import PUBLIC_DIR


class UtilsTest(TestCase):
    def test_run_doctest(self):
        """Run doctests in g2p.mappings.utils"""
        results = doctest.testmod(utils)
        assert not results.failed, results

    def test_abb_expand(self):
        test_dict = defaultdict(list)
        bad_dict = defaultdict(list)
        test_dict["VOWELS"].extend(["HIGH_VOWELS", "e", "o"])
        test_dict["HIGH_VOWELS"].extend(["i", "u"])
        bad_dict["VOWELS"].extend(["HIGH_VOWELS", "e", "o"])
        bad_dict["HIGH_VOWELS"].extend(
            ["HIGH_VOWELS", "u"]
        )  # shouldn't allow self-referential abbreviations
        expanded_plain = utils.expand_abbreviations("test", test_dict)
        expanded_bad_plain = utils.expand_abbreviations("test", bad_dict)
        with self.assertRaises(g2p.exceptions.RecursionError) as cm:
            utils.expand_abbreviations("HIGH_VOWELS", bad_dict)
        assert "Too many levels of recursion" in str(cm.exception)
        expanded_non_recursive = utils.expand_abbreviations("HIGH_VOWELS", test_dict)
        expanded_recursive = utils.expand_abbreviations("VOWELS", test_dict)
        assert "test" == expanded_plain
        assert "test" == expanded_bad_plain
        assert "i|u" == expanded_non_recursive
        assert "i|u|e|o" == expanded_recursive

    def test_abb_flatten_and_expand_format(self):
        test_rows = [["VOWEL", "a", "e", "i", "o", "u"], ["OTHER", "t", "e", "s", "t"]]
        default_dict = defaultdict(list)
        default_dict["VOWEL"].extend(["a", "e", "i", "o", "u"])
        default_dict["OTHER"].extend(["t", "e", "s", "t"])
        empty_rows = [["", "", "", "", "", ""] for _ in range(10)]
        assert utils.flatten_abbreviations_format(test_rows) == default_dict
        assert utils.expand_abbreviations_format(default_dict) == test_rows
        assert utils.expand_abbreviations_format({}) == empty_rows

    def test_unicode_escape(self):
        """Should turn \u0331 declared in CSVs
        into actual Unicode string for that codepoint
        """
        assert "\u0000" == utils.unicode_escape("\\u0000")
        assert "\u0331" == utils.unicode_escape("\\u0331")
        assert "\u26f0" == utils.unicode_escape("\\u26F0")

    def test_fixed_width(self):
        test_dict = defaultdict(list)
        test_dict["VOWELS"].extend(["e", "o", "ee"])
        lookbehind_pattern = re.compile(r"\(\?\<\=[^)]*\)")
        patterns = [
            (utils.create_fixed_width_lookbehind("a|b"), 1),
            (utils.create_fixed_width_lookbehind("a|b|cc"), 2),
            (utils.create_fixed_width_lookbehind("a|'|b|cc|ddd|$"), 4),
            (utils.create_fixed_width_lookbehind("a|^|$"), 2),
            (utils.create_fixed_width_lookbehind("[abcd]"), 1),
            (utils.create_fixed_width_lookbehind(r"[x'kgh\.𝚐̲𝚔̲𝚡̲̲]"), 1),
            (
                utils.create_fixed_width_lookbehind(
                    utils.expand_abbreviations("VOWELS", test_dict)
                ),
                2,
            ),
            (
                utils.create_fixed_width_lookbehind(
                    utils.expand_abbreviations("(VOWELS|eee)", test_dict)
                ),
                3,
            ),
        ]
        for pattern in patterns:
            assert len(re.split(lookbehind_pattern, pattern[0])) - 1 == pattern[1]

    def test_load_mapping(self):
        with self.assertLogs(LOGGER, "WARNING"):
            Mapping.load_mapping_from_path(
                os.path.join(PUBLIC_DIR, "mappings", "malformed_config-g2p.yaml")
            )
        minimal = Mapping.load_mapping_from_path(
            os.path.join(PUBLIC_DIR, "mappings", "minimal_config-g2p.yaml")
        )
        csv = Mapping.load_mapping_from_path(
            os.path.join(PUBLIC_DIR, "mappings", "minimal_configs.yaml"), 0
        )
        tsv = Mapping.load_mapping_from_path(
            os.path.join(PUBLIC_DIR, "mappings", "minimal_configs.yaml"), 1
        )
        psv = Mapping.load_mapping_from_path(
            os.path.join(PUBLIC_DIR, "mappings", "minimal_configs.yaml"), 2
        )
        json = Mapping.load_mapping_from_path(
            os.path.join(PUBLIC_DIR, "mappings", "minimal_configs.yaml"), 3
        )
        xlsx = Mapping.load_mapping_from_path(
            os.path.join(PUBLIC_DIR, "mappings", "minimal_configs.yaml"), 4
        )
        assert minimal.rules == csv.rules
        assert minimal.rules == tsv.rules
        assert minimal.rules == psv.rules
        assert minimal.rules == json.rules
        assert minimal.rules == xlsx.rules

    def test_escape_special(self):
        assert (
            utils.escape_special_characters(
                Rule(rule_input="?", rule_output="")
            ).rule_input
            == "\\?"
        )

    def test_load_abbs(self):
        with self.assertRaises(g2p.exceptions.IncorrectFileType):
            utils.load_abbreviations_from_file(
                os.path.join(PUBLIC_DIR, "mappings", "abbreviations.json")
            )
        for abb in ["abbreviations.csv", "abbreviations.tsv", "abbreviations.psv"]:
            abbs = utils.load_abbreviations_from_file(
                os.path.join(PUBLIC_DIR, "mappings", abb)
            )
            assert "VOWEL" in abbs
            assert abbs["VOWEL"] == ["a", "e", "i", "o", "u"]

    def test_generated_mapping(self):
        try:
            # config = utils.generate_config('test', 'test-out', 'Test', 'TestOut')
            mapping = Mapping(
                in_lang="test",
                out_lang="test-out",
                rule_ordering=RULE_ORDERING_ENUM.apply_longest_first,
                rules=[Rule(rule_input="a", rule_output="b")],
            )
            with self.assertLogs(LOGGER, level="WARNING"):
                mapping.config_to_file(
                    os.path.join(PUBLIC_DIR, "mappings", "test_config-g2p.yaml")
                )
            with self.assertLogs(LOGGER, level="WARNING"):
                mapping.config_to_file(
                    os.path.join(PUBLIC_DIR, "mappings", "generated_add.yaml")
                )
            mapping.mapping_to_file(os.path.join(PUBLIC_DIR, "mappings"))
            test_config = Mapping.load_mapping_from_path(
                os.path.join(PUBLIC_DIR, "mappings", "test_config-g2p.yaml")
            )

            test_config_added = Mapping.load_mapping_from_path(
                os.path.join(PUBLIC_DIR, "mappings", "generated_add.yaml")
            )
            assert (
                test_config.rules[0].export_to_dict()
                == Rule(
                    **{"in": "a", "out": "b", "context_before": "", "context_after": ""}
                ).export_to_dict()
            )
            assert test_config.in_lang == "test"
            assert test_config.out_lang == "test-out"
            assert test_config.language_name == "test"
            assert test_config.display_name == "test custom to test-out custom"
            assert test_config_added.rules[0].export_to_dict() == {
                "in": "a",
                "out": "b",
            }
            assert test_config_added.in_lang == "test"
            assert test_config_added.out_lang == "test-out"
            assert test_config_added.language_name == "test"
            assert test_config_added.display_name == "test custom to test-out custom"
        finally:
            gen_mapping = os.path.join(PUBLIC_DIR, "mappings", "test_to_test-out.json")
            gen_config = os.path.join(PUBLIC_DIR, "mappings", "test_config-g2p.yaml")
            if os.path.exists(gen_config):
                os.remove(gen_config)
            if os.path.exists(gen_mapping):
                os.remove(gen_mapping)
            fresh_config = {"language_name": "generated", "mappings": []}
            with open(
                os.path.join(PUBLIC_DIR, "mappings", "generated_add.yaml"),
                "w",
                encoding="utf8",
            ) as f:
                yaml.dump(
                    fresh_config, f, Dumper=utils.IndentDumper, default_flow_style=False
                )

    def test_bad_normalization(self):
        with self.assertRaises(g2p.exceptions.InvalidNormalization):
            utils.normalize_with_indices("test", "bad")

    def test_normalize_to_NFD_with_indices(self):
        # Useful site to get combining character code points:
        # http://www.alanwood.net/unicode/combining_diacritical_marks.html
        e_acute_nfd = "e\u0301"
        assert utils.normalize_with_indices("é", "NFD") == (
            e_acute_nfd,
            [(0, 0), (0, 1)],
        )
        o_graveabove_nfd = "o\u0300"
        assert utils.normalize_with_indices("ò", "NFD") == (
            o_graveabove_nfd,
            [(0, 0), (0, 1)],
        )
        # TODO: this test case really should have indices (0,0),(0,2), (1,1)
        o_graveabove_acutebelow_mixed = "ò\u0317"  # 'ò̗'
        o_graveabove_acutebelow_nfd = "o\u0317\u0300"  # 'ò̗'
        assert utils.normalize_with_indices(o_graveabove_acutebelow_mixed, "NFD") == (
            o_graveabove_acutebelow_nfd,
            [(0, 0), (0, 2), (1, 1)],
        )
        o_graveabove_acutebelow_disordered = "o\u0300\u0317"
        assert utils.normalize_with_indices(
            o_graveabove_acutebelow_disordered, "NFD"
        ) == (o_graveabove_acutebelow_nfd, [(0, 0), (1, 2), (2, 1)])
        # From https://en.wikipedia.org/wiki/Precomposed_character:
        # "\u1e53" (ṓ) == "\u014d\u0301" (ṓ) == "\u006f\u0304\u0301" (ṓ)
        assert utils.normalize_with_indices("\u1e53", "NFD") == (
            "\u006f\u0304\u0301",
            [(0, 0), (0, 1), (0, 2)],
        )
        assert utils.normalize_with_indices("\u014d\u0301", "NFD") == (
            "\u006f\u0304\u0301",
            [(0, 0), (0, 1), (1, 2)],
        )
        assert utils.normalize_with_indices("'שָׂ'", "NFD") == (
            "'שָׂ'",
            [(0, 0), (1, 1), (2, 3), (3, 2), (4, 4)],
        )

    def test_compose_indices(self):
        assert utils.compose_indices(
            [(0, 1), (1, 4)], [(0, 0), (1, 2), (1, 3), (4, 2)]
        ) == [(0, 2), (0, 3), (1, 2)]
        assert utils.compose_indices(
            [(0, 0), (0, 1), (1, 2)], [(0, 3), (1, 3), (2, 3)]
        ) == [(0, 3), (1, 3)]
        assert utils.compose_indices([(0, 1), (1, 2)], [(1, 4), (3, 1)]) == [(0, 4)]

    def test_normalize_to_NFC_with_indices(self):
        assert utils.normalize_with_indices("e\u0301", "NFC") == ("é", [(0, 0), (1, 0)])
        assert utils.normalize_with_indices("ò\u0317", "NFC") == ("ò̗", [(0, 0), (1, 1)])
        assert utils.normalize_with_indices("\u014d\u0301", "NFC") == (
            "\u1e53",
            [(0, 0), (1, 0)],
        )
        assert utils.normalize_with_indices("o\u0304\u0301", "NFC") == (
            "\u1e53",
            [(0, 0), (1, 0), (2, 0)],
        )
        assert utils.normalize_with_indices("\u014d\u0301", "none") == (
            "\u014d\u0301",
            [(0, 0), (1, 1)],
        )
        assert utils.normalize_with_indices("o\u0300\u0317", "NFC") == (
            "\u00f2\u0317",
            [(0, 0), (1, 0), (2, 1)],
        )

    def test_normalize_to_NFK_with_indices(self):
        e_acute_nfd = "e\u0301"
        assert utils.normalize_with_indices(e_acute_nfd, "NFKC") == (
            "é",
            [(0, 0), (1, 0)],
        )
        assert utils.normalize_with_indices("é", "NFKD") == (
            e_acute_nfd,
            [(0, 0), (0, 1)],
        )

    def test_get_arpabet_langs(self):
        LANGS, LANG_NAMES = get_arpabet_langs()
        assert LANGS == sorted(LANGS)
        assert list(LANG_NAMES.keys()) == sorted(LANG_NAMES.keys())
        assert LANGS == list(LANG_NAMES.keys())
        assert "kwk-umista" in LANG_NAMES
        assert "str" in LANG_NAMES
        self.assertGreater(len(LANGS), 40)
        LANGS2, LANG_NAMES2 = get_arpabet_langs()
        self.assertIs(LANGS2, LANGS)
        self.assertIs(LANG_NAMES2, LANG_NAMES)

    def test_version_is_pep440_compliant(self):
        """We test for almost PEP 440 compliance: hatch adds +local_sha1, which is not compliant."""
        main_version, _, _ = VERSION.partition("+")
        assert is_canonical(main_version)

    def test_scm_pretend_version_is_up_to_date(self):
        """.SETUPTOOLS_SCM_PRETEND_VERSION is set to the version in pyproject.toml"""
        filename = Path(g2p.__file__).parent.parent / ".SETUPTOOLS_SCM_PRETEND_VERSION"
        try:
            with open(filename) as f:
                pretend_version = f.read().strip()
            (major, minor, *_rest) = version_tuple
            major_minor = f"{major}.{minor}"
            assert (
                major_minor == pretend_version
            ), "Mismatch between .SETUPTOOLS_SCM_PRETEND_VERSION and the version setuptools_scm determined dynamically. Try: 1) fetch recent tags from GitHub, 2) rerun \"pip install -e .\", 3) if you're working on the next major or minor release, update .SETUPTOOLS_SCM_PRETEND_VERSION to match the dynamic version's major.minor."
        except FileNotFoundError:
            # This is fine, it's only used in development
            pass

    def test_token_class(self):
        from g2p.shared_types import Token

        t1 = Token("test", True)
        t2 = Token(":", False)

        # Current and deprecated usages
        for t in t1, t2:
            with self.assertWarns(DeprecationWarning):
                assert t.text == t["text"]
            with self.assertWarns(DeprecationWarning):
                assert t.is_word == t["is_word"]
        # new way to set
        t1.text = "test2"
        t1.is_word = False
        assert t1.text == "test2"
        assert not t1.is_word
        # deprecated way to set
        with self.assertWarns(DeprecationWarning):
            t1["text"] = "test3"
        with self.assertWarns(DeprecationWarning):
            t1["is_word"] = True
        assert t1.text == "test3"
        assert t1.is_word

        with self.assertRaises(KeyError):
            with self.assertWarns(DeprecationWarning):
                t1["bad_key"] = "test"
        with self.assertRaises(KeyError):
            with self.assertWarns(DeprecationWarning):
                _ = t2["bad_key"]


if __name__ == "__main__":
    main([__file__, *sys.argv])
