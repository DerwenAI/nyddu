#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FastAPI router based on `classy_fastapi` for Nyddu endpoints to handle
reporting and content search/discovery.
"""

import json
import pathlib

from fastapi import Request  # pylint: disable=E0401
from fastapi.responses import HTMLResponse  # pylint: disable=E0401,W0611
from fastapi.templating import Jinja2Templates  # pylint: disable=E0401

from icecream import ic  # type: ignore  # pylint: disable=W0611
import classy_fastapi
import kuzu
import pandas as pd  # type: ignore  # pylint: disable=W0611

from .db import db_connect


class NydduEndpoints (classy_fastapi.Routable):  # pylint: disable=R0903
    """
Implements an endpoint class which serves Nyddu analysis.
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

        self.templates: Jinja2Templates = Jinja2Templates(
            directory = config["webapp"]["templates"],
        )

        ## set up the KùzuDB connection
        self.conn: kuzu.Connection = db_connect(db_path = pathlib.Path(config["db"]["db_path"]))


    @classy_fastapi.get(
        "/pages",
    )
    def pages_index (
        self,
        request: Request,
        ) -> HTMLResponse:
        """
Serve an HTML page to search the crawled pages via DataTables.
        """
        pages_query: str = """
    MATCH (p:Page)
    RETURN
        p.id as id,
        p.uri as uri,
        p.slug as slug,
        p.redirect as redirect,
        p.type as type,
        p.status as status,
        p.title as title,
        p.summary as summary,
        p.error as error,
        p.timing as timing
        """

        pages_df: pd.DataFrame = self.conn.execute(  # type: ignore
            pages_query,
        ).get_as_df()

        response: HTMLResponse = self.templates.TemplateResponse(
            "pages.html",
            {
                "request": request,
                "pages": json.loads(
                    pages_df.fillna("").to_json(
                        orient = "records",
                        #lines = True,
                        #indent = 2,
                    ),
                ),
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
        detail_query: str = """
    MATCH (p:Page {id: $id})
    RETURN
        p.uri as uri,
        p.slug as slug,
        p.redirect as redirect,
        p.type as type,
        p.status as status,
        p.title as title,
        p.summary as summary,
        p.error as error,
        p.timing as timing
        """

        detail_df: pd.DataFrame = self.conn.execute(  # type: ignore
            detail_query,
            { "id": int(page_id) },
        ).get_as_df()

        dst_links_query: str = """
    MATCH (src:Page)-[:Link]->(dst:Page {id: $id})
    RETURN
        src.id as id,
        src.uri as uri
        """

        dst_links_df: pd.DataFrame = self.conn.execute(  # type: ignore
            dst_links_query,
            { "id": int(page_id) },
        ).get_as_df()

        src_links_query: str = """
    MATCH (src:Page {id: $id})-[:Link]->(dst:Page)
    RETURN
        dst.id as id,
        dst.uri as uri
        """

        src_links_df: pd.DataFrame = self.conn.execute(  # type: ignore
            src_links_query,
            { "id": int(page_id) },
        ).get_as_df()

        response: HTMLResponse = self.templates.TemplateResponse(
            "detail.html",
            {
                "request": request,
                "detail": json.loads(
                    detail_df.fillna("").to_json(
                        orient = "records",
                    ),
                ),
                "dst_links": json.loads(
                    dst_links_df.fillna("").to_json(
                        orient = "records",
                    ),
                ),
                "src_links": json.loads(
                    src_links_df.fillna("").to_json(
                        orient = "records",
                    ),
                ),
            },
        )

        return response
