#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Crawler class for Nyddu.
see copyright/license https://github.com/DerwenAI/nyddu/README.md
"""

import asyncio
import typing
import warnings

from icecream import ic  # type: ignore
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
        site_base: str = "https://example.com",
        path_rewrites: typing.Dict[ str, str ] = {},
        ignored_paths: typing.Set[ str ] = set([]),
        shorty: typing.Dict[ str, ShortenedURL ] = {},
        ) -> None:
        """
Constructor.
        """
        # configuration
        self.site_base: str = site_base
        self.path_rewrites: typing.Dict[ str, str ] = path_rewrites
        self.ignored_paths: typing.Set[ str ] = ignored_paths
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
            backend = requests_cache.SQLiteCache("nyddu.cache"),
        )

        session.settings.expire_after = 360

        return session


    async def load_queue (  # pylint: disable=R0912
        self,
        uri: str,
        ref: typing.Optional[ Page ],
        *,
        debug: bool = False,
        ) -> None:
        """
Coroutine to load URIs into the queue.
        """
        kind: URLKind = URLKind.INTERNAL
        slug: typing.Optional[ str ] = None

        if uri in self.shorty:
            kind = self.shorty[uri].kind

            if kind in [ URLKind.INTERNAL, URLKind.EXTERNAL ]:
                slug = uri
                uri = self.shorty[uri].expanded_uri
            else:
                ## fuck: handle shows
                pass

        if uri.startswith("#") or uri.startswith("data:"):
            # ignore internal anchors and data URLs (for now)
            pass

        elif uri.startswith("/") or uri.startswith(self.site_base):
            # normalize internal links to just their path
            path: str = Page.get_path(
                uri,
                base = self.site_base,
            )

            if path in self.path_rewrites:
                path = self.path_rewrites[path]

            if path in self.ignored_paths:
                # fuck: is this really one of ours?
                #self.outbound[u] = "?"
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

                page.normalize(
                    base = self.site_base,
                )

                self.known_pages[path] = page

                if ref is not None:
                    page.add_ref(ref.path, slug)
                    ref.outbound.add(path)

                if debug or True:  # pylint: disable=R1727
                    ic("LOAD", page)

                await self.queue.put(page)

        else:
            # a bona fide external link
            uri = w3lib.url.canonicalize_url(uri)

            if not uri.startswith("http"):
                ic("WTF!!!", uri, ref)

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


    async def consume_tasks (
        self,
        *,
        debug: bool = True,
        ) -> None:
        """
Coroutine to consume URLs from the queue.
        """
        if debug:
            print("QUEUE status: start")

        while True:
            page: typing.Optional[ Page ] = await self.queue.get()

            if page is None:
                print("QUEUE size at end:", self.queue.qsize())
                break

            # crawl!
            if debug:
                print(f">got {page}")

            html: typing.Optional[ str ] = await page.request_content(self.session)

            if html is not None and page.content_type in [ "text/html" ]:
                for emb_uri in page.extract_links(html):
                    await self.load_queue(emb_uri, page)

        if debug:
            print("QUEUE status: all done")


    async def crawl (
        self,
        site_map: str = "https://example.com",
        ) -> None:
        """
Crawler entry point coroutine.
        """
        for uri in Page.get_site_links(site_map, self.session):
            await self.load_queue(uri, None)

        # send an "all done" signal
        await self.queue.put(None)
        await asyncio.gather(self.consume_tasks())


    def report (
        self,
        ) -> None:
        """
Report results.
        """
        for uri, page in sorted(self.known_pages.items()):
            with warnings.catch_warnings(action = "ignore"):
                print(uri)
                ic(page.model_dump())
