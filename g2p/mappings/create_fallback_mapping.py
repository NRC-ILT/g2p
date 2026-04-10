import datetime as dt

from text_unidecode import unidecode  # type: ignore

from g2p import make_g2p
from g2p.log import LOGGER
from g2p.mappings import Mapping
from g2p.mappings.create_ipa_mapping import align_inventories
from g2p.mappings.utils import is_ipa, unicode_escape

DUMMY_INVENTORY = ["ɑ", "i", "u", "t", "s", "n"]


def align_to_dummy_fallback(
    mapping: Mapping,
    io: str = "in",
    distance: str = "weighted_feature_edit_distance",
):
    """Create a mapping from mapping's output inventory to a minimalist dummy inventory"""
    mapping_config = mapping.model_dump()
    config = {
        "in_lang": mapping_config[f"{io}_lang"],
        "out_lang": "dummy",
        "authors": [f"Generated {dt.datetime.now()}"],
    }
    default_char = "t"
    if is_ipa(mapping_config[f"{io}_lang"]):
        list_of_rules = align_inventories(
            mapping.inventory(io), DUMMY_INVENTORY, distance=distance
        )
    else:
        und_g2p = make_g2p("und", "und-ipa", tokenize=False)
        list_of_rules = [
            {
                "in": unicode_escape(x),
                "out": und_g2p(unidecode(x).lower()).output_string,
            }
            for x in mapping.inventory(io)
        ]
        dummy_list = align_inventories(
            [x["out"] for x in list_of_rules], DUMMY_INVENTORY, distance=distance
        )
        dummy_dict = {}
        for x in dummy_list:
            if x["in"]:
                dummy_dict[x["in"]] = x["out"]

        for x in list_of_rules:
            try:
                x["out"] = dummy_dict[x["out"]]
            except KeyError:
                LOGGER.warning(
                    f"We couldn't guess at what {x['in']} means, so it's being "
                    f"replaced with '{default_char}' instead."
                )
                x["out"] = default_char

    config["rules"] = list_of_rules
    return Mapping(**config)
