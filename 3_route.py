#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ASGI local mode via FastAPI and Uvicorn.
"""

import json
import pathlib
import sys
import tomllib
import typing

from fastapi import FastAPI, Request  # pylint: disable=E0401
from fastapi.responses import HTMLResponse  # pylint: disable=E0401,W0611
from fastapi.templating import Jinja2Templates  # pylint: disable=E0401
from icecream import ic
from sentence_transformers import SentenceTransformer
import kuzu
import uvicorn  # pylint: disable=E0401


TEMPLATES: Jinja2Templates = Jinja2Templates(
    directory = ".",
)

PAGES: list = []

APP: FastAPI = FastAPI(
    title = "Nyddu",
    description = "ALL YOUR LINQS ARE BELONG TO US.",
)


@APP.get("/")
def read_root (
    request: Request,
    ) -> HTMLResponse:
    """
Serve the home page.
    """
    response: HTMLResponse = TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "pages": PAGES,
        },
    )

    return response


def db_connect (
    *,
    db_path: pathlib.Path = pathlib.Path("db"),
    ) -> kuzu.Connection:
    """
Initialize a KùzuDB connection, relying on a previous built database.
    """
    return kuzu.Connection(kuzu.Database(db_path))


def load_model (
    *,
    embed_model: str = "all-MiniLM-L6-v2",
    ) -> SentenceTransformer:
    """
Load a pre-trained embedding generation model, defaulting to
<https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>
for 384-dimensional embedding vectors.
    """
    return SentenceTransformer(embed_model)


if __name__ == "__main__":
    # main entry point
    config_path: pathlib.Path = pathlib.Path("config.toml")
    config: dict = {}

    with open(config_path, mode = "rb") as fp:
        config = tomllib.load(fp)

    TEMPLATES = Jinja2Templates(
        directory = config["webapp"]["templates"],
    )

    conn: kuzu.Connection = db_connect(db_path = pathlib.Path(config["db"]["db_path"]))
    model: SentenceTransformer = load_model(embed_model = config["db"]["embed_model"])

    result = conn.execute(
        """
    MATCH (p:Page)
    RETURN
        p.id as id,
        p.uri as uri,
        p.path as path,
        p.slug as slug,
        p.type as type,
        p.status as status,
        p.title as title,
        p.summary as summary
        """,
    )

    PAGES = json.loads(
        result.get_as_df().to_json(
            orient = "records",
            #lines = True,
            #indent = 2,
        )
    )

    #print(PAGES)
    #sys.exit(0)

    uvicorn.run(
        APP,
        port = config["webapp"]["port"],
        host = config["webapp"]["host"],
        log_level = "debug",
        reload = False,
    )
