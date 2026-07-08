#!/usr/bin/env python

"""
Test that the --config switch to g2p convert works

This test modifies the g2p database in memory, so it's important that it get
run last, in order to avoid changing the results of other unit test cases.

This file is also the right place to include other tests that make use of --config
to exercise different things.

We accomplish that in two ways:
 - in "./run.py dev", it gets appended after all the other tests, explicitly.
 - the file name has a "z" so it sorts last when "./run.py all" uses LOADER.discover()
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml
from click.testing import CliRunner
from pytest import fixture, main, raises

from g2p import exceptions
from g2p.cli import convert, generate_mapping
from g2p.mappings import Mapping
from g2p.mappings.utils import normalize
from g2p.tests.public import PUBLIC_DIR

MAPPINGS_DIR = Path(PUBLIC_DIR) / "mappings"


class TestLocalConfig:
    @fixture(autouse=True)
    def setup(self):
        self.runner = CliRunner()

    def test_local_config(self) -> None:
        config_path = str(MAPPINGS_DIR / "test.yaml")
        result = self.runner.invoke(
            convert,
            [
                "bbbb",
                "local-config-in",
                "local-config-out",
                "--config",
                config_path,
            ],
        )
        assert "aaaa" in result.stdout
        result = self.runner.invoke(
            convert,
            [
                "b",
                "local-config-in",
                "eng-ipa",
                "--config",
                config_path,
            ],
        )
        assert "ɑ" in result.stdout

    def test_case_insensitive_tokenizer(self) -> None:
        # Unit testing for https://github.com/ReadAlongs/Studio/issues/40
        # That issue was raised in Studio when the tokenizer was there, but
        # the tokenizer has been migrated to g2p since then, so the test and
        # fix belong here in g2p.

        # This test incidentally exercises passing --config a config file with
        # only one mapping in it, without the top-level "mappings:" list.
        tok_config = str(MAPPINGS_DIR / "tokenize_punct_config-g2p.yaml")
        results = self.runner.invoke(
            convert, ["--tok", "--config", tok_config, "AAA-BBB", "tok-in", "tok-out"]
        )
        assert results.exit_code == 0
        assert "aac_dbb" in results.output

        # While "AAA-BBB" gets tokenized as [word("AAA-BBB")], since "A-B" is
        # in the inventory, "D-C" gets tokenized as [word("D"), non-word("-"),
        # word("C")]. With rule D,d_end,,$, D will only become "d_end" if D is
        # at the end, which only occurs where we tokenize.
        results = self.runner.invoke(
            convert, ["--tok", "--config", tok_config, "D-C", "tok-in", "tok-out"]
        )
        assert results.exit_code == 0
        assert "d_end-c" in results.output

    def test_null_mapping(self) -> None:
        """Empty lines in a mapping should just get ignored"""
        # Unit test case for bug fix: as of 2021-12-01, an empty rule would
        # cause the next rule to not get its match pattern created, and raise
        # an exception later. The null.csv mapping has such an empty rule,
        # which should get ignored, with the next rule, d->e, still working.
        null_config = str(MAPPINGS_DIR / "null_config-g2p.yaml")
        results = self.runner.invoke(
            convert, ["--config", null_config, "x-ad-x", "null-in", "null-out"]
        )
        assert results.exit_code == 0
        assert "x-be-x" in results.output

    def test_case_feeding_mapping(self) -> None:
        """Exercise the mapping using case to prevent feeding on in/out but not context"""
        case_feeding_config = str(MAPPINGS_DIR / "case-feed" / "config-g2p.yaml")
        results = self.runner.invoke(
            convert,
            [
                "--config",
                case_feeding_config,
                "--tok",
                "ka-intinatin",
                "cf-in",
                "cf-out",
            ],
        )
        # print(results.output)
        assert results.exit_code == 0
        assert "ke-antinetin" in results.output

    def test_missing_files(self) -> None:
        """Nice error messages when the mapping file or abbreviations file are missing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "mapping-file-not-found.yaml")
            with open(config_file, "w", encoding="utf8") as f:
                yaml.dump({"mappings": [{"rules_path": "no-such-file.csv"}]}, f)
            results = self.runner.invoke(
                convert, ["--config", config_file, "a", "b", "c"]
            )
            assert results.exit_code != 0
            assert "No such file or directory" in results.output + str(
                results.exception
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "abbrev-file-not-found.yaml")
            with open(os.path.join(tmpdir, "tiny.csv"), "w", encoding="utf8") as f:
                f.write("a,b\n")
            with open(config_file, "w", encoding="utf8") as f:
                yaml.dump(
                    {
                        "mappings": [
                            {
                                "rules_path": "tiny.csv",
                                "abbreviations_path": "no-such-file.csv",
                            }
                        ]
                    },
                    f,
                )
            results = self.runner.invoke(
                convert, ["--config", config_file, "a", "b", "c"]
            )
            assert results.exit_code != 0
            assert "No such file or directory" in results.output + str(
                results.exception
            )

    def test_empty_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "empty-rules-file.yaml")
            with open(os.path.join(tmpdir, "empty.csv"), "w", encoding="utf8") as f:
                pass
            with open(config_file, "w", encoding="utf8") as f:
                yaml.dump({"mappings": [{"rules_path": "empty.csv"}]}, f)
            with raises(exceptions.MalformedMapping) as e:
                # This is a deep pydantic exception, we should raise MalformedMapping
                Mapping.load_mapping_from_path(config_file)
            assert "empty.csv does not contain any rules" in str(e.value)
            results = self.runner.invoke(
                convert, ["--config", config_file, "a", "b", "c"]
            )
            assert results.exit_code != 0
            assert "empty.csv does not contain any rules" in results.output + str(
                results.exception
            )

    def test_generate_mapping(self) -> None:
        """Use a local config to test generate mapping with --from and --to"""
        # This test is rather hacky, because it relies on the fact that calling
        # g2p convert --config loads a config and keeps it in memory for the rest
        # of the unit tests. While that's a potential bug for testing g2p update,
        # and the very reason this file is called test_z_..., forcing it to be
        # called last, we're using it as a feature here.

        # It would be better to have a proper function to load in additional
        # mappings from a given config file, but right now that's not
        # implemented, and I don't want to make that a requirement for testing
        # "g2p generate-mapping --from/--to", so it'll have to wait.
        # TODO: write a internal load_from_config() function, or some such, and
        # factor out the repeated code to use it.

        # This first case has the side effect of loading gen-map_config-g2p.yaml
        config_path = str(MAPPINGS_DIR / "gen-map_config-g2p.yaml")
        result = self.runner.invoke(
            convert, ["uyoesnmklbdt", "gm2", "gm2-ipa", "--config", config_path]
        )
        assert "uyɔɛsnmklbdt" in result.stdout
        # This second case confirms that gen-map_config-g2p.yaml is still loaded
        result = self.runner.invoke(convert, ["uyoesnmklbdt", "gm3a", "gm3-ipa"])
        assert "uyoesnmklbdt" in result.stdout

        # Now we do the real tests
        with tempfile.TemporaryDirectory() as output_dir_s:
            output_dir = Path(output_dir_s)
            # for debugging:
            # output_dir = Path(".") / "gen-map-tests"
            # output_dir.mkdir(exist_ok=True)
            # 1 mapping in to 1 mapping out
            result = self.runner.invoke(
                generate_mapping,
                ["--from", "gm1", "--to", "gm2", "--out-dir", output_dir_s],
            )
            assert result.exit_code == 0
            with open(MAPPINGS_DIR / "gm1-ipa_to_gm2-ipa.json") as f:
                ref = json.load(f)
            with open(output_dir / "gm1-ipa_to_gm2-ipa.json") as f:
                output = json.load(f)
            assert output == ref

            # 2 mappings in to 1 mapping out
            result = self.runner.invoke(
                generate_mapping,
                ["--from", "gm3", "--to", "gm2", "--out-dir", output_dir_s],
            )
            assert result.exit_code == 0
            with open(MAPPINGS_DIR / "gm3-ipa_to_gm2-ipa.json") as f:
                ref = json.load(f)
            with open(output_dir / "gm3-ipa_to_gm2-ipa.json") as f:
                output = json.load(f)
            assert output == ref

            # 1 mapping in to 2 mappings out
            result = self.runner.invoke(
                generate_mapping,
                ["--from", "gm2", "--to", "gm3", "--out-dir", output_dir_s],
            )
            assert result.exit_code == 0
            with open(MAPPINGS_DIR / "gm2-ipa_to_gm3-ipa.json") as f:
                ref = json.load(f)
            with open(output_dir / "gm2-ipa_to_gm3-ipa.json") as f:
                output = json.load(f)
            assert output == ref

    def test_compose_NFC_NFD(self) -> None:
        config_path = str(MAPPINGS_DIR / "compose.yaml")
        result = self.runner.invoke(
            convert,
            [
                normalize("é", "NFD"),
                "c1",
                "c3",
                "--no-tok",
                "--config",
                config_path,
                "-d",
                "-e",
            ],
        )
        assert result.exit_code == 0
        assert "[[(0, 0), (1, 0)], [(0, 0), (0, 1)]]" in result.output
        assert "[[('e', 'ò'), ('́', 'ò')], [('ò', 'u'), ('ò', '̀')]]" in result.output

        result = self.runner.invoke(
            convert,
            [
                normalize("é", "NFC"),
                "c1",
                "c3",
                "--no-tok",
                "--config",
                config_path,
                "-d",
                "-e",
            ],
        )
        assert result.exit_code == 0
        assert "[[(0, 0)], [(0, 0), (0, 1)]]" in result.output
        assert "[[('é', 'ò')], [('ò', 'u'), ('ò', '̀')]]" in result.output

    def test_nofeed_indices(self) -> None:
        config_path = str(MAPPINGS_DIR / "nofeed-indices.yaml")
        args = ("nofeed-indices-in", "nofeed-indices-out")
        result = self.runner.invoke(convert, ["ab", *args, "--config", config_path])
        assert "ced" in result.stdout
        result = self.runner.invoke(convert, ["abft", *args, "-d"])
        assert "cedft" in result.stdout
        result = self.runner.invoke(convert, ["deft", *args, "-d"])
        assert "ghit" in result.stdout
        result = self.runner.invoke(convert, ["aātaāabtaā", *args, "-e"])
        assert "aʼataʼacedtaʼa" in result.stdout

    def test_invalid_abbrev_path(self) -> None:
        config = """
            mappings:
             - name: "invalid"
               abbreviations_path: {}
               rules: []
        """
        with tempfile.TemporaryDirectory() as tmpdir_s:
            tmpdir = Path(tmpdir_s)
            # type bool is not valid
            with open(tmpdir / "invalid.yaml", "w", encoding="utf8") as fh:
                fh.write(config.format("true"))
            with raises(Exception) as e:
                # Currently raise a deep pydantic exception, exceptions.MalformedMapping would be better
                Mapping.load_mapping_from_path(tmpdir / "invalid.yaml")
            assert re.search(
                r"(?s)abbreviations_path.*Input is not a valid path", str(e.value)
            )

            # type float is not valid
            with open(tmpdir / "invalid.yaml", "w", encoding="utf8") as fh:
                fh.write(config.format("1.0"))
            with raises(Exception) as e:
                # Currently raise a deep pydantic exception, exceptions.MalformedMapping would be better
                Mapping.load_mapping_from_path(tmpdir / "invalid.yaml")
            assert re.search(
                r"(?s)abbreviations_path.*Input is not a valid path", str(e.value)
            )

            # non-existent file
            with open(tmpdir / "invalid.yaml", "w", encoding="utf8") as fh:
                fh.write(config.format("file_not_found.csv"))
            # This is super unfriendly to the user, but that's what happens now.
            with raises(FileNotFoundError):
                Mapping.load_mapping_from_path(tmpdir / "invalid.yaml")


if __name__ == "__main__":
    main([__file__, *sys.argv])
