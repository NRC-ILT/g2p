#!/usr/bin/env python

import sys

from pytest import main, skip

from g2p import make_g2p
from g2p.log import LOGGER
from g2p.mappings.utils import has_neural_support
from g2p.tests.public.data import load_neural_test_data


class TestNeuralLang:
    """Basic Test for individual lookup tables.

    Test file is in g2p/tests/public/data/neural.psv.

    Each line in the test file consists of SOURCE,TARGET,INPUT,OUTPUT

    """

    def test_io(self):
        if not has_neural_support():
            skip("neural not installed; skipping neural tests")
        langs_to_test = load_neural_test_data()

        # go through each language declared in the test case set up
        # Instead of asserting immediately, we go through all the cases first, so that
        # running test_neural.py prints all the errors at once, to help debugging a given g2p mapping.
        # Then we call assertEqual on the first failed case, to make unittest register the failure.
        error_count = 0
        error_prefix = "test_neural.py: mapping error"
        for test in langs_to_test:
            transducer = make_g2p(test[0], test[1], neural=True)
            output_string = transducer(test[2]).output_string.strip()
            if output_string != test[3].strip():
                LOGGER.error(
                    f"{error_prefix} for {test[-1]}: {test[2]} from {test[0]} to {test[1]} should be {test[3]}, got {output_string}"
                )
                error_count += 1

        assert (
            error_count == 0
        ), f'Search for "ERROR - {error_prefix}" above to find all the g2p mapping errors.'


if __name__ == "__main__":
    main([__file__, *sys.argv])
