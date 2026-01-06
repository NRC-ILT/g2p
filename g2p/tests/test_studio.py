#!/usr/bin/env python

"""
Test suite for the g2p-studio web app.

Requirements: python 3.8 and `test` dependencies

Before running this test suite, launch the g2p-studio server:
minimal dev mode:
    python run_studio.py
or robust server mode (*nix only, gunicorn does not work on Windows):
    gunicorn --worker-class uvicorn.workers.UvicornWorker -w 1 g2p.app:APP --bind 0.0.0.0:5000 --daemon
"""

from datetime import datetime
from random import sample
from unittest import IsolatedAsyncioTestCase, SkipTest, main

import socketio  # type: ignore
from playwright.async_api import Error as PlaywrightError  # type: ignore
from playwright.async_api import async_playwright, expect  # type: ignore

from g2p.log import LOGGER
from g2p.tests.public.data import load_public_test_data


class StudioTest(IsolatedAsyncioTestCase):
    def __init__(self, *args):
        super().__init__(*args)
        self.port = 5000
        self.debug_convert = True
        self.timeout_delay = 500

    async def test_socket_connection(self):
        client = socketio.AsyncClient()
        await client.connect(
            f"http://127.0.0.1:{self.port}", socketio_path="/ws/socket.io"
        )
        await client.disconnect()

    async def test_sanity(self):
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(channel="chrome", headless=True)
            except PlaywrightError:
                raise SkipTest("Cannot launch browser, skipping playwright tests")
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{self.port}/docs")
            await page.wait_for_timeout(self.timeout_delay)
            await page.goto(f"http://127.0.0.1:{self.port}/static/swagger.json")
            await page.wait_for_timeout(self.timeout_delay)
            await page.goto(f"http://127.0.0.1:{self.port}")
            await page.wait_for_timeout(self.timeout_delay)
            input_el = page.locator("#input")
            output_el = page.locator("#output")
            await page.type("#input", "hello world")
            await page.wait_for_timeout(self.timeout_delay)
            input_text = await input_el.input_value()
            output_text = await output_el.input_value()
            self.assertEqual(input_text, output_text)
            self.assertEqual(input_text, "hello world")
            await input_el.fill("")
            await output_el.fill("")
            await page.type("#input", "hello world")
            await page.wait_for_timeout(self.timeout_delay)
            radio_el = page.locator("#animated-radio")
            await radio_el.click()
            await page.wait_for_timeout(self.timeout_delay)

    async def test_switch_langs(self):
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(channel="chrome", headless=True)
            except PlaywrightError:
                raise SkipTest("Cannot launch browser, skipping playwright tests")
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{self.port}")
            await page.wait_for_timeout(self.timeout_delay)
            await page.type("#input", "a")
            in_lang_selector = page.locator("#input-langselect")
            # Switch to a language
            await in_lang_selector.select_option(value="alq")
            await page.wait_for_timeout(self.timeout_delay)
            settings_title = await page.text_content("#link-0")
            self.assertEqual(settings_title, "Algonquin to IPA")
            # Switch output language
            out_lang_selector = page.locator("#output-langselect")
            await out_lang_selector.select_option("eng-arpabet")
            settings_title_3 = await page.text_content("#link-2")
            self.assertEqual(settings_title_3, "English IPA to Arpabet")
            # Switch back to custom
            await in_lang_selector.select_option(value="Custom")
            await page.wait_for_timeout(self.timeout_delay)
            settings_title = await page.text_content("#link-0")
            self.assertEqual(settings_title, "Custom")
            # FIXME: Test that the table works somewhere, somehow
            # Switch to in_lang = eng-arpabet, which means there is no possible outlang
            await in_lang_selector.select_option(value="eng-arpabet")
            await page.wait_for_timeout(self.timeout_delay)
            self.assertEqual(await page.locator("#link-0").count(), 0)

    async def test_langs(self):
        langs_to_test = load_public_test_data()
        # Doing the whole test set takes a long time, so let's use a 10% random sample,
        # knowing that all cases always get exercised in test_cli.py and test_langs.py.
        # 10% is enough to catch a sudden drift where the studio might stop being campatible.
        langs_to_test = [
            langs_to_test[i]
            for i in sorted(
                sample(range(len(langs_to_test)), k=len(langs_to_test) // 10)
            )
        ]
        # Make sure we test at least one lexicon-based example
        langs_to_test.append(["eng", "eng-arpabet", "hello", "HH AH L OW "])
        # Make sure case-insensitive lexicon-based mappings are applied case insensitive
        langs_to_test.append(["eng", "eng-arpabet", "HELLO", "HH AH L OW "])
        # Exercise a multi-word lexicon-based example now that we tokenize in studio
        langs_to_test.append(
            [
                "eng",
                "eng-arpabet",
                "Well, hello there!",
                "W EH L , HH AH L OW  DH EH R !",
            ]
        )
        # And with a Custom mapping with no rules in it, we just get passthrough
        langs_to_test.append(["custom", "custom", "foo bar", "foo bar"])

        # Known issue (#441): make sure "&"->"êkwa" is not exercised until we fix #441
        # This was causing CI failures we don't want to see until the bug is fixed.
        # TODO as part of the fix for #441, please delete this block of code
        def find_test_case(test_case, langs_to_test) -> int:
            """Return the index of test_case in langs_to_test if found, -1 otherwise."""
            for i, (in_lang, out_lang, input_text, output_text, *_) in enumerate(
                langs_to_test
            ):
                if [in_lang, out_lang, input_text, output_text] == test_case:
                    return i
            return -1

        known_failure = ["crk", "crk-no-symbols", "&", "êkwa"]
        known_failure_index = find_test_case(known_failure, langs_to_test)
        if known_failure_index != -1:
            LOGGER.warning(
                f"Ignoring record {known_failure} which is known to fail due to #441"
            )
            langs_to_test.pop(known_failure_index)
        # End of #441 work-around block of code

        error_count = 0

        # The current g2p-studio app leaks memory, so that if we try to run all the test
        # cases in one single browser instance, a case (not always the same) eventually
        # breaks. While that should get patched, for now, let's make unit testing
        # reliable by running tests by blocks we know the app can handle.
        block_size = 50

        max_action_delay = 5000  # in ms - max time we'll wait for an action to work
        polling_period = 20  # in ms - polling period for action effects

        for block in range((len(langs_to_test) - 1) // block_size + 1):
            LOGGER.info("Lauching async_playwright")
            async with async_playwright() as p:
                LOGGER.info(("L" if block == 0 else "Rel") + "aunching browser")
                try:
                    browser = await p.chromium.launch(channel="chrome", headless=True)
                except PlaywrightError:
                    raise SkipTest("Cannot launch browser, skipping playwright tests")
                LOGGER.info("Loading page")
                page = await browser.new_page()
                await page.goto(
                    f"http://127.0.0.1:{self.port}", wait_until="networkidle"
                )

                # Define element locators
                input_el = page.locator("#input")
                output_el = page.locator("#output")
                in_lang_selector = page.locator("#input-langselect")
                out_lang_selector = page.locator("#output-langselect")
                table_status_selector = page.locator("#table-status")

                for i, test in enumerate(
                    langs_to_test[block_size * block : block_size * (block + 1)]
                ):
                    test_in_lang = test[0].strip()
                    test_out_lang = test[1].strip()
                    test_input_text = test[2].strip()
                    test_expected_output = test[3].strip()
                    LOGGER.info(
                        f"{i + block * block_size} {datetime.now()} "
                        f"{test_in_lang}->{test_out_lang} {test_input_text} -> {test_expected_output}"
                    )
                    timed_out_count = 0
                    for attempt in range(1, 4):
                        if attempt > 1:
                            LOGGER.info(f"Attempt #{attempt}")
                            await page.wait_for_timeout(self.timeout_delay)
                        # Clear input and output
                        await input_el.fill("")
                        await output_el.fill("")
                        output_text = ""

                        # Select the input language
                        # descendants_promise = page.wait
                        async with page.expect_request(
                            "**/descendants/" + test_in_lang
                        ) as req_info:
                            await in_lang_selector.select_option(value=test_in_lang)
                        await req_info.value
                        # wait up to max_action_delay ms for input lang to be set
                        # and for mappings to be populated give it maximum 20s to show up and fail
                        await expect(table_status_selector).to_have_attribute(
                            "state", "loaded", timeout=20000
                        )

                        # Select the output language
                        await out_lang_selector.select_option(value=test_out_lang)
                        # wait up to max_action_delay ms for output lang to be set
                        # and for mappings to be populated
                        await page.wait_for_timeout(polling_period)
                        await expect(table_status_selector).to_have_attribute(
                            "state", "loaded", timeout=20000
                        )

                        # Type fill input, then trigger rendering with keyup event
                        # optimization: make sure there is only 1 keyup event
                        await input_el.fill(test_input_text + " ")
                        await input_el.press("Backspace")

                        loop_time = 0
                        # wait up to max_action_delay ms for output to be populated
                        while loop_time <= max_action_delay:
                            output_text = await output_el.input_value()
                            if output_text.strip() == test_expected_output:
                                break
                            await page.wait_for_timeout(polling_period)
                            loop_time += polling_period
                        else:
                            LOGGER.warning(
                                f"Reached timeout setting input text for {test}"
                            )
                            timed_out_count += 1
                            continue

                        # We're done trying once an attempt succeeds
                        if output_text.strip() == test_expected_output:
                            break

                    if (
                        timed_out_count == 3
                        and output_text.strip() != test_expected_output
                    ):  # pragma: no cover
                        output_text = output_text + " (TIMED OUT)"
                    # Check that output is correct after the first succesful attempt or
                    # after all the attempts have failed.
                    if not self.debug_convert:
                        self.assertEqual(output_text.strip(), test_expected_output)
                        LOGGER.info(
                            f"Successfully converted {test_input_text} from {test_in_lang} to {test_out_lang}"
                        )
                    elif output_text.strip() != test_expected_output:
                        LOGGER.warning(
                            f"test_langs.py: mapping error: {test_input_text} from {test_in_lang} "
                            f"to {test_out_lang} should be {test_expected_output}, got {output_text}"
                        )
                        if error_count == 0:
                            first_failed_test = [test_expected_output, output_text]
                        error_count += 1
                    else:
                        LOGGER.info(
                            f"Successfully converted {test_input_text} from {test_in_lang} to {test_out_lang}"
                        )

                # Let the user know we're closing the browser (by exiting the p context
                # manager scope) to explain why there's a delay here.
                LOGGER.info("Closing browser")

        if self.debug_convert and error_count > 0:
            self.assertEqual(
                first_failed_test[0],
                first_failed_test[1],
                f"{error_count} lang mapping test case(s) failed, "
                "look for warnings in the logs above for details.",
            )


if __name__ == "__main__":
    main()
