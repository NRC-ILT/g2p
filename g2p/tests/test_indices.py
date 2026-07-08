#!/usr/bin/env python

"""
    Unittests for index preservation
"""

import sys
from unicodedata import normalize

from pytest import fixture, main

from g2p.log import LOGGER
from g2p.mappings import Mapping
from g2p.transducer import Transducer


class TestIndices:
    """Basic Transducer Test
    Preserve character-level mappings:

    Test Case #1
        # Simple conversion

        0 1 2 3
        t e s t

        p e s t
        0 1 2 3

        [ ((0, 't'), (0, 'p')),
          ((1, 'e'), (1, 'e')),
          ((2, 's'), (2, 's')),
          ((3, 't'), (3, 't')) ]

    Test Case #2:
        # Allow for deletion of segments

        0 1 2 3
        t e s t

        t s t
        0 1 2

        [ ((0, 't'), (0, 't')),
          ((1, 'e'), (1, '')),
          ((2, 's'), (2, 's')),
          ((3, 't'), (3, 't')) ]

    Test Case #3
        # Allow for one-to-many

        0 1 2 3
        t e s t

        c h e s t
        0 1 2 3 4

        [ ((0, 't'), (0, 'c')),
          ((0, 't'), (1, 'h')),
          ((1, 'e'), (2, 'e')),
          ((2, 's'), (3, 's')),
          ((3, 't'), (4, 't')) ]

    Test Case #4
        # Allow for many-to-one

        0 1 2 3
        t e s t

        p s t
        0 1 2

        [ ((0, 't'), (0, 'p')),
          ((1, 'e'), (0, 'p')),
          ((2, 's'), (1, 's')),
          ((3, 't'), (2, 't')) ]

    Test Case #5
        # Allow for epenthesis
         0 1 2 3
         t e s t

         t e s t y
         0 1 2 3 4

        [ ((-1, 'y'), (4, 'y')),
          ((0, 't'), (0, 't')),
          ((1, 'e'), (1, 'e')),
          ((2, 's'), (2, 's')),
          ((3, 't'), (3, 't')) ]

     Test Case #6
        # Allow metathesis
         0 1 2 3
         t e s t

         t s e t
         0 1 2 3

        [ ((0, 't'), (0, 't')),
          ((1, 'e'), (2, 'e')),
          ((2, 's'), (1, 's')),
          ((3, 't'), (3, 't')) ]

    Test Case #7
        # Allow order-sensitive operations
        0 1 2 3
        t e s t

        t e s h t
        0 1 2 3 4

        t e s t
        0 1 2 3

        AS IS

        [ ((0, 't'), (0, 't')),
          ((1, 'e'), (1, 'e')),
          ((2, 's'), (2, 's')),
          ((3, 't'), (3, 't')) ]

          or not

        [ ((0, 't'), (0, 't')),
          ((1, 'e'), (1, 'e')),
          ((2, 's'), (2, 's')),
          ((2, 's'), (3, 'h')),
          ((3, 't'), (4, 't')) ]

    Test Case #8
        # Allow multiple processes which alter the indices
        0 1 2 3
        t e s t

        c h e s t
        0 1 2 3 4

        c h e s s
        0 1 2 3 4

        [ ((0, 't'), (0, 'c')),
          ((1, 'e'), (1, 'h')),
          ((1, 'e'), (2, 'e')),
          ((2, 's'), (3, 's')),
          ((3, 't'), (4, 's')) ]

    Test Case # 9
        # Allow multiple character deletion
        0 1
        a a

        None None

        [ ((0, 'a'), (None, '')),
          ((1, 'a'), (None, '')) ]

    Test Case # 10
        # Another deletion test
        0 1 2
        a b c

        a
        0

        [ ((0, 'a'), (0, 'a')),
          ((1, 'b'), (0, '')),
          ((1, 'c'), (0, '')) ]

    Test case # 11
        # Sort of an insertion test (empty inputs are not allowed)

    Test case # 12
        # Verify that empty inputs are not allowed
    """

    @fixture(autouse=True)
    def setup(self):
        self.test_mapping_one = Mapping(
            rules=[{"in": "t", "out": "p", "context_after": "e"}]
        )
        self.test_mapping_two = Mapping(rules=[{"in": "e", "out": ""}])
        self.test_mapping_three = Mapping(
            rules=[{"in": "t", "out": "ch", "context_after": "e"}]
        )
        self.test_mapping_four = Mapping(rules=[{"in": "te", "out": "p"}])
        self.test_mapping_five = Mapping(
            rules=[{"context_before": "t", "context_after": "$", "in": "", "out": "y"}]
        )
        self.test_mapping_six = Mapping(rules=[{"in": "e{1}s{2}", "out": "s{2}e{1}"}])
        self.test_mapping_seven = Mapping(
            rules=[{"in": "s", "out": "sh"}, {"in": "sh", "out": "s"}],
            rule_ordering="apply-longest-first",
        )
        self.test_mapping_seven_as_written = Mapping(
            rules=[{"in": "s", "out": "sh"}, {"in": "sh", "out": "s"}]
        )
        self.test_mapping_eight = Mapping(
            rules=[{"in": "te", "out": "che"}, {"in": "t", "out": "s"}]
        )
        self.test_mapping_nine = Mapping(rules=[{"in": "aa", "out": ""}])
        self.test_mapping_ten = Mapping(rules=[{"in": "abc", "out": "a"}])
        self.test_mapping_eleven = Mapping(rules=[{"in": "a", "out": "aaaa"}])
        self.test_mapping_combining = Mapping(
            rules=[{"in": "k{1}\u0313{2}", "out": "'{2}k{1}"}]
        )
        self.test_mapping_wacky = Mapping(
            rules=[
                {
                    "in": "\U0001f600{1}\U0001f603\U0001f604{2}\U0001f604{3}",
                    "out": "\U0001f604\U0001f604\U0001f604{2}\U0001f604{3}\U0001f604{1}",
                }
            ]
        )
        self.test_mapping_wacky_lite = Mapping(
            rules=[{"in": "a{1}bc{2}c{3}", "out": "ccc{2}c{3}c{1}"}]
        )
        self.test_mapping_circum = Mapping(
            rules=[{"in": "a{1}c{2}", "out": "c{2}a{1}c{2}"}]
        )
        self.test_mapping_explicit_equal_1 = Mapping(
            rules=[{"in": "a{1}b{1}", "out": "c{1}d{1}"}]
        )
        self.test_mapping_explicit_equal_2 = Mapping(
            rules=[{"in": "ab{1}", "out": "cd{1}"}]
        )
        self.test_mapping_explicit_equal_3 = Mapping(rules=[{"in": "ab", "out": "cd"}])
        self.test_mapping_explicit_equal_4 = Mapping(
            rules=[{"in": "a{1}b{2}", "out": "c{1}d{2}"}]
        )
        self.test_issue_173_1 = Mapping(
            rules=[
                {"in": "x{1}y{2}z{3}", "out": "a{2}b{1}"},
                {"in": "d{1}e{2}f{3}", "out": "d{1}e{2}f{3}"},
            ]
        )
        self.test_issue_173_2 = Mapping(
            rules=[
                {"in": "x{1}y{2}z{3}", "out": "a{1}b{2}"},
                {"in": "d{1}e{2}f{3}", "out": "d{1}e{2}f{3}"},
            ]
        )
        self.test_issue_157_mapping = Mapping(
            rules=[
                {"in": "a", "out": "d"},
                {"in": "bc", "out": "e"},
                {"in": "g{1}h{2}i{3}", "out": "G{2}H{1}I{3}J{1}"},
                {"in": "m{1}n{2}", "out": "N{2}M{1}"},
            ]
        )
        self.test_feeding_mapping_1 = Mapping(
            rules=[{"in": "ab", "out": "a"}, {"in": "a", "out": "cd"}]
        )
        self.test_feeding_mapping_2 = Mapping(
            rules=[{"in": "a", "out": "cd"}, {"in": "cd", "out": "b"}]
        )
        self.test_issue_173_3 = Mapping(rules=[{"in": "ab{1}c{2}", "out": "X{1}Y{2}"}])
        self.test_issue_173_4 = Mapping(rules=[{"in": "a{1}bc{2}", "out": "xy{1}z{2}"}])
        self.trans_one = Transducer(self.test_mapping_one)
        self.trans_two = Transducer(self.test_mapping_two)
        self.trans_three = Transducer(self.test_mapping_three)
        self.trans_four = Transducer(self.test_mapping_four)
        self.trans_six = Transducer(self.test_mapping_six)
        self.trans_seven = Transducer(self.test_mapping_seven)
        self.test_seven_as_written = Transducer(self.test_mapping_seven_as_written)
        self.trans_eight = Transducer(self.test_mapping_eight)
        self.trans_nine = Transducer(self.test_mapping_nine)
        self.trans_ten = Transducer(self.test_mapping_ten)
        self.trans_eleven = Transducer(self.test_mapping_eleven)
        self.trans_combining = Transducer(self.test_mapping_combining)
        self.trans_wacky = Transducer(self.test_mapping_wacky)
        self.trans_wacky_lite = Transducer(self.test_mapping_wacky_lite)
        self.trans_circum = Transducer(self.test_mapping_circum)
        self.trans_explicit_equal_1 = Transducer(self.test_mapping_explicit_equal_1)
        self.trans_explicit_equal_2 = Transducer(self.test_mapping_explicit_equal_2)
        self.trans_explicit_equal_3 = Transducer(self.test_mapping_explicit_equal_3)
        self.trans_explicit_equal_4 = Transducer(self.test_mapping_explicit_equal_4)
        self.trans_173_1 = Transducer(self.test_issue_173_1)
        self.trans_173_2 = Transducer(self.test_issue_173_2)
        self.trans_173_3 = Transducer(self.test_issue_173_3)
        self.trans_173_4 = Transducer(self.test_issue_173_4)
        self.trans_157 = Transducer(self.test_issue_157_mapping)
        self.trans_feeding_1 = Transducer(self.test_feeding_mapping_1)
        self.trans_feeding_2 = Transducer(self.test_feeding_mapping_2)

    def test_feeding(self):
        """Test feeding"""
        transducer_1 = self.trans_feeding_1("ab")
        assert transducer_1.output_string == "cd"
        assert transducer_1.edges == [(0, 0), (0, 1), (1, 0), (1, 1)]
        # because of "crossed" indices, we get one single monotonic alignment
        assert transducer_1.substring_alignments() == [("ab", "cd")]
        transducer_2 = self.trans_feeding_2("a")
        assert transducer_2.output_string == "b"
        assert transducer_2.edges == [(0, 0)]
        assert transducer_2.substring_alignments() == [("a", "b")]

    def test_issue_157(self):
        """Test explicit problem from Issue 157"""
        transducer = self.trans_157("abcmn")
        assert transducer.output_string == "deNM"
        assert transducer.edges == [(0, 0), (1, 1), (2, 1), (3, 3), (4, 2)]
        assert transducer.substring_alignments() == [
            ("a", "d"),
            ("bc", "e"),
            ("mn", "NM"),
        ]

    def test_issue_173(self):
        """Test explicit problems from Issue 173"""
        transducer_1 = self.trans_173_1("xyzmndef")
        transducer_2 = self.trans_173_2("xyzmndef")
        transducer_3 = self.trans_173_3("abc")
        transducer_4 = self.trans_173_4("abc")
        assert transducer_1.output_string == "abmndef"
        assert transducer_2.output_string == "abmndef"
        assert transducer_3.output_string == "XY"
        assert transducer_4.output_string == "xyz"
        assert transducer_1.edges == [
            (0, 1),
            (1, 0),
            (2, 0),
            (3, 2),
            (4, 3),
            (5, 4),
            (6, 5),
            (7, 6),
        ]
        assert transducer_1.substring_alignments() == [
            ("xyz", "ab"),
            ("m", "m"),
            ("n", "n"),
            ("d", "d"),
            ("e", "e"),
            ("f", "f"),
        ]
        assert transducer_2.edges == [
            (0, 0),
            (1, 1),
            (2, 1),
            (3, 2),
            (4, 3),
            (5, 4),
            (6, 5),
            (7, 6),
        ]
        assert transducer_2.substring_alignments() == [
            ("x", "a"),
            ("yz", "b"),
            ("m", "m"),
            ("n", "n"),
            ("d", "d"),
            ("e", "e"),
            ("f", "f"),
        ]
        assert transducer_3.edges == [(0, 0), (1, 0), (2, 1)]
        assert transducer_3.substring_alignments() == [("ab", "X"), ("c", "Y")]
        assert transducer_4.edges == [(0, 0), (0, 1), (1, 2), (2, 2)]
        assert transducer_4.substring_alignments() == [("a", "xy"), ("bc", "z")]

    def test_explicit_equal(self):
        """Test synonymous syntax for explicit indices"""
        explicit_1 = self.trans_explicit_equal_1("ab")
        explicit_2 = self.trans_explicit_equal_2("ab")
        explicit_3 = self.trans_explicit_equal_4("ab")
        implicit = self.trans_explicit_equal_3("ab")
        assert explicit_1.output_string == "cd"
        assert explicit_2.output_string == "cd"
        assert implicit.output_string == "cd"
        assert explicit_3.output_string == "cd"
        assert explicit_1.edges == [(0, 0), (1, 1)]
        assert explicit_2.edges == [(0, 0), (1, 1)]
        assert implicit.edges == [(0, 0), (1, 1)]
        assert explicit_3.edges == [(0, 0), (1, 1)]

    def test_no_indices(self):
        """Test straightforward conversion without returning indices."""
        transducer = self.trans_combining("k\u0313am")
        assert transducer.output_string == "'kam"

    def test_combining(self):
        """Test index preserving combining characters"""
        transducer = self.trans_combining("k\u0313am")
        assert transducer.output_string == "'kam"
        assert transducer.edges == [(0, 1), (1, 0), (2, 2), (3, 3)]

    def test_wacky(self):
        """Test weird Unicode emoji transformation..."""
        transducer_lite = self.trans_wacky_lite("abcc")
        transducer_lite_extra = self.trans_wacky_lite("abcca")
        assert transducer_lite.output_string == "ccccc"
        assert transducer_lite_extra.output_string == "ccccca"
        assert transducer_lite.edges == [(0, 4), (1, 0), (2, 1), (2, 2), (3, 3)]
        assert transducer_lite.substring_alignments() == [("abcc", "ccccc")]
        assert transducer_lite_extra.edges == [
            (0, 4),
            (1, 0),
            (2, 1),
            (2, 2),
            (3, 3),
            (4, 5),
        ]
        assert transducer_lite_extra.substring_alignments() == [
            ("abcc", "ccccc"),
            ("a", "a"),
        ]
        transducer_no_i = self.trans_wacky("\U0001f600\U0001f603\U0001f604\U0001f604")
        assert (
            transducer_no_i.output_string
            == "\U0001f604\U0001f604\U0001f604\U0001f604\U0001f604"
        )
        transducer = self.trans_wacky("\U0001f600\U0001f603\U0001f604\U0001f604")
        assert (
            transducer.output_string
            == "\U0001f604\U0001f604\U0001f604\U0001f604\U0001f604"
        )
        assert transducer.edges == [(0, 4), (1, 0), (2, 1), (2, 2), (3, 3)]
        assert transducer.substring_alignments() == [
            (
                "\U0001f600\U0001f603\U0001f604\U0001f604",
                "\U0001f604\U0001f604\U0001f604\U0001f604\U0001f604",
            )
        ]

    def test_circum(self):
        """Test circumfixing"""
        transducer = self.trans_circum("ac")
        assert transducer.output_string == "cac"
        assert transducer.edges == [(0, 1), (1, 0), (1, 2)]
        assert transducer.substring_alignments() == [("ac", "cac")]

    def test_case_one(self):
        """Test case one"""
        transducer = self.trans_one("test")
        assert transducer.output_string == "pest"
        assert transducer.edges == [(0, 0), (1, 1), (2, 2), (3, 3)]
        assert transducer.substring_alignments() == [
            ("t", "p"),
            ("e", "e"),
            ("s", "s"),
            ("t", "t"),
        ]
        transducer = self.trans_one("")
        assert transducer.output_string == ""
        assert transducer.edges == []
        assert transducer.substring_alignments() == []

    def test_case_two(self):
        transducer = self.trans_two("test")
        assert transducer.output_string == "tst"
        assert transducer.edges == [(0, 0), (1, 0), (2, 1), (3, 2)]
        assert transducer.substring_alignments() == [
            ("te", "t"),
            ("s", "s"),
            ("t", "t"),
        ]

    def test_case_three(self):
        transducer = self.trans_three("test")
        assert transducer.output_string == "chest"
        assert transducer.edges == [(0, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
        assert transducer.substring_alignments() == [
            ("t", "ch"),
            ("e", "e"),
            ("s", "s"),
            ("t", "t"),
        ]

    def test_case_four(self):
        transducer = self.trans_four("test")
        assert transducer.output_string == "pst"
        assert transducer.edges == [(0, 0), (1, 0), (2, 1), (3, 2)]
        assert transducer.substring_alignments() == [
            ("te", "p"),
            ("s", "s"),
            ("t", "t"),
        ]

    def test_case_six(self):
        transducer = self.trans_six("test")
        assert transducer.output_string == "tset"
        assert transducer.edges == [(0, 0), (1, 2), (2, 1), (3, 3)]
        assert transducer.substring_alignments() == [
            ("t", "t"),
            ("es", "se"),
            ("t", "t"),
        ]

    def test_case_long_six(self):
        transducer = self.trans_six("esesse")
        assert transducer.output_string == "sesese"
        # Ensure that *minimal* monotonic segments are output
        assert transducer.substring_alignments() == [
            ("es", "se"),
            ("es", "se"),
            ("s", "s"),
            ("e", "e"),
        ]

    def test_case_seven(self):
        transducer_as_written = self.test_seven_as_written("test")
        assert transducer_as_written.output_string == "test"
        assert transducer_as_written.edges == [(0, 0), (1, 1), (2, 2), (3, 3)]
        assert transducer_as_written.substring_alignments() == [
            ("t", "t"),
            ("e", "e"),
            ("s", "s"),
            ("t", "t"),
        ]
        transducer = self.trans_seven("test")
        assert transducer.output_string == "tesht"
        assert transducer.edges == [(0, 0), (1, 1), (2, 2), (2, 3), (3, 4)]
        assert transducer.substring_alignments() == [
            ("t", "t"),
            ("e", "e"),
            ("s", "sh"),
            ("t", "t"),
        ]

    def test_case_eight(self):
        transducer = self.trans_eight("test")
        assert transducer.output_string == "chess"
        assert transducer.edges == [(0, 0), (1, 1), (1, 2), (2, 3), (3, 4)]
        assert transducer.substring_alignments() == [
            ("t", "c"),
            ("e", "he"),
            ("s", "s"),
            ("t", "s"),
        ]

    def test_case_nine(self):
        transducer = self.trans_nine("aa")
        assert transducer.output_string == ""
        assert transducer.edges == [(0, None), (1, None)]
        # Support deletions in substring_alignments
        assert transducer.substring_alignments() == [("aa", "")]
        transducer = self.trans_nine("aabbaab")
        assert transducer.output_string == "bbb"
        assert transducer.edges == [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 1),
            (4, 1),
            (5, 1),
            (6, 2),
        ]
        # Support deletions in substring_alignments.  NOTE: these
        # alignments are quite bogus due to the ad-hoc treatment of
        # deletions by rule-based mappings
        assert transducer.substring_alignments() == [
            ("aab", "b"),
            ("baa", "b"),
            ("b", "b"),
        ]

    def test_case_ten(self):
        transducer = self.trans_ten("abc")
        assert transducer.output_string == "a"
        assert transducer.edges == [(0, 0), (1, 0), (2, 0)]
        assert transducer.substring_alignments() == [("abc", "a")]

    def test_case_eleven(self):
        transducer = self.trans_eleven("a")
        assert transducer.output_string == "aaaa"
        assert transducer.edges == [(0, 0), (0, 1), (0, 2), (0, 3)]
        assert transducer.substring_alignments() == [("a", "aaaa")]

    def test_case_twelve(self, caplog):
        # Empty inputs are not allowed (should it actually throw an exception?)
        with caplog.at_level("WARNING", logger=LOGGER.name):
            self.test_mapping_twelve = Mapping(
                rules=[{"in": "", "out": "aa", "context_before": "b"}]
            )
            self.trans_twelve = Transducer(self.test_mapping_twelve)
            transducer = self.trans_twelve("b")
        assert (
            "disallowed" in caplog.text
        ), "it should warn that empty inputs are disallowed"
        assert transducer.output_string == "b"

    def test_case_acdc(self):
        transducer = Transducer(
            Mapping(rules=[{"in": "a{1}c{2}", "out": "c{2}a{1}c{2}"}])
        )
        tg = transducer("acdc")
        assert tg.output_string == "cacdc"
        assert tg.edges == [(0, 1), (1, 0), (1, 2), (2, 3), (3, 4)]
        assert tg.substring_alignments() == [("ac", "cac"), ("d", "d"), ("c", "c")]

    def test_case_acac(self):
        transducer = Transducer(Mapping(rules=[{"in": "ab{1}c{2}", "out": "ab{2}"}]))
        transducer_default = Transducer(
            Mapping(rules=[{"in": "ab", "out": ""}, {"in": "c", "out": "ab"}])
        )
        tg = transducer("abcabc")
        assert tg.output_string == "abab"
        assert tg.edges == [
            (0, 0),
            (1, 0),
            (2, 0),
            (2, 1),
            (3, 1),
            (4, 1),
            (5, 2),
            (5, 3),
        ]
        assert tg.substring_alignments() == [("abcab", "ab"), ("c", "ab")]
        tg_default = transducer_default("abcabc")
        assert tg_default.output_string == "abab"
        assert tg_default.edges == [
            (0, 0),
            (1, 0),
            (2, 0),
            (2, 1),
            (3, 1),
            (4, 1),
            (5, 2),
            (5, 3),
        ]
        assert tg_default.substring_alignments() == [("abcab", "ab"), ("c", "ab")]

    def test_arpabet(self):
        transducer = Transducer(
            Mapping(
                rules=[{"in": "ĩ", "out": "IY N"}], norm_form="NFC", out_delimiter=" "
            )
        )
        transducer_nfd = Transducer(
            Mapping(
                rules=[{"in": "ĩ", "out": "IY N"}], norm_form="NFD", out_delimiter=" "
            )
        )
        tg = transducer(normalize("NFC", "ĩĩ"))
        tg_nfd = transducer_nfd(normalize("NFD", "ĩĩ"))
        assert tg.output_string == "IY N IY N "
        assert tg_nfd.output_string == "IY N IY N "
        assert tg.edges == [
            (0, 0),
            (0, 1),
            (0, 2),
            (0, 3),
            (0, 4),
            (1, 5),
            (1, 6),
            (1, 7),
            (1, 8),
            (1, 9),
        ]
        assert tg.substring_alignments() == [("ĩ", "IY N "), ("ĩ", "IY N ")]
        assert tg_nfd.edges == [
            (0, 0),
            (1, 1),
            (1, 2),
            (1, 3),
            (1, 4),
            (2, 5),
            (3, 6),
            (3, 7),
            (3, 8),
            (3, 9),
        ]
        assert tg_nfd.substring_alignments() == [
            ("i", "I"),
            ("̃", "Y N "),
            ("i", "I"),
            ("̃", "Y N "),
        ]


if __name__ == "__main__":
    main([__file__, *sys.argv])
