"""
The g2p Studio web app.

You can run the app (and API) for development purposes on any platform with:
    pip install uvicorn
    uvicorn g2p.app:APP --reload --port 5000
- The --reload switch will watch for changes under the directory where it's
  running and reload the code whenever it changes.

You can also spin up the app server grade (on Linux, not Windows) with gunicorn:
    gunicorn -w 4 -k uvicorn.workers.UvicornWorker g2p.app:APP --port 5000

Once spun up, the application will be visible at
http://localhost:5000/ and the API at http://localhost:5000/api/v1/docs

"""

import os
from pathlib import Path
from typing import Dict, List, Union

import socketio  # type: ignore
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

import g2p
from g2p import make_g2p, make_tokenizer
from g2p.api import api as api_v1
from g2p.api_v2 import api as api_v2
from g2p.log import LOGGER
from g2p.mappings import Mapping, Rule
from g2p.mappings.langs import LANGS_NETWORK
from g2p.mappings.utils import (
    _MappingModelDefinition,
    expand_abbreviations_format,
    flatten_abbreviations_format,
)
from g2p.transducer import (
    BaseTransducer,
    CompositeTransducer,
    CompositeTransductionGraph,
    TokenizingTransducer,
    Transducer,
    TransductionGraph,
)

DEFAULT_N = 10

BASE_DIR = Path(g2p.__file__).parent

TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
server_args: Dict[str, Union[bool, str]] = {"async_mode": "asgi"}
if os.getenv("G2P_STUDIO_DEBUG"):
    server_args["logger"] = server_args["engineio_logger"] = True
SIO = socketio.AsyncServer(**server_args)
SIO_APP = socketio.ASGIApp(socketio_server=SIO, socketio_path="/ws/socket.io")


async def home(request: Request) -> HTMLResponse:
    """Return homepage of g2p studio"""
    return TEMPLATES.TemplateResponse(request, "index.html")


async def redirect_to_docs(request: Request) -> RedirectResponse:
    """Redirect to v1 API docs for backward compatibility"""
    return RedirectResponse(url="/api/v1/docs/")


async def redirect_to_openapi(request: Request) -> RedirectResponse:
    """Redirect to v1 API JSON for backward compatibility"""
    return RedirectResponse(url="/api/v1/openapi.json")


APP = Starlette(
    debug=True,
    routes=[
        Route("/", home),
        Mount("/ws", SIO_APP),
        Mount("/api/v1", api_v1),
        Mount("/api/v2", api_v2),
        Route("/static/swagger.json", redirect_to_openapi),
        Mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static"),
        Route("/docs", redirect_to_docs),
    ],
)


def shade_colour(colour, percent, r=0, g=0, b=0):
    R = hex(min(255, int(int(colour[1:3], 16) * (100 + percent + r) / 100))).lstrip(
        "0x"
    )
    G = hex(min(255, int(int(colour[3:5], 16) * (100 + percent + g) / 100))).lstrip(
        "0x"
    )
    B = hex(min(255, int(int(colour[5:], 16) * (100 + percent + b) / 100))).lstrip("0x")
    return "#" + str(R) + str(G) + str(B)


def contrasting_text_color(hex_str):
    (R, G, B) = (hex_str[1:3], hex_str[3:5], hex_str[5:])
    return (
        "#000"
        if 1 - (int(R, 16) * 0.299 + int(G, 16) * 0.587 + int(B, 16) * 0.114) / 255
        < 0.5
        else "#fff"
    )


def return_echart_data(tg: Union[CompositeTransductionGraph, TransductionGraph]):
    x = 100
    diff = 200
    nodes = []
    edges = []
    index_offset = 0
    colour = "#222222"
    if isinstance(tg, CompositeTransductionGraph):
        steps = len(tg.tiers)
    else:
        steps = 1
    for ind, tier in enumerate(tg.tiers):
        if ind == 0:
            symbol_size = round(min(300 / max(1, len(tier.input_string)), 40), 2)
            input_x = x + (ind * diff)
            input_y = 300
            x += diff
            inputs = [
                {
                    "name": f"{x}",
                    "id": f"(in{ind + index_offset}-in{i + index_offset})",
                    "x": input_x,
                    "y": input_y + (i * 50),
                    "symbolSize": symbol_size,
                    "label": {"color": contrasting_text_color(colour)},
                    "itemStyle": {
                        "color": colour,
                        "borderColor": contrasting_text_color(colour),
                    },
                }
                for i, x in enumerate(tier.input_string)
            ]
            nodes += inputs
        edges += [
            {
                "source": x[0] + index_offset,
                "target": x[1] + len(tier.input_string) + index_offset,
            }
            for x in tier.edges
            if x[1] is not None
        ]
        index_offset += len(tier.input_string)
        symbol_size = round(min(300 / max(1, len(tier.output_string)), 40), 2)
        colour = shade_colour(colour, (1 / steps) * 350, g=50, b=20)
        output_x = x + (ind * diff)
        output_y = 300
        outputs = [
            {
                "name": f"{x}",
                "id": f"({ind + index_offset}-{i + index_offset})",
                "x": output_x,
                "y": output_y + (i * 50),
                "symbolSize": symbol_size,
                "label": {"color": contrasting_text_color(colour)},
                "itemStyle": {
                    "color": colour,
                    "borderColor": contrasting_text_color(colour),
                },
            }
            for i, x in enumerate(tier.output_string)
        ]
        nodes += outputs
    return nodes, edges


@SIO.on("conversion event", namespace="/convert")  # type: ignore
async def convert(sid, message):
    """Convert input text and return output"""
    transducers = []
    LOGGER.debug("/convert: %s", message)
    transducer: BaseTransducer
    for mapping in message["data"]["mappings"]:
        mapping_args = {**mapping["kwargs"]}
        mapping_args["abbreviations"] = flatten_abbreviations_format(
            mapping["abbreviations"]
        )
        if mapping_args["type"] == "lexicon":
            lexicon = Mapping.find_mapping(
                mapping_args["in_lang"], mapping_args["out_lang"]
            )
            mapping_args["alignments"] = lexicon.alignments
        else:
            mapping_args["rules"] = mapping["rules"]
        try:
            mappings_obj = Mapping(**mapping_args)
            transducer = Transducer(mappings_obj)
            transducers.append(transducer)
        except Exception as e:
            LOGGER.warning(
                "Skipping invalid mapping %s->%s:\n%s",
                mapping_args["in_lang"],
                mapping_args["out_lang"],
                e,
            )
    if len(transducers) == 0:
        # This happens when we switch between output langs in g2p-studio
        await SIO.emit(
            "conversion response",
            {"output_string": message["data"]["input_string"]},
            sid,
            namespace="/convert",
        )
        return
    transducer = CompositeTransducer(transducers)
    try:
        in_lang = message["data"]["mappings"][0]["kwargs"]["in_lang"]
        tokenizer = make_tokenizer(in_lang)
        transducer = TokenizingTransducer(transducer, tokenizer)
    except Exception:
        # We tokenize by default when it works (see try block) but just skip
        # tokenization in case of problem: it's not a bug, tokenization is optional.
        pass
    if message["data"]["index"]:
        tg = transducer(message["data"]["input_string"])
        data, links = return_echart_data(tg)
        await SIO.emit(  # type: ignore
            "conversion response",
            {
                "output_string": tg.output_string,
                "index_data": data,
                "index_links": links,
            },
            sid,
            namespace="/convert",
        )
    else:
        output_string = transducer(message["data"]["input_string"]).output_string
        await SIO.emit(  # type: ignore
            "conversion response",
            {"output_string": output_string},
            sid,
            namespace="/convert",
        )


@SIO.on("table event", namespace="/table")  # type: ignore
async def change_table(sid, message) -> None:
    """Change the lookup table"""
    LOGGER.debug("/table: %s", message)
    if "in_lang" not in message or "out_lang" not in message:
        await SIO.emit(
            "table response",
            [],
            sid,
            namespace="/table",
        )
    elif message["in_lang"] == "custom" or message["out_lang"] == "custom":
        # These are only used to generate JSON to send to the client,
        # so it's safe to create a list of references to the same thing.
        mapping_dicts = [
            {"in": "", "out": "", "context_before": "", "context_after": ""}
        ] * DEFAULT_N
        abbs = [[""] * 6] * DEFAULT_N

        kwargs = _MappingModelDefinition(
            language_name="Custom",
            display_name="Custom",
            in_lang="custom",
            out_lang="custom",
            type="mapping",
            norm_form="NFC",
            # Put something here to silence a warning
            rules=[Rule(rule_input="a", rule_output="a")],
        ).model_dump()
        kwargs["rules"] = []
        # Remove the bogus rule we used to silence the validator
        kwargs["include"] = False
        await SIO.emit(
            "table response",
            [
                {
                    "mappings": mapping_dicts,
                    "abbs": abbs,
                    "kwargs": kwargs,
                }
            ],
            sid,
            namespace="/table",
        )
    else:
        path = LANGS_NETWORK.shortest_path(message["in_lang"], message["out_lang"])
        mappings: List[Mapping] = []
        for lang1, lang2 in zip(path[:-1], path[1:]):
            transducer = make_g2p(lang1, lang2, tokenize=False)
            mappings.append(transducer.mapping)  # type: ignore
        await SIO.emit(
            "table response",
            [
                {
                    "mappings": mapping.plain_mapping(),
                    "abbs": expand_abbreviations_format(mapping.abbreviations),
                    "kwargs": mapping.model_dump(exclude={"alignments"}),
                }
                for mapping in mappings
            ],
            sid,
            namespace="/table",
        )


@SIO.on("connect", namespace="/connect")  # type: ignore
async def test_connect(sid, message):
    """Let client know disconnected"""
    await SIO.emit(  # type: ignore
        "connection response", {"data": "Connected"}, sid, namespace="/connect"
    )


@SIO.on("disconnect", namespace="/connect")  # type: ignore
async def test_disconnect(sid):
    """Let client know disconnected"""
    await SIO.emit(  # type: ignore
        "connection response", {"data": "Disconnected"}, sid, namespace="/connect"
    )
