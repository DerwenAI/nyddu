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
from icecream import ic
from sentence_transformers import SentenceTransformer
import kuzu
import uvicorn  # pylint: disable=E0401

from nyddu import NydduEndpoints, \
    db_connect, load_model



APP: FastAPI = FastAPI(
    title = "nyddu",
    description = "ALL YOUR PAGE ARE BELONG TO US.",
)

@APP.get("/")
def home (
    ) -> dict:
    """
Serve a default home page.
    """
    return {
        "message": "Bienvenidos a Hotel California",
    }



if __name__ == "__main__":
    ## set up the endpoints
    config_path: pathlib.Path = pathlib.Path("config.toml")
    config: dict = {}

    with open(config_path, mode = "rb") as fp:
        config = tomllib.load(fp)

    endpoints: NydduEndpoints = NydduEndpoints(config)
    APP.include_router(endpoints.router)

    ## set up the KùzuDB connection
    conn: kuzu.Connection = db_connect(db_path = pathlib.Path(config["db"]["db_path"]))

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

    endpoints.pages = json.loads(
        result.get_as_df().to_json(
            orient = "records",
            #lines = True,
            #indent = 2,
        )
    )

    #print(endpoints.pages)
    #sys.exit(0)

    ## run the webapp
    uvicorn.run(
        APP,
        port = config["webapp"]["port"],
        host = config["webapp"]["host"],
        log_level = "debug",
        reload = False,
    )
