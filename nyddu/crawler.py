#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Crawler class for Nyddu.
see copyright/license https://github.com/DerwenAI/nyddu/README.md
"""

from collections.abc import Iterator
import asyncio
import typing
import warnings

from bs4 import BeautifulSoup
from icecream import ic  # type: ignore
import requests
import w3lib.url

from .page import InternalPage, ExternalPage, Page


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
        ) -> None:
        """
Constructor.
        """
        self.site_base: str = site_base
        self.path_rewrites: typing.Dict[ str, str ] = path_rewrites
        self.ignored_paths: typing.Set[ str ] = ignored_paths
        self.known_pages: typing.Dict[ str, Page ] = {}
        self.queue: asyncio.Queue = asyncio.Queue(maxsize = 0)


    @classmethod
    def validate_link (
        cls,
        uri: str,
        path: str,
        ) -> typing.Optional[ str ]:
        """
Filter valid links.
        """
        if not (uri.startswith("#") or uri in [ "." ]):
            if not (uri.startswith("http") or uri.startswith("/")):
                return f"{path}{uri}"

            return uri

        return None


    @classmethod
    def extract_links (
        cls,
        html: str,
        path: str,
        ) -> Iterator[ str ]:
        """
Extract all the links from an HTML document.
        """
        soup: BeautifulSoup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all("a"):
            if "href" in tag.attrs:  # type: ignore
                uri: typing.Optional[ str ] = cls.validate_link(tag.attrs["href"], path)  # type: ignore  # pylint: disable=C0301

                if uri is not None:
                    yield uri

        for tag in soup.find_all("img"):
            if "src" in tag.attrs:  # type: ignore
                uri = cls.validate_link(tag.attrs["src"], path)  # type: ignore

                if uri is not None:
                    yield uri

        for tag in soup.find_all("iframe"):
            if "src" in tag.attrs:  # type: ignore
                uri = cls.validate_link(tag.attrs["src"], path)  # type: ignore

                if uri is not None:
                    yield uri


    async def load_queue (  # pylint: disable=R0912
        self,
        uri: str,
        ref: typing.Optional[ InternalPage ],
        *,
        debug: bool = False,
        ) -> None:
        """
Coroutine to load URIs into the queue.
        """
        if uri.startswith("#"):
            # ignore internal anchors (for now)
            pass

        elif uri.startswith("/") or uri.startswith(self.site_base):
            # normalize internal links to just their path
            path: str = InternalPage.get_path(
                uri,
                base = self.site_base,
            )

            if path in self.path_rewrites:
                path = self.path_rewrites[path]

            if path in self.ignored_paths:
                # is this really one of ours?
                # fuck
                #self.outbound[u] = "?"
                pass

            elif path in self.known_pages:
                # add a back-reference
                int_page: InternalPage = self.known_pages[path]  # type: ignore

                if ref is not None:
                    int_page.add_ref(ref.path)
                    ref.outbound.add(path)

            else:
                int_page = InternalPage(
                    uri = uri,
                    path = path,
                )

                int_page.normalize(
                    base = self.site_base,
                )

                self.known_pages[path] = int_page

                if ref is not None:
                    int_page.add_ref(ref.path)
                    ref.outbound.add(path)

                if debug:
                    ic("LOAD", uri, int_page, ref)

                task: tuple = ( uri, int_page, ref, )
                await self.queue.put(task)

        else:
            # a bona fide external link
            uri = w3lib.url.canonicalize_url(uri)

            if not uri.startswith("http"):
                ic("WTF!!!", uri, ref)

            if uri not in self.known_pages:
                ext_page: ExternalPage = ExternalPage(
                    uri = uri,
                    slug = None,
                )

                self.known_pages[uri] = ext_page

            else:
                ext_page = self.known_pages[uri]  # type: ignore

            if ref is not None:
                ext_page.add_ref(ref.path)
                ref.outbound.add(uri)


    async def consumer (
        self,
        *,
        debug: bool = False,
        ) -> None:
        """
Coroutine to consume URLs from the queue.
        """
        print("consumer: start")

        while True:
            task = await self.queue.get()

            if task is None:
                break

            # crawl!
            print(f">got {task}")
            uri, int_page, ref = task  # pylint: disable=W0612

            try:
                response: requests.Response = requests.get(
                    uri,
                    timeout = 10,
                    headers = {
                        "User-Agent": "Custom",
                    },
                )

                html: str = response.text
                headers: typing.Dict[ str, str ] = response.headers  # type: ignore
                content_type: str = headers.get("content-type").split(";")[0]  # type: ignore

                if debug:
                    ic(uri, response.status_code, headers, content_type)

                int_page.content_type = content_type

                if content_type in [ "text/html" ]:
                    for emb_uri in self.extract_links(html, int_page.path):
                        await self.load_queue(emb_uri, int_page)

            except requests.exceptions.Timeout:
                print("timed out", uri)

        print("consumer: all done")


    async def crawl (
        self,
        site_map: str = "https://example.com",
        ) -> None:
        """
Crawler entry point coroutine.
        """
        for uri in InternalPage.get_site_links(site_map):
            await self.load_queue(uri, None)

        # send an "all done" signal
        await self.queue.put(None)
        await asyncio.gather(self.consumer())


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
