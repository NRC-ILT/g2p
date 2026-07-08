#!/usr/bin/env python

import sys
from unittest import TestCase

from pytest import main

from g2p import make_g2p
from g2p.mappings import Mapping
from g2p.mappings.utils import normalize
from g2p.transducer import Transducer


class UnidecodeTransducerTest(TestCase):
    def test_unidecode_mapping(self):
        m = Mapping(type="unidecode")
        assert m.rules == []
        assert m.type == "unidecode"
        t = Transducer(m)
        tg = t("été Nunavut ᓄᓇᕗᑦ")
        assert tg.output_string == "ete Nunavut nonafot"

    def test_unidecode_g2p(self):
        transducer = make_g2p("und", "und-ascii", tokenize=False)
        tg = transducer(normalize("éçà", "NFD"))
        assert tg.output_string == "eca"
        assert tg.edges == [(0, 0), (1, 0), (2, 1), (3, 1), (4, 2), (5, 2)]

        tg = transducer(normalize("éçà", "NFC"))
        assert tg.output_string == "eca"
        assert tg.edges == [(0, 0), (1, 1), (2, 2)]

    def test_unidecode_empty_output(self):
        transducer = make_g2p("und", "und-ascii", tokenize=False)
        # \u0361 on its own gets deleted completely by unidecode
        tg = transducer("\u0361")
        assert tg.output_string == ""
        assert tg.edges == []

    def test_unidecode_to_arpabet(self):
        transducer = make_g2p("und", "eng-arpabet", tokenize=False)
        tg = transducer("été Nunavut ᓄᓇᕗᑦ")
        assert tg.output_string == "EY T EY  N UW N AA V UW T  N OW N AA F OW T "

    def test_unidecode_arabic_to_arpabet(self):
        transducer = make_g2p("und", "eng-arpabet")
        tg = transducer("السلام عليكم")
        assert tg.output_string == "L S L M  L Y K M "

    def test_unidecode_arabic_presentation_to_arpabet(self):
        transducer = make_g2p("und", "eng-arpabet")
        tg = transducer("ﺷﻜﺮﺍﹰ")
        assert tg.output_string == "S HH K D AA N "

    def test_unidecode_kanji_to_arpabet(self):
        transducer = make_g2p("und", "eng-arpabet")
        tg = transducer("日本語")
        assert tg.output_string == "D IY B EY N Y UW "

    def test_unidecode_hanzi_to_arpabet(self):
        transducer = make_g2p("und", "eng-arpabet", tokenize=False)
        tg = transducer("你们好!你们说汉语马?")
        assert (
            tg.output_string
            == "N IY M EY N HH AA OW N IY M EY N S HH UW OW Y IY Y UW M AA HH "
        )


if __name__ == "__main__":
    main([__file__, *sys.argv])
