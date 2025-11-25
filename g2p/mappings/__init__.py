"""

Module for all things related to lookup tables

"""

import csv
import json
import os
import re
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Callable, Dict, List, Pattern, Union

import yaml
from pydantic import BaseModel

from g2p import exceptions
from g2p._version import version_tuple
from g2p.exceptions import NeuralDependencyError
from g2p.log import LOGGER
from g2p.mappings.langs import _LANGS, _MAPPINGS_AVAILABLE
from g2p.mappings.langs import __file__ as LANGS_FILE
from g2p.mappings.utils import (
    MAPPING_TYPE,
    NORM_FORM_ENUM,
    RULE_ORDERING_ENUM,
    CompactJSONMappingEncoder,
    IndentDumper,
    Rule,
    _MappingModelDefinition,
    create_fixed_width_lookbehind,
    escape_special_characters,
    expand_abbreviations,
    has_neural_support,
    load_abbreviations_from_file,
    load_alignments_from_file,
    load_from_file,
    normalize,
    strip_index_notation,
)

GEN_DIR = os.path.join(os.path.dirname(LANGS_FILE), "generated")


class Mapping(_MappingModelDefinition):
    """Class for lookup tables"""

    def model_post_init(self, *_args, **_kwargs) -> None:
        """After the model is constructed, we process the model specs by
        applying all the configuration to the rules (ie prevent feeding,
        unicode normalization etc..)"""

        if self.type == MAPPING_TYPE.mapping or self.type is None:
            # load abbreviations from path
            if self.abbreviations_path is not None and not self.abbreviations:
                self.abbreviations = load_abbreviations_from_file(
                    self.abbreviations_path
                )
            # load rules from path
            if self.rules_path is not None and not self.rules:
                # make sure self.rules is always a List[Rule] like we say it is!
                self.rules = [Rule(**obj) for obj in load_from_file(self.rules_path)]
            # Process the rules, keeping only non-empty ones, and
            # expanding abbreviations.  This is also required so that
            # we don't keep escaping special characters for example
            self.rules = self.process_model_specs()
        elif self.type == MAPPING_TYPE.lexicon:
            # load alignments from path
            if self.alignments_path is not None and not self.alignments:
                self.alignments = load_alignments_from_file(self.alignments_path)
        else:
            self.rules = []

    @staticmethod
    def find_mapping(
        in_lang: Union[None, str] = None,
        out_lang: Union[None, str] = None,
        neural: bool = False,
    ) -> "Mapping":
        """Given an input and an output language, find a mapping to get between them."""
        # Early checking for if neural is available:
        if neural and not has_neural_support():
            raise NeuralDependencyError()

        if in_lang is None or out_lang is None:
            raise exceptions.MappingMissing(in_lang, out_lang)
        fallback_mapping = None
        for mapping in MAPPINGS_AVAILABLE:
            # Don't return a neural mapping if neural is False
            if not neural and mapping.type == MAPPING_TYPE.neural:
                continue
            if mapping.in_lang == in_lang and mapping.out_lang == out_lang:
                if neural and mapping.type == MAPPING_TYPE.neural:
                    return deepcopy(mapping)
                if mapping.type == MAPPING_TYPE.lexicon:
                    # do *not* deep copy this, because alignments are big!
                    fallback_mapping = mapping.model_copy()
                else:
                    fallback_mapping = deepcopy(mapping)

        if fallback_mapping is None:
            raise exceptions.MappingMissing(in_lang, out_lang)
        else:
            return fallback_mapping

    @staticmethod
    def find_mapping_by_id(map_id: str) -> "Mapping":
        """Find the mapping with a given ID, i.e., the "id" found in the
        mapping, like in the "panphon_preprocessor" mapping."""
        for mapping in MAPPINGS_AVAILABLE:
            if mapping.id == map_id:
                return deepcopy(mapping)
        raise exceptions.MappingMissing(map_id, None)

    @staticmethod
    def load_mapping_from_path(path_to_mapping_config: Union[str, Path], index=0):
        """Loads a mapping from a path, if there is more than one mapping,
        then it loads based on the int provided to the 'index'
        argument. Default is 0."""
        mapping_config = MappingConfig.load_mapping_config_from_path(
            path_to_mapping_config
        )
        return mapping_config.mappings[index]

    @staticmethod
    def _string_to_pua(string: str, offset: int) -> str:
        """Given an string of length n, and an offset m,
           produce a string of n * chr(983040 + m).
           This makes use of the Supplementary Private Use Area A Unicode block.

        Args:
            string (str): The string to convert
            offset (int): The offset from the start of the Supplementary Private Use Area

        Returns:
            str: The resulting string
        """
        intermediate_char = chr(983040 + offset)
        prev_end = 0
        result = ""
        for match in re.finditer(r"{\d+}|$", string):
            result += intermediate_char * (match.start() - prev_end) + match.group()
            prev_end = match.end()
        return result

    def index(self, item):
        """Find the location of an item in self"""
        return self.rules.index(item)

    def inventory(self, in_or_out: str = "in", non_empty: bool = False):
        """Return just inputs or outputs as inventory of mapping"""
        if in_or_out == "in":
            in_or_out = "rule_input"
        if in_or_out == "out":
            in_or_out = "rule_output"
        inv = [getattr(x, in_or_out) for x in self.rules]
        if non_empty:
            return [sym for sym in inv if sym != ""]
        else:
            return inv

    def plain_mapping(self):
        """Return the plain mapping for displaying or saving to disk.

        Args:
            skip_empty_contexts: when set, filter out empty context_before/after
        """
        return [rule.export_to_dict() for rule in self.rules]

    def process_model_specs(self) -> List[Rule]:
        """Process all model specifications"""
        if self.as_is is not None:
            appropriate_setting = (
                RULE_ORDERING_ENUM.as_written
                if self.as_is
                else RULE_ORDERING_ENUM.apply_longest_first
            )
            self.rule_ordering = appropriate_setting

            LOGGER.warning(
                f"mapping from {self.in_lang} to {self.out_lang} "
                'is using the deprecated parameter "as_is"; '
                f"replace `as_is: {self.as_is}` with `rule_ordering: {appropriate_setting.value}`"
            )
            if version_tuple < (3,):
                LOGGER.warning(
                    "as_is support will be removed in the next major version, g2p 3."
                )
            else:
                LOGGER.error("The as_is feature has been removed in version 3.0.0")
                import sys

                sys.exit(1)

        # Sorting must happen before the calculation of PUA intermediate forms for proper indexing
        if self.rule_ordering == RULE_ORDERING_ENUM.apply_longest_first:
            self.rules = sorted(
                # Temporarily normalize to NFD for heuristic sorting of NFC-defined rules
                self.rules,
                key=lambda x: len(normalize(strip_index_notation(x.rule_input), "NFD")),
                reverse=True,
            )

        def apply_to_attributes(rule: Rule, func: Callable, *attrs):
            for k in attrs:
                value = getattr(rule, k)
                if value:  # won't be None since default is ""
                    setattr(rule, k, func(value))

        non_empty_mappings: List[Rule] = []
        for i, rule in enumerate(self.rules):
            # We explicitly exclude match_pattern and
            # intermediate_form when saving rules.  Seeing either of
            # them is a programmer error.
            assert (
                rule.match_pattern is None
            ), "Either match_pattern was specified explicitly or process_model_specs was called more than once"
            assert (
                rule.intermediate_form is None
            ), "Either intermediate_form was specified explicitly or process_model_specs was called more than once"
            # Expand Abbreviations
            if self.abbreviations:
                apply_to_attributes(
                    rule,
                    partial(expand_abbreviations, abbs=self.abbreviations),
                    "rule_input",
                    "context_before",
                    "context_after",
                )
            # Reverse Rule
            if self.reverse:
                rule.rule_input, rule.rule_output = rule.rule_output, rule.rule_input
                rule.context_before = ""
                rule.context_after = ""
            # Escape Special
            if not self.processed and self.escape_special:
                rule = escape_special_characters(rule)
            # Unicode Normalization
            if self.norm_form != NORM_FORM_ENUM.none:
                apply_to_attributes(
                    rule,
                    partial(normalize, norm_form=self.norm_form.value),
                    "rule_input",
                    "rule_output",
                    "context_before",
                    "context_after",
                )
            # Prevent Feeding
            if self.prevent_feeding or rule.prevent_feeding:
                rule.intermediate_form = self._string_to_pua(rule.rule_output, i)
            # Create match pattern
            rule.match_pattern = self.rule_to_regex(rule)
            # Only add non-empty rules
            if rule.match_pattern:
                non_empty_mappings.append(rule)

        self.processed = True
        return non_empty_mappings

    def rule_to_regex(self, rule: Union[Rule, dict]) -> Union[Pattern, None]:
        """Turns an input string (and the context) from an input/output pair
        into a regular expression pattern"

        The 'in' key is the match.
        The 'context_after' key creates a lookahead.
        The 'context_before' key creates a lookbehind.

        Args:
            rule: A dictionary containing 'in', 'out', 'context_before', and 'context_after' keys

        Raises:
            Exception: This is raised when un-supported regex characters or symbols exist in the rule

        Returns:
            Pattern: returns a regex pattern (re.Pattern)
            None: if input is null
        """
        # Prevent null input. See, https://github.com/NRC-ILT/g2p/issues/24
        if isinstance(rule, dict):
            rule = Rule(**rule)
        if not rule.rule_input:
            LOGGER.warning(
                f"Rule {rule} has no input. This is disallowed. "
                "Please check your mapping file for rules with null inputs."
            )
            return None
        input_match = strip_index_notation(rule.rule_input)
        try:
            inp = create_fixed_width_lookbehind(rule.context_before) + input_match
            if rule.context_after:
                inp += f"(?={rule.context_after})"
            if not self.case_sensitive:
                rule_regex = re.compile(inp, re.I)
            else:
                rule_regex = re.compile(inp)
        except re.error as e:
            in_lang = self.in_lang
            out_lang = self.out_lang
            LOGGER.error(
                "Your regex in mapping between %s and %s is malformed.  "
                "Do you have un-escaped regex characters in your input %s, contexts %s, %s?  "
                "Error is: %s",
                in_lang,
                out_lang,
                inp,
                rule.context_before,
                rule.context_after,
                e.msg,
            )
            raise exceptions.MalformedMapping(
                f"Your regex in mapping between {in_lang} and {out_lang} is malformed.  "
                f"Do you have un-escaped regex characters in your input {inp}, "
                f"contexts {rule.context_before}, {rule.context_after}?"
            ) from e
        return rule_regex

    def extend(self, mapping: "Mapping"):
        """Add all the rules from mapping into self, effectively merging two mappings

        Caveat: if self and mapping have contradictory rules, which one will
        "win" is unspecified, and may depend on mapping configuration options.
        """
        self.rules.extend(mapping.rules)

    def deduplicate(self):
        """Remove duplicate rules found in self, keeping the first copy found."""
        # Since Python 3.6, dict keeps its element in insertion order (while
        # set does not), so deduplicating the rules is a one-liner:
        self.rules = list({repr(rule): rule for rule in self.rules}.values())

    def mapping_to_stream(self, out_stream, file_type: str = "json"):
        """Write mapping to a stream"""

        if file_type == "json":
            json.dump(
                self.plain_mapping(),
                out_stream,
                indent=4,
                ensure_ascii=False,
                cls=CompactJSONMappingEncoder,
            )
            print("\n", end="", file=out_stream)
        elif file_type == "csv":
            fieldnames = ["in", "out", "context_before", "context_after"]
            writer = csv.DictWriter(
                out_stream, fieldnames=fieldnames, extrasaction="ignore"
            )
            for io in self.rules:
                writer.writerow(io.export_to_dict())
        else:
            raise exceptions.IncorrectFileType(f"File type {file_type} is invalid.")

    def mapping_to_file(self, output_path: str = GEN_DIR, file_type: str = "json"):
        """Write mapping to file"""

        if not os.path.isdir(output_path):
            raise Exception(f"Path {output_path} is not a directory")
        fn = os.path.join(
            output_path,
            self.in_lang + "_to_" + self.out_lang + "." + file_type,
        )
        with open(fn, "w", encoding="utf8", newline="\n") as f:
            self.mapping_to_stream(f, file_type)

    def export_to_dict(self, mapping_type="json", config_only=False):
        """Export a mapping to a dictionary, optionally including only the
        configuration (and not the rules or alignments) in the case
        where we are just writing the config file.
        """
        if config_only:
            model_dict = self.model_dump(
                mode="json",
                exclude_none=True,
                exclude={
                    "parent_dir": True,
                    "rules": True,
                    "processed": True,
                    "alignments": True,
                    "abbreviations": True,
                },
            )
        else:
            model_dict = self.model_dump(
                mode="json",
                exclude_none=True,
                exclude={"parent_dir": True},
            )
        if not model_dict.get("rules_path"):
            model_dict["rules_path"] = (
                f"{self.in_lang}_to_{self.out_lang}.{mapping_type}"
            )
        return model_dict

    def config_to_file(
        self,
        output_path: str = os.path.join(GEN_DIR, "config-g2p.yaml"),
    ):
        """Write configuration to file."""
        add_config = False
        if os.path.isdir(output_path):
            output_path = os.path.join(output_path, "config-g2p.yaml")
        if os.path.exists(output_path) and os.path.isfile(output_path):
            LOGGER.warning(f"Adding mapping config to file at {output_path}")
            add_config = True
        else:
            LOGGER.warning(f"writing mapping config to file at {output_path}")
        fn = output_path
        config_template = self.export_to_dict(config_only=True)
        # Serialize piece-by-piece, which is why this is a list of type dict and not type Mapping
        # If config file exists already, just add the mapping.
        to_export = None
        if add_config:
            existing_data = MappingConfig.load_mapping_config_from_path(fn)
            updated = False
            for i, mapping in enumerate(existing_data.mappings):
                # if the mapping exists, just update the generation data
                if (
                    mapping.in_lang == config_template["in_lang"]
                    and mapping.out_lang == config_template["out_lang"]
                ):
                    existing_data.mappings[i].authors = config_template["authors"]
                    updated = True
                    break
            if not updated:
                existing_data.mappings.append(config_template)
            to_export = {
                "mappings": [
                    x.export_to_dict(config_only=True) if isinstance(x, Mapping) else x
                    for x in existing_data.mappings
                ],
            }
        else:
            to_export = {"mappings": [config_template]}
        with open(fn, "w", encoding="utf8", newline="\n") as f:
            yaml.dump(
                to_export,
                f,
                Dumper=IndentDumper,
                default_flow_style=False,
                # do not write strings as unreadable \u escapes! (see
                # https://stackoverflow.com/questions/10648614/dump-in-pyyaml-as-utf-8)
                allow_unicode=True,
            )


MAPPINGS_AVAILABLE: List[Mapping] = [
    Mapping(**mapping) for mapping in _MAPPINGS_AVAILABLE
]


class MappingConfig(BaseModel):
    """This is the format used by g2p for configuring mappings."""

    mappings: List[Mapping]

    def export_to_dict(self):
        return {"mappings": [mapping.export_to_dict() for mapping in self.mappings]}

    @staticmethod
    def load_mapping_config_from_path(
        path_to_mapping_config: Union[str, Path],
    ) -> "MappingConfig":
        """Loads a mapping configuration from a path, if you just want one specific mapping
        from the config, you can try Mapping.load_mapping_from_path instead.
        """
        if isinstance(path_to_mapping_config, str):
            path = Path(path_to_mapping_config)
        else:
            path = path_to_mapping_config
        parent_dir = path.parent
        with open(path, encoding="utf8") as f:
            loaded_config = yaml.safe_load(f)
            if "mappings" in loaded_config:
                for mapping in loaded_config["mappings"]:
                    mapping["parent_dir"] = parent_dir
        try:
            return MappingConfig(**loaded_config)
        except exceptions.MalformedMapping as e:
            e.message = f"{e.message}\nProblem in config file: {path}"
            raise e
        except TypeError as e:
            raise exceptions.MalformedMapping("Config file: {path}") from e


LANGS: Dict[str, MappingConfig] = {k: MappingConfig(**v) for k, v in _LANGS.items()}
