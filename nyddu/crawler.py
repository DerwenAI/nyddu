#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Crawler class for Nyddu.
see copyright/license https://github.com/DerwenAI/nyddu/README.md
"""

from http import HTTPStatus
import asyncio
import logging
import pathlib
import posixpath
import sys  # pylint: disable=W0611
import tomllib
import typing
import urllib.parse
import warnings

from bs4 import BeautifulSoup
from icecream import ic  # type: ignore  # pylint: disable=W0611
import requests_cache
import urllib3
import w3lib.url

from .page import Page, ShortenedURL, URLKind


class Crawler:  # pylint: disable=R0902
    """
A spider-ish crawler.
    """
    def __init__ (  # pylint: disable=W0102
        self,
        *,
        config_path: typing.Optional[ pathlib.Path ] = None,
        path_rewrites: typing.Dict[ str, str ] = {},
        ignored_paths: typing.Set[ str ] = set([]),
        ignored_prefix: typing.List[ str ] = [],
        shorty: typing.Dict[ str, ShortenedURL ] = {},
        ) -> None:
        """
Constructor.
        """
        # configuration
        with open(config_path, mode = "rb") as fp:  # type: ignore
            self.config = tomllib.load(fp)

        self.site_base: str = self.config["nyddu"]["site_base"]
        self.path_rewrites: typing.Dict[ str, str ] = path_rewrites
        self.ignored_paths: typing.Set[ str ] = ignored_paths
        self.ignored_prefix: typing.List[ str ] = ignored_prefix
        self.shorty: typing.Dict[ str, ShortenedURL ] = shorty

        # configure warnings
        urllib3.disable_warnings()

        # runtime data structures
        self.known_pages: typing.Dict[ str, Page ] = {}
        self.session: requests_cache.CachedSession = self.get_cache()

        self.queue: asyncio.Queue = asyncio.Queue(
            maxsize = self.config["nyddu"]["queue_maxsize"],
            )


    def get_cache (
        self,
        ) -> requests_cache.CachedSession:
        """
Build a URL request cache session, optionally loading any
previous serialized cache from disk.
        """
        session: requests_cache.CachedSession = requests_cache.CachedSession(
            backend = requests_cache.SQLiteCache(
                self.config["nyddu"]["cache_path"],
            ),
        )

        session.settings.expire_after = self.config["nyddu"]["cache_expire"]

        return session


    async def load_queue (  # pylint: disable=R0912
        self,
        uri: str,
        ref: typing.Optional[ Page ],
        ) -> None:
        """
Load one URI into the queue.
        """
        kind: URLKind = URLKind.INTERNAL
        slug: typing.Optional[ str ] = None

        if uri in self.shorty:
            kind = self.shorty[uri].kind

            if kind in [ URLKind.INTERNAL, URLKind.EXTERNAL ]:
                slug = uri
                uri = self.shorty[uri].expanded_uri

        if uri.startswith("#") or uri.startswith("data:"):
            # ignore internal anchors and data URLs (for now)
            return

        if uri.startswith("/") or uri.startswith(self.site_base):
            # normalize internal links to just their path
            if uri.startswith("/"):
                uri = f"{self.site_base}{uri}"

            parsed: urllib.parse.ParseResult = urllib.parse.urlparse(uri)
            normalized_path: str = posixpath.normpath(parsed.path)
            uri = parsed._replace(path = normalized_path).geturl()
            uri = uri.split("#")[0]
            uri = uri.split("?")[0]

            # determine a canonical path
            path: str = Page.get_path(
                uri,
                base = self.site_base,
            )

            # filter out URLs to be ignored
            if path in self.path_rewrites:
                path = self.path_rewrites[path]

            for prefix in self.ignored_prefix:
                if path.startswith(prefix):
                    return

            if path in self.ignored_paths:
                return

            if path in self.known_pages:
                # add a back-reference
                page: Page = self.known_pages[path]

                if ref is not None:
                    page.add_ref(ref.path, slug)
                    ref.outbound.add(path)

            else:
                page = Page(
                    uri = uri,
                    kind = kind,
                    path = path,
                    slug = slug,
                )

                self.known_pages[path] = page

                message: str = f"load: {page.uri} {ref}"
                logging.debug(message)

                await self.queue.put(page)

                if ref is not None:
                    page.add_ref(ref.path, slug)
                    ref.outbound.add(path)

        else:
            # a bona fide external link
            uri = w3lib.url.canonicalize_url(uri)

            if not uri.startswith("http"):
                message = f"unknown scheme: {uri} {ref}"
                logging.error(message)

            if uri not in self.known_pages:
                page = Page(
                    uri = uri,
                    kind = URLKind.EXTERNAL,
                    slug = slug,
                )

                self.known_pages[uri] = page

                message: str = f"load: {page.uri} {ref}"
                logging.debug(message)

                await self.queue.put(page)

            else:
                page = self.known_pages[uri]

            if ref is not None:
                page.add_ref(ref.path, slug)
                ref.outbound.add(uri)


    async def produce_tasks (
        self,
        site_map: str = "https://example.com",
        ) -> None:
        """
Coroutine to produce URLs into the queue.
        """
        for uri in Page.get_site_links(site_map, self.session):
            await self.load_queue(uri, None)


    async def consume_tasks (
        self,
        ) -> None:
        """
Coroutine to consume URLs from the queue.
        """
        count: int = 0
        logging.info("queue start")

        while not self.queue.empty():
            page: Page = await self.queue.get()
            assert page is not None

            # crawl!
            message: str = f"task: {page.kind} {page.uri} {page.path}"
            logging.debug(message)

            if page.path in self.shorty:
                ## FUCK: handle shows
                page.kind = self.shorty[page.path].kind

            match page.kind:
                case URLKind.INTERNAL:
                    html: typing.Optional[ str ] = await page.request_content(
                        self.session,
                    )

                    if page.status_code in [ HTTPStatus.OK ]:
                        if html is not None and page.content_type in [ "text/html" ]:
                            count += 1

                            for emb_uri in page.extract_links(html):
                                await self.load_queue(emb_uri, page)

                case URLKind.EXTERNAL:
                    html: typing.Optional[ str ] = await page.request_content(
                        self.session,
                        allow_redirects = True,
                    )

                    if page.status_code not in [ HTTPStatus.NOT_FOUND ]:
                        if html is not None and page.content_type in [ "text/html" ]:
                            count += 1

                            soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
                            page.extract_meta(soup)

                case _:
                    ic("how to crawl?", page)

            self.queue.task_done()

        logging.info(f"queue done: {count} / {len(self.known_pages)}")
        ic(self.queue.qsize())


    async def crawl (
        self,
        ) -> None:
        """
Crawler entry point coroutine.
        """
        await asyncio.gather(
            self.produce_tasks(self.config["nyddu"]["site_map"]),
            self.consume_tasks(),
        )


    def report (
        self,
        ) -> list:
        """
Report results.
        """
        with warnings.catch_warnings(action = "ignore"):
            return [
                page.to_json()
                for _, page in sorted(self.known_pages.items())
            ]
