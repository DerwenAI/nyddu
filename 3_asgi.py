#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ASGI local mode via FastAPI and Uvicorn.
"""

import pathlib
import tomllib
import typing

from fastapi import FastAPI, Request  # pylint: disable=E0401
import uvicorn  # pylint: disable=E0401

from nyddu import NydduEndpoints


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
        "message": "Bienvenido al Hotel California",
    }


if __name__ == "__main__":
    ## set up the endpoints
    config_path: pathlib.Path = pathlib.Path("config.toml")
    config: dict = {}

    with open(config_path, mode = "rb") as fp:
        config = tomllib.load(fp)

    endpoints: NydduEndpoints = NydduEndpoints(
        config,
    )

    APP.include_router(endpoints.router)

    ## run the webapp
    uvicorn.run(
        APP,
        port = config["webapp"]["port"],
        host = config["webapp"]["host"],
        log_level = "debug",
        reload = False,
    )
