"""REST API for G2P index-preserving grapheme-to-phoneme conversion using FastAPI."""

from enum import Enum
from typing import List

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse

from g2p import make_g2p
from g2p.exceptions import NoPath
from g2p.log import LOGGER
from g2p.mappings.langs import LANGS_NETWORK

# Create the v1 version of the API
api = FastAPI(
    title="Simple G2P API",
    description="A simple API for the G2P module",
    version="1.1.1",
    contact={"email": "readalong.studio@gmail.com"},
    license_info={
        "name": "MIT",
        "url": "https://github.com/NRC-ILT/g2p/blob/main/LICENSE",
    },
    openapi_tags=[
        {
            "name": "ancestors",
            "description": "Find which mappings can convert to a given node",
        },
        {
            "name": "descendants",
            "description": "Find which mappings can be converted to from a given node",
        },
        {"name": "g2p", "description": "Transduced, g2p'ed forms"},
        {"name": "langs", "description": "Languages/mappings available for G2P"},
    ],
)

# Get the langs
LANGS = sorted(LANGS_NETWORK.nodes)
Lang = Enum("Lang", [(name, name) for name in LANGS])  # type: ignore


# Be compatible with previous API which returned 404 on an unknown node
@api.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    error = exc.errors()[0]
    LOGGER.error("%s", error.get("msg", "Unknown Error"))
    if error.get("type") == "enum":
        return PlainTextResponse(
            "Unknown input or output language code", status_code=404
        )
    else:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "body": exc.body},
        )


@api.get(
    "/ancestors/{node}",
    summary="get all ancestors of node",
    tags=["ancestors"],
    operation_id="getAncestors",
    response_description="The valid ancestors of a node",
)
def get_all_ancestors_of_node(
    node: Lang = Path(description="language node name"),
) -> List[str]:
    """Get the valid ancestors in the network's path to a given node. These
    are all the mappings that you can convert from in order to get the
    given node."""
    return sorted(LANGS_NETWORK.ancestors(node.name))


@api.get(
    "/descendants/{node}",
    summary="get all descendants of node",
    tags=["descendants"],
    operation_id="getDescendants",
    response_description="The valid descendants of a node",
)
def get_all_descendants_of_node(
    node: Lang = Path(description="language node name"),
) -> List[str]:
    return sorted(LANGS_NETWORK.descendants(node.name))


@api.get(
    "/g2p",
    summary="get g2p'ed form",
    tags=["g2p"],
    operation_id="convertString",
    response_description="The converted text",
)
def g2p(
    in_lang: Lang = Query(alias="in-lang", description="input lang of string"),
    out_lang: Lang = Query(alias="out-lang", description="output lang of string"),
    text: str = Query(description="string to convert"),
    index: bool = Query(False, description="return indices"),
    debugger: bool = Query(False, description="return debugging information"),
    tokenize: bool = Query(
        False,
        description="tokenize before transducing; warning: set this to true unless your text is already a single word without punctuation",
    ),
) -> dict:
    """Get the converted version of a string, given an input and output lang"""
    try:
        transducer = make_g2p(in_lang.name, out_lang.name, tokenize=tokenize)
        tg = transducer(text)
        return {
            "input-text": tg.input_string,
            "output-text": tg.output_string,
            "debugger": tg.debugger if debugger else debugger,
            "index": tg.edges if index else index,
        }
    except NoPath:
        raise HTTPException(
            status_code=400, detail=f"No path from {in_lang} to {out_lang}"
        )


@api.get(
    "/langs",
    summary="find all possible languages in g2p",
    tags=["langs"],
    operation_id="searchTable",
    response_description="search results matching criteria",
)
def langs() -> List[str]:
    """By passing in the appropriate options, you can find available mappings"""
    return LANGS
