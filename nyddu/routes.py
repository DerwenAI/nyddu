#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FastAPI router based on `classy_fastapi` for Nyddu endpoints to handle
reporting and content search/discovery.
"""

from fastapi import Request  # pylint: disable=E0401
from fastapi.responses import HTMLResponse  # pylint: disable=E0401,W0611
from fastapi.templating import Jinja2Templates  # pylint: disable=E0401

import classy_fastapi


class NydduEndpoints (classy_fastapi.Routable):  # pylint: disable=R0903
    """
Implements an endpoint class which can be used in Cysoni.
    """

    def __init__ (
        self,
        config: dict,
        ) -> None:
        """
Constructor.
        """
        super().__init__()

        self.config = config
        self.pages: list = []

        self.templates: Jinja2Templates = Jinja2Templates(
            directory = config["webapp"]["templates"],
        )


    @classy_fastapi.get(
        "/pages",
    )
    def index_page (
        self,
        request: Request,
        ) -> HTMLResponse:
        """
Serve an HTML page to search the crawled pages.
        """
        response: HTMLResponse = self.templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "pages": self.pages,
            },
        )

        return response


    @classy_fastapi.get(
        "/detail/{page_id}",
    )
    def page_detail (
        self,
        request: Request,
        page_id: str,
        ) -> HTMLResponse:
        """
Show details for a given crawled URL.
        """
        return page_id
