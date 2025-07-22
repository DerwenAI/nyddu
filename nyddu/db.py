#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utility methods to support KùzuDB access patterns.
"""

import pathlib

import kuzu
from sentence_transformers import SentenceTransformer


def db_connect (
    *,
    db_path: pathlib.Path = pathlib.Path("db"),
    ) -> kuzu.Connection:
    """
Initialize a KùzuDB connection.
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
