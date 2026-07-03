#!/usr/bin/env python

import sys
from unittest import TestCase

from pytest import main

from g2p.mappings import Mapping, Rule
from g2p.mappings.create_fallback_mapping import align_to_dummy_fallback


class FallbackTest(TestCase):
    """Basic Mapping Fallback Test.
    This feature is experimental, but it will try to map each character
    in a Mapping to one of the following 'unmarked' phonemes:
        ["ɑ", "i", "u", "t", "s", "n"]
    If the mapping is 'ipa', it will align the inventories directly.
    If not, it will take a best guess at what the Unicode character using Unidecode and then align from there.
    """

    def setUp(self):
        pass

    def test_mapping(self):
        self.maxDiff = None
        mapping = Mapping(
            rules=[
                {"in": "a", "out": "æ"},
                {"in": "e", "out": "ɐ"},
                {"in": "i", "out": "ɑ̃"},
                {"in": "b", "out": "β"},
                {"in": "g", "out": "ɡ"},
                {"in": "g", "out": "g"},
                {"in": "i", "out": "ةُ"},
            ],
            in_lang="test",
            out_lang="test-out",
        )
        ipa_mapping = Mapping(
            rules=[
                {"in": "a", "out": "æ"},
                {"in": "e", "out": "ɐ"},
                {"in": "i", "out": "ɑ̃"},
                {"in": "b", "out": "β"},
                {"in": "g", "out": "ɡ"},
            ],
            in_lang="test",
            out_lang="test-ipa",
        )
        test_in = align_to_dummy_fallback(mapping)
        self.assertEqual(
            test_in.rules,
            [
                Rule(rule_input="a", rule_output="ɑ", match_pattern="a"),
                Rule(rule_input="e", rule_output="i", match_pattern="e"),
                Rule(rule_input="i", rule_output="i", match_pattern="i"),
                Rule(rule_input="b", rule_output="t", match_pattern="b"),
                Rule(rule_input="g", rule_output="t", match_pattern="g"),
                Rule(rule_input="g", rule_output="t", match_pattern="g"),
                Rule(rule_input="i", rule_output="i", match_pattern="i"),
            ],
        )

        test_out = align_to_dummy_fallback(mapping, "out")
        self.assertEqual(
            test_out.rules,
            [
                Rule(rule_input="æ", rule_output="ɑi", match_pattern="æ"),
                Rule(rule_input="ɐ", rule_output="ɑ", match_pattern="ɐ"),
                Rule(rule_input="ɑ̃", rule_output="ɑ", match_pattern="ɑ̃"),
                Rule(rule_input="β", rule_output="t", match_pattern="β"),
                Rule(rule_input="ɡ", rule_output="t", match_pattern="ɡ"),
                Rule(rule_input="g", rule_output="t", match_pattern="g"),
                Rule(rule_input="ةُ", rule_output="ɑu", match_pattern="ةُ"),
            ],
        )
        test_ipa = align_to_dummy_fallback(ipa_mapping, "out")
        panphon_021_ref = [
            Rule(rule_input="æ", rule_output="ɑ", match_pattern="æ"),
            Rule(rule_input="ɐ", rule_output="i", match_pattern="ɐ"),
            Rule(rule_input="ɑ̃", rule_output="ɑ", match_pattern="ɑ̃"),
            Rule(rule_input="β", rule_output="s", match_pattern="β"),
            Rule(rule_input="ɡ", rule_output="t", match_pattern="ɡ"),
        ]
        panphon_020_ref = [
            panphon_021_ref[0],
            Rule(rule_input="ɐ", rule_output="ɑ", match_pattern="ɐ"),
            *panphon_021_ref[2:],
        ]
        if test_ipa.rules != panphon_021_ref:
            assert test_ipa.rules == panphon_020_ref


if __name__ == "__main__":
    main([__file__, *sys.argv])
