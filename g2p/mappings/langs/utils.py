"""

Utilities used by other classes

"""

import gzip
import json
from pathlib import Path
from typing import Any, Optional

from g2p.log import LOGGER
from g2p.mappings import MAPPINGS_AVAILABLE, Mapping, MappingConfig
from g2p.mappings.langs import LANGS_DIR, LANGS_NETWORK, LANGS_NWORK_PATH, LANGS_PKL
from g2p.mappings.utils import MAPPING_TYPE, is_ipa

from .network_lite import DiGraph, node_link_data

# panphon.distance.Distance() takes a long time to initialize, so...
# a) we don't want to load it if we don't need it, i.e., don't use a constant
# b) we don't want to load it more than once, i.e., don't use a local variable.
# Conclusion: use a singleton with lazy initialization
# Profiling results: calling is_panphon() the first time still costs 400ms, but subsequent
# calls cost .02ms each. With dst=panphone.distance.Distance() instead of
# dst=getPanphonDistanceSingleton(), the first call costs 400ms and subsequent calls
# cost 180ms each.

_PANPHON_DISTANCE_SINGLETON = None


def getPanphonDistanceSingleton():
    global _PANPHON_DISTANCE_SINGLETON
    if _PANPHON_DISTANCE_SINGLETON is None:
        # Expensive import, only do it when actually needed
        import panphon.distance  # type: ignore

        _PANPHON_DISTANCE_SINGLETON = panphon.distance.Distance()
    return _PANPHON_DISTANCE_SINGLETON


def check_ipa_known_segs(mappings_to_check=False) -> bool:
    """Check the given mappings, or all IPA mappings, for invalid IPA in the "out" fields

    Returns True iff not errors were found.
    """
    if not mappings_to_check:
        mappings_to_check = [x.out_lang for x in MAPPINGS_AVAILABLE]
    found_error = False

    for mapping in [x for x in MAPPINGS_AVAILABLE if x.out_lang in mappings_to_check]:
        if is_ipa(mapping.out_lang) and mapping.type == MAPPING_TYPE.mapping:
            reverse = mapping.reverse
            for rule in mapping.rules:
                output = rule.rule_input if reverse else rule.rule_output
                if not is_panphon(output):
                    LOGGER.warning(
                        f"Output '{rule.rule_output}' in rule {rule} in mapping between {mapping.in_lang} "
                        f"and {mapping.out_lang} is not recognized as valid IPA by panphon."
                    )
                    found_error = True
    if found_error:
        LOGGER.warning(
            "Please refer to https://github.com/dmort27/panphon for information about panphon."
        )
    return not found_error


_is_panphon_g_warning_printed = False
_is_panphon_colon_warning_printed = False


def is_panphon(string, display_warnings=False):
    # Deferred importing required here, because g2p.transducer also imports this file.
    # Such circular dependency is probably bad design, maybe a reviewer of this code will
    # have a better solution to recommend?
    import g2p.transducer

    dst = getPanphonDistanceSingleton()
    panphon_preprocessor = g2p.transducer.Transducer(
        Mapping.find_mapping_by_id("panphon_preprocessor")
    )
    preprocessed_string = panphon_preprocessor(string).output_string
    # Use a loop that prints the warnings on all strings that are not panphon, even though
    # logically this should not be necessary to calculate the answer.
    result = True
    for word in preprocessed_string.split():
        word_ipa_segs = dst.fm.ipa_segs(word)
        word_ipa = "".join(word_ipa_segs)
        if word != word_ipa:
            if not display_warnings:
                return False
            LOGGER.warning(
                f'String "{word}" is not identical to its IPA segmentation: {word_ipa_segs}'
            )
            global _is_panphon_g_warning_printed
            if "g" in word and not _is_panphon_g_warning_printed:
                LOGGER.warning(
                    "Common IPA gotcha: the ASCII 'g' character is not IPA, use 'ɡ' (\\u0261) instead."
                )
                _is_panphon_g_warning_printed = True
            global _is_panphon_colon_warning_printed
            if ":" in word and not _is_panphon_colon_warning_printed:
                LOGGER.warning(
                    "Common IPA gotcha: the ASCII ':' character is not IPA, use 'ː' (\\u02D0) instead."
                )
                _is_panphon_colon_warning_printed = True
            for c in word:
                if c not in word_ipa:
                    LOGGER.warning(
                        f"Character '{c}' (\\u{format(ord(c), '04x')}) in word '{word}' "
                        "was not recognized as IPA by panphon."
                    )
            result = False
    return result


_ARPABET_SET = None


def is_arpabet(string):
    global _ARPABET_SET
    if _ARPABET_SET is None:
        _ARPABET_SET = set(
            Mapping.find_mapping(in_lang="eng-ipa", out_lang="eng-arpabet").inventory(
                "out"
            )
        )
    # print(f"arpabet_set={_ARPABET_SET}")
    for sound in string.split():
        if sound not in _ARPABET_SET:
            return False
    return True


def cache_langs(
    dir_path: str = LANGS_DIR,
    langs_path: str = LANGS_PKL,
    network_path: str = LANGS_NWORK_PATH,
):
    """Read in all files and save as pickle.

    Args:
       dir_path: Path to scan for config-g2p.yaml files.  Default is the
                 installed g2p/mappings/langs directory.
       langs_path: Path to output langs.json.gz file.  Default is
                   the installed g2p/mappings/langs/langs.json.gz
       network_path: Path to output pickle file.  Default is the
                     installed g2p/mappings/langs/network.pkl.
    """
    langs = {}

    # Sort by language code
    paths = sorted(
        Path(dir_path).glob("./*/config-g2p.y*ml"), key=lambda x: x.parent.stem
    )
    mappings_legal_pairs = []
    if not paths:
        raise FileNotFoundError(
            f"There don't seem to be any valid mappings in {dir_path}"
        )
    for path in paths:
        code = path.parent.stem
        mapping_config = MappingConfig.load_mapping_config_from_path(path)
        # TODO: should put in some measure to prioritize non-generated
        # mappings and warn when they override
        mappings_legal_pairs.extend(
            [(mapping.in_lang, mapping.out_lang) for mapping in mapping_config.mappings]
        )
        langs[code] = mapping_config.export_to_dict()

    # Save as a Directional Graph
    lang_network: DiGraph[str] = DiGraph()
    lang_network.add_edges_from(mappings_legal_pairs)
    write_json_gz(network_path, node_link_data(lang_network))
    write_json_gz(langs_path, langs)
    return langs


def write_json_gz(path: str, data: Any):
    """Write data into a .json.gz compressed file.

    If the file exists but the contents have not changed, do not rewrite it: gzip output
    is no longer stable with Python 3.14 starting to replace zlib by the faster zlib-ng,
    which produces equivalently valid -- but not identical!!! -- compressed output.

    See https://www.man.com/technology/faster-python for more info.
    """
    contents = json.dumps(
        data,
        separators=(",", ":"),
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")

    if Path(path).exists():
        with gzip.open(path, "rb") as f:
            old_contents = f.read()
        if contents == old_contents:
            LOGGER.info(f"{path} already up to date.")
            return

    with gzip.GzipFile(path, "wb", mtime=0) as zipfile:
        zipfile.write(contents)
    LOGGER.info(f"{path} updated.")


def network_to_echart(outfile: Optional[str] = None, layout: bool = False):
    nodes = []
    no_nodes = len(LANGS_NETWORK.nodes)
    for node in LANGS_NETWORK.nodes:
        lang_name = node.split("-")[0]
        no_ancestors = len(LANGS_NETWORK.ancestors(node))
        no_descendants = len(LANGS_NETWORK.descendants(node))
        size = min(
            20,
            max(
                2, ((no_ancestors / no_nodes) * 100 + (no_descendants / no_nodes) * 100)
            ),
        )
        size = round(size, 2)
        nodes.append(
            {"name": node, "symbolSize": size, "id": node, "category": lang_name}
        )
    nodes.sort(key=lambda x: x["name"])  # type: ignore
    edges = []
    for edge in LANGS_NETWORK.edges:
        edges.append({"source": edge[0], "target": edge[1]})
    if outfile:
        with open(
            outfile,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as f:
            f.write(json.dumps({"nodes": nodes, "edges": edges}) + "\n")
        LOGGER.info(f"Wrote network nodes and edges to static file {outfile}.")
    return nodes, edges
