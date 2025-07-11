#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Adapted from a scraper based on Selenium by Clair Sullivan:
<https://github.com/cj2001/senzing_website_scraper/>
"""

from urllib.parse import urlparse
import time
import typing

from icecream import ic  # type: ignore  # pylint: disable=W0611
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


FAUX_USER_AGENT: str = "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

EXCLUDED_EXTENSIONS: typing.List[ str ] = [
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
]


class SeleniumScraper:
    """
Selenium-based web page scraper, for when sites block the direct use
of the `requests` library.
    """

    def __init__ (
        self,
        delay: int = 3,
        ) -> None:
        """
Constructor.
        """
        self.delay: int = delay
        self.driver = None

        # setup driver options
        self.chrome_options = Options()

        self.chrome_options.add_argument("--headless")  # Run in background
        self.chrome_options.add_argument(FAUX_USER_AGENT)

        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", [ "enable-automation" ])
        self.chrome_options.add_experimental_option("useAutomationExtension", False)

        # timeout settings
        self.chrome_options.add_argument("--page-load-strategy=eager")  # don't wait for all resources
        self.chrome_options.add_argument("--disable-extensions")
        self.chrome_options.add_argument("--disable-plugins")

    
    def test_driver (
        self
        ) -> bool:
        """
Test driver before scraping.
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
            
            return True

        except Exception as ex:
            print(f"❌ Failed to initialize Chrome driver: {str(ex)}")
            return False

    
    def close_driver (
        self
        ) -> None:
        """
Close the Chrome driver.
        """
        if self.driver:
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
            parsed = urlparse(url)
            path = parsed.path.lower()

            for ext in EXCLUDED_EXTENSIONS:
                if path.endswith(ext):
                    return False
            
            return parsed.scheme in [ "http", "https" ]

        except:
            return False

    
    def scrape_page (
        self,
        url: str,
        *,
        debug: bool = True,
        max_retries: int = 3,
        ) -> typing.Optional[ str ]:
        """
Scrape a single page with timeout handling and retries
        """
        if not self.valid_for_extraction(url):
            return None

        for attempt in range(max_retries):
            try:
                if debug:
                    print(f"scraping: {url} (attempt {attempt + 1}/{max_retries})")
                
                # for renderer timeout issues, restart driver on second attempt
                if attempt == 1 and "timeout: Timed out receiving message from renderer" in str(getattr(self, "last_error", "")):
                    if debug:
                        print("  🔧 Detected renderer timeout")

                    return None
                
                # try a simple get first to test connection
                try:
                    self.driver.get("about:blank")
                    time.sleep(0.5)
                except:
                    if debug:
                        print("  🔧 Driver seems stuck")
                
                # navigate to the actual page
                self.driver.get(url)
                
                # wait for body element with timeout
                try:
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except TimeoutException:
                    if debug:
                        print("  ⏰ Body element not found, but continuing...")
                
                # additional wait for dynamic content
                time.sleep(min(self.delay, 3) if attempt > 0 else self.delay)
                
                # try to scroll, but don't fail if it doesn't work
                try:
                    self.driver.execute_script("window.scrollTo(0, Math.min(document.body.scrollHeight, 1000));")
                    time.sleep(1)
                except Exception as scroll_error:
                    if debug:
                        print(f"  ⚠️ Scroll failed: {scroll_error}")
                
                # get page source - this is where renderer timeouts often happen
                try:
                    page_source = self.driver.page_source

                    if not page_source or len(page_source) < 10:
                        raise Exception("page source too short or empty")
                except Exception as source_error:
                    if debug:
                        print(f"  ❌ Failed to get page source: {source_error}")

                    if attempt < max_retries - 1:
                        if debug:
                            print(f"  🔄 Will retry {url}...")

                        continue
                    else:
                        return None
                
                if debug:
                    print(f"  ✅ Successfully scraped {url}")

                return page_source
                
            except TimeoutException as ex:
                error_msg = str(ex)

                if debug:
                    print(f"  ⏰ Timeout on {url} (attempt {attempt + 1}): {error_msg[:100]}...")
                
                    if "renderer" in error_msg.lower():
                        print("  🔧 Renderer timeout detected")
                
                if attempt < max_retries - 1:
                    if debug:
                        print(f"  🔄 Retrying {url}...")

                    time.sleep(3)  # Longer pause for timeouts
                else:
                    if debug:
                        print(f"  ❌ Failed to scrape {url} after {max_retries} attempts")

                    return None
                    
            except WebDriverException as ex:
                error_msg = str(ex)

                if debug:
                    print(f"  🚫 WebDriver error on {url} (attempt {attempt + 1}): {error_msg[:100]}...")
                
                # check for specific error types that need driver restart
                restart_keywords = [ "renderer", "session", "connection", "chrome not reachable" ]

                if debug and any(keyword in error_msg.lower() for keyword in restart_keywords):
                    print("  🔧 detected driver issue, restart before next attempt")
                
                if attempt < max_retries - 1:
                    if debug:
                        print(f"  🔄 Retrying {url}...")

                    # wait even longer for WebDriver errors
                    time.sleep(5)
                else:
                    return None
                    
            except Exception as ex:
                error_msg = str(ex)

                if debug:
                    print(f"  ❌ Unexpected error on {url}: {error_msg}")

                if attempt < max_retries - 1:
                    if debug:
                        print(f"  🔄 Retrying {url}...")

                    time.sleep(2)
                else:
                    return None
        
        return None

    
if __name__ == "__main__":
    try:
        scraper: SeleniumScraper = SeleniumScraper()
        
        if scraper.test_driver():
            url: str = "https://senzing.com/consult-entity-resolution-paco/"
            #url = "https://derwen.ai/paco"

            html: str = scraper.scrape_page(url)
            ic(url, len(html))

    except KeyboardInterrupt:
        print("\n🛑 scraping interrupted by user")
    except Exception as ex:
        print(f"\n❌ error: {str(ex)}")

    finally:
        if scraper.driver is not None:
            scraper.close_driver()
