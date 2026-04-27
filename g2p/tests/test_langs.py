#!/usr/bin/env python

import sys
from typing import Collection

from pytest import main

from g2p import get_arpabet_langs, get_ipa_code, make_g2p
from g2p.log import LOGGER
from g2p.mappings.langs import LANGS_NETWORK
from g2p.tests.public.data import load_public_test_data


def test_io() -> None:
    """Basic Test for individual lookup tables.

    Test files (in g2p/tests/public/data) are either .csv, .psv, or
    .tsv files, the only difference being the delimiter used (comma,
    pipe, or tab).

    Each line in the test files consist of SOURCE,TARGET,INPUT,OUTPUT"""
    langs_to_test = load_public_test_data()

    # go through each language declared in the test case set up
    # Instead of asserting immediately, we go through all the cases first, so that
    # running test_langs.py prints all the errors at once, to help debugging a given g2p mapping.
    # Then we call assertEqual on the first failed case, to make unittest register the failure.
    error_count = 0
    error_prefix = "test_langs.py: mapping error"
    for test in langs_to_test:
        transducer = make_g2p(test[0], test[1])
        output_string = transducer(test[2]).output_string.strip()
        if output_string != test[3].strip():
            LOGGER.error(
                f"{error_prefix} for {test[-1]}: {test[2]} from {test[0]} to {test[1]} should be {test[3]}, got {output_string}"
            )
            error_count += 1

    assert (
        error_count == 0
    ), f'g2p mapping errors found, look for "{error_prefix}" above for detail.'


def test_ipa_heuristic(subtests) -> None:
    """Make sure we have a reliable heuristic for finding the IPA code for all langs.

    In EveryVoice, we want to be able to assume that a simple heuristic works to find
    the IPA language code for a given language code, so let's exercise this heuristic
    here and thus make sure it will always work.

    The first heuristic was lang_id + "-ipa" was the IPA code, but that breaks with
    sal-apa -> sal-ipa and oji-syl -> oji-ipa.
    A mostly correct heuristic is lang_id.split("-",1)[0]+"-ipa", but this fails for
    iku-sro -> iku-sro-ipa, since iku-ipa exists but there is no path from iku-sro
    to iku-ipa.
    So the correct heuristic is:
        1) try lang_id + "-ipa" and use it if it is in LANGS_NETWORK.nodes
        2) otherwise use lang_id.split("-",1)[0] + "-ipa"
    Sigh..."""

    def locked_get_ipa_code(lang_id: str) -> str:
        # Prevent inadvertent changes to g2p.get_ipa_code with this locked test copy,
        # including this deep import which we promise will keep working.
        from g2p.mappings.langs import LANGS_NETWORK

        if lang_id + "-ipa" in LANGS_NETWORK.nodes:
            return lang_id + "-ipa"
        else:
            return lang_id.split("-", 1)[0] + "-ipa"

    # Make sure client code can assume "lang_id in nodes" will work
    nodes: Collection[str] = LANGS_NETWORK.nodes
    assert isinstance(nodes, Collection)

    langs, _ = get_arpabet_langs()

    for lang in langs:
        with subtests.test(lang=lang):
            ipa_code = get_ipa_code(lang)
            assert ipa_code == locked_get_ipa_code(lang)
            assert ipa_code in LANGS_NETWORK.nodes
            assert LANGS_NETWORK.has_path(lang, ipa_code)

    for hypothetical_lang, ref_ipa_code in (
        ("ll-foo", "ll-ipa"),
        ("lll-bar", "lll-ipa"),
        ("lang-foo", "lang-ipa"),
        ("language-bar", "language-ipa"),
        ("lang", "lang-ipa"),
        ("lll-foo-bar-baz", "lll-ipa"),
    ):
        assert get_ipa_code(hypothetical_lang) == ref_ipa_code


if __name__ == "__main__":
    main([__file__, *sys.argv])
