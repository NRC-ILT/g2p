#!/usr/bin/env python

""" Checks all data resources give 200s
"""

import json
import os
import re
import sys
from typing import Dict, Union
from unittest import TestCase

from fastapi.testclient import TestClient
from pytest import main

from g2p.app import APP
from g2p.log import LOGGER
from g2p.mappings.langs import LANGS_NETWORK
from g2p.tests.public import __file__ as PUB_FILE

PUB_DIR = os.path.dirname(PUB_FILE)


class ResourceIntegrationTest(TestCase):
    """
    This tests that the api returns 200s for all basic
    GET requests.
    """

    def setUp(self):
        # routes
        self.conversion_route = "/g2p"
        for route in APP.routes:
            if route.path == "/api/v1":  # type: ignore
                self.api = route.app  # type: ignore
                self.routes = route.routes  # type: ignore
        self.routes_no_args = [
            route.path
            for route in self.routes
            if "{" not in route.path and route.path != self.conversion_route
        ]
        self.routes_only_args = [
            route.path for route in self.routes if "{" in route.path
        ]
        self.client = TestClient(self.api)
        # args
        self.arg_match = re.compile(r"\{[a-z:]+\}")
        self.args_to_check = "node"

    def test_response_code(self):
        """
        Ensure all routes return 200
        """
        for rt in self.routes_no_args:
            try:
                with self.assertLogs():  # silence the logs by asserting them
                    r = self.client.get(rt)
                assert r.status_code == 200
                LOGGER.debug("Route " + rt + " returned " + str(r.status_code))
            except Exception as exc:
                LOGGER.error("Couldn't connect. Is the API running? %s", exc)

    def test_response_code_with_args(self):
        """
        Ensure all args return 200
        """
        for ep in self.routes_only_args:
            for node in LANGS_NETWORK.nodes:
                rt = re.sub(self.arg_match, node, ep)
                try:
                    with self.assertLogs():  # silence the logs by asseting them
                        r = self.client.get(rt)
                    assert r.status_code == 200
                except Exception as exc:
                    LOGGER.error("Couldn't connect. Is the API running? %s", exc)
            LOGGER.debug(
                "Successfully tested "
                + str(len(LANGS_NETWORK.nodes))
                + " node resources at route "
                + ep
                + " ."
            )

    def test_g2p_conversion(self):
        """
        Ensure conversion returns proper response
        """
        params: Dict[str, Union[str, bool]] = {
            "in-lang": "dan",
            "out-lang": "eng-arpabet",
            "text": "hej",
            "debugger": True,
            "index": True,
        }
        minimal_params: Dict[str, Union[str, bool]] = {
            "in-lang": "dan",
            "out-lang": "eng-arpabet",
            "text": "hej",
            "debugger": False,
            "index": False,
        }
        bad_params = {"in-lang": "dan", "out-lang": "moh", "text": "hej"}
        same_params = {"in-lang": "dan", "out-lang": "dan", "text": "hej"}
        missing_params = {
            "in-lang": "not-here",
            "out-lang": "eng-arpabet",
            "text": "hej",
        }
        self.maxDiff = None
        with self.assertLogs():
            response = self.client.get(self.conversion_route, params=params)  # type: ignore
        res_json = response.json()
        assert response.status_code == 200
        with open(os.path.join(PUB_DIR, "sample_response.json")) as f:
            data = json.load(f)
        assert res_json == data
        # check minimal response
        with self.assertLogs():
            minimal_response = self.client.get(
                self.conversion_route, params=minimal_params
            )
        data["debugger"] = False
        data["index"] = False
        assert minimal_response.status_code == 200
        assert minimal_response.json() == data
        with self.assertLogs(LOGGER, level="ERROR"):
            bad_response = self.client.get(self.conversion_route, params=bad_params)
        with self.assertLogs(LOGGER, level="ERROR"):
            same_response = self.client.get(self.conversion_route, params=same_params)
        assert bad_response.status_code == 400
        assert same_response.status_code == 400
        with self.assertLogs(LOGGER, level="ERROR"):
            missing_response = self.client.get(
                self.conversion_route, params=missing_params
            )
        assert missing_response.status_code == 404
        invalid_params = {
            "in-lang": "dan",
            "out-lang": "eng-arpabet",
            "text": "hej",
            "debugger": "THIS IS NOT A BOOLEAN!!!",
            "index": "NEITHER IS THIS!!!",
        }
        with self.assertLogs(LOGGER, level="ERROR"):
            invalid_response = self.client.get(
                self.conversion_route, params=invalid_params
            )
        assert invalid_response.status_code == 422

    def test_g2p_conversion_with_tok(self):
        params_with_tok: Dict[str, Union[str, bool]] = {
            "in-lang": "fra",
            "out-lang": "eng-arpabet",
            "text": "ceci, celà",
            "debugger": True,
            "index": True,
            "tokenize": True,
        }
        with self.assertLogs():
            response = self.client.get(self.conversion_route, params=params_with_tok)
        assert response.status_code == 200
        res_json_tok = response.json()
        assert res_json_tok["debugger"][0][0][0]["input"] == "ceci"

        params_no_tok: Dict[str, Union[str, bool]] = {
            "in-lang": "fra",
            "out-lang": "eng-arpabet",
            "text": "ceci, celà",
            "debugger": True,
            "index": True,
            "tokenize": False,
        }
        with self.assertLogs():
            response = self.client.get(self.conversion_route, params=params_no_tok)
        assert response.status_code == 200
        res_json_no_tok = response.json()
        self.assertNotEqual(res_json_tok, res_json_no_tok)
        self.assertEqual(res_json_no_tok["debugger"][0][0][0]["input"], "ceci, celà")

        self.assertNotEqual(res_json_tok["debugger"], res_json_no_tok["debugger"])


if __name__ == "__main__":
    main([__file__, *sys.argv])
