#!/usr/bin/env python

import sys

from pytest import main

from g2p import make_g2p
from g2p.log import LOGGER
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


if __name__ == "__main__":
    main([__file__, *sys.argv])
