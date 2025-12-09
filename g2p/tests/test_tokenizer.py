#!/usr/bin/env python

from unittest import TestCase, main

import g2p.mappings.tokenizer as tok
from g2p.log import LOGGER


class TokenizerTest(TestCase):
    """Test suite for tokenizing text in a language-specific way"""

    def setUp(self):
        pass

    def test_tokenize_fra(self):
        input = "ceci était 'un' test."
        tokenizer = tok.make_tokenizer("fra")
        tokens = tokenizer.tokenize_text(input)
        self.assertEqual(len(tokens), 8)
        self.assertTrue(tokens[0].is_word)
        self.assertEqual(tokens[0].text, "ceci")
        self.assertFalse(tokens[1].is_word)
        self.assertEqual(tokens[1].text, " ")
        self.assertTrue(tokens[2].is_word)
        self.assertEqual(tokens[2].text, "était")
        self.assertFalse(tokens[3].is_word)
        self.assertEqual(tokens[3].text, " '")
        self.assertTrue(tokens[4].is_word)
        self.assertEqual(tokens[4].text, "un")
        self.assertFalse(tokens[5].is_word)
        self.assertEqual(tokens[5].text, "' ")
        self.assertTrue(tokens[6].is_word)
        self.assertEqual(tokens[6].text, "test")
        self.assertFalse(tokens[7].is_word)
        self.assertEqual(tokens[7].text, ".")

    def test_tokenize_eng(self):
        input = "This is éçà test."
        tokenizer = tok.make_tokenizer("eng")
        tokens = tokenizer.tokenize_text(input)
        self.assertEqual(len(tokens), 8)
        self.assertTrue(tokens[0].is_word)
        self.assertEqual(tokens[0].text, "This")
        self.assertFalse(tokens[1].is_word)
        self.assertEqual(tokens[1].text, " ")

    def test_lexicon_tokenizer(self):
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
            with self.subTest(input_text=input_text):
                tokens = tokenizer.tokenize_text(input_text)
                self.assertEqual([x.text for x in tokens], expected_tokens)

    def test_tokenize_win(self):
        """win is easy to tokenize because win -> win-ipa exists and has ' in its inventory"""
        input = "p'ōį̄ą"
        self.assertEqual(len(tok.make_tokenizer("fra").tokenize_text(input)), 3)

        tokenizer = tok.make_tokenizer("win")
        tokens = tokenizer.tokenize_text(input)
        self.assertEqual(len(tokens), 1)
        self.assertTrue(tokens[0].is_word)
        self.assertEqual(tokens[0].text, "p'ōį̄ą")

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
        self.assertEqual(len(tok.make_tokenizer("fra").tokenize_text(input)), 3)

        tokenizer = tok.make_tokenizer("tce")
        tokens = tokenizer.tokenize_text(input)
        self.assertEqual(len(tokens), 1)
        self.assertTrue(tokens[0].is_word)
        self.assertEqual(tokens[0].text, "ts'nj")

    def test_tokenize_tce_equiv(self):
        input = "ts'e ts`e ts‘e ts’"
        self.assertEqual(len(tok.make_tokenizer("fra").tokenize_text(input)), 14)
        # tce_tokens = tok.make_tokenizer("tce").tokenize_text(input)
        # LOGGER.warning([x.text for x in tce_tokens])
        self.assertEqual(len(tok.make_tokenizer("tce").tokenize_text(input)), 7)

    def test_tokenizer_identity_tce(self):
        self.assertNotEqual(tok.make_tokenizer("eng"), tok.make_tokenizer("fra"))
        self.assertNotEqual(tok.make_tokenizer("eng"), tok.make_tokenizer("tce"))
        self.assertEqual(tok.make_tokenizer("tce"), tok.make_tokenizer("tce"))
        self.assertNotEqual(tok.make_tokenizer("tce"), tok.make_tokenizer())
        self.assertEqual(tok.make_tokenizer("foo"), tok.make_tokenizer())

    def test_tokenize_kwk(self):
        """kwk is easier than tce: we just need to use kwk-umista -> kwk-ipa, but that's not
        implemented yet.
        Now works - issue #46 fixed this.
        """
        self.assertEqual(
            len(tok.make_tokenizer("kwk-umista").tokenize_text("kwak'wala")), 1
        )

    def test_three_hop_tokenizer(self):
        # This used to test the three hop tokenizer with haa -> haa-ipa via haa-equiv and haa-simp
        # tokenizer = tok.make_tokenizer("haa", tok_path=["haa", "haa-equiv", "haa-simp", "haa-ipa"])
        # But now haa has been redesigned to not use haa-simp, so downgrade the test to two hops
        tokenizer = tok.make_tokenizer("haa", tok_path=["haa", "haa-equiv", "haa-ipa"])
        tokens = tokenizer.tokenize_text("ch'ch")
        self.assertEqual(len(tokens), 1)

    def test_tokenize_not_ipa_explicit(self):
        tokenizer = tok.make_tokenizer("fn-unicode-font", "fn-unicode")
        self.assertNotEqual(tokenizer, tok.make_tokenizer())

    def test_tokenize_not_ipa_implicit(self):
        tokenizer = tok.make_tokenizer("fn-unicode-font")
        self.assertNotEqual(tokenizer, tok.make_tokenizer())

    def test_tokenize_lang_does_not_exist(self):
        self.assertEqual(tok.make_tokenizer("not_a_language"), tok.make_tokenizer())
        with self.assertLogs(LOGGER):
            self.assertEqual(
                tok.make_tokenizer("fra", "not_a_language"), tok.make_tokenizer()
            )

    def test_make_tokenizer_error(self):
        with self.assertRaises(ValueError):
            _ = tok.make_tokenizer("fra", "eng-arpabet", ["fra-ipa", "eng-ipa"])

    def test_deprecated_warning(self):
        with self.assertLogs(LOGGER, level="WARNING") as cm:
            self.assertEqual(tok.get_tokenizer("fra"), tok.make_tokenizer("fra"))
        self.assertIn("deprecated", "".join(cm.output))

    def test_gwi_multichar_grapheme_makeg2p(self):
        from g2p import make_g2p

        g2p_engine = make_g2p("gwi", "gwi-ipa")
        _ = g2p_engine("ı̨")  # we're just confirming this does not raise, see #430

    def test_gwi_multichar_grapheme_tok(self):
        tokd = tok.make_tokenizer("gwi").tokenize_text("ı̨")
        self.assertEqual("ı̨", tokd[0].text)


if __name__ == "__main__":
    main()
