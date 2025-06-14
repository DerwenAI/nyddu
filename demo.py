#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo script.
"""

import asyncio
import json
import pathlib
import sys  # pylint: disable=W0611
import typing

from icecream import ic
from pyinstrument import Profiler
import w3lib.url

from nyddu import Crawler, ShortenedURL, URLKind


if __name__ == "__main__":
    # load the shortened URLs
    shorty: typing.Dict[ str, ShortenedURL ] = {}

    with open(pathlib.Path("shorty.json"), encoding = "utf-8") as fp:
        for key, val in json.load(fp).items():
            if not (key.startswith("http://") or key.startswith("https://")):
                uri: str = f"/s/{key}"

                if val.startswith("urn:"):
                    shorty[uri] = ShortenedURL(uri, val, URLKind.URN)
                    ic(shorty[uri])

                elif val.startswith("https://derwen.ai"):
                    shorty[uri] = ShortenedURL(uri, val, URLKind.INTERNAL)

                else:
                    val = w3lib.url.canonicalize_url(val)
                    shorty[uri] = ShortenedURL(uri, val, URLKind.EXTERNAL)

    ## start code profiling
    profiler: Profiler = Profiler()
    profiler.start()

    # run the crawler
    crawler: Crawler = Crawler(
        site_base = "https://derwen.ai",
        path_rewrites = {
            "/rates": "/flywheel",
            "/watchlist": "/events",
        },
        ignored_paths = set([
            "/articles",
            "/auth/account",
            "/auth/login",
            "/cdn-cgi/l/email-protection",
            "/cysoni",
            "/docs/kgl",
            "/docs/kgl/",
            "/docs/kgl/learn",
            "/docs/ptr",
            "/docs/ptr/",
            "/docs/txg",
            "/docs/txg/",
            "/liber118_tboo",
            "/merch",
            "/newsletter",
            "/robots.txt",
            "/sitemap.xml",
            "/uptime",
        ]),
        shorty = shorty,
    )

    asyncio.run(
        crawler.crawl(
            site_map = "https://derwen.ai/sitemap.xml",
        )
    )

    ## end code profiling
    profiler.stop()

    #sys.exit(0)
    crawler.report()
    profiler.print()
