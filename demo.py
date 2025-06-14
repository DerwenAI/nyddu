#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo script.
"""

from collections.abc import Iterator
import asyncio
import typing
import warnings

from bs4 import BeautifulSoup
from icecream import ic
import nyddu
import requests
import w3lib.url


SITE_BASE: str = "https://derwen.ai"
SITE_MAP: str = "https://derwen.ai/sitemap.xml"

IGNORED_PATHS: typing.Set[ str ] = set([
    "/articles",
    "/auth/login",
    "/merch",
    "/cdn-cgi/l/email-protection",
    "/robots.txt",
    "/sitemap.xml",
])

PATH_REWRITES: typing.Dict[ str, str ] = {
    "/rates": "/flywheel",
    "/watchlist": "/events",
}

KNOWN_PAGES: typing.Dict[ str, nyddu.Page ] = {}


def validate_link (
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


def extract_links (
    html: str,
    path: str,
    ) -> Iterator[ str ]:
    """
Extract all the links from an HTML document.
    """
    soup: BeautifulSoup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all("a"):
        if "href" in tag.attrs:
            uri: typing.Optional[ str ] = validate_link(tag.attrs["href"], path)

            if uri is not None:
                yield uri

    for tag in soup.find_all("img"):
        if "src" in tag.attrs:
            uri: typing.Optional[ str ] = validate_link(tag.attrs["src"], path)

            if uri is not None:
                yield uri

    for tag in soup.find_all("iframe"):
        if "src" in tag.attrs:
            uri: typing.Optional[ str ] = validate_link(tag.attrs["src"], path)

            if uri is not None:
                yield uri


async def load_queue (
    queue: asyncio.Queue,
    uri: str,
    ref: typing.Optional[ nyddu.InternalPage ],
    ) -> None:
    """
Coroutine to load URIs into the queue.
    """
    if uri.startswith("#"):
        # ignore internal anchors (for now)
        ic("IGNORE", uri)
        pass

    elif uri.startswith("/") or uri.startswith(SITE_BASE):
        # normalize internal links to just their path
        path: str = nyddu.InternalPage.get_path(
            uri,
            base = SITE_BASE,
        )

        if path in PATH_REWRITES:
            path = PATH_REWRITES[path]

        if path in IGNORED_PATHS:
            # is this really one of ours?
            # fuck
            #self.outbound[u] = "?"
            pass

        elif path in KNOWN_PAGES:
            # add a back-reference
            int_page: nyddu.InternalPage = KNOWN_PAGES[path]

            if ref is not None:
                int_page.add_ref(ref.path)
                ref.outbound.add(path)

        else:
            int_page = nyddu.InternalPage(
                uri = uri,
                path = path,
            )

            int_page.normalize(
                base = SITE_BASE,
            )

            KNOWN_PAGES[path] = int_page

            if ref is not None:
                int_page.add_ref(ref.path)
                ref.outbound.add(path)

            ic("LOAD", uri, int_page, ref)
            task: tuple = ( uri, int_page, ref, )
            await queue.put(task)

    else:
        # a bona fide external link
        uri = w3lib.url.canonicalize_url(uri)

        if not uri.startswith("http"):
            ic("WTF!!!", uri, ref)

        if uri not in KNOWN_PAGES:
            ext_page: nyddu.ExternalPage = nyddu.ExternalPage(
                uri = uri,
                slug = None,
            )

            KNOWN_PAGES[uri] = ext_page

        else:
            ext_page = KNOWN_PAGES[uri]

        if ref is not None:
            ext_page.add_ref(ref.path)
            ref.outbound.add(uri)


async def consumer (
    queue: asyncio.Queue
    ) -> None:
    """
Coroutine to consume URLs from the queue.
    """
    print("consumer: start")

    while True:
        task = await queue.get()

        if task is None:
            break

        # crawl!
        print(f">got {task}")
        uri, int_page, ref = task

        try:
            response: request.Response = requests.get(
                uri,
                timeout = 10,
                headers = {
                    "User-Agent": "Custom",
                },
            )

            html: str = response.text
            headers: typing.Dict[ str, str ] = response.headers
            content_type: str = headers.get("content-type").split(";")[0]

            ic(uri, response.status_code, headers, content_type)
            int_page.content_type = content_type

            if content_type in [ "text/html" ]:
                for emb_uri in extract_links(html, int_page.path):
                    await load_queue(queue, emb_uri, int_page)

        except requests.exceptions.Timeout:
            print("timed out", uri)

    print("consumer: all done")

 
async def crawl (
    ) -> None:
    """
Entry point coroutine.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize = 1000)

    for uri in nyddu.InternalPage.get_site_links(SITE_MAP):
        await load_queue(queue, uri, None)

    # send an "all done" signal
    await queue.put(None)
    await asyncio.gather(consumer(queue))
 

if __name__ == "__main__":
    asyncio.run(crawl())

    for uri, page in sorted(KNOWN_PAGES.items()):
        with warnings.catch_warnings(action = "ignore"):
            print(uri)
            ic(page.model_dump())
