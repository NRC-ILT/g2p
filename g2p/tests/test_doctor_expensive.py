#!/usr/bin/env python

import sys
from unittest import TestCase

from click.testing import CliRunner
from pytest import main

from g2p.cli import doctor
from g2p.log import LOGGER
from g2p.mappings.langs.utils import check_ipa_known_segs


class ExpensiveDoctorTest(TestCase):
    # We segragate the expensive tests for g2p doctor in this suite which is not included
    # in dev, so that it doesn't slow down our Travis CI tests, but can still be run by
    # hand when desired.
    # These tests are not very good because they don't assert enough to make sure doctor
    # actually works, but they still exercise the code.
    #
    # This test suite is deliberately left out of run.py: it will only get run if you run
    # ./run.py all, or ./test_doctor_expensive.py.

    # Migrated here from test_cli.py
    def test_doctor_cli(self):
        # TODO: assert something more useful here...
        # This test simulates calling "g2p doctor" on the command line with no arguments,
        # which runs doctor on all mappings.
        runner = CliRunner()
        with self.assertLogs(LOGGER, level="WARNING") as cm:
            result = runner.invoke(doctor)
        assert result.exit_code == 0
        self.assertGreaterEqual(len(cm.output), 10)

    # Migrated here from test_doctor.py
    # And skip this test, because test_doctor_cli() indirectly does the
    # expensive call to check_ipa_know_segs already so there is no value in
    # doing it a second time here.
    def not_test_ipa_known_segs_all(self):
        # This test simulates the innards of having called "g2p doctor" on the command
        # line with no arguments, again running the innards of doctor on all mappings.
        with self.assertLogs(LOGGER, level="WARNING") as cm:
            check_ipa_known_segs()
        self.assertGreaterEqual(len(cm.output), 20)


if __name__ == "__main__":
    main([__file__, *sys.argv])
