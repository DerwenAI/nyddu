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

from fastapi import FastAPI  # pylint: disable=E0401
from icecream import ic
from sentence_transformers import SentenceTransformer
import kuzu
import uvicorn  # pylint: disable=E0401


APP: FastAPI = FastAPI(
    title = "Nyddu",
    description = "ALL YOUR LINQS ARE BELONG TO US.",
)


@APP.get("/")
def read_root (
    ) -> dict:
    """
Example page route.
    """
    return {
        "Hello": "World",
    }


@APP.get("/items/{item_id}")
def read_item (
    item_id: int,
    q: typing.Union[ str, None ] = None,
    ) -> dict:
    """
Example API route.
    """
    return {
        "item_id": item_id,
        "q": q,
    }


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

    conn: kuzu.Connection = db_connect(db_path = pathlib.Path(config["db"]["db_path"]))
    model: SentenceTransformer = load_model(embed_model = config["db"]["embed_model"])

    result = conn.execute(
        """
    MATCH (p:Page)
    RETURN p.id, p.uri, p.path, p.slug, p.type, p.status, p.title, p.summary
        """,
    )

    dat: dict = result.get_as_df().to_json(
        orient = "records",
        lines = True,
        indent = 2,
    )

    print(dat)
    sys.exit(0)

    uvicorn.run(
        APP,
        port = config["webapp"]["port"],
        host = config["webapp"]["host"],
        log_level = "debug",
        reload = False,
    )
