#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Page representation for Nyddu.
see copyright/license https://github.com/DerwenAI/nyddu/README.md
"""

from collections.abc import Iterator
from urllib.parse import urlparse
import enum
import sys  # pylint: disable=W0611
import typing
import uuid

from bs4 import BeautifulSoup
from defusedxml import ElementTree
from icecream import ic  # type: ignore
from pydantic import BaseModel
import requests
import requests_cache


class URLKind (enum.StrEnum):
    """
An enumeration class representing URL kinds.
    """
    EXTERNAL = enum.auto()
    INTERNAL = enum.auto()
    URN = enum.auto()


class ShortenedURL:  # pylint: disable=R0903
    """
Represents a shortened URL.
    """
    def __init__ (
        self,
        uri: str,
        expanded_uri: str,
        kind: URLKind,
        ) -> None:
        """
Constructor.
        """
        self.uri: str = uri
        self.expanded_uri: str = expanded_uri
        self.kind: URLKind = kind


    def __repr__ (
        self,
        ) -> str:
        """
Represent object as a string.
        """
        return f"{self.kind}  {self.uri} : {self.expanded_uri}"


class Page (BaseModel):
    """
A data class representing one HTML page.
    """
    uri: str
    kind: URLKind
    uid: str = str(uuid.uuid4())
    path: typing.Optional[ str ] = None
    slug: typing.Optional[ str ] = None
    content_type: typing.Optional[ str ] = None
    status_code: typing.Optional[ int ] = None
    outbound: typing.Set[ str ] = set([])
    refs: typing.Set[ str ] = set([])
    raw_refs: typing.Set[ str ] = set([])


    def __repr__ (
        self,
        ) -> str:
        """
Represent object as a string.
        """
        match self.kind:
            case URLKind.INTERNAL:
                return self.path  # type: ignore
            case _:
                return self.uri


    @classmethod
    def get_site_links (
        cls,
        uri: str,
        session: requests_cache.CachedSession,
        ) -> Iterator[ str ]:
        """
Iterate through the links in a given `sitemap.xml` page.
        """
        try:
            xml = session.get(uri, timeout = 10).text
            tree = ElementTree.XML(xml)

            for node in tree:
                yield node[0].text  # type: ignore
        except Exception as ex:  # pylint: disable=W0718
            print("OH FUCK!", ex, uri)


    def get_scheme (
        self,
        ) -> str:
        """
Accessor for the HTTP scheme component of a URL.
        """
        return urlparse(self.uri).scheme.lower()


    @classmethod
    def get_path (
        cls,
        uri: str,
        *,
        base: str = "https://example.com/"
        ) -> str:
        """
Extract the path for an internal URL.
        """
        return uri.replace(base, "").strip().split("#")[0]


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
            if uri.startswith("http") or uri.startswith("data:") or uri.startswith("/"):
                return uri

            if not path.endswith("/"):
                path = f"{path}/"

            return f"{path}{uri}"

        return None


    def extract_links (
        self,
        html: str,
        ) -> Iterator[ str ]:
        """
Extract all the links from an HTML document.
        """
        soup: BeautifulSoup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all("a"):
            if "href" in tag.attrs:  # type: ignore
                uri: typing.Optional[ str ] = self.validate_link(tag.attrs["href"], self.path)  # type: ignore  # pylint: disable=C0301

                if uri is not None:
                    yield uri

        for tag in soup.find_all("img"):
            if "src" in tag.attrs:  # type: ignore
                uri = self.validate_link(tag.attrs["src"], self.path)  # type: ignore

                if uri is not None:
                    yield uri

        for tag in soup.find_all("iframe"):
            if "src" in tag.attrs:  # type: ignore
                uri = self.validate_link(tag.attrs["src"], self.path)  # type: ignore

                if uri is not None:
                    yield uri


    def add_ref (
        self,
        ref: typing.Optional[ str ],
        slug: typing.Optional[ str ] = None,
        ) -> None:
        """
Add a back-reference link.
        """
        if ref is not None:
            if slug is not None:
                self.refs.add(ref)
            else:
                self.raw_refs.add(ref)


    async def request_content (
        self,
        session: requests_cache.CachedSession,
        *,
        debug: bool = False,
        ) -> typing.Optional[ str ]:
        """
Request URI to get HTML, status_code, content_type
        """
        html: typing.Optional[ str ] = None

        try:
            assert self.uri is not None

            response: requests.Response = session.get(
                self.uri,
                timeout = 10,
                headers = {
                    "User-Agent": "Custom",
                },
            )

            assert response is not None

            self.status_code = response.status_code
            html = response.text

            if response.headers is not None and "content-type" in response.headers:
                self.content_type = response.headers.get("content-type").split(";")[0]  # type: ignore  # pylint: disable=C0301

            if debug or True:  # pylint: disable=R1727
                ic(self.status_code, self.uri, self.content_type)

            if self.status_code not in [ 200 ]:
                sys.exit(0)

        except requests.exceptions.Timeout:
            print("timed out", self.uri)
        except Exception as ex:  # pylint: disable=W0718
            ic("WTF?", ex, self.uri)

        return html
