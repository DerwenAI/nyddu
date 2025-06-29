#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utility methods to support KùzuDB access patterns.
"""

import contextlib
import pathlib
import shutil

import kuzu
from sentence_transformers import SentenceTransformer


def db_connect (
    *,
    db_path: pathlib.Path = pathlib.Path("db"),
    clean: bool = False,
    ) -> kuzu.Connection:
    """
Initialize a KùzuDB connection, optionally removing any previous data if it exits.
    """
    if clean:
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
