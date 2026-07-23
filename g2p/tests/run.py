#!/usr/bin/env python

"""Organize tests into Test Suites

Run with "python run.py <suite>" where <suite> can be all, dev, or slow.

Add --describe to list the contents of the selected suite instead of running it.
"""

import argparse
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Dict, List, Optional

import pytest

# Unit tests
from g2p.log import LOGGER

SUITES: Dict[str, List[str]] = {
    "all": [],  # empty list triggers complete test discovery
    "dev": [],  # subtractive logic: dev = all - slow
    "langs": ["test_langs"],  # kept here because part 7 of the 7-part blog mentions it
    "slow": ["test_studio", "test_neural"],
}


class PytestCollectorPlugin:
    def __init__(self):
        self.collected = []

    def pytest_collection_modifyitems(self, session, config, items):
        self.collected.extend([item.nodeid for item in items])


def list_tests(suite: List[str]):
    plugin = PytestCollectorPlugin()
    pytest_args = ["--collect-only", *suite, "-q"]
    if sys.version_info >= (3, 10):
        with redirect_stdout(io.StringIO()):  # broken with py 3.8/3.9...
            pytest.main(pytest_args, plugins=[plugin])
    else:
        pytest.main(pytest_args, plugins=[plugin])
    # print("===========\n", o.getvalue(), "\n================")
    return plugin.collected


def describe_suite(suite_name, suite_filenames: List[str]):
    full_list = list_tests([])
    requested_list = list_tests(suite_filenames)
    requested_set = set(requested_list)
    print(f"Test suite '{suite_name}' includes:", *sorted(requested_list), sep="\n")
    print(
        f"\nTest suite '{suite_name}' excludes:",
        *sorted(test for test in full_list if test not in requested_set),
        sep="\n",
    )
    print(
        "\nTotal test cases",
        f"found: {len(full_list)};",
        f"included: {len(requested_list)};",
        f"excluded: {len(full_list)-len(requested_list)}.",
    )


def run_tests(suite: Optional[str], describe=False, verbose=False) -> bool:
    """Run the test suite specified in suite.

    Args:
        suite: one of SUITES, "dev" if the empty string
        describe: if True, list all the test cases instead of running them.

    Returns: Bool: True iff success
    """
    if not suite:
        LOGGER.info(
            "No test suite specified, defaulting to 'dev', which skips the slow tests."
        )
        suite = "dev"

    if suite not in SUITES:
        LOGGER.error("Please specify a test suite to run among: " + ", ".join(SUITES))
        return False

    tests_dir = Path(__file__).parent
    if suite == "dev":
        expensive_files = [tests_dir / f"{file}.py" for file in SUITES["slow"]]
        test_suite_filenames = [
            str(file)
            for file in tests_dir.glob("test*.py")
            if file not in expensive_files
        ]
    else:
        test_suite = SUITES[suite]
        test_suite_filenames = [str(tests_dir / f"{file}.py") for file in test_suite]

    if describe:
        describe_suite(suite, test_suite_filenames)
        return True
    else:
        pytest_args = ["--verbose"] if verbose else []
        return 0 == pytest.main([*test_suite_filenames, *pytest_args])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run g2p test suites.")
    parser.add_argument("--verbose", "-v", action="store_true", help="verbose output")
    parser.add_argument(
        "--describe", action="store_true", help="describe the selected test suite"
    )
    parser.add_argument(
        "suite",
        nargs="?",
        help="the test suite to run [dev]",
        choices=SUITES.keys(),
    )
    args = parser.parse_args()
    result = run_tests(args.suite, args.describe, args.verbose)
    if not result:
        sys.exit(1)


if __name__ == "__main__":
    main()
