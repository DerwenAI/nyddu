#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Adapted from an HTML scraper based on Selenium by Clair Sullivan:
<https://github.com/cj2001/senzing_website_scraper/>
"""

import logging
import time
import typing
import urllib.parse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


FAUX_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"  # pylint: disable=C0301

EXCLUDED_EXTENSIONS: typing.Set[ str ] = set([
    ".7z",
    ".avi",
    ".bmp",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".flv",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".jsonl",
    ".log",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".sql",
    ".svg",
    ".tar",
    ".tsv",
    ".txt",
    ".webp",
    ".wmv",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
])

RESTART_KEYWORDS: typing.Set[ str ] = set([
    "chrome not reachable",
    "connection",
    "renderer",
    "session",
])


class Scraper:
    """
Selenium-based web page scraper, for when sites block the direct use
of the `requests` library.
    """

    def __init__ (
        self,
        *,
        delay: int = 3,
        user_agent: str = FAUX_USER_AGENT,
        ) -> None:
        """
Constructor.
        """
        self.driver: typing.Optional[ webdriver.Chrome ] = None
        self.delay: int = delay

        # setup driver options
        self.chrome_options: Options = Options()

        self.chrome_options.add_argument("--headless")  # Run in background
        self.chrome_options.add_argument(f"--user-agent={user_agent}")

        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", [ "enable-automation" ])
        self.chrome_options.add_experimental_option("useAutomationExtension", False)

        # timeout settings
        self.chrome_options.add_argument("--page-load-strategy=eager")
        self.chrome_options.add_argument("--disable-extensions")
        self.chrome_options.add_argument("--disable-plugins")


    def init_driver (
        self
        ) -> bool:
        """
Test the installed driver before scraping.
        """
        try:
            self.driver = webdriver.Chrome(
                options = self.chrome_options,
            )

            self.driver.set_page_load_timeout(45)  # increased timeout
            self.driver.implicitly_wait(5)  # reduced implicit wait

            # remove `webdriver` property
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception as ex:  # pylint: disable=W0718
            logging.error("failed to initialize Chrome driver: %s", str(ex))
            return False

        return True


    def close_driver (
        self
        ) -> None:
        """
Close the Chrome driver.
        """
        if self.driver is not None:
            self.driver.quit()
            self.driver = None


    def valid_for_extraction (
        self,
        url: str,
        ) -> bool:
        """
Check if URL is valid for extraction:

  * filter out non-HTML files
  * confirm that URL doesn't end with an excluded extension
        """
        try:
            parsed: urllib.parse.ParseResult = urllib.parse.urlparse(url)
            path: str = parsed.path.lower()

            for ext in EXCLUDED_EXTENSIONS:
                if path.endswith(ext):
                    return False

            return parsed.scheme in [ "http", "https" ]
        except Exception:  # pylint: disable=W0718
            return False


    async def scrape_page (  # pylint: disable=R0911,R0912,R0915
        self,
        url: str,
        *,
        max_retries: int = 3,
        ) -> typing.Optional[ str ]:
        """
Scrape a single page, with timeout handling.
        """
        if not self.valid_for_extraction(url):
            return None

        for attempt in range(max_retries):
            try:
                logging.debug("scraping: %s (attempt %d/%d", url, attempt + 1, max_retries)

                if attempt == 1:
                    msg: str = str(getattr(self, "last_error", ""))

                    if "timeout: Timed out receiving message from renderer" in msg:
                        logging.error("🔧 detected renderer timeout")
                        return None

                # try a simple get first to test connection
                try:
                    self.driver.get("about:blank")  # type: ignore
                    time.sleep(0.5)
                except Exception:  # pylint: disable=W0718
                    logging.error("🔧 driver seems stuck")
                    return None

                # navigate to the actual page
                self.driver.get(url)  # type: ignore

                # wait for body element with timeout
                try:
                    WebDriverWait(self.driver, 20).until(  # type: ignore
                        EC.presence_of_element_located((By.TAG_NAME, "body"))  # type: ignore
                    )
                except TimeoutException:
                    logging.error("⏰ body element not found, continuing anyway")

                # additional wait for dynamic content
                if attempt == 0:
                    time.sleep(self.delay)
                else:
                    time.sleep(min(self.delay, 3))

                # try to scroll, but don't fail if it doesn't work
                try:
                    scroll_script: str = "window.scrollTo(0, Math.min(document.body.scrollHeight, 1000));"  # pylint: disable=C0301
                    self.driver.execute_script(scroll_script)  # type: ignore
                    time.sleep(1)
                except Exception as scroll_error:  # pylint: disable=W0718
                    logging.error("⚠️  scroll failed: %s", scroll_error)

                # get the page source, which is where renderer timeouts often happen
                try:
                    page_source: typing.Optional[ str ] = self.driver.page_source  # type: ignore

                    if page_source is None or len(page_source) < 10:
                        raise RuntimeError("page source too short or empty")
                except Exception as source_error:  # pylint: disable=W0718
                    logging.error("❌ failed to get page source: %s", source_error)

                    if attempt < max_retries - 1:
                        logging.debug("🔄 will retry %s", url)
                        continue

                    return None

                logging.debug("✅ successfully scraped %s", url)
                return page_source

            except TimeoutException as ex:
                error_msg: str = str(ex)
                logging.error("⏰ timeout on %s (attempt %d): %s", url, attempt + 1, error_msg[:100])

                if "renderer" in error_msg.lower():
                    logging.error("🔧 renderer timeout detected")

                if attempt < max_retries - 1:
                    logging.debug("🔄 will retry %s", url)
                    time.sleep(3)  # Longer pause for timeouts
                else:
                    logging.error("❌ failed to scrape %s after %d attempts", url, max_retries)
                    return None

            except WebDriverException as ex:
                error_msg = str(ex)
                logging.error("🚫 WebDriver error on %s (attempt %d): %s", url, attempt + 1, error_msg[:100])  # pylint: disable=C0301

                # check for specific error types that need driver restart
                if any(keyword in error_msg.lower() for keyword in RESTART_KEYWORDS):
                    logging.debug("🔧 detected driver issue, restart before next attempt")

                if attempt < max_retries - 1:
                    logging.debug("🔄 will retry %s", url)
                    time.sleep(5) # wait even longer for WebDriver errors
                else:
                    return None

            except Exception as ex:  # pylint: disable=W0718
                error_msg = str(ex)
                logging.error("❌ unexpected error on %s: %s", url, error_msg)

                if attempt < max_retries - 1:
                    logging.debug("🔄 will retry %s", url)
                    time.sleep(2)
                else:
                    return None

        return None
