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

from nyddu import db_connect, load_model
from sentence_transformers import SentenceTransformer


def verify_page (
    page: dict,
    model: SentenceTransformer,
    ) -> dict:
    """
Format the data for one row, so that neither Polars nor Pandas loose their minds.
    """
    if page["status"] is not None:
        page["status"] = str(page["status"])

    if page["slug"] is not None:
        page["slug"] = page["slug"].strip().lstrip("/s/")

    embedding: typing.Optional[ list ] = None

    if page["title"] is not None:
        embedding = model.encode(page["title"]).tolist()

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
        "timing": page["timing"],
        "embedding": embedding,
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

    model: SentenceTransformer = load_model()

    conn: kuzu.Connection = db_connect(
        db_path = pathlib.Path(config["db"]["db_path"]),
        clean = True,
    )

    # install and load vector extension
    # create tables
    conn.execute("""
INSTALL vector;
LOAD vector;
    """)

    ## start code profiling
    profiler: Profiler = Profiler()
    profiler.start()

    ######################################################################
    ## define schema

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
    timing DOUBLE,
    embedding DOUBLE[384]
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
        verify_page(page, model)
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

    ## vector search
    conn.execute(
        """
    CALL CREATE_VECTOR_INDEX(
        'Page',
        'title_vec_index',
        'embedding'
    );
        """
    )

    query: str = "paco"
    query_vector: list = model.encode(query).tolist()

    result: QueryResult = conn.execute(
        """
    CALL QUERY_VECTOR_INDEX(
        'Page',
        'title_vec_index',
        $query_vector,
        2
    )
    RETURN node.title ORDER BY distance;
        """,
        { "query_vector": query_vector, },
    )

    ic(result.get_as_pl())

    result = conn.execute(
        """
    CALL QUERY_VECTOR_INDEX('Page', 'title_vec_index', $query_vector, 2)
    WITH node AS n, distance
    MATCH (n)-[:Link]->(p:Page)
    RETURN n.uri, p.uri, distance
    ORDER BY distance LIMIT 5;
        """,
        { "query_vector": query_vector,},
    )

    ic(result.get_as_pl())

    ## end code profiling
    profiler.stop()
    profiler.print()


if __name__ == "__main__":
    main()
