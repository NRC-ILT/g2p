#!/usr/bin/env python

import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent
from unittest import mock

import jsonschema
import pydantic
import pytest
import yaml
from click.testing import CliRunner

import g2p._version
from g2p.cli import (
    convert,
    doctor,
    generate_mapping,
    scan,
    show_mappings,
    update,
    update_schema,
)
from g2p.exceptions import NeuralDependencyError
from g2p.log import LOGGER
from g2p.mappings import MappingConfig
from g2p.mappings.langs import (
    LANGS_DIR,
    LANGS_FILE_NAME,
    NETWORK_FILE_NAME,
    load_langs,
    load_network,
)
from g2p.tests.public.data import DATA_DIR, load_public_test_data


def set_g2p_version(version_tuple, version_string=None):
    if version_string is None:
        version_string = ".".join(str(part) for part in version_tuple)
    g2p._version.VERSION = g2p._version.__version__ = g2p._version.version = (
        version_string
    )
    g2p._version.__version_tuple__ = g2p._version.version_tuple = tuple(version_tuple)


def relaxed_int(int_or_str) -> int:
    """Parse a version component returning only its numerical prefix.

    Motivation: in CI, sometimes we end up with a version like 2.3.dev0
    E.g.: 42 -> 42, 1dev2 -> 1, dev -> 0
    """
    if isinstance(int_or_str, int):
        return int_or_str
    m = re.search(r"^[0-9]+", int_or_str)
    return int(m.group()) if m else 0


@contextmanager
def monkey_patch_g2p_version(increment_tuple):
    saved_version = g2p._version.VERSION
    saved_version_tuple = g2p._version.version_tuple
    incremented_version = list(g2p._version.version_tuple)
    while len(incremented_version) < len(increment_tuple):
        incremented_version.append(0)
    for part, increment in enumerate(increment_tuple):
        incremented_version[part] = relaxed_int(incremented_version[part]) + increment
    set_g2p_version(incremented_version)
    yield
    set_g2p_version(saved_version_tuple, saved_version)


class TestCli:
    """Test suite for the g2p Command Line Interface"""

    @pytest.fixture(autouse=True)
    def setup_runner(self):
        self.runner = CliRunner()

    def test_update(self, caplog):
        result = self.runner.invoke(update)

        # Test running in another directory
        with tempfile.TemporaryDirectory() as tmpdir:
            lang1_dir = os.path.join(tmpdir, "lang1")
            os.mkdir(lang1_dir)
            mappings_dir = os.path.join(DATA_DIR, "..", "mappings")
            for name in os.listdir(mappings_dir):
                if name.startswith("minimal."):
                    shutil.copy(
                        os.path.join(mappings_dir, name), os.path.join(lang1_dir, name)
                    )
            shutil.copy(
                os.path.join(mappings_dir, "minimal_configs.yaml"),
                os.path.join(lang1_dir, "config-g2p.yaml"),
            )
            result = self.runner.invoke(update, ["-i", tmpdir])
            langs_json = os.path.join(tmpdir, LANGS_FILE_NAME)
            network_pkl = os.path.join(tmpdir, NETWORK_FILE_NAME)
            assert os.path.exists(langs_json)
            assert os.path.exists(network_pkl)

        # Make sure it produces output
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(update, ["-o", tmpdir])
            assert result.exit_code == 0
            langs_json = os.path.join(tmpdir, LANGS_FILE_NAME)
            network_pkl = os.path.join(tmpdir, NETWORK_FILE_NAME)
            assert os.path.exists(langs_json)
            assert os.path.exists(network_pkl)
            langs = load_langs(langs_json)
            assert langs is not None
            network = load_network(network_pkl)
            assert network is not None

            # Corrupt the output and make sure we still can run
            with open(langs_json, "wb") as fh:
                fh.write(b"spam spam spam")
            with open(network_pkl, "wb") as fh:
                fh.write(b"eggs bacon spam")

            with caplog.at_level("WARNING", logger=LOGGER.name):
                langs = load_langs(langs_json)
            assert langs is not None

            with caplog.at_level("WARNING", logger=LOGGER.name):
                network = load_network(network_pkl)
            assert network is not None

        # Make sure it fails meaningfully on invalid input
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_langs_dir = os.path.join(DATA_DIR, "..", "mappings", "bad_langs")
            result = self.runner.invoke(update, ["-i", bad_langs_dir, "-o", tmpdir])
            assert result.exit_code != 0
            assert "mappings" in str(result.exception)

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_langs_dir = os.path.join(DATA_DIR, "..", "mappings", "bad_langs2")
            result = self.runner.invoke(update, ["-i", bad_langs_dir, "-o", tmpdir])
            assert result.exit_code == 0

    def test_update_schema_with_pydantic_lt29(self):
        """Make sure schema update works (requires Pydantic<2.9)"""

        # Skip this test if the currently installed pydantic version is >= 2.9
        pydantic_major, pydantic_minor, _ = pydantic.VERSION.split(".", 3)
        if (int(pydantic_major), int(pydantic_minor)) >= (2, 9):
            # With Pydantic>=2.9, we cannot update the schemas, instead we
            # expect an error message telling us to use an older version
            result = self.runner.invoke(update_schema)
            assert result.exit_code == 0
            assert "Please use Pydantic" in result.output
            LOGGER.info(
                "Skipping the rest of the schema update test since we have pydantic>=2.9"
            )
            return  # skip the rest of the test

        # The rest of this test can assume pydantic<2.9 is installed.

        # It's an error for the currently saved schema to be out of date
        result = self.runner.invoke(update_schema)
        assert result.exit_code == 0
        assert "up to date" in result.output

        with tempfile.TemporaryDirectory() as tmpdir:
            # Exercise writing a new schema to disk even if up to date
            result = self.runner.invoke(update_schema, ["-o", tmpdir])
            assert result.exit_code == 0
            assert "Wrote" in result.output

            # Reload the written schema for further unit tests
            major, minor, *_rest = g2p._version.version_tuple
            major_minor = f"{major}.{minor}"
            with open(
                Path(tmpdir) / f"g2p-config-schema-{major_minor}.json",
                encoding="utf8",
            ) as f:
                schema = json.load(f)

            # A second run will necessarily already be up to date even if the patch is bumped
            with monkey_patch_g2p_version((0, 0, +1)):
                result_rerun = self.runner.invoke(update_schema, ["-o", tmpdir])
                assert result_rerun.exit_code == 0
                assert "already up to date" in result_rerun.output

            # Monkey patch the version to test a previous version still being up to date
            with monkey_patch_g2p_version((+0, +1)):
                result_new = self.runner.invoke(update_schema, ["-o", tmpdir])
                assert result_new.exit_code == 0
                assert "still up to date" in result_new.output

            # Monkey patch the version and the model to require a schema update
            with monkey_patch_g2p_version((+1, +0)):
                saved_doc = MappingConfig.__doc__
                MappingConfig.__doc__ = "Changed docstring"
                result_update = self.runner.invoke(update_schema, ["-o", tmpdir])
                MappingConfig.__doc__ = saved_doc
                assert result_update.exit_code == 0
                assert "Wrote" in result_update.output

            # Require a schema update when it's already written: that's an error
            with monkey_patch_g2p_version((+1, +0)):
                result_bad_update = self.runner.invoke(update_schema, ["-o", tmpdir])
                assert result_bad_update.exit_code != 0
                assert "but is not up to date" in result_bad_update.output

        # Validate all configurations against the current schema, quietly unless there's an error:
        for config in Path(LANGS_DIR).glob("**/config-g2p.yaml"):
            with open(config, encoding="utf8") as f:
                config_yaml = yaml.safe_load(f)
            try:
                jsonschema.validate(config_yaml, schema=schema)
            except jsonschema.exceptions.ValidationError as e:
                pytest.fail(f"Error validating {config}: {e}")

    def test_convert(self):
        """Running all g2p convert test cases found in g2p/tests/public/data"""
        langs_to_test = load_public_test_data()
        error_count = 0
        first_failed_test = None

        for tok_option in [["--tok", "--check"], ["--no-tok"]]:
            for (
                in_lang,
                out_lang,
                word_to_convert,
                reference_string,
                *_,
                fileline,
            ) in langs_to_test:
                result = self.runner.invoke(
                    convert, [*tok_option, word_to_convert, in_lang, out_lang]
                )
                assert result.exit_code == 0
                if "--no-tok" not in tok_option:
                    output_string = result.stdout.strip()
                    if reference_string.strip() not in output_string:
                        LOGGER.warning(
                            f"test_cli.py for {fileline}: {in_lang}->{out_lang} mapping error: '{word_to_convert}' "
                            f"should map to '{reference_string}', got '{output_string}' (with {tok_option})."
                        )
                        if error_count == 0:
                            first_failed_test = (
                                in_lang,
                                out_lang,
                                word_to_convert,
                                tok_option,
                                reference_string,
                            )
                        error_count += 1

        if error_count > 0:
            assert first_failed_test is not None
            (
                in_lang,
                out_lang,
                word_to_convert,
                tok_option,
                reference_string,
            ) = first_failed_test
            output_string = self.runner.invoke(
                convert,
                [*tok_option, word_to_convert, in_lang, out_lang],
            ).stdout.strip()

            assert output_string == reference_string.strip(), (
                f"{in_lang}->{out_lang} mapping error for '{word_to_convert}'.\n"
                "Look for warnings in the log for any more mapping errors"
            )

    def test_convert_neural(self):
        with mock.patch("g2p.mappings.utils.has_neural_support", return_value=False):
            with pytest.raises(NeuralDependencyError):
                result = self.runner.invoke(
                    convert, ["--neural", "hello world", "str", "str-ipa"]
                )
                raise result.exception  # type: ignore[misc]

    def test_doctor(self):
        result = self.runner.invoke(doctor, "-m fra")
        assert result.exit_code == 2

        result = self.runner.invoke(doctor, "-m fra-ipa")
        assert result.exit_code == 0

        # Disable this test: it's very slow (8s, just by itself) and does not assert
        # anything useful.
        # Migrated to test_doctor_expensive.py so we can still run it, manually or via
        # ./run.py all.
        # result = self.runner.invoke(doctor)
        # assert result.exit_code == 0
        # assert len(result.stdout) >= 10000

        result = self.runner.invoke(doctor, "-m eng-arpabet")
        assert result.exit_code == 0
        assert "No checks implemented" in result.output

    def test_doctor_lists(self):
        result = self.runner.invoke(doctor, "--list-all")
        assert result.exit_code == 0
        assert "eng-arpabet:" in result.stdout
        assert "eng-ipa:" in result.stdout

        result = self.runner.invoke(doctor, "--list-ipa")
        assert result.exit_code == 0
        assert "eng-arpabet:" not in result.stdout
        assert "eng-ipa:" in result.stdout

    def test_scan_fra(self, caplog):
        """Test g2p scan with all French characters, in NFC and NFD"""
        for paragram_file in ["fra_panagrams.txt", "fra_panagrams_NFD.txt"]:
            with caplog.at_level("WARNING", logger=LOGGER.name):
                result = self.runner.invoke(
                    scan, ["fra", os.path.join(DATA_DIR, paragram_file)]
                )
            assert result.exit_code == 0
            diacritics = "àâéèêëîïôùûüç"
            for d in diacritics:
                assert d not in result.stdout
            unmapped_chars = ":/,'-()2"
            for c in unmapped_chars:
                assert c in result.stdout

    def test_scan_fra_simple(self, caplog):
        # Unit test g2p scan using a simpler piece of French
        with caplog.at_level("WARNING", logger=LOGGER.name):
            result = self.runner.invoke(
                scan, ["fra", os.path.join(DATA_DIR, "fra_simple.txt")]
            )
        assert result.exit_code == 0
        diacritics = "àâéèêëîïôùûüç"
        for d in diacritics:
            assert d not in result.stdout
        unmapped_chars = ":,"
        for c in unmapped_chars:
            assert c in result.stdout

    def test_scan_str_case(self, caplog) -> None:
        with caplog.at_level("WARNING", logger=LOGGER.name):
            result = self.runner.invoke(
                scan, ["str", os.path.join(DATA_DIR, "str_un_human_rights.txt")]
            )
        returned_set = re.search("{(.*)}", result.stdout).group(1)  # type: ignore
        assert result.exit_code == 0

        unmapped_upper = "FGR"
        for u in unmapped_upper:
            assert u in returned_set

        unmapped_lower = "abcdefghijklqrtwxyz"
        for low in unmapped_lower:
            assert low in returned_set

        mapped_upper = "ABCDEHIJKLMNOPQSTUVWXYZ"
        for u in mapped_upper:
            assert u not in returned_set

        mapped_lower = "s"
        assert mapped_lower not in returned_set

    def test_scan_err(self):
        results = self.runner.invoke(
            scan, ["bad_lang", os.path.join(DATA_DIR, "fra_simple.txt")]
        )
        assert results.exit_code != 0
        assert "is not a valid value for 'LANG'" in results.output

    def test_convert_option_a(self):
        result = self.runner.invoke(convert, "-a hello eng eng-arpabet")
        assert (
            "[('h', 'HH '), ('e', 'AH '), ('ll', 'L '), ('o', 'OW ')]" in result.stdout
        )

    def test_convert_option_e(self):
        result = self.runner.invoke(convert, "-e est fra eng-arpabet")
        for s in [
            "[('e', 'ɛ'), ('s', 'ɛ'), ('t', 'ɛ')]",
            "[('ɛ', 'ɛ')]",
            "[('ɛ', 'E'), ('ɛ', 'H'), ('ɛ', ' ')]",
        ]:
            assert s in result.stdout

    def test_convert_option_d(self):
        result = self.runner.invoke(convert, "-d est fra eng-arpabet")
        for s in ["'input': 'est'", "'output': 'ɛ'", "'input': 'ɛ'", "'output': 'EH '"]:
            assert s in result.stdout

    def test_convert_option_t(self):
        result = self.runner.invoke(convert, "-t e\\'i oji oji-ipa")
        assert "eːʔi" in result.stdout

    def test_convert_option_tl(self):
        result = self.runner.invoke(convert, "--tok-lang fra e\\'i oji oji-ipa")
        assert "eː'i" in result.stdout

    def test_generate_mapping_config(self):
        """Ensure that generate-mapping creates valid configuration."""
        # The underlying create_mapping() function is tested in
        # test_create_mapping.py, and align_to_dummy_fallback() in
        # test_fallback.py, with less expensive inputs than our real
        # g2p mappings, and with predictable results.  However, we do
        # need to ensure that it creates/updates a correct
        # configuration, so we test that here.
        with tempfile.TemporaryDirectory() as tmpdir:
            results = self.runner.invoke(
                generate_mapping, ["--ipa", "atj", "--out-dir", tmpdir]
            )
            assert results.exit_code == 0
            rulespath = os.path.join(tmpdir, "atj-ipa_to_eng-ipa.json")
            assert os.path.exists(rulespath)
            confpath = os.path.join(tmpdir, "config-g2p.yaml")
            config = MappingConfig.load_mapping_config_from_path(confpath)
            assert len(config.mappings) == 1
            assert config.mappings[0].rules_path == Path(rulespath)

            # Run it again, should get the same result
            results = self.runner.invoke(
                generate_mapping, ["--ipa", "atj", "--out-dir", tmpdir]
            )
            assert results.exit_code == 0
            config = MappingConfig.load_mapping_config_from_path(confpath)
            assert len(config.mappings) == 1
            assert config.mappings[0].rules_path == Path(rulespath)

            # Run it with a different language, should get more config
            results = self.runner.invoke(
                generate_mapping, ["--ipa", "alq", "--out-dir", tmpdir]
            )
            assert results.exit_code == 0
            config = MappingConfig.load_mapping_config_from_path(confpath)
            assert len(config.mappings) == 2

    def test_generate_mapping_errors(self):
        """Exercise various error situations with the g2p generate-mapping CLI command"""

        results = self.runner.invoke(generate_mapping)
        assert results.exit_code != 0
        assert "Nothing to do" in results.output

        results = self.runner.invoke(generate_mapping, "--ipa")
        assert results.exit_code != 0
        assert "Missing argument" in results.output

        results = self.runner.invoke(generate_mapping, "fra")
        assert results.exit_code != 0
        assert (
            "Nothing to do" in results.output
        ), '"g2p generate-mapping fra" should say need --ipa or --dummy or --list-dummy'

        results = self.runner.invoke(generate_mapping, "--ipa foo")
        assert results.exit_code != 0
        assert "Invalid value for IN_LANG" in results.output

        results = self.runner.invoke(generate_mapping, "--dummy fra foo")
        assert results.exit_code != 0
        assert "Invalid value for OUT_LANG" in results.output

        results = self.runner.invoke(generate_mapping, "--ipa crl")
        assert results.exit_code != 0
        assert "Cannot find IPA mapping" in results.output

        results = self.runner.invoke(generate_mapping, "--ipa fra dan-ipa")
        assert results.exit_code != 0
        assert "Cannot find IPA mapping" in results.output

        results = self.runner.invoke(generate_mapping, "--list-dummy")
        assert results.exit_code == 0  # this one not an error
        assert "Dummy phone inventory" in results.output

        results = self.runner.invoke(generate_mapping, "--list-dummy fra")
        assert results.exit_code != 0
        assert "IN_LANG is not allowed with --list-dummy" in results.output

        results = self.runner.invoke(generate_mapping, "--ipa --dummy fra")
        assert results.exit_code != 0
        assert "Error: Multiple modes selected" in results.output

        results = self.runner.invoke(
            generate_mapping, "--out-dir does-not-exist --ipa fra"
        )
        assert results.exit_code != 0
        assert (
            "does not exist" in results.output
        ), "Non-existent out-dir must be reported as error"

        results = self.runner.invoke(generate_mapping, "--from asdf")
        assert results.exit_code != 0
        assert "Error: --from and --to must be used together" in results.output

        results = self.runner.invoke(
            generate_mapping, "--from fra_to_fra-ipa --to haa_to_haa-equiv"
        )
        assert results.exit_code != 0
        assert "Cannot guess in/out for IPA lang spec" in results.output

        results = self.runner.invoke(generate_mapping, "--from eng --to fra[out]")
        assert results.exit_code != 0
        assert "is only supported with the full" in results.output

        results = self.runner.invoke(
            generate_mapping, "--from fra_to_fra-ipa[foo] --to eng"
        )
        assert results.exit_code != 0
        assert "is allowed in square brackets" in results.output

        results = self.runner.invoke(generate_mapping, "--from fra_to_eng --to eng")
        assert results.exit_code != 0
        assert "Cannot find mapping" in results.output

        results = self.runner.invoke(generate_mapping, "--merge --from fra --to eng")
        assert results.exit_code != 0
        assert "--merge is only compatible with --ipa and --dummy" in results.output

        results = self.runner.invoke(generate_mapping, "--merge --ipa fra")
        assert results.exit_code != 0
        assert "OUT_LANG is required with --merge" in results.output

        results = self.runner.invoke(
            generate_mapping, "--ipa --out-dir foo_bar_baz fra"
        )
        assert results.exit_code != 0
        assert "Invalid value for '--out-dir': Directory" in results.output

    def test_show_mappings(self):
        # One arg = all mappings to or from that language
        results = self.runner.invoke(show_mappings, ["fra-ipa", "--verbose"])
        assert results.exit_code == 0
        assert "French to IPA" in results.output
        assert "French IPA to English IPA" in results.output
        assert len(re.findall(r"display_name", results.output)) == 3

        # One arg = all mappings to or from that language, terse output
        results = self.runner.invoke(show_mappings, ["fra-ipa"])
        assert results.exit_code == 0
        assert "fra-ipa" in results.output
        assert "eng-ipa" in results.output
        assert len(re.findall(r"→", results.output)) == 3
        # including descendants
        assert "eng-arpabet" in results.output
        fra_output = dedent(
            """\
            1: fra → fra-ipa  (French to IPA)
            2: fra-ipa → eng-ipa  (French IPA to English IPA)
            3: eng-ipa → eng-arpabet  (English IPA to Arpabet)
            """
        )
        assert fra_output in results.output

        # Topological ordering for one arg gives same result from fra and fra-ipa
        results = self.runner.invoke(show_mappings, ["fra"])
        assert results.exit_code == 0
        assert fra_output in results.output

        # Two conencted args = that mapping
        results = self.runner.invoke(show_mappings, ["fra", "fra-ipa", "--verbose"])
        assert results.exit_code == 0
        assert "French to IPA" in results.output
        assert r'{"in": "&", "out": "et"},' in results.output
        assert (
            r'{"in": "c", "out": "s", "context_after": "e|i|è|é|ê|ë|î|ï|ÿ"},'
            in results.output
        )
        assert (
            r'{"in": "e", "out": "", "context_before": "\\S", "context_after": "\\b"},'
            in results.output
        )
        assert len(re.findall(r"display_name", results.output)) == 1

        # Two args connected via a intermediate steps = all mappings on that path
        results = self.runner.invoke(show_mappings, ["fra", "eng-arpabet", "--verbose"])
        assert results.exit_code == 0
        assert "French to IPA" in results.output
        assert "French IPA to English IPA" in results.output
        assert "English IPA to Arpabet" in results.output
        assert len(re.findall(r"display_name", results.output)) == 3

        # --all = all mappings
        results = self.runner.invoke(show_mappings, [])
        assert results.exit_code == 0
        assert len(re.findall(r"→", results.output)) > 100

        # --csv = CSV formatted output
        results = self.runner.invoke(show_mappings, ["--csv", "crl-equiv", "--verbose"])
        assert results.exit_code == 0
        assert "Northern East Cree Equivalencies" in results.output
        assert "thwaa,ᕨ,," in results.output
        assert "Northern East Cree to IPA" in results.output
        assert "ᐧᕓ,vʷeː,," in results.output

        # Bad language code
        results = self.runner.invoke(show_mappings, ["not-a-lang"])
        assert results.exit_code != 0
        assert "No language called" in results.output
        results = self.runner.invoke(show_mappings, ["fra", "not-a-lang"])
        assert results.exit_code != 0
        assert "No language called" in results.output

        # No path
        results = self.runner.invoke(show_mappings, ["fra", "moe"])
        assert results.exit_code != 0
        assert "Cannot find mapping from" in results.output

    def test_convert_from_file(self, caplog):
        input_file = os.path.join(DATA_DIR, "fra_simple.txt")
        results = self.runner.invoke(convert, [input_file, "fra", "fra-ipa", "--file"])
        assert results.exit_code == 0
        assert "fʁɑ̃sɛ" in results.output

        with open(input_file, encoding="utf8") as f:
            lines_in = len(list(f))
        # Make sure there is no resource warning about unclosed files
        assert "ResourceWarning" not in results.output
        assert "unclosed file" not in results.output
        # The output should have the same number of lines as the input
        assert lines_in == len(results.output.splitlines())

        # - is stdin
        results = self.runner.invoke(
            convert, ["--file", "-", "fra", "fra-ipa"], input="français"
        )
        assert results.exit_code == 0
        assert "fʁɑ̃sɛ" in results.output

        # warning about deprecated heuristic file detection
        with caplog.at_level("WARNING", logger=LOGGER.name):
            self.runner.invoke(convert, [input_file, "fra", "fra-ipa"])
        assert "deprecated" in "".join(caplog.messages)

        # Error for --file with non existent file
        results = self.runner.invoke(
            convert, ["does_not_exist.txt", "fra", "fra-ipa", "--file"]
        )
        assert results.exit_code != 0
        assert "No such file or directory" in results.output

    def test_convert_errors(self):
        """Exercise code handling error situations in g2p convert"""
        results = self.runner.invoke(convert, "asdf bad_in_lang eng-ipa")
        assert results.exit_code != 0
        assert "not a valid value for 'IN_LANG'" in results.output

        results = self.runner.invoke(convert, "asdf fra bad_out_lang")
        assert results.exit_code != 0
        assert "not a valid value for 'OUT_LANG'" in results.output

        results = self.runner.invoke(convert, "asdf fra dan")
        assert results.exit_code != 0
        assert "Path between" in results.output
        assert "does not exist" in results.output

        results = self.runner.invoke(
            convert, "--no-tok --tok-lang fra asdf fra fra-ipa"
        )
        assert results.exit_code != 0
        assert "Specified conflicting --no-tok and --tok-lang options" in results.output

    def test_short_dash_h(self):
        results_short = self.runner.invoke(convert, "-h")
        assert results_short.exit_code == 0
        assert "Show this message and exit" in results_short.output

        results_long = self.runner.invoke(convert, "--help")
        assert results_long.exit_code == 0
        assert results_short.output == results_long.output

    def test_generate_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(
                generate_mapping, ["--ipa", "--out-dir", tmpdir, "fra"]
            )
            assert result.exit_code == 0
            with open(
                os.path.join(tmpdir, "fra-ipa_to_eng-ipa.json"), encoding="utf8"
            ) as f:
                fra2eng_ipa = json.load(f)
            for s in ("ɛj", "ks", "ɔn"):
                assert {"in": s, "out": s} in fra2eng_ipa

    def test_generate_mapping_dummy(self):
        """Create a dummy mapping in a specified outdir"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(
                generate_mapping, ["--dummy", "--out-dir", tmpdir, "fra"]
            )
            assert result.exit_code == 0
            assert (Path(tmpdir) / "fra_to_dummy.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, *sys.argv])
