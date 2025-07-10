#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo script.
"""

import asyncio
import json
import logging
import pathlib
import sys  # pylint: disable=W0611
import typing

from icecream import ic  # type: ignore  # pylint: disable=W0611
from pyinstrument import Profiler
import w3lib.url

from nyddu import Crawler, ShortenedURL, URLKind


if __name__ == "__main__":
    # set up logging
    logging.basicConfig(
        encoding = "utf-8",
        level = logging.INFO,
    )

    # load the shortened URLs
    shorty: typing.Dict[ str, ShortenedURL ] = {}

    with open(pathlib.Path("shorty.json"), encoding = "utf-8") as fp:
        for key, val in json.load(fp).items():
            if not (key.startswith("http://") or key.startswith("https://")):
                uri: str = f"/s/{key}"

                if val.startswith("urn:"):
                    shorty[uri] = ShortenedURL(uri, val, URLKind.URN)

                elif val.startswith("https://derwen.ai"):
                    shorty[uri] = ShortenedURL(uri, val, URLKind.INTERNAL)

                else:
                    val = w3lib.url.canonicalize_url(val)
                    shorty[uri] = ShortenedURL(uri, val, URLKind.EXTERNAL)

    # start code profiling
    profiler: Profiler = Profiler()
    profiler.start()

    # run the crawler
    crawler: Crawler = Crawler(
        config_path = pathlib.Path("config.toml"),
        path_rewrites = {
            "/rates": "/flywheel",
            "/watchlist": "/events",
        },
        ignored_paths = set([
            "/articles",
            "/cdn-cgi/l/email-protection",
            "/cysoni",
            "/liber118_tboo",
            "/merch",
            "/meet",
            "/newsletter",
            "/sitemap.xml",
            "/uptime",
        ]),
        ignored_prefix = [
            "/docs/",
            "/auth/",
        ],
        shorty = shorty,
    )

    asyncio.run(
        crawler.crawl()
    )

    #sys.exit(0)

    # end code profiling
    profiler.stop()

    # serialize intermediate data / report
    with open(pathlib.Path("report"), "w", encoding = "utf-8") as fp:
        fp.write(
            json.dumps(
                crawler.report(),
                sort_keys = True,
                indent = 2,
            )
        )

    profiler.print()
