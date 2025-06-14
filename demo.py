#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo script.
"""

import asyncio

from nyddu import Crawler


if __name__ == "__main__":
    crawler: Crawler = Crawler(
        site_base = "https://derwen.ai",
        path_rewrites = {
            "/rates": "/flywheel",
            "/watchlist": "/events",
        },
        ignored_paths = set([
            "/articles",
            "/auth/login",
            "/merch",
            "/cdn-cgi/l/email-protection",
            "/robots.txt",
            "/sitemap.xml",
        ]),
    )

    asyncio.run(
        crawler.crawl(
            site_map = "https://derwen.ai/sitemap.xml",
        )
    )

    crawler.report()
