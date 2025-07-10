#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo how to crawl a web site.
"""

from http import HTTPStatus
import asyncio
import json
import pathlib
import sys

from bs4 import BeautifulSoup
from icecream import ic
import requests
import requests_cache

from nyddu import Crawler, Page


async def queue (
    page_queue: list,
    session: requests_cache.CachedSession,
    ) -> None:
    """
Crawl the external pages.
    """
    for i, page in enumerate(page_queue):
        ic(page)

        html: typing.Optional[ str ] = await page.request_content(
            session,
            allow_redirects = True,
        )

        if html is not None and page.content_type in [ "text/html" ] and page.status_code not in [ HTTPStatus.NOT_FOUND ]:
            soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
            page.extract_meta(soup)

        ic(page.to_json())

        if i > 11:
            sys.exit(0)                
    

if __name__ == "__main__":
    page_queue: list = []
    report_path: pathlib.Path = pathlib.Path("report")

    with open(report_path, "rb") as fp:
        report: list = json.load(fp)

        for item in report:
            page: Page = Page(
                uri = item["uri"],
                kind = item["kind"],
                path = item["path"],
                slug = item["slug"],
            )

            if page.kind in [ "external" ]:
                page_queue.append(page)


    crawler: Crawler = Crawler(
        config_path = pathlib.Path("config.toml"),
    )

    asyncio.run(
        queue(
            page_queue,
            crawler.session,
        )
    )
