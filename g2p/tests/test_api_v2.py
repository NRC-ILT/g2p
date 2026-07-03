#!/usr/bin/env python
import sys
from contextlib import redirect_stderr
from io import StringIO
from unittest import TestCase

from fastapi.testclient import TestClient
from pytest import main

from g2p.api_v2 import api

API_CLIENT = TestClient(api)


class TestAPIV2(TestCase):
    def test_langs(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.get("/langs")
        self.assertEqual(response.status_code, 200)
        codes = {x["code"] for x in response.json()}
        assert "fin" in codes
        assert "atj" in codes
        self.assertFalse("generated" in codes)
        self.assertFalse("atj-ipa" in codes)
        names = {x["name"] for x in response.json()}
        assert "Finnish" in names

    def test_langs_allcodes(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.get("/nodes")
        self.assertEqual(response.status_code, 200)
        codes = {x["code"] for x in response.json()}
        assert "eng-arpabet" in codes
        assert "eng-ipa" in codes
        assert "atj" in codes
        self.assertFalse("generated" in codes)

    def test_outputs_for(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.get("/outputs_for/fin")
        self.assertEqual(response.status_code, 200)
        assert "eng-arpabet" in response.json()
        assert "eng-ipa" in response.json()

    def test_inputs_for(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.get("/inputs_for/eng-arpabet")
        self.assertEqual(response.status_code, 200)
        assert "fin" in response.json()
        assert "eng-ipa" in response.json()

    def test_convert(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.post(
                "/convert",
                json={
                    "in_lang": "fin",
                    "out_lang": "eng-arpabet",
                    "text": "hyvää yötä",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "conversions": [
                        {
                            "in_lang": "eng-ipa",
                            "out_lang": "eng-arpabet",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["h", "HH "],
                                ["u", "UW "],
                                ["w", "W "],
                                ["æ", "AE "],
                            ],
                        },
                        {
                            "in_lang": "fin-ipa",
                            "out_lang": "eng-ipa",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["h", "h"],
                                ["y", "u"],
                                ["ʋ", "w"],
                                ["æː", "æ"],
                            ],
                        },
                        {
                            "in_lang": "fin",
                            "out_lang": "fin-ipa",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["h", "h"],
                                ["y", "y"],
                                ["v", "ʋ"],
                                ["ä", "æ"],
                                ["ä", "ː"],
                            ],
                        },
                    ]
                },
                {
                    "conversions": [
                        {
                            "in_lang": None,
                            "out_lang": None,
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [[" ", " "]],
                        }
                    ]
                },
                {
                    "conversions": [
                        {
                            "in_lang": "eng-ipa",
                            "out_lang": "eng-arpabet",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["u", "UW "],
                                ["ə", "AH "],
                                ["t", "T "],
                                ["æ", "AE "],
                            ],
                        },
                        {
                            "in_lang": "fin-ipa",
                            "out_lang": "eng-ipa",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["y", "u"],
                                ["ø", "ə"],
                                ["t", "t"],
                                ["æ", "æ"],
                            ],
                        },
                        {
                            "in_lang": "fin",
                            "out_lang": "fin-ipa",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["y", "y"],
                                ["ö", "ø"],
                                ["t", "t"],
                                ["ä", "æ"],
                            ],
                        },
                    ]
                },
            ],
        )

    def test_convert_composed(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.post(
                "/convert",
                json={
                    "in_lang": "fin",
                    "out_lang": "eng-arpabet",
                    "text": "hyvää yötä",
                    "compose_from": "fin",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "conversions": [
                        {
                            "in_lang": "fin",
                            "out_lang": "eng-arpabet",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["h", "HH "],
                                ["y", "UW "],
                                ["v", "W "],
                                ["ää", "AE "],
                            ],
                        },
                    ],
                },
                {
                    "conversions": [
                        {
                            "in_lang": None,
                            "out_lang": None,
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [[" ", " "]],
                        }
                    ]
                },
                {
                    "conversions": [
                        {
                            "in_lang": "fin",
                            "out_lang": "eng-arpabet",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["y", "UW "],
                                ["ö", "AH "],
                                ["t", "T "],
                                ["ä", "AE "],
                            ],
                        },
                    ]
                },
            ],
        )

    def test_convert_compose_from(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.post(
                "/convert",
                json={
                    "in_lang": "fin",
                    "out_lang": "eng-arpabet",
                    "text": "hyvää yötä",
                    "compose_from": "fin-ipa",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "conversions": [
                        {
                            "in_lang": "fin-ipa",
                            "out_lang": "eng-arpabet",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["h", "HH "],
                                ["y", "UW "],
                                ["ʋ", "W "],
                                ["æː", "AE "],
                            ],
                        },
                        {
                            "in_lang": "fin",
                            "out_lang": "fin-ipa",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["h", "h"],
                                ["y", "y"],
                                ["v", "ʋ"],
                                ["ä", "æ"],
                                ["ä", "ː"],
                            ],
                        },
                    ],
                },
                {
                    "conversions": [
                        {
                            "in_lang": None,
                            "out_lang": None,
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [[" ", " "]],
                        }
                    ]
                },
                {
                    "conversions": [
                        {
                            "in_lang": "fin-ipa",
                            "out_lang": "eng-arpabet",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["y", "UW "],
                                ["ø", "AH "],
                                ["t", "T "],
                                ["æ", "AE "],
                            ],
                        },
                        {
                            "in_lang": "fin",
                            "out_lang": "fin-ipa",
                            "input_nodes": None,
                            "output_nodes": None,
                            "alignments": None,
                            "substring_alignments": [
                                ["y", "y"],
                                ["ö", "ø"],
                                ["t", "t"],
                                ["ä", "æ"],
                            ],
                        },
                    ]
                },
            ],
        )

    def test_convert_surrogates(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.post(
                "/convert",
                json={
                    "in_lang": "eng-ipa",
                    "out_lang": "eng-arpabet",
                    "text": "hi🙂hi",
                    "indices": True,
                    "tokenize": False,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "conversions": [
                        {
                            "in_lang": "eng-ipa",
                            "out_lang": "eng-arpabet",
                            "input_nodes": ["h", "i", "🙂", "h", "i"],
                            "output_nodes": [
                                "H",
                                "H",
                                " ",
                                "I",
                                "Y",
                                " ",
                                "🙂",
                                "H",
                                "H",
                                " ",
                                "I",
                                "Y",
                                " ",
                            ],
                            "alignments": [
                                [0, 0],
                                [0, 1],
                                [0, 2],
                                [1, 3],
                                [1, 4],
                                [1, 5],
                                [2, 6],
                                [3, 7],
                                [3, 8],
                                [3, 9],
                                [4, 10],
                                [4, 11],
                                [4, 12],
                            ],
                            "substring_alignments": [
                                ["h", "HH "],
                                ["i", "IY "],
                                ["🙂", "🙂"],
                                ["h", "HH "],
                                ["i", "IY "],
                            ],
                        }
                    ]
                }
            ],
        )

    def test_convert_no_path(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.post(
                "/convert",
                json={
                    "in_lang": "fin",
                    "out_lang": "fra",
                    "text": "hyvää yötä",
                },
            )
        self.assertEqual(response.status_code, 400)

    def test_convert_invalid(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.post(
                "/convert",
                json={
                    "in_lang": "Finnish",
                    "out_lang": "eng-arpabet",
                    "text": "hyvää yötä",
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertIn("Input should be", response.json()["detail"][0]["msg"])

    def test_path(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.get("/path/fin/eng-arpabet")
        self.assertEqual(response.status_code, 200)
        path = response.json()
        self.assertEqual(path, ["fin", "fin-ipa", "eng-ipa", "eng-arpabet"])

    def test_no_path(self):
        with redirect_stderr(StringIO()):
            response = API_CLIENT.get("/path/fin/fra")
        self.assertEqual(response.status_code, 400)
        self.assertIn("No path", response.json()["detail"])


if __name__ == "__main__":
    main([__file__, *sys.argv])
