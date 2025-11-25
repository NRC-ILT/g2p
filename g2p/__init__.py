"""

Basic init file for g2p module

The main entry points for the g2p module are:
 - make_g2p() to create a mapper from and lang to another
 - make_tokenizer() to create a tokenizer for a given language
 - get_arpabet_langs() to get the list of languages with a path to eng-arpabet

Basic Usage:
    from g2p import make_g2p
    converter = make_g2p(in_lang, out_lang)
    transduction_graph = converter(input_text_in_in_alang)
    converted_text_in_out_lang = transduction_graph.output_string

    from g2p import make_tokenizer
    tokenizer = make_tokenizer(lang)
    for token in tokenizer.tokenize_text(input_text):
        if token.is_word:
            word = token.text
        else:
            interword_punctuation_and_spaces = token.text

    from g2p import get_arpabet_langs
    LANGS, LANG_NAMES = get_arpabet_langs()
"""

import sys
from typing import Dict, Optional, Tuple, Union

from g2p.exceptions import InvalidLanguageCode, NeuralDependencyError, NoPath
from g2p.shared_types import BaseTokenizer, BaseTransducer, Token

if sys.version_info < (3, 8):  # pragma: no cover
    sys.exit(
        "Python 3.8 or more recent is required by g2p.\n"
        f"You are using Python {sys.version}.\n"
        "Please use a newer version of Python."
    )

_g2p_cache: Dict[Tuple[str, str, bool, bool, int], BaseTransducer] = {}


def make_g2p(  # noqa: C901
    in_lang: str,
    out_lang: str,
    *,
    tokenize: bool = True,
    custom_tokenizer: Optional[BaseTokenizer] = None,
    neural: bool = False,
) -> BaseTransducer:
    """Make a g2p Transducer for mapping text from in_lang to out_lang via the
    shortest path between them.

    By default, the input is tokenized using the path of mappings from in_lang
    to out_lang, because transducers are not guaranteed to deal with whitespace,
    punctuation, and word boundaries properly.

    Args:
        in_lang (str): input language code
        out_lang (str): output language code
        tokenize (bool): whether tokenization should happen (default: True)
                         Warning: only set this to False if you've already
                         segmented your text into words without punctuation
        custom_tokenizer (Tokenizer): the tokenizer to use (default: a tokenizer
                                      built on the path from in_lang and out_lang)
        neural (bool): whether to use a neural model if it is available (default: False)

    Returns:
        Transducer from in_lang to out_lang, optionally with a tokenizer.

    Raises:
        InvalidLanguageCode: if in_lang or out_lang don't exist
        NoPath: if there is path between in_lang and out_lang
    """
    # Defer expensive imports
    from g2p.log import LOGGER
    from g2p.mappings import Mapping
    from g2p.mappings.langs import LANGS_NETWORK
    from g2p.mappings.utils import has_neural_support
    from g2p.transducer import CompositeTransducer, TokenizingTransducer, Transducer

    # Early checking for if neural is available:
    if neural and not has_neural_support():
        raise NeuralDependencyError()

    if (in_lang, out_lang, tokenize, neural, id(custom_tokenizer)) in _g2p_cache:
        return _g2p_cache[(in_lang, out_lang, tokenize, neural, id(custom_tokenizer))]

    # Check in_lang is a node in network
    if in_lang not in LANGS_NETWORK.nodes:
        LOGGER.error(f"No lang called '{in_lang}'. Please try again.")
        raise InvalidLanguageCode(in_lang)

    # Check out_lang is a node in network
    if out_lang not in LANGS_NETWORK.nodes:
        LOGGER.error(f"No lang called '{out_lang}'. Please try again.")
        raise InvalidLanguageCode(out_lang)

    if in_lang == out_lang:
        LOGGER.error(
            "Sorry, you can't transduce between the same language. "
            "Please select a different output language code."
        )
        raise NoPath(in_lang, out_lang)

    # Try to find the shortest path between the nodes
    try:
        path = LANGS_NETWORK.shortest_path(in_lang, out_lang)
    except ValueError:
        LOGGER.error(
            f"Sorry, we couldn't find a way to convert {in_lang} to {out_lang}. "
            "Please update your langs by running `g2p update` and try again."
        )
        raise NoPath(in_lang, out_lang)

    # Find all mappings needed
    mappings_needed = []
    for lang1, lang2 in zip(path[:-1], path[1:]):
        mapping = Mapping.find_mapping(in_lang=lang1, out_lang=lang2, neural=neural)
        LOGGER.debug(
            f"Adding mapping between {lang1} and {lang2} to composite transducer."
        )
        mappings_needed.append(mapping)

    # Either construct a Transducer or Composite Transducer
    transducer: Union[Transducer, CompositeTransducer, TokenizingTransducer]
    if len(mappings_needed) == 1:
        transducer = Transducer(mappings_needed[0])
    else:
        transducer = CompositeTransducer([Transducer(x) for x in mappings_needed])

    # If tokenization was requested, return a TokenizingTransducer
    if custom_tokenizer:
        transducer = TokenizingTransducer(transducer, custom_tokenizer)
    elif tokenize:
        tokenizer = make_tokenizer(in_lang=in_lang, tok_path=path)
        transducer = TokenizingTransducer(transducer, tokenizer)

    _g2p_cache[(in_lang, out_lang, tokenize, neural, id(custom_tokenizer))] = transducer
    return transducer


def tokenize_and_map(tokenizer: BaseTokenizer, transducer: BaseTransducer, input: str):
    result = ""
    for token in tokenizer.tokenize_text(input):
        if token.is_word:
            result += transducer(token.text).output_string
        else:
            result += token.text
    return result


_langs_cache = None
_lang_names_cache = None


def get_arpabet_langs():
    """Get the list of language codes and names supported by the g2p library
    for mapping to ARPABET.

    Example uses can be found in https://github.com/ReadAlongs/Studio and
    https://github.com/EveryVoiceTTS/EveryVoice

    Returns:
        LANGS (List[str]), LANG_NAMES (Dict[str,str]):
            LANGS is the sorted list of valid language codes supported
            LANG_NAMES maps each code to its full language name and is ordered by codes
    """
    # Defer expensive imports
    from g2p.mappings import LANGS
    from g2p.mappings.langs import LANGS_NETWORK

    global _langs_cache
    global _lang_names_cache

    if _langs_cache is not None and _lang_names_cache is not None:
        # Cache the results so we only calculate this information once.
        return _langs_cache, _lang_names_cache
    else:
        # langs_available in g2p lists langs inferred by the directory structure of
        # g2p/mappings/langs, but in ReadAlongs, we need all input languages to any mappings.
        # E.g., for Michif, we need to allow crg-dv and crg-tmd, but not crg, which is what
        # langs_available contains. So we define our own list of languages here.
        langs_available = []

        # this will be the set of all langs in g2p, which we need temporarily
        full_lang_names = {}

        for v in LANGS.values():
            for mapping in v.mappings:
                # add mapping to names hash table
                full_lang_names[mapping.in_lang] = mapping.language_name
                # add input id to all available langs list
                if mapping.in_lang not in langs_available:
                    langs_available.append(mapping.in_lang)

        # get the key from all networks in g2p module that have a path to 'eng-arpabet',
        # which is needed for the readalongs
        # Filter out <lang>-ipa: we only want "normal" input languages.
        # Filter out *-norm and crk-no-symbols, these are just intermediate representations.

        _langs_cache = [
            x
            for x in langs_available
            if not x.endswith("-ipa")
            and not x.endswith("-equiv")
            and not x.endswith("-no-symbols")
            and x not in ["und-ascii", "moh-festival"]
            and x in LANGS_NETWORK
            and LANGS_NETWORK.has_path(x, "eng-arpabet")
        ]

        # Sort LANGS so the -h messages list them alphabetically
        _langs_cache = sorted(_langs_cache)

        # Set up _lang_names_cache hash table for studio UI to properly name the dropdown options
        _lang_names_cache = {
            lang_code: full_lang_names[lang_code] for lang_code in _langs_cache
        }

        return _langs_cache, _lang_names_cache


def make_tokenizer(in_lang=None, out_lang=None, tok_path=None) -> BaseTokenizer:
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
    from g2p.mappings.tokenizer import make_tokenizer as _make_tokenizer

    return _make_tokenizer(in_lang, out_lang, tok_path)


# Declare what's actually part of g2p's programmatic API.
# Please don't import anything else from g2p directly.
__all__ = [
    "BaseTokenizer",
    "BaseTransducer",
    "InvalidLanguageCode",
    "NoPath",
    "Token",
    "get_arpabet_langs",
    "make_g2p",
    "make_tokenizer",
    "tokenize_and_map",
]
