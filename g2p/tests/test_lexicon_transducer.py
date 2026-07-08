#!/usr/bin/env python

import os
import sys
from unittest import TestCase

from pytest import main

from g2p import make_g2p
from g2p.log import LOGGER
from g2p.mappings import Mapping
from g2p.tests.public import __file__ as public_data
from g2p.transducer import Transducer


class LexiconTransducerTest(TestCase):
    def test_lexicon_mapping(self):
        """Test loading a lexicon mapping directly in the constructor."""
        with self.assertLogs(LOGGER, level="INFO"):
            m = Mapping(
                type="lexicon",
                case_sensitive=False,
                out_delimiter=" ",
                alignments_path=os.path.join(
                    os.path.dirname(public_data), "mappings", "hello.aligned.txt"
                ),
            )
        assert m.rules == []
        assert m.type == "lexicon"
        t = Transducer(m)
        tg = t("hello")
        assert tg.output_string == "HH EH L OW "
        assert tg.edges == [
            (0, 0),
            (0, 1),
            (1, 3),
            (1, 4),
            (2, 6),
            (3, 6),
            (4, 8),
            (4, 9),
        ]
        tg = t("you're")
        assert tg.output_string == "Y UH R "
        assert tg.edges == [
            (0, 0),
            (1, 2),
            (1, 3),
            (2, 2),
            (2, 3),
            (3, 4),
            (4, 5),
            (5, 5),
        ]
        # These alignments are somewhat bogus, hence the name
        tg = t("bogus")
        assert tg.input_string == "bogus"
        assert tg.output_string == ""
        assert tg.edges == [(0, None), (1, None), (2, None), (3, None), (4, None)]
        assert tg.substring_alignments() == [("bogus", "")]
        tg = t("bogus")
        tg += t("hello")
        assert tg.input_string == "bogushello"
        assert tg.output_string == "HH EH L OW "
        assert tg.edges == [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (4, 0),
            (5, 0),
            (5, 1),
            (6, 3),
            (6, 4),
            (7, 6),
            (8, 6),
            (9, 8),
            (9, 9),
        ]
        assert tg.substring_alignments() == [
            ("bogush", "HH"),
            ("e", "EH"),
            ("ll", "L"),
            ("o", "OW"),
        ]
        tg = t("hello")
        tg += t("bogus")
        tg += t("you're")
        tg += t("bogus")
        assert tg.input_string == "hellobogusyou'rebogus"
        assert tg.edges == [
            (0, 0),
            (0, 1),
            (1, 3),
            (1, 4),
            (2, 6),
            (3, 6),
            (4, 8),
            (4, 9),
            (5, 9),
            (6, 9),
            (7, 9),
            (8, 9),
            (9, 9),
            (10, 11),
            (11, 13),
            (11, 14),
            (12, 13),
            (12, 14),
            (13, 15),
            (14, 16),
            (15, 16),
            (16, 16),
            (17, 16),
            (18, 16),
            (19, 16),
            (20, 16),
        ]
        assert tg.substring_alignments() == [
            ("h", "HH"),
            ("e", "EH"),
            ("ll", "L"),
            ("obogus", "OW"),
            ("y", "Y"),
            ("ou", "UH"),
            ("'", " "),
            ("rebogus", "R"),
        ]

    def test_load_lexicon_mapping(self):
        """Test loading a lexicon mapping through a config file."""
        with self.assertLogs(LOGGER, level="INFO"):
            m = Mapping.load_mapping_from_path(
                os.path.join(
                    os.path.dirname(public_data), "mappings", "lexicon_config-g2p.yaml"
                )
            )
        assert m.rules == []
        assert m.type == "lexicon"
        t = Transducer(m)
        tg = t("hello")
        assert tg.output_string == "HH EH L OW "
        assert tg.edges == [
            (0, 0),
            (0, 1),
            (1, 3),
            (1, 4),
            (2, 6),
            (3, 6),
            (4, 8),
            (4, 9),
        ]

    def test_bad_lexicon_mapping(self):
        """Test failure to load alignments."""
        with (
            self.assertRaises(FileNotFoundError),
            self.assertLogs(LOGGER, level="INFO"),
        ):
            _ = Mapping.load_mapping_from_path(
                os.path.join(
                    os.path.dirname(public_data),
                    "mappings",
                    "bad_lexicon_config-g2p.yaml",
                )
            )

    def test_eng_lexicon(self):
        """Test the cached eng to eng-ipa lexicon as a Mapping."""
        m = Mapping.find_mapping(in_lang="eng", out_lang="eng-ipa")
        assert m.type == "lexicon"
        t = Transducer(m)
        tg = t("hello")
        assert tg.output_string == "hʌloʊ"
        assert tg.edges == [(0, 0), (1, 1), (2, 2), (3, 2), (4, 3), (4, 4)]
        tg = t("you're")
        assert tg.output_string == "jʊɹ"
        assert tg.edges == [(0, 0), (1, 0), (2, 1), (3, 1), (4, 2), (5, 2)]
        tg = t("change")
        assert tg.output_string == "tʃeɪndʒ"
        assert tg.input_string == "change"
        assert tg.edges == [
            (0, 0),
            (0, 1),
            (1, 1),
            (2, 2),
            (2, 3),
            (3, 4),
            (4, 5),
            (4, 6),
            (5, 6),
        ]
        tg = t("chain")
        # These aligments are weird but they are the ones EM gave us
        # (and the ones that our arbitrary assignment of deletions to
        # adjacent outputs gives us, too...)
        assert tg.output_string == "tʃeɪn"
        assert tg.input_string == "chain"
        assert tg.edges == [(0, 0), (0, 1), (1, 1), (2, 2), (3, 3), (4, 4)]
        tg = t("xtra")
        assert tg.output_string == "ɛkstɹʌ"
        assert tg.input_string == "xtra"
        assert tg.edges == [(0, 0), (0, 1), (0, 2), (1, 3), (2, 4), (3, 5)]
        pe = tg.pretty_edges()
        assert pe == [
            ("x", "ɛ"),
            ("x", "k"),
            ("x", "s"),
            ("t", "t"),
            ("r", "ɹ"),
            ("a", "ʌ"),
        ]

    def test_eng_transducer(self):
        """Test the cached eng to eng-ipa lexicon from make_g2p."""
        transducer = make_g2p("eng", "eng-arpabet")
        tg = transducer("hello")
        assert tg.output_string == "HH AH L OW "

        # since we tokenize by default now, this works:
        assert (
            transducer("hello my friend").output_string
            == "HH AH L OW  M AY  F R EH N D "
        )

    def test_eng_lexicon_corner_cases(self):
        """White-box testing for compact storage of lexicon mappings."""
        test_cases = (
            ("'bout", "baʊt"),  # first entry in eng->eng-ipa
            ("'cause", "kʌz"),  # second entry
            ("'course", "kɔɹs"),  # third
            ("'tis", "tɪz"),  # 15th entry
            ("'twas", "twʌz"),  # 16th entry
            ("a", "ʌ"),  # 17th entry
            ("buttering", "bʌtɜ˞ɪŋ"),  # 15998th, which is -2 mod 16
            ("buttermilk", "bʌtɜ˞mɪlk"),  # 15999th, -1 mod 16
            ("buttermore", "bʌtɜ˞mɔɹ"),  # 16000th, 0 mod 16
            ("butters", "bʌtɜ˞z"),  # 16001th, 1 mod 16
            ("butterscotch", "bʌtɜ˞skɑtʃ"),
            ("butterworth", "bʌtɜ˞wɜ˞θ"),
            ("buttery", "bʌtɜ˞i"),
            ("butthead", "bʌthɛd"),
            ("butting", "bʌtɪŋ"),
            ("buttitta", "butitʌ"),
            ("buttke", "bʌtki"),
            ("buttler", "bʌtlɜ˞"),
            ("buttner", "bʌtnɜ˞"),
            ("buttock", "bʌtʌk"),
            ("buttocks", "bʌtʌks"),
            ("button", "bʌtʌn"),
            ("buttoned", "bʌtʌnd"),
            ("buttonhole", "bʌtʌnhoʊl"),
            ("buttonholed", "bʌtʌnhoʊld"),
            ("buttonholes", "bʌtʌnhoʊlz"),
            ("buttons", "bʌtʌnz"),  # 16018th
            ("zwieg", "zwiɡ"),  # last block of the lexicon
            ("zwilling", "zwɪlɪŋ"),
            ("zwolinski", "zvʌlɪnski"),
            ("zycad", "zɪkæd"),
            ("zych", "zaɪtʃ"),
            ("zycher", "zɪkɜ˞"),
            ("zydeco", "zaɪdʌkoʊ"),
            ("zygmunt", "zɪɡmʌnt"),
            ("zygote", "zaɪɡoʊt"),
            ("zyla", "zɪlʌ"),
            ("zylka", "zɪlkʌ"),
            ("zylstra", "zɪlstɹʌ"),
            ("zyman", "zaɪmʌn"),
            ("zynda", "zɪndʌ"),
            ("zysk", "zaɪsk"),
            ("zyskowski", "zɪskɔfski"),
            ("zyuganov", "zjuɡɑnɑv"),
            ("zyuganov's", "zjuɡɑnɑvz"),
            ("zywicki", "zɪwɪki"),
        )

        transducer = make_g2p("eng", "eng-ipa", tokenize=False)
        for word, expected in test_cases:
            tg = transducer(word)
            assert tg.output_string == expected
            before = word[:-1] + chr(ord(word[-1]) - 1) + "z"
            assert (
                transducer(before).output_string == ""
            ), f"word={word} before={before}"
            after = word[:-1] + chr(ord(word[-1]) + 1) + "z"
            assert transducer(after).output_string == "", f"word={word} after={after}"


if __name__ == "__main__":
    main([__file__, *sys.argv])
