#!/usr/bin/env python

""" Test Mapping langs utility functions and their use in g2p convert --check """

import sys

from pytest import main

from g2p import make_g2p
from g2p.log import LOGGER
from g2p.mappings.langs import utils


class TestCheckIpaArpabet:
    def test_is_IPA(self, caplog):
        assert utils.is_panphon("ijŋeːʒoːɡd͡ʒ")  # All panphon chars
        assert utils.is_panphon("ij ij")  # tokenizes on spaces
        # ASCII g is not ipa/panphon use ɡ (\u0261)
        # assert not utils.is_panphon("ga")  - tolerated because of panphon preprocessor!
        # ASCII : is not ipa/panphon, use ː (\u02D0)
        with caplog.at_level("WARNING", logger=LOGGER.name):
            assert not utils.is_panphon("ge:", display_warnings=True)

    def test_is_arpabet(self):
        arpabet_string = "S AH S IY  EH  AO N  T EH"
        non_arpabet_string = "sometext"
        assert utils.is_arpabet(arpabet_string)
        assert not utils.is_arpabet(non_arpabet_string)

    def test_check_arpabet(self):
        transducer = make_g2p("eng-ipa", "eng-arpabet")
        assert transducer.check(transducer("jŋeːi"))
        assert not transducer.check(transducer("gaŋi"))
        assert transducer.check(transducer("ɡɑŋi"))
        assert not transducer.check(transducer("ñ"))

    def test_check_ipa(self, caplog):
        transducer = make_g2p("fra", "fra-ipa", tokenize=False)
        assert transducer.check(transducer("ceci"))
        assert not transducer.check(transducer("ñ"))
        with caplog.at_level("WARNING", logger=LOGGER.name):
            assert not transducer.check(transducer("ñ"), display_warnings=True)
        assert transducer.check(transducer("ceci est un test été à"))

        transducer = make_g2p("fra-ipa", "eng-ipa")
        assert not transducer.check(transducer("ñ"))

    def test_is_ipa_with_panphon_preprocessor(self):
        # panphon doesn't like these directly, but our panphon proprocessor "patches" them
        # because they are valid IPA phonetic constructs that panphon is a bit too picky about.
        assert utils.is_panphon("ɻ̊j̊ oⁿk oᵐp")

    def test_check_composite_transducer(self):
        transducer = make_g2p("fra", "eng-arpabet", tokenize=False)
        assert transducer.check(transducer("ceci est un test été à"))
        assert not transducer.check(transducer("ñ"))

    def test_check_tokenizing_transducer(self):
        transducer = make_g2p("fra", "fra-ipa")
        assert transducer.check(transducer("ceci est un test été à"))
        assert not transducer.check(transducer("ñ oǹ"))
        assert transducer.check(
            transducer("ceci, cela; c'est tokenizé: alors c'est bon!")
        )
        assert not transducer.check(
            transducer("mais... c'est ñoñ, si du texte ne passe pas!")
        )

    def test_check_tokenizing_composite_transducer(self, caplog):
        transducer = make_g2p("fra", "eng-arpabet")
        assert transducer.check(transducer("ceci est un test été à"))
        assert not transducer.check(transducer("ñ oǹ"))
        assert transducer.check(
            transducer("ceci, cela; c'est tokenizé: alors c'est bon!")
        )
        assert not transducer.check(
            transducer("mais... c'est ñoñ, si du texte ne passe pas!")
        )
        with caplog.at_level("WARNING", logger=LOGGER.name):
            assert not transducer.check(
                transducer("mais... c'est ñoñ, si du texte ne passe pas!"),
                display_warnings=True,
            )

    def test_shallow_check(self):
        transducer = make_g2p("win", "eng-arpabet")
        # This is False, but should be True! It's False because the mapping outputs :
        # instead of ː
        # EJJ 2022-06-16 With #100 fixed, this check is no longer failing.
        # assert not transducer.check(transducer("uu"))
        assert transducer.check(transducer("uu"))
        assert transducer.check(transducer("uu"), shallow=True)

    def test_check_with_equiv(self):
        transducer = make_g2p("tau", "eng-arpabet")
        tau_ipa = make_g2p("tau", "tau-ipa")(
            "sh'oo Jign maasee' do'eent'aa shyyyh"
        ).output_string
        assert utils.is_panphon(tau_ipa)
        eng_ipa = make_g2p("tau", "eng-ipa")(
            "sh'oo Jign maasee' do'eent'aa shyyyh"
        ).output_string
        assert utils.is_panphon(eng_ipa)
        eng_arpabet = make_g2p("tau", "eng-arpabet")(
            "sh'oo Jign maasee' do'eent'aa shyyyh"
        ).output_string
        assert utils.is_arpabet(eng_arpabet)
        # LOGGER.warning(
        #     f"tau-ipa {tau_ipa}\neng-ipa {eng_ipa}\n eng-arpabet {eng_arpabet}"
        # )
        assert transducer.check(transducer("sh'oo Jign maasee' do'eent'aa shyyyh"))


if __name__ == "__main__":
    main([__file__, *sys.argv])
