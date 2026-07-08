#!/usr/bin/env python

import sys

from pytest import main, raises

import g2p.mappings.tokenizer as tok
from g2p.log import LOGGER


class TestTokenizer:
    """Test suite for tokenizing text in a language-specific way"""

    def test_tokenize_fra(self):
        input = "ceci était 'un' test."
        tokenizer = tok.make_tokenizer("fra")
        tokens = tokenizer.tokenize_text(input)
        assert len(tokens) == 8
        assert tokens[0].is_word
        assert tokens[0].text == "ceci"
        assert not tokens[1].is_word
        assert tokens[1].text == " "
        assert tokens[2].is_word
        assert tokens[2].text == "était"
        assert not tokens[3].is_word
        assert tokens[3].text == " '"
        assert tokens[4].is_word
        assert tokens[4].text == "un"
        assert not tokens[5].is_word
        assert tokens[5].text == "' "
        assert tokens[6].is_word
        assert tokens[6].text == "test"
        assert not tokens[7].is_word
        assert tokens[7].text == "."

    def test_tokenize_eng(self):
        input = "This is éçà test."
        tokenizer = tok.make_tokenizer("eng")
        tokens = tokenizer.tokenize_text(input)
        assert len(tokens) == 8
        assert tokens[0].is_word
        assert tokens[0].text == "This"
        assert not tokens[1].is_word
        assert tokens[1].text == " "

    def test_lexicon_tokenizer(self, subtests):
        tokenizer = tok.make_tokenizer("eng")
        tests = [
            ("It's", ["It's"]),
            ("'cause", ["'cause"]),
            ('"\'cause"', ['"', "'cause", '"']),
            ("aardvark's", ["aardvark", "'s"]),
            ("'aardvark's'", ["'", "aardvark", "'s", "'"]),
            ("ten a.m.", ["ten", " ", "a.m."]),
            ('ten "a.m.,!"', ["ten", ' "', "a.m.", ',!"']),
            ("all-out war", ["all-out", " ", "war"]),  # all-out is in the lexicon
            ("all-in: nonsense", ["all", "-", "in", ": ", "nonsense"]),  # all-in is not
        ]
        for input_text, expected_tokens in tests:
            with subtests.test(input_text=input_text):
                tokens = tokenizer.tokenize_text(input_text)
                assert [x.text for x in tokens] == expected_tokens

    def test_tokenize_win(self):
        """win is easy to tokenize because win -> win-ipa exists and has ' in its inventory"""
        input = "p'ōį̄ą"
        assert len(tok.make_tokenizer("fra").tokenize_text(input)) == 3

        tokenizer = tok.make_tokenizer("win")
        tokens = tokenizer.tokenize_text(input)
        assert len(tokens) == 1
        assert tokens[0].is_word
        assert tokens[0].text == "p'ōį̄ą"

    def test_tokenize_tce(self):
        """tce is hard to tokenize correctly because we have tce -> tce-equiv -> tce-ipa, and ' is
        only mapped in the latter.
        Challenges:
         - since tce->tce-ipa is not a direct mapping, we're probably getting a default
           tokenizer
         - we want to merge the input inventory of both tce->tce-equiv and tce-equiv->tce-ipa
           into just one joint inventory for the purpose of tokenization.
        Now works - issue #46 fixed this.
        """
        input = "ts'nj"
        assert len(tok.make_tokenizer("fra").tokenize_text(input)) == 3

        tokenizer = tok.make_tokenizer("tce")
        tokens = tokenizer.tokenize_text(input)
        assert len(tokens) == 1
        assert tokens[0].is_word
        assert tokens[0].text == "ts'nj"

    def test_tokenize_tce_equiv(self):
        input = "ts'e ts`e ts‘e ts’"
        assert len(tok.make_tokenizer("fra").tokenize_text(input)) == 14
        # tce_tokens = tok.make_tokenizer("tce").tokenize_text(input)
        # LOGGER.warning([x.text for x in tce_tokens])
        assert len(tok.make_tokenizer("tce").tokenize_text(input)) == 7

    def test_tokenizer_identity_tce(self):
        assert tok.make_tokenizer("eng") != tok.make_tokenizer("fra")
        assert tok.make_tokenizer("eng") != tok.make_tokenizer("tce")
        assert tok.make_tokenizer("tce") == tok.make_tokenizer("tce")
        assert tok.make_tokenizer("tce") != tok.make_tokenizer()
        assert tok.make_tokenizer("foo") == tok.make_tokenizer()

    def test_tokenize_kwk(self):
        """kwk is easier than tce: we just need to use kwk-umista -> kwk-ipa, but that's not
        implemented yet.
        Now works - issue #46 fixed this.
        """
        assert len(tok.make_tokenizer("kwk-umista").tokenize_text("kwak'wala")) == 1

    def test_three_hop_tokenizer(self):
        # This used to test the three hop tokenizer with haa -> haa-ipa via haa-equiv and haa-simp
        # tokenizer = tok.make_tokenizer("haa", tok_path=["haa", "haa-equiv", "haa-simp", "haa-ipa"])
        # But now haa has been redesigned to not use haa-simp, so downgrade the test to two hops
        tokenizer = tok.make_tokenizer("haa", tok_path=["haa", "haa-equiv", "haa-ipa"])
        tokens = tokenizer.tokenize_text("ch'ch")
        assert len(tokens) == 1

    def test_tokenize_not_ipa_explicit(self):
        tokenizer = tok.make_tokenizer("fn-unicode-font", "fn-unicode")
        assert tokenizer != tok.make_tokenizer()

    def test_tokenize_not_ipa_implicit(self):
        tokenizer = tok.make_tokenizer("fn-unicode-font")
        assert tokenizer != tok.make_tokenizer()

    def test_tokenize_lang_does_not_exist(self):
        assert tok.make_tokenizer("not_a_language") == tok.make_tokenizer()
        assert tok.make_tokenizer("fra" == "not_a_language"), tok.make_tokenizer()

    def test_make_tokenizer_error(self):
        with raises(ValueError):
            _ = tok.make_tokenizer("fra", "eng-arpabet", ["fra-ipa", "eng-ipa"])

    def test_deprecated_warning(self, caplog):
        with caplog.at_level("WARNING", logger=LOGGER.name):
            tok._deprecated_warning_printed = False
            assert tok.get_tokenizer("fra") == tok.make_tokenizer("fra")
        assert "deprecated" in caplog.text

    def test_gwi_multichar_grapheme_makeg2p(self):
        from g2p import make_g2p

        g2p_engine = make_g2p("gwi", "gwi-ipa")
        _ = g2p_engine("ı̨")  # we're just confirming this does not raise, see #430

    def test_gwi_multichar_grapheme_tok(self):
        tokd = tok.make_tokenizer("gwi").tokenize_text("ı̨")
        assert "ı̨" == tokd[0].text


if __name__ == "__main__":
    main([__file__, *sys.argv])
