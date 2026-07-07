#!/usr/bin/env python

"""
Test all Mappings
"""

import io
import sys
from contextlib import redirect_stderr
from unittest import TestCase

from pytest import main

from g2p.log import LOGGER
from g2p.mappings import Mapping
from g2p.mappings.create_ipa_mapping import (
    DISTANCE_METRICS,
    create_mapping,
    create_multi_mapping,
)
from g2p.transducer import Transducer


class MappingCreationTest(TestCase):
    def setUp(self):
        self.mappings = [
            {"in": "ɑ", "out": "AA"},
            {"in": "eː", "out": "EY"},
            {"in": "i", "out": "IY"},
            {"in": "u", "out": "UW"},
            {"in": "tʃ", "out": "CH"},
            {"in": "p", "out": "P"},
            {"in": "t", "out": "T"},
            {"in": "k", "out": "K"},
            {"in": "w", "out": "W"},
            {"in": "ɡ", "out": "G"},
            {"in": "ʒ", "out": "ZH"},
        ]
        self.mappings_xsampa = [
            {"in": "A", "out": "AA"},
            {"in": "e:", "out": "EY"},
            {"in": "i", "out": "IY"},
            {"in": "u", "out": "UW"},
            {"in": "tS", "out": "CH"},
            {"in": "p", "out": "P"},
            {"in": "t", "out": "T"},
            {"in": "k", "out": "K"},
            {"in": "w", "out": "W"},
            {"in": "g", "out": "G"},
            {"in": "Z", "out": "ZH"},
        ]
        self.target_mapping = Mapping(
            rules=self.mappings,
            in_lang="eng-ipa",
            out_lang="eng-arpabet",
            out_delimiter=" ",
        )
        self.target_mapping_xsampa = Mapping(
            rules=self.mappings_xsampa,
            in_lang="eng-xsampa",
            out_lang="eng-arpabet",
            out_delimiter=" ",
        )

    def test_unigram_mappings(self):
        src_mappings = [
            {"in": "ᐃ", "out": "i"},
            {"in": "ᐅ", "out": "u"},
            {"in": "ᐊ", "out": "a"},
        ]
        src_mapping = Mapping(rules=src_mappings, in_lang="crj", out_lang="crj-ipa")
        mapping = create_mapping(src_mapping, self.target_mapping)
        transducer = Transducer(mapping)
        assert transducer("a").output_string == "ɑ"
        assert transducer("i").output_string == "i"
        assert transducer("u").output_string == "u"

    def test_bigram_mappings(self):
        src_mappings = [
            {"in": "ᐱ", "out": "pi"},
            {"in": "ᑎ", "out": "ti"},
            {"in": "ᑭ", "out": "ki"},
        ]
        src_mapping = Mapping(rules=src_mappings, in_lang="crj", out_lang="crj-ipa")
        mapping = create_mapping(src_mapping, self.target_mapping)
        transducer = Transducer(mapping)
        assert transducer("pi").output_string == "pi"
        assert transducer("ti").output_string == "ti"
        assert transducer("ki").output_string == "ki"

    def test_trigram_mappings(self):
        src_mappings = [
            {"in": "ᒋ", "out": "t͡ʃi"},
            {"in": "ᒍ", "out": "t͡ʃu"},
            {"in": "ᒐ", "out": "t͡ʃa"},
        ]
        src_mapping = Mapping(rules=src_mappings, in_lang="crj", out_lang="crj-ipa")
        mapping = create_mapping(src_mapping, self.target_mapping)
        transducer = Transducer(mapping)
        assert transducer("t͡ʃi").output_string == "tʃi"
        assert transducer("t͡ʃu").output_string == "tʃu"
        assert transducer("t͡ʃa").output_string == "tʃɑ"

    def test_trigram_mappings_xsampa(self):
        src_mappings = [
            {"in": "ᒋ", "out": "tSi"},
            {"in": "ᒍ", "out": "tSu"},
            {"in": "ᒐ", "out": "tSa"},
        ]
        src_mapping = Mapping(rules=src_mappings, in_lang="crj", out_lang="crj-xsampa")
        mapping = create_mapping(src_mapping, self.target_mapping_xsampa)
        transducer = Transducer(mapping)
        assert transducer("tSi").output_string == "tSi"
        assert transducer("tSu").output_string == "tSu"
        assert transducer("tSa").output_string == "tSA"

    def test_long_mappings(self):
        src_mappings = [
            {"in": "ᐧᐯ", "out": "pʷeː"},
            {"in": "ᐧᑌ", "out": "tʷeː"},
            {"in": "ᐧᑫ", "out": "kʷeː"},
        ]
        src_mapping = Mapping(rules=src_mappings, in_lang="crj", out_lang="crj-ipa")
        mapping = create_mapping(src_mapping, self.target_mapping)
        transducer = Transducer(mapping)
        assert transducer("pʷeː").output_string == "pweː"
        assert transducer("tʷeː").output_string == "tweː"
        assert transducer("kʷeː").output_string == "kweː"

    def test_distance_errors(self):
        src_mappings = [{"in": "ᐃ", "out": "i"}]
        src_mapping = Mapping(rules=src_mappings, in_lang="crj", out_lang="crj-ipa")
        # Exercise looking up distances in the known list
        with self.assertRaises(ValueError):
            _ = create_mapping(
                src_mapping, self.target_mapping, distance="not_a_distance"
            )
        with self.assertRaises(ValueError):
            _ = create_multi_mapping(
                [(src_mapping, "out")],
                [(self.target_mapping, "in")],
                distance="not_a_distance",
            )
        # White box testing: monkey-patch an invalid distance to validate the
        # second way we make sure distances are supported
        DISTANCE_METRICS.append("not_a_real_distance")
        with self.assertRaises(ValueError), self.assertLogs(LOGGER, level="ERROR"):
            _ = create_mapping(
                src_mapping, self.target_mapping, distance="not_a_real_distance"
            )
        with self.assertRaises(ValueError), self.assertLogs(LOGGER, level="ERROR"):
            _ = create_multi_mapping(
                [(src_mapping, "out")],
                [(self.target_mapping, "in")],
                distance="not_a_real_distance",
            )
        DISTANCE_METRICS.pop()

    def test_distances(self):
        # These mapppings are chosen to create different generated mappings
        # from the various distances.
        src_mappings = [
            {"in": "ᐧᐯ", "out": "pʷeː"},
            {"in": "ᒋ", "out": "t͡ʃi"},
            {"in": "ᕃ", "out": "ʁaj"},
        ]
        src_mapping = Mapping(rules=src_mappings, in_lang="crj", out_lang="crj-ipa")
        mapping = create_mapping(src_mapping, self.target_mapping)
        # print("mapping", mapping, list(mapping), "distance", "default")
        assert isinstance(mapping, Mapping)
        set_of_mappings = {tuple(rule.rule_output for rule in mapping.rules)}
        for distance in DISTANCE_METRICS:
            mapping = create_mapping(
                src_mapping, self.target_mapping, distance=distance
            )
            # print("mapping", mapping, list(mapping), "distance", distance)
            assert isinstance(mapping, Mapping)
            set_of_mappings.add(tuple(rule.rule_output for rule in mapping.rules))

            mapping = create_multi_mapping(
                [(src_mapping, "out")], [(self.target_mapping, "in")], distance=distance
            )
            assert isinstance(mapping, Mapping)
            set_of_mappings.add(tuple(rule.rule_output for rule in mapping.rules))
        self.assertGreater(len(set_of_mappings), 3)

    def test_deletion_mapping(self):
        """Ensure that deletion rules do not lead to spurious warnings."""
        src_mappings = [
            {"in": "foo", "out": ""},
            {"in": "ᐃ", "out": "i"},
            {"in": "ᐅ", "out": "u"},
            {"in": "ᐊ", "out": "a"},
        ]
        src_mapping = Mapping(rules=src_mappings, in_lang="crj", out_lang="crj-ipa")
        log_output = io.StringIO()
        with redirect_stderr(log_output):
            mapping = create_mapping(src_mapping, self.target_mapping)
        assert "WARNING" not in log_output.getvalue()
        transducer = Transducer(mapping)
        assert transducer("a").output_string == "ɑ"
        assert transducer("i").output_string == "i"
        assert transducer("u").output_string == "u"


if __name__ == "__main__":
    main([__file__, *sys.argv])
