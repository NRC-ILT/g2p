#!/usr/bin/env python

"""Organize tests into Test Suites

Run with "python run.py <suite>" where <suite> can be all, dev, or slow.

Add --describe to list the contents of the selected suite instead of running it.

Note: this script is no longer the recommended way to run the tests -- instead,
use pytest -- but it is still supported and should never be deprecated since it
is mentioned in the 7-part blog post.
"""

import argparse
import io
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pytest

# Unit tests
from g2p.log import LOGGER


@dataclass
class Suite:
    tests: List[str]
    description: str


SUITES: Dict[str, Suite] = {
    "all": Suite([], "all tests, using pytest discovery"),  # empty list => discovery
    "dev": Suite([], "all but the slow tests"),  # subtractive logic: dev = all - slow
    # "langs" required because part 7 of the 7-part blog mentions it
    "langs": Suite(["test_langs"], "language mapping tests"),
    "slow": Suite(["test_studio", "test_neural"], "slow tests"),
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
        suite = "dev"

    if suite not in SUITES:
        LOGGER.error("Please specify a test suite to run among: " + ", ".join(SUITES))
        return False

    LOGGER.info(f"Running suite '{suite}': {SUITES[suite].description}")

    tests_dir = Path(__file__).parent
    if suite == "dev":
        expensive_files = [tests_dir / f"{file}.py" for file in SUITES["slow"].tests]
        test_suite_filenames = [
            str(file)
            for file in tests_dir.glob("test*.py")
            if file not in expensive_files
        ]
    else:
        test_suite = SUITES[suite].tests
        test_suite_filenames = [str(tests_dir / f"{file}.py") for file in test_suite]

    if describe:
        describe_suite(suite, test_suite_filenames)
        return True
    else:
        pytest_args = ["--verbose"] if verbose else []
        return 0 == pytest.main([*test_suite_filenames, *pytest_args])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run g2p test suites.\nNote: while this script is still supported, we now recommend using pytest instead.\n\nSuites:\n"
        + "\n".join(
            " - " + name + ": " + suite.description for name, suite in SUITES.items()
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
