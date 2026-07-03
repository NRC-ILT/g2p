#!/usr/bin/env python

import sys
from unittest import TestCase

from pytest import main

from g2p.log import LOGGER
from g2p.mappings.langs.utils import check_ipa_known_segs


class DoctorTest(TestCase):
    def setUp(self):
        pass

    # the fra to fra-ipa mapping was fixed, this test no longer works
    def not_test_ipa_known_segs_fra(self):
        with self.assertLogs(LOGGER, level="WARNING") as cm:
            check_ipa_known_segs(["fra-ipa"])
        assert "vagon" in "".join(cm.output)
        assert "panphon" in "".join(cm.output)
        self.assertGreaterEqual(len(cm.output), 2)

    def test_ipa_known_segs_fra_fixed(self):
        assert check_ipa_known_segs(["fra-ipa"])

    def test_ipa_known_segs_alq(self):
        with self.assertLogs(LOGGER, level="WARNING") as cm:
            self.assertFalse(check_ipa_known_segs(["alq-ipa"]))
        assert "o:" in "".join(cm.output)
        assert "panphon" in "".join(cm.output)

    # this test takes 8 seconds and doesn't do anything useful: it trivially increases
    # code coverage but does not have enough assertions to catch a future code-breaking
    # change.
    # Migrated to test_doctor_expensive.py so we can still run it, manually or via
    # ./run.py all.
    def not_test_ipa_known_segs_all(self):
        with self.assertLogs(LOGGER, level="WARNING") as cm:
            check_ipa_known_segs()
        self.assertGreaterEqual(len(cm.output), 20)


if __name__ == "__main__":
    main([__file__, *sys.argv])
