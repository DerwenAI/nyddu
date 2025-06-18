#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Crawler class for Nyddu.
see copyright/license https://github.com/DerwenAI/nyddu/README.md
"""

import asyncio
import logging
import pathlib
import posixpath
import sys  # pylint: disable=W0611
import tomllib
import typing
import urllib.parse
import warnings

from icecream import ic  # type: ignore  # pylint: disable=W0611
import requests_cache
import w3lib.url

from .page import Page, ShortenedURL, URLKind


class Crawler:
    """
A spider-ish crawler.
    """
    def __init__ (  # pylint: disable=W0102
        self,
        *,
        config_path: typing.Optional[ pathlib.Path ] = None,
        site_base: str = "https://example.com",
        path_rewrites: typing.Dict[ str, str ] = {},
        ignored_paths: typing.Set[ str ] = set([]),
        ignored_prefix: typing.List[ str ] = [],
        shorty: typing.Dict[ str, ShortenedURL ] = {},
        ) -> None:
        """
Constructor.
        """
        # configuration
        with open(config_path, mode = "rb") as fp:
            self.config = tomllib.load(fp)

        self.site_base: str = site_base
        self.path_rewrites: typing.Dict[ str, str ] = path_rewrites
        self.ignored_paths: typing.Set[ str ] = ignored_paths
        self.ignored_prefix: typing.List[ str ] = ignored_prefix
        self.shorty: typing.Dict[ str, ShortenedURL ] = shorty

        # runtime data structures
        self.known_pages: typing.Dict[ str, Page ] = {}
        self.queue: asyncio.Queue = asyncio.Queue(maxsize = 0)
        self.session: requests_cache.CachedSession = self.get_cache()


    def get_cache (
        self,
        ) -> requests_cache.CachedSession:
        """
Build a URL request cache session, optionally loading any
previous serialized cache from disk.
        """
        # NB: these parameters should move into config

        session: requests_cache.CachedSession = requests_cache.CachedSession(
            backend = requests_cache.SQLiteCache("cache.nyddu"),
        )

        session.settings.expire_after = 360

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
            pass

        elif uri.startswith("/") or uri.startswith(self.site_base):
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

            ignore: bool = False

            if path in self.ignored_paths:
                # fuck: double-check is this really one of ours?
                ignore = True

            for prefix in self.ignored_prefix:
                if path.startswith(prefix):
                    ignore = True
                    break

            if ignore:
                pass

            elif path in self.known_pages:
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

                if ref is not None:
                    page.add_ref(ref.path, slug)
                    ref.outbound.add(path)

                message: str = f"load: {page.uri} {ref}"
                logging.debug(message)

                await self.queue.put(page)

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
        logging.info("queue start")

        while not self.queue.empty():
            page: Page = await self.queue.get()
            assert page is not None

            # crawl!
            message: str = f"task: {page.kind} {page.uri} {page.path}"
            logging.debug(message)

            if page.path in self.shorty:
                ## fuck: handle shows
                page.kind = self.shorty[page.path].kind

            if page.kind in [ URLKind.INTERNAL ]:
                html: typing.Optional[ str ] = await page.request_content(self.session)

                if html is not None and page.content_type in [ "text/html" ]:
                    for emb_uri in page.extract_links(html):
                        await self.load_queue(emb_uri, page)

            self.queue.task_done()

        logging.info("queue done")


    async def crawl (
        self,
        site_map: str = "https://example.com",
        ) -> None:
        """
Crawler entry point coroutine.
        """
        await asyncio.gather(self.produce_tasks(site_map), self.consume_tasks())


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

