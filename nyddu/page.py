#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Page representation for Nyddu.
see copyright/license https://github.com/DerwenAI/nyddu/README.md
"""

from collections.abc import Iterator
from urllib.parse import urlparse
import typing
import uuid

from defusedxml import ElementTree 
from pydantic import BaseModel
import requests


class Page (BaseModel):
    """
A data class representing one HTML page.
    """
    uri: str
    uid: str = str(uuid.uuid4())
    content_type: typing.Optional[ str ] = None
    refs: typing.Set[ str ] = set([])


    def __repr__ (
        self,
        ) -> str:
        """
Represent object as a string.
        """
        return self.uri


    def get_scheme (
        self,
        ) -> str:
        """
Accessor for the HTTP scheme component of a URL.
        """
        return urlparse(self.uri).scheme.lower()


    def add_ref (
        self,
        ref: typing.Optional[ str ],
        ) -> None:
        """
Add a back-reference link.
        """
        if ref is not None:
            self.refs.add(ref)


class ExternalPage (Page):
    """
A data class representing one external HTML page.
    """
    slug: typing.Optional[ str ] = None


class InternalPage (Page):
    """
A data class representing one internal HTML page.
    """
    path: str
    outbound: typing.Set[ str ] = set([])


    def __repr__ (
        self,
        ) -> str:
        """
Represent object as a string.
        """
        return self.path


    def normalize (
        self,
        *,
        base: str = "https://example.com/"
        ) -> None:
        """
Normalize the URL to represent an internal HTML page.
        """
        self.uri = self.uri.split("#")[0]

        if not self.uri.startswith(base):
            self.uri = f"{base}{self.uri}"


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
    def get_site_links (
        cls,
        uri: str,
        ) -> Iterator[ str ]:
        """
Iterate through the links in a given `sitemap.xml` page.
        """
        try:
            xml = requests.get(uri).text
            tree = ElementTree.XML(xml)

            for node in tree:
                yield node[0].text
        except Exception as ex:
            print(ex, uri)
