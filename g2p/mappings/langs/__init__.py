"""
Language mappings for g2p.
"""

import gzip
import json
import os

from g2p.constants import LANGS_DIR, LANGS_FILE_NAME, NETWORK_FILE_NAME
from g2p.log import LOGGER

from .network_lite import DiGraph, node_link_graph

assert LANGS_DIR == os.path.dirname(__file__)
LANGS_PKL = os.path.join(LANGS_DIR, LANGS_FILE_NAME)
LANGS_NWORK_PATH = os.path.join(LANGS_DIR, NETWORK_FILE_NAME)


def load_langs(path: str = LANGS_PKL):
    try:
        with gzip.open(path, "rt", encoding="utf8") as f:
            return json.load(f)
    except Exception as e:
        LOGGER.warning(f"Failed to read language cache from {path}: {e}")
        return {}


def load_network(path: str = LANGS_NWORK_PATH) -> DiGraph[str]:
    try:
        with gzip.open(path, "rt", encoding="utf8") as f:
            data = json.load(f)
            return node_link_graph(data)
    except Exception as e:
        LOGGER.warning(f"Failed to read language network from {path}: {e}")
        return DiGraph()


def get_available_languages(langs: dict) -> list:
    language_names = set()
    for k, v in langs.items():
        if k in ["generated", "font-encodings"]:
            continue
        for vv in v["mappings"]:
            if "language_name" in vv:
                language_names.add(vv["language_name"])
    return sorted(language_names)


def get_available_mappings(langs: dict) -> list:
    mappings_available = []
    for v in langs.values():
        if "mappings" in v:
            mappings_available.extend(v["mappings"])
        else:
            mappings_available.append(v)
    return mappings_available


# Inadvertently part of the g2p programmatic API because this is not available for
# import elsewhere. Don't change this! The following code must always work:
#     from g2p.mappings.langs import LANGS_NETWORK
#     nodes: Collection[str] = LANGS_NETWORK.nodes
LANGS_NETWORK = load_network()
# Making private because it should be imported from g2p.mappings instead
_LANGS = load_langs()
LANGS_AVAILABLE = get_available_languages(_LANGS)
_MAPPINGS_AVAILABLE = get_available_mappings(_LANGS)


def reload_db():
    """Reload the langs and network data, necessary after a g2p update."""

    # We update all structures in place, so that another module having done from
    # g2p.mappings.langs import VAR will see the udpates without any code changes.

    global _LANGS
    _LANGS.clear()
    _LANGS.update(load_langs())

    global LANGS_NETWORK
    LANGS_NETWORK.clear()
    new_langs_network = load_network()
    LANGS_NETWORK.update(new_langs_network.edges, new_langs_network.nodes)

    global LANGS_AVAILABLE
    LANGS_AVAILABLE.clear()
    LANGS_AVAILABLE.extend(get_available_languages(_LANGS))

    global _MAPPINGS_AVAILABLE
    _MAPPINGS_AVAILABLE.clear()
    _MAPPINGS_AVAILABLE.extend(get_available_mappings(_LANGS))
