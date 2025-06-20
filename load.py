#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Prototype the use of KùzuDB
"""

import contextlib
import json
import pathlib
import shutil
import sys
import tomllib
import typing

from icecream import ic
from pyinstrument import Profiler
from sentence_transformers import SentenceTransformer
import kuzu
import pandas as pd


def db_connect (
    *,
    db_path: pathlib.Path = pathlib.Path("db"),
    ) -> kuzu.Connection:
    """
Initialize a KùzuDB connection, removing any previous data if it exits.
    """
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(db_path)

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

    return {
        "uri": page["uri"],
        "status": page["status"],
        "type": page["type"],
        "path": page["path"],
        "slug": page["slug"],
        "title": page["title"],
        "summary": page["summary"],
        "thumbnail": page["thumbnail"],
        "embedding": model.encode(page["title"]).tolist(),
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

    conn: kuzu.Connection = db_connect(db_path = pathlib.Path(config["nyddu"]["db_path"]))
    model: SentenceTransformer = load_model(embed_model = config["nyddu"]["embed_model"])

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
    title STRING,
    summary STRING,
    thumbnail STRING,
    embedding FLOAT[384]
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
        if page["title"] is not None
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

    ######################################################################
    ## vector search

    # vector search indexing
    conn.execute(
        """
    CALL CREATE_VECTOR_INDEX(
        'Page',
        'title_vec_index',
        'embedding'
    );
        """
    )

    # vector search query
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
    RETURN node.uri, node.title ORDER BY distance;
        """,
        { "query_vector": query_vector, },
    )

    ic(result.get_as_pl())

    result = conn.execute(
        """
    CALL QUERY_VECTOR_INDEX('page', 'title_vec_index', $query_vector, 2)
    WITH node AS p, distance
    MATCH (p)-[:Link]->(dst:Page)
    RETURN p.uri, dst.uri, p.title, distance
    ORDER BY distance LIMIT 50;
        """,
        { "query_vector": query_vector, },
    )

    ic(result.get_as_pl())

    ## end code profiling
    profiler.stop()
    profiler.print()


if __name__ == "__main__":
    main()
