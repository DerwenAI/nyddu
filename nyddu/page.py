#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Page representation for Nyddu.
see copyright/license https://github.com/DerwenAI/nyddu/README.md
"""

from collections.abc import Iterator
from urllib.parse import urlparse
import enum
import logging
import ssl
import sys  # pylint: disable=W0611
import traceback  # pylint: disable=W0611
import typing
import xml

from bs4 import BeautifulSoup
from defusedxml import ElementTree
from icecream import ic  # type: ignore  # pylint: disable=W0611
from pydantic import BaseModel
import requests
import requests_cache


FAUX_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36"  # pylint: disable=C0301


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
    path: typing.Optional[ str ] = None
    slug: typing.Optional[ str ] = None
    content_type: typing.Optional[ str ] = None
    status_code: typing.Optional[ int ] = None
    redirect: typing.Optional[ str ] = None
    title: typing.Optional[ str ] = None
    summary: typing.Optional[ str ] = None
    thumbnail: typing.Optional[ str ] = None
    keywords: typing.Set[ str ] = set([])
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


    def to_json (
        self,
        ) -> dict:
        """
Represent data for serialization.
        """
        return {
            "uri": self.uri,
            "kind": self.kind.value,
            "path": self.path,
            "slug": self.slug,
            "type": self.content_type,
            "status": self.status_code,
            "redirect": self.redirect,
            "title": self.title,
            "summary": self.summary,
            "thumbnail": self.thumbnail,
            "keywords": list(self.keywords),
            "outbound": list(self.outbound),
            "refs": list(self.refs),
            "raw": list(self.raw_refs),
        }


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
            xml_doc: str = session.get(uri, timeout = 10).text
            tree: xml.etree.ElementTree.Element = ElementTree.XML(xml_doc)  # type: ignore

            for node in tree:
                yield node[0].text  # type: ignore
        except Exception as ex:  # pylint: disable=W0718
            message: str = f"bad site links: {uri} : {ex}"
            logging.error(message)


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


    def extract_meta (
        self,
        soup: BeautifulSoup,
        ) -> None:
        """
Extract metadata from an HTML document.
        """
        if soup.title is not None:
            self.title = soup.title.string  # type: ignore

        for tag in soup.find_all("meta"):
            if "content" in tag.attrs:  # type: ignore
                if "property" in tag.attrs:  # type: ignore
                    match tag.attrs["property"]:  # type: ignore
                        case "og:image":
                            self.thumbnail = tag.attrs["content"]  # type: ignore

                elif "name" in tag.attrs:  # type: ignore
                    match tag.attrs["name"]:  # type: ignore
                        case "description":
                            self.summary = tag.attrs["content"]  # type: ignore

                        case "keywords":
                            key_list: typing.Optional[ str ] = tag.attrs["content"]  # type: ignore

                            if key_list is not None:
                                self.keywords = { key.strip() for key in key_list.split(",") }


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
        self.extract_meta(soup)

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
        allow_redirects: bool = False,
        user_agent: str = FAUX_USER_AGENT,
        ) -> typing.Optional[ str ]:
        """
Request URI to get HTML, status_code, content_type
        """
        html: typing.Optional[ str ] = None

        try:
            assert self.uri is not None

            response: requests.Response = session.get(
                self.uri,
                verify = ssl.CERT_NONE,
                timeout = 10,
                allow_redirects = allow_redirects,
                headers = {
                    "User-Agent": user_agent,
                },
            )

            assert response is not None

            self.status_code = response.status_code
            html = response.text

            if response.headers is not None and response.headers.get("content-type") is not None:
                content_type: typing.Optional[ str ] = response.headers.get("content-type")  # type: ignore  # pylint: disable=C0301

                if content_type is not None:
                    self.content_type = content_type.split(";")[0]

            message: str = f"{self.status_code} {self.content_type} {self.uri}"
            logging.debug(message)

            ic(message)

            if len(response.history) > 0:
                self.redirect = response.url

        except requests.exceptions.Timeout:
            message = f"request timeout: {self.uri}"
            logging.error(message)
        except Exception as ex:  # pylint: disable=W0718
            #traceback.print_exc()
            message = f"request error: {self.uri} : {ex}"
            logging.error(message)

        return html
