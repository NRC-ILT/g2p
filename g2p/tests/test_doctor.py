#!/usr/bin/env python

import sys

from pytest import main

from g2p.log import LOGGER
from g2p.mappings.langs.utils import check_ipa_known_segs


class TestDoctor:
    # the fra to fra-ipa mapping was fixed, this test no longer works
    def not_test_ipa_known_segs_fra(self, caplog):
        with caplog.at_level("WARNING", logger=LOGGER.name):
            check_ipa_known_segs(["fra-ipa"])
        assert "vagon" in caplog.text
        assert "panphon" in caplog.text
        assert len(caplog.records) >= 2

    def test_ipa_known_segs_fra_fixed(self):
        assert check_ipa_known_segs(["fra-ipa"])

    def test_ipa_known_segs_alq(self, caplog):
        with caplog.at_level("WARNING", logger=LOGGER.name):
            assert not check_ipa_known_segs(["alq-ipa"])
        assert "o:" in caplog.text
        assert "panphon" in caplog.text

    # this test takes 8 seconds and doesn't do anything useful: it trivially increases
    # code coverage but does not have enough assertions to catch a future code-breaking
    # change.
    # Migrated to test_doctor_expensive.py so we can still run it, manually or via
    # ./run.py all.
    def not_test_ipa_known_segs_all(self, caplog):
        with caplog.at_level("WARNING", logger=LOGGER.name):
            check_ipa_known_segs()
        assert len(caplog.records) >= 20


if __name__ == "__main__":
    main([__file__, *sys.argv])
