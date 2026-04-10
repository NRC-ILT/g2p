######################################################################
# Patrick Littell
#
# create_ipa_mapping.py
#
# Given two IPA inventories in JSON (either as dedicated inventory
# files or the input/output sides of mapping files), map the first
# onto the second by use of panphon's phonetic distance calculators.
#
# The resulting mappings are used just like other mappings: to make
# converters and pipelines of converters in convert_orthography.py
#
# AP Note: Taken from ReadAlongs-Studio and implemented with G2P formatting
######################################################################
import datetime as dt
from typing import Iterable, List, Tuple

from g2p.constants import DISTANCE_METRICS
from g2p.log import LOGGER
from g2p.mappings import Mapping
from g2p.mappings.langs.utils import getPanphonDistanceSingleton
from g2p.mappings.utils import RULE_ORDERING_ENUM, is_ipa, is_xsampa
from g2p.transducer import Transducer

#################################
#
# Preprocessing:
#
# Panphon can only match a single segment to another segment, rather
# than (say) try to combine two segments to better match the features.
# For example, you might want "kʷ" to match to "kw", but Panphon will
# only match the "kʷ" to "k" and consider the "w" to be a dropped
# character.  In order to get around this, we preprocess strings so
# that common IPA segments that you might expect map to two characters
# in another language, like affricates or rounded consonants, are
# treated as two characters rather than one.
#
#################################
_xsampa_converter = None  # Cache this but create it only if needed


def process_character(p, is_xsampa=False):
    if is_xsampa:
        global _xsampa_converter
        if _xsampa_converter is None:
            # Expensive import, do it only when needed:
            from panphon.xsampa import XSampa  # type: ignore

            _xsampa_converter = XSampa()
        p = _xsampa_converter.convert(p)
    panphon_preprocessor = Transducer(
        Mapping.find_mapping_by_id("panphon_preprocessor")
    )
    return panphon_preprocessor(p).output_string


def process_characters(inv, is_xsampa=False):
    return [process_character(p, is_xsampa) for p in inv]


##################################
#
# Creating the mapping
#
#
#
###################################


def get_distance_method(dst, distance: str):
    if distance not in DISTANCE_METRICS:
        raise ValueError(f"Distance metric {distance} not supported")
    try:
        distance_method = getattr(dst, distance)
    except AttributeError as e:
        # Older versions of panphon mispelled Dolgopolsky's name as Dogolpolsky...
        # Try again with the older name, so we stay compatible with both <=0.19
        # and >=0.19.1
        if distance == "dolgo_prime_distance":
            return getattr(dst, "dogol_prime_distance")

        LOGGER.error(f"The distance metric {distance} is not supported by PanPhon")
        raise ValueError(f"Distance metric {distance} not supported") from e
    return distance_method


def create_multi_mapping(
    src_mappings: List[Tuple[Mapping, str]],
    tgt_mappings: List[Tuple[Mapping, str]],
    distance: str = "weighted_feature_edit_distance",
) -> Mapping:
    """Create a mapping for a set of source mappings to a set of target mappings

    Each src/tgt mappings is a (mapping: Mapping, in_or_out: str) pair specifying
    the mapping to use and whether its input ("in") or output ("out") inventory
    should be used to create the new mapping.

    The name of the mapping is infered from src_mappings[0] and tgt_mappings[0]'s
    metadata.
    """

    def compact_ipa_names(ipa_names: Iterable) -> str:
        # ["fra-ipa", "eng-ipa", "kwk-ipa"] -> "fra-eng-kwk-ipa"
        return (
            "-".join(name[:-4] if name.endswith("-ipa") else name for name in ipa_names)
            + "-ipa"
        )

    def long_ipa_names(ipa_names: Iterable) -> str:
        # ["fra-ipa", "eng-ipa", "kwk-ipa"] -> "fra-ipa and eng-ipa and kwk-ipa"
        return " and ".join(ipa_names)

    def get_sorted_unique_names(mappings: List[Tuple[Mapping, str]]) -> List[str]:
        return sorted(
            {getattr(mapping, f"{in_or_out}_lang") for mapping, in_or_out in mappings}
        )

    def deduplicate(iterable: Iterable) -> List:
        # Use a dict, and not a set, to preserve the original order.
        return list({v: v for v in iterable}.values())

    map_1_names = get_sorted_unique_names(src_mappings)
    map_2_names = get_sorted_unique_names(tgt_mappings)

    src_inventory = []
    for mapping, io in src_mappings:
        name = getattr(mapping, f"{io}_lang")
        if not is_ipa(name):
            LOGGER.warning(
                "Unsupported orthography of src inventory: %s; must be IPA", name
            )
        src_inventory.extend(mapping.inventory(io))
    src_inventory = deduplicate(src_inventory)

    tgt_inventory = []
    for mapping, io in tgt_mappings:
        name = getattr(mapping, f"{io}_lang")
        if not is_ipa(name):
            LOGGER.warning(
                "Unsupported orthography of tgt inventory: %s; must be IPA", name
            )
        tgt_inventory.extend(mapping.inventory(io))
    tgt_inventory = deduplicate(tgt_inventory)

    mapping = align_inventories(src_inventory, tgt_inventory, distance=distance)

    config = {
        "in_lang": compact_ipa_names(map_1_names),
        "out_lang": compact_ipa_names(map_2_names),
        "language_name": "IPA",
        "rule_ordering": RULE_ORDERING_ENUM.apply_longest_first.value,
        "rules": mapping,
        "prevent_feeding": True,
        "norm_form": "NFC",
        "authors": [f"Generated {dt.datetime.now()}"],
        "display_name": (
            long_ipa_names(map_1_names) + " to " + long_ipa_names(map_2_names)
        ),
    }

    return Mapping(**config)


def create_mapping(
    mapping_1: Mapping,
    mapping_2: Mapping,
    mapping_1_io: str = "out",
    mapping_2_io: str = "in",
    distance: str = "weighted_feature_edit_distance",
) -> Mapping:
    """Create a mapping from mapping_1's output inventory to mapping_2's input inventory"""

    map_1_name = getattr(mapping_1, f"{mapping_1_io}_lang")
    map_2_name = getattr(mapping_2, f"{mapping_2_io}_lang")
    if not is_ipa(map_1_name) and not is_xsampa(map_1_name):
        LOGGER.warning(
            "Unsupported orthography of inventory 1: %s (must be ipa or x-sampa)",
            map_1_name,
        )
    if not is_ipa(map_2_name) and not is_xsampa(map_2_name):
        LOGGER.warning(
            "Unsupported orthography of inventory 2: %s (must be ipa or x-sampa)",
            map_2_name,
        )
    l1_is_xsampa, l2_is_xsampa = is_xsampa(map_1_name), is_xsampa(map_2_name)
    rules = align_inventories(
        mapping_1.inventory(mapping_1_io, non_empty=True),
        mapping_2.inventory(mapping_2_io, non_empty=True),
        l1_is_xsampa,
        l2_is_xsampa,
        distance=distance,
    )

    # Initialize mapping with input language parameters (as_is,
    # case_sensitive, prevent_feeding, etc) but *not* the same filename!
    config = mapping_1.model_copy().model_dump(exclude={"rules_path"})
    config = {
        **config,
        "authors": [f"Generated {dt.datetime.now()}"],
        "display_name": None,
        "language_name": None,
        "in_lang": map_1_name,
        "out_lang": map_2_name,
        "rules": rules,
        "prevent_feeding": True,
        "rule_ordering": RULE_ORDERING_ENUM.apply_longest_first,
    }

    return Mapping(**config)


def align_inventories(
    inventory_l1,
    inventory_l2,
    l1_is_xsampa=False,
    l2_is_xsampa=False,
    distance="weighted_feature_edit_distance",
):
    """Align inventories by finding a good sequence in inventory_l2 for each
    character in inventory_l1"""

    # find_good_match() is a function inside align_inventories() because it
    # lets us initialize dst and ps_pseqs globally once, yielding a roughly 8x
    # speed inprovements over the previous version of the code.

    # Initializing panphon.distance.Distance() is expensive, so do it just once
    dst = getPanphonDistanceSingleton()
    # Initializing p2_pseqs is expensive, so do it only once per call to align_inventories()
    p2_pseqs = [
        dst.fm.ipa_segs(p) for p in process_characters(inventory_l2, l2_is_xsampa)
    ]

    def find_good_match(p1, inventory_l2):
        """Find a good sequence in inventory_l2 matching p1."""

        # The proper way to do this would be with some kind of beam search
        # through a determinized/minimized FST, but in the absence of that
        # we can do a kind of heurstic greedy search.  (we don't want any
        # dependencies outside of PyPI otherwise we'd just use OpenFST)

        p1_pseq = dst.fm.ipa_segs(p1)

        i = 0
        good_match = []
        while i < len(p1_pseq):
            best_input = ""
            best_output = -1
            best_score = 0xDEADBEEF
            for j, p2_pseq in enumerate(p2_pseqs):
                # FIXME: Should also consider the (weighted) possibility
                # of deleting input or inserting any segment (but that
                # can't be done with a greedy search)
                if len(p2_pseq) == 0:
                    LOGGER.warning(
                        "No panphon mapping for %s - skipping", inventory_l2[j]
                    )
                    continue
                e = min(i + len(p2_pseq), len(p1_pseq))
                input_seg = p1_pseq[i:e]
                distance_method = get_distance_method(dst, distance)
                score = distance_method("".join(input_seg), "".join(p2_pseq))
                # Be very greedy and take the longest match
                if (
                    score < best_score
                    or score == best_score
                    and len(input_seg) > len(best_input)
                ):
                    best_input = input_seg
                    best_output = j
                    best_score = score
            LOGGER.debug(
                "Best match at position %d: %s => %s",
                i,
                best_input,
                inventory_l2[best_output],
            )
            good_match.append(inventory_l2[best_output])
            i += len(best_input)  # greedy!
        return "".join(good_match)

    mapping = []
    for i1, p1 in enumerate(process_characters(inventory_l1, l1_is_xsampa)):
        # we enumerate the strings because we want to save the original string
        # (e.g., 'kʷ') to the mapping, not the processed one (e.g. 'kw')
        good_match = find_good_match(p1, inventory_l2)
        mapping.append({"in": inventory_l1[i1], "out": good_match})
    return mapping
