"""

Tokenizer module, to provide language-dependent tokenization of text.
A token is defined as a sequence of characters that are either part of the
language's input mapping or that are unicode letters, numbers and diacritics.

"""

import re
from typing import List

from g2p.exceptions import MappingMissing
from g2p.log import LOGGER
from g2p.mappings import Mapping, utils
from g2p.mappings.langs import LANGS_NETWORK
from g2p.mappings.utils import is_ipa
from g2p.shared_types import BaseTokenizer, Token


class Tokenizer(BaseTokenizer):
    """Base class for all g2p tokenizers; implements the default tokenizing behaviour.

    By default, a token is defined as a sequence of letters, numbers and
    diacritics, as defined in the Unicode Standard.
    """

    def __init__(self):
        self.inventory = []
        self.delim = ""
        self.case_sensitive = False
        # Hack for Tlingit where . is a letter when not word final:
        self.dot_is_letter = False
        self.escape_special = False

    def tokenize_aux(self, text):
        return text

    def is_word_character(self, characters):
        if not self.case_sensitive:
            characters = characters.lower()
        inventory_check = re.escape(characters) if self.escape_special else characters
        if inventory_check in self.inventory:
            return True
        if self.delim and characters == self.delim:
            return True
        return all(
            utils.get_unicode_category(c) in ["letter", "number", "diacritic"]
            for c in characters
        )

    def tokenize_text(self, text: str) -> List[Token]:
        matches = self.tokenize_aux(text)
        units = [Token(m, self.is_word_character(m)) for m in matches]
        if self.dot_is_letter:
            for i, unit in enumerate(units):
                if unit.text == "." and i + 1 < len(units) and units[i + 1].is_word:
                    unit.is_word = True
        return utils.merge_same_type_tokens(units)


class SpecializedTokenizer(Tokenizer):
    def __init__(self, mapping: Mapping):
        self.delim = ""
        self.inventory = mapping.inventory("in")
        self.lang = mapping.language_name
        self.case_sensitive = mapping.case_sensitive
        self.dot_is_letter = False
        self.escape_special = mapping.escape_special
        # create regex
        self._build_regex()

    def _build_regex(self):
        if not self.case_sensitive:
            self.inventory = [c.lower() for c in self.inventory]
        # Remove the indices, they're not part of the text input for the rules
        self.inventory = [re.sub(r"{[0-9]+}", "", x) for x in self.inventory]
        # Rules with "in": "è|é" have two distinct inputs, split them.
        self.inventory = [
            part
            for rule_input in self.inventory
            for part in re.split(r"(?<!\\)\|", rule_input)
        ]
        regex_pieces = sorted(self.inventory, key=lambda s: -len(s))
        regex_pieces = [re.escape(p) for p in regex_pieces]
        if self.delim:
            regex_pieces.append(self.delim)
        pattern = "|".join(regex_pieces + ["."])
        pattern = "(" + pattern + ")"
        # LOGGER.warning(f"pattern for {self.lang}: {pattern}.")
        flags = re.DOTALL
        if not self.case_sensitive:
            flags |= re.I
        self.regex = re.compile(pattern, flags)

    def tokenize_aux(self, text):
        return self.regex.findall(text)


class LexiconTokenizer(Tokenizer):
    """Lexicon-based tokenizer will consider any entry in the lexicon a token,
    even if it contains punctuation characters. For text not in the lexicon,
    falls back to the default tokenization.
    """

    def __init__(self, mapping: Mapping):
        super().__init__()
        self.mapping = mapping
        self.lang = mapping.language_name

    def _recursive_helper(self, tokens: list, output_tokens: list):
        """Emit the longest prefix found in the lexicon, if any, as a token.
        If None, emit the first unit as a token.
        Recursively process the rest of the units.
        """
        if not tokens:
            return
        if len(tokens) == 1:
            output_tokens.append(tokens[0])
            return
        for i in range(len(tokens), 0, -1):
            candidate = "".join([u.text for u in tokens[:i]])
            if utils.find_alignment(self.mapping.alignments, candidate.lower()):
                output_tokens.append(Token(candidate, True))
                return self._recursive_helper(tokens[i:], output_tokens)
        # No prefix found, emit the first unit as a token
        output_tokens.append(tokens[0])
        self._recursive_helper(tokens[1:], output_tokens)

    def tokenize_text(self, text: str) -> List[Token]:
        blocks = re.split(r"(\s+)", text)
        output_tokens = []
        for i, block in enumerate(blocks):
            if i % 2 == 1 and block:
                output_tokens.append(Token(block, False))
            else:
                default_tokens = super().tokenize_text(block)
                # Split non-word tokens into smaller parts for lexicon lookup
                candidate_tokens = utils.split_non_word_tokens(default_tokens)
                self._recursive_helper(candidate_tokens, output_tokens)

        return utils.merge_non_word_tokens(output_tokens)


class MultiHopTokenizer(SpecializedTokenizer):
    def __init__(self, mappings: List[Mapping]):
        self.delim = ""
        assert mappings
        self.inventory = sum([m.inventory("in") for m in mappings], [])
        self.lang = mappings[0].language_name
        self.case_sensitive = mappings[0].case_sensitive
        self.dot_is_letter = False
        self.escape_special = mappings[0].escape_special
        self._build_regex()
        # LOGGER.warning(pprint.pformat([self.lang, self.delim, self.case_sensitive, self.inventory]))


class TokenizerLibrary:
    """
    The TokenizerLibrary holds the collection of tokenizers that have been
    initialized so far. We don't initialize them all since that takes costly
    loading time; instead, we initialize each only as requested.
    """

    def __init__(self):
        self.tokenizers = {None: Tokenizer()}

    def make_tokenizer_key(self, in_lang, out_lang=None, tok_path=None):
        if not in_lang:
            return None
        if tok_path:
            return in_lang + "+tok_path=" + "-to-".join(tok_path)
        if not out_lang:
            out_lang = in_lang + "-ipa"
        return in_lang + "-to-" + out_lang

    def make_tokenizer(  # noqa C901
        self, in_lang, out_lang=None, tok_path=None
    ) -> Tokenizer:
        tokenizer_key = self.make_tokenizer_key(in_lang, out_lang, tok_path)
        if not self.tokenizers.get(tokenizer_key):
            # This tokenizer was not created yet, initialize it now.
            if tok_path:
                # LOGGER.warning(f"in_lang={in_lang} tok_path={tok_path}")
                if tok_path[0] != in_lang:
                    raise ValueError(
                        "calling make_tokenizer() with tok_path requires that tok_path[0] == in_lang"
                    )
                assert len(tok_path) >= 2
                if len(tok_path) == 2 or is_ipa(tok_path[1]):
                    out_lang = tok_path[1]
                elif len(tok_path) == 3 or is_ipa(tok_path[2]):
                    out_lang = tok_path[1:3]
                elif len(tok_path) > 3 and is_ipa(tok_path[3]):
                    out_lang = tok_path[1:4]
                else:
                    out_lang = tok_path[1:3]
            if not out_lang:
                try:
                    successors = list(LANGS_NETWORK.successors(in_lang))
                except KeyError:
                    successors = []
                ipa_successors = [x for x in successors if is_ipa(x)]
                # LOGGER.warning(pprint.pformat([in_lang, "->", successors, ipa_successors]))
                if ipa_successors:
                    # in_lang has an ipa successor, tokenize using it
                    # there currently are no langs with more than 1 IPA successor, but to
                    # be future-proof we'll arbitrarily take the first if there are more.
                    out_lang = ipa_successors[0]
                else:
                    # There is no direct IPA successor, look for a two-hop path to -ipa
                    for x in successors:
                        ipa_successors_two_hops = [
                            y for y in LANGS_NETWORK.successors(x) if is_ipa(y)
                        ]
                        # LOGGER.warning(pprint.pformat([in_lang, x, "->", [ipa_successors_two_hops]]))
                        if ipa_successors_two_hops:
                            out_lang = [x, ipa_successors_two_hops[0]]
                        break
                    # There is no two-hop IPA successor, use the first direct successor
                    if out_lang is None and successors:
                        out_lang = successors[0]
            # LOGGER.warning(f"Tokenizer for {in_lang} is {out_lang}.")
            if out_lang is None:
                # Default tokenizer:
                self.tokenizers[tokenizer_key] = self.tokenizers[None]
            elif isinstance(out_lang, list):
                # Build a multi-hop tokenizer
                assert len(out_lang) > 1
                try:
                    mappings = [
                        Mapping.find_mapping(in_lang=in_lang, out_lang=out_lang[0])
                    ]
                    for i in range(1, len(out_lang)):
                        mappings.append(
                            Mapping.find_mapping(
                                in_lang=out_lang[i - 1], out_lang=out_lang[i]
                            )
                        )
                    self.tokenizers[tokenizer_key] = MultiHopTokenizer(mappings)
                except MappingMissing:
                    self.tokenizers[tokenizer_key] = self.tokenizers[None]
                    LOGGER.warning(
                        f"missing mapping yet we looked for mappings in graph for {in_lang}-{out_lang}."
                    )
            else:
                # Build a one-hop tokenizer
                try:
                    mapping = Mapping.find_mapping(in_lang=in_lang, out_lang=out_lang)
                    if mapping.type == utils.MAPPING_TYPE.lexicon:
                        self.tokenizers[tokenizer_key] = LexiconTokenizer(mapping)
                    else:
                        self.tokenizers[tokenizer_key] = SpecializedTokenizer(mapping)
                except MappingMissing:
                    self.tokenizers[tokenizer_key] = self.tokenizers[None]
                    LOGGER.warning(
                        f"Cannot find mapping from '{in_lang}' to '{out_lang}'. Using default tokenizer instead"
                    )

            # Hack for Tlingit using dot as a letter when non word-final
            # We also apply it for sal-apa so it can work with Secwempetsín
            if in_lang == "tli" or in_lang == "sal-apa":
                self.tokenizers[tokenizer_key].dot_is_letter = True

        return self.tokenizers[tokenizer_key]


_the_tokenizer_library = TokenizerLibrary()


def make_tokenizer(in_lang=None, out_lang=None, tok_path=None) -> Tokenizer:
    """Make the tokenizer for input in language in_lang

    Logic used when only in_lang is provided:
    - if in_lang -> in_lang-ipa, or in_lang -> X-ipa exists, tokenize using the input
      inventory of that mapping.
    - elif in_lang -> X -> Y-ipa exists, e.g., tce -> tce-equiv -> tce-ipa, tokenize
      using the input inventory of those two hops.
    - otherwise, just use the default tokenizer, which accepts as part of words all
      unicode letter, numbers and diacritics

    Logic used when in_lang and out_lang are provided:
    - if in_lang -> out_lang exists, tokenize using the input inventory of that mapping
    - otherwise use the default tokenizer

    Logic used when in_lang and tok_path are provided:
    - use the first one or two hops in path, stopping at the first -ipa node
    """
    return _the_tokenizer_library.make_tokenizer(in_lang, out_lang, tok_path)


_deprecated_warning_printed = False


def get_tokenizer(*args, **kwargs):
    """Deprecated; use make_tokenizer() instead."""

    global _deprecated_warning_printed
    if not _deprecated_warning_printed:
        LOGGER.warning(
            "g2p.get_tokenizer() / g2p.mappings.tokenizer.get_tokenizer() is deprecated. Import and use g2p.make_tokenizer() instead."
        )
        _deprecated_warning_printed = True

    return make_tokenizer(*args, **kwargs)
