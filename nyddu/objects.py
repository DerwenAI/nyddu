#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Class definitions for Nyddu.
see copyright/license https://github.com/DerwenAI/nyddu/README.md
"""

from urllib.parse import urlparse
import typing
import uuid

from icecream import ic
from pydantic import BaseModel


class Page (BaseModel):
    """
A data class representing one HTML page.
    """
    url: str
    uid: str = str(uuid.uuid4())
    refs: set = set([])
    requests: float = 0.0
    reported: bool = False
    is_internal: bool = False
    name: typing.Optional[ str ] = None
    is_html: typing.Optional[ bool ] = None

    #scheme: typing.Optional[ str ] = None
    #kwargs.update({ "scheme": urlparse(url).scheme.lower() })


    def add_ref (
        self,
        page_obj,
        *,
        name: typing.Optional[ str ] = None,
        ) -> None:
        """
Add a back-reference link.
        """
        self.refs.add(page_obj)
