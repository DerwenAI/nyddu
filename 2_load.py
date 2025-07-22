#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Prototype the use of KùzuDB
"""

import json
import pathlib
import sys
import tomllib
import typing

from icecream import ic
from pyinstrument import Profiler
import kuzu
import pandas as pd

from nyddu import db_connect


def verify_page (
    page: dict,
    ) -> dict:
    """
Format the data for one row, so that neither Polars nor Pandas loose their minds.
    """
    if page["status"] is not None:
        page["status"] = str(page["status"])

    if page["slug"] is not None:
        page["slug"] = page["slug"].strip().lstrip("/s/")

    return {
        "uri": page["uri"],
        "status": page["status"],
        "type": page["type"],
        "path": page["path"],
        "slug": page["slug"],
        "redirect": page["redirect"],
        "title": page["title"],
        "summary": page["summary"],
        "thumbnail": page["thumbnail"],
        "error": page["error"],
        "timing": page["timing"]
    }


def main (
    ) -> int:
    """
Main entry point
    """
    config_path: pathlib.Path = pathlib.Path("config.toml")
    config: dict = {}

    with open(config_path, mode = "rb") as fp:
        config = tomllib.load(fp)

    conn: kuzu.Connection = db_connect(
        db_path = pathlib.Path(config["db"]["db_path"]),
    )

    ## start code profiling
    profiler: Profiler = Profiler()
    profiler.start()

    ######################################################################
    ## define schema

    conn.execute("""
DROP TABLE IF EXISTS Link;
DROP TABLE IF EXISTS Page;
    """)

    conn.execute("""
CREATE NODE TABLE Page(
    id SERIAL PRIMARY KEY,
    uri STRING,
    status STRING,
    type STRING,
    path STRING,
    slug STRING,
    redirect STRING,
    title STRING,
    summary STRING,
    thumbnail STRING,
    error STRING,
    timing DOUBLE
);
    """)

    conn.execute("""
CREATE REL TABLE Link(
    FROM Page TO Page,
    sym BOOLEAN
);
    """)

    ######################################################################
    ## load JSON data

    with open(pathlib.Path("report"), "r", encoding = "utf-8") as fp:
        dat: list = json.load(fp)

    df_page = pd.DataFrame([
        verify_page(page)
        for page in dat
    ])
    ic(df_page)

    conn.execute("""
COPY Page FROM df_page
    """)

    df_ref = pd.DataFrame([
        {
            "src": ref,
            "dst": page["uri"],
        }
        for page in dat
        for ref in page["refs"]
    ])
    ic(df_ref)

    for row in df_ref.to_dict(orient = "records"):
        conn.execute(
            """
    MATCH (src:Page {path: $src})
    MATCH (dst:Page {uri: $dst})
    CREATE (src)-[:Link {sym: true}]->(dst);
            """,
            row,
        )

    df_raw = pd.DataFrame([
        {
            "src": ref,
            "dst": page["uri"],
        }
        for page in dat
        for ref in page["raw"]
    ])
    ic(df_raw)

    for row in df_raw.to_dict(orient = "records"):
        conn.execute(
            """
    MATCH (src:Page {path: $src})
    MATCH (dst:Page {uri: $dst})
    CREATE (src)-[:Link {sym: false}]->(dst);
            """,
            row,
        )

    ## end code profiling
    profiler.stop()
    profiler.print()


if __name__ == "__main__":
    main()
