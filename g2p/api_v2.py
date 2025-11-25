"""REST API for G2P index-preserving grapheme-to-phoneme conversion using FastAPI.

You can run the API app for development purposes on any platform with:
    pip install uvicorn fastapi
    DEVELOPMENT=1 uvicorn g2p.api_v2:api --reload --port 5000
- The --reload switch will watch for changes under the directory where it's
  running and reload the code whenever it changes.
- DEVELOPMENT=1 tells the API to accept cross-origin requests (i.e. by sending the
  appropriate CORS headers) from development servers running on localhost, e.g.
  http://localhost:4200

For deployment, you can use the ORIGIN environment variable to set the
URL of your application in order to make it accept requests from that
site.  For instance if you deployed an application that uses it at
https://my.awesome.site you would set ORIGIN=https://my.awesome.site
in your environment variables.  This is usually done through an
environment variable file (or in a dashboard) and will depend on your
hosting environment.

You can also spin up the API server grade (on Linux, not Windows) with gunicorn:
    pip install -r requirements.api.txt
    gunicorn -b 127.0.0.1:5000 -w 4 -k uvicorn.workers.UvicornWorker g2p.api_v2:api

Once spun up, the API will be visible at
http://localhost:5000/docs

"""

import os
from enum import Enum
from typing import Dict, List, Tuple, Union

from fastapi import Body, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import g2p
import g2p.mappings as g2p_mappings
import g2p.mappings.langs as g2p_langs
from g2p.exceptions import InvalidLanguageCode, NoPath
from g2p.log import LOGGER
from g2p.transducer import CompositeTransductionGraph, TransductionGraph

# Create the v2 version of the API
api = FastAPI(
    title="Simple G2P API",
    description="A simple API for the G2P module",
    version="2.0.0",
    contact={"email": "readalong.studio@gmail.com"},
    license_info={
        "name": "MIT",
        "url": "https://github.com/NRC-ILT/g2p/blob/main/LICENSE",
    },
)
# Allow for development/non-g2p-studio deployments
middleware_args: Dict[str, Union[str, List[str]]] = {}
if os.getenv("DEVELOPMENT", False):  # pragma: no cover
    LOGGER.info(
        "Running in development mode, will allow requests from http://localhost:*"
    )
    # Allow requests from localhost dev servers
    middleware_args["allow_origin_regex"] = "http://localhost(:.*)?"
else:
    # Allow requests from a configured site name
    origin = os.getenv("ORIGIN")
    if origin is not None:
        middleware_args["allow_origins"] = origin.split()
        LOGGER.info("Allowing requests from the following sites:")
        for site in middleware_args["allow_origins"]:
            LOGGER.info("   %s", site)
# If DEVELOPMENT or ORIGIN are not specified then same-origin only
if middleware_args:
    api.add_middleware(
        CORSMiddleware, allow_methods=["GET", "POST", "OPTIONS"], **middleware_args
    )

# All possible language codes
LanguageNode = Enum("LanguageNode", [(name, name) for name in g2p_langs.LANGS_NETWORK.nodes])  # type: ignore


class SupportedLanguage(BaseModel):
    """Writing or phonetic system for conversion"""

    code: str = Field(
        description="Language, writing, or phonetic system code as passed to /convert",
        examples=["eng"],
    )
    name: Union[str, None] = Field(
        description="Display name (not internationalized) for language, may be None",
        examples=["English"],
    )


MAPPING_NAMES: Dict[str, Union[str, None]] = {}
for mapping in g2p_mappings.MAPPINGS_AVAILABLE:
    MAPPING_NAMES[mapping.in_lang] = mapping.language_name
LANGS = []
for code, config in g2p_mappings.LANGS.items():
    if code not in ("generated", "font-encodings"):
        language_name = config.mappings[0].language_name
        if MAPPING_NAMES.get(code) is None:
            MAPPING_NAMES[code] = language_name
        LANGS.append(SupportedLanguage(code=code, name=language_name))
LANGS.sort(key=lambda x: str(x.name).lower())
CODES = []
for code in g2p_langs.LANGS_NETWORK.nodes:
    CODES.append(SupportedLanguage(code=code, name=MAPPING_NAMES.get(code, None)))
CODES.sort(key=lambda x: x.code)


@api.get(
    "/langs",
    response_description="Supported languages for conversion",
)
def get_supported_input_languages() -> List[SupportedLanguage]:
    """Return a list of language codes (possible inputs for /convert) and their names."""
    return LANGS


@api.get(
    "/nodes",
    response_description="Supported writing or phonetic systems for conversion",
)
def get_all_writing_or_phonetic_systems() -> List[SupportedLanguage]:
    """Return a list of all possible inputs for /convert and
    associated language names, if any.
    """
    return CODES


class ConvertRequest(BaseModel):
    """Request conversion from one writing or phonetic system to another."""

    in_lang: LanguageNode = Field(
        description="Name of input node", examples=["eng-ipa"]
    )
    out_lang: LanguageNode = Field(
        description="Name of output node", examples=["eng-arpabet"]
    )
    text: str = Field(description="Text to convert", examples=["hɛloʊ"])
    tokenize: Union[bool, None] = Field(
        True,
        description="Tokenize input and return a list of segments.  This is "
        "the default behaviour, set this to `False` to treat input as a single segment. "
        "Warning: only use False if text is already a single word without punctuation.",
    )
    compose_from: Union[str, None] = Field(
        None,
        description="Compose all conversions from a specific step onwards."
        "  Useful if you wish to recover alignments for a specific intermediate step",
    )
    indices: Union[bool, None] = Field(
        False,
        description="Return lists of input and output characters and alignments "
        "as indices into those lists.  These are guaranteed to be usable no matter "
        "how your platform defines a 'character'.",
    )


class Conversion(BaseModel):
    """One step in G2P conversion"""

    in_lang: Union[None, LanguageNode] = Field(
        None,
        description="Name of input language, absent if no conversion was done",
        examples=["eng-ipa"],
    )
    out_lang: Union[None, LanguageNode] = Field(
        None,
        description="Name of output language, absent if no conversion was done",
        examples=["eng-arpabet"],
    )
    input_nodes: Union[None, List[str]] = Field(
        None,
        description="Characters in input, which can be safely indexed by alignments, "
        "present only if `indices` was True in request.",
        examples=[["h", "i", "🙂", "🙂", "🙂"]],
    )
    output_nodes: Union[None, List[str]] = Field(
        None,
        description="Characters in output, which can be safely indexed by alignments, "
        "present only if `indices` was True in request.",
        examples=[["H", "H", " ", "I", "Y", " ", "🙂", "🙂", "🙂"]],
    )
    alignments: Union[None, List[Tuple[int, Union[int, None]]]] = Field(
        None,
        description="Alignments from input to output indices, "
        "present only if `indices` was True in request.",
        examples=[
            [
                [0, 0],
                [0, 1],
                [0, 2],
                [1, 3],
                [1, 4],
                [1, 5],
                [2, 6],
                [2, 7],
                [3, 8],
                [3, 9],
                [3, 10],
            ]
        ],
    )
    substring_alignments: List[Tuple[str, str]] = Field(
        description="Minimal montonic substring alignments from input to output substrings",
        examples=[
            [
                ["h", "HH "],
                ["ɛ", "EH "],
                ["l", "L "],
                ["oʊ", "OW "],
            ]
        ],
    )


class Segment(BaseModel):
    """Result of G2P conversion of one segment of input, with
    intermediate steps and substring_alignments."""

    conversions: List[Conversion] = Field(
        description="Sequence of conversions in reverse order.",
        examples=[
            [
                {
                    "in_lang": "eng-ipa",
                    "out_lang": "eng-arpabet",
                    "substring_alignments": [
                        ["h", "HH "],
                        ["ɛ", "EH "],
                        ["l", "L "],
                        ["oʊ", "OW "],
                    ],
                }
            ]
        ],
    )


@api.post("/convert")
def convert_one_writing_or_phonetic_system_to_another(  # noqa: C901
    request: ConvertRequest = Body(
        openapi_examples={
            "eng-ipa to eng-arpabet": {
                "summary": "Convert English IPA to ARPABET",
                "description": "G2P can do simple conversions between equivalent phonetic notations",
                "value": {
                    "in_lang": "eng-ipa",
                    "out_lang": "eng-arpabet",
                    "text": "hɛloʊ",
                },
            },
            "fin to eng-arpabet": {
                "summary": "Convert Finnish orthography to nearest ARPABET phones",
                "description": """
G2P can do also (sometimes) approximate one language's phonology using phones from another.
To find out possible output languages for an input, use the 'outputs_for' endpoint.""",
                "value": {
                    "in_lang": "fin",
                    "out_lang": "eng-arpabet",
                    "text": "hyvää yötä",
                },
            },
            "composed conversion": {
                "summary": "Convert Finnish orthography directly to nearest ARPABET phones",
                "description": "By default all the conversion steps are returned.  "
                "You can get the direct mapping from input to output by setting compose_from: in_lang",
                "value": {
                    "in_lang": "fin",
                    "out_lang": "eng-arpabet",
                    "text": "hyvää huomenta",
                    "compose_from": "fin",
                },
            },
            "tokenized conversion": {
                "summary": "Convert Finnish orthography with punctuation directly to nearest ARPABET phones",
                "description": "Non-word segments are returned with in_lang and out_lang as null",
                "value": {
                    "in_lang": "fin",
                    "out_lang": "eng-arpabet",
                    "text": "Varaus! Sieni, joka kasvaa korvessa, on myrkyllinen!",
                    "compose_from": "fin-ipa",
                },
            },
        }
    )
) -> List[Segment]:
    """Tokenize a text return the converted and intermediate forms of each
    segment (non-token segments will have converted=False).  The final
    conversion comes first in the output, followed by prevoius
    conversions.  If you do not want the intermediate conversions, set
    "compose_from" to in_lang.

    """
    in_lang = request.in_lang.name
    out_lang = request.out_lang.name
    try:
        transducer = g2p.make_g2p(in_lang, out_lang)
        if request.tokenize:
            tokenizer = g2p.make_tokenizer(in_lang)
            tokens = tokenizer.tokenize_text(request.text)
        else:
            tokens = [g2p.Token(request.text, is_word=True)]
    except NoPath:
        raise HTTPException(
            status_code=400, detail=f"No path from {in_lang} to {out_lang}"
        )
    except InvalidLanguageCode:  # pragma: nocover
        # Will never happen due to FastAPI validation (will get 422 instead)
        raise HTTPException(
            status_code=404, detail="Unknown input or output language code"
        )

    segments: List[Segment] = []
    for token in tokens:
        conversions: List[Conversion] = []
        if not token.is_word:  # non-word, has no in_lang/out_lang
            tg = TransductionGraph(token.text)
            conv = Conversion(substring_alignments=tg.substring_alignments())
            if request.indices:
                conv.alignments = tg.alignments()
                conv.input_nodes = list(tg.input_string)
                conv.output_nodes = list(tg.output_string)
            conversions.append(conv)
        else:
            tg = transducer(token.text)
            if request.compose_from:
                composed_tiers: List[TransductionGraph] = []
                for tr, tier in zip(transducer.transducers, tg.tiers):
                    if composed_tiers:
                        composed_tiers.append(tier)
                    else:
                        if tr.in_lang == request.compose_from:
                            composed_tiers.append(tier)
                        else:
                            conv = Conversion(
                                in_lang=tr.in_lang,
                                out_lang=tr.out_lang,
                                substring_alignments=tier.substring_alignments(),
                            )
                            if request.indices:
                                conv.input_nodes = list(tier.input_string)
                                conv.output_nodes = list(tier.output_string)
                                conv.alignments = tier.alignments()
                            conversions.insert(0, conv)
                if composed_tiers:
                    composed_tg = CompositeTransductionGraph(composed_tiers)
                    conv = Conversion(
                        in_lang=request.compose_from,
                        out_lang=transducer.out_lang,
                        substring_alignments=composed_tg.substring_alignments(),
                    )
                    if request.indices:
                        conv.input_nodes = list(composed_tg.input_string)
                        conv.output_nodes = list(composed_tg.output_string)
                        conv.alignments = composed_tg.alignments()
                    conversions.insert(0, conv)
            else:
                for tr, tier in zip(transducer.transducers, tg.tiers):
                    conv = Conversion(
                        in_lang=tr.in_lang,
                        out_lang=tr.out_lang,
                        substring_alignments=tier.substring_alignments(),
                    )
                    if request.indices:
                        conv.input_nodes = list(tier.input_string)
                        conv.output_nodes = list(tier.output_string)
                        conv.alignments = tier.alignments()
                    conversions.insert(0, conv)
        segments.append(Segment(conversions=conversions))
    return segments


@api.get(
    "/outputs_for/{lang}",
    response_description="List of language codes into which {lang} can be converted",
)
def get_possible_output_conversions_for_a_writing_system(
    lang: LanguageNode = Path(description="Input language name"),
) -> List[str]:
    """Get the possible output languages for a given input language. These
    are all the phonetic or orthographic systems into which you can convert
    this input.
    """
    return sorted(g2p_langs.LANGS_NETWORK.descendants(lang.name))


@api.get(
    "/inputs_for/{lang}",
    response_description="List of language codes which can be converted into {lang}",
)
def get_writing_systems_that_can_be_converted_to_an_output(
    lang: LanguageNode = Path(description="Output language name"),
) -> List[str]:
    """Get the possible input languages for a given output language. These
    are all the phonetic or orthographic systems that you can convert
    into this output.
    """
    return sorted(g2p_langs.LANGS_NETWORK.ancestors(lang.name))


@api.get(
    "/path/{in_lang}/{out_lang}",
    response_description="Path from {in_lang} to {out_lang}",
)
def get_path_from_one_language_to_another(
    in_lang: LanguageNode = Path(description="Input language name"),
    out_lang: LanguageNode = Path(description="Output language name"),
) -> List[str]:
    """Get the sequence of intermediate forms used to convert from {in_lang} to {out_lang}."""
    try:
        return g2p_langs.LANGS_NETWORK.shortest_path(in_lang.name, out_lang.name)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"No path from {in_lang} to {out_lang}"
        )
