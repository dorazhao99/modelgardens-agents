import argparse
import math
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from sqlite3 import connect, Connection

from litellm.constants import DB_SPEND_UPDATE_JOB_NAME
from mcp.server.fastmcp import FastMCP
import logging

logger = logging.getLogger(__name__)
_db_path: str = ""


@dataclass
class AppContext:
    gum_db: Connection


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def _query_db(db: Connection, query: str, limit: int = 3) -> List[Tuple[str, float, float]]:
    """Return the top-`limit` propositions ranked by BM25 similarity to `query`.

    Each result is a (description, confidence, bm25_score) tuple.
    If `query` is empty, rows are returned in DB order with score 0.
    """
    rows = db.execute("SELECT description, confidence FROM gum_propositions").fetchall()

    if not rows:
        return []

    descriptions = [row[0] or "" for row in rows]
    query_tokens = _tokenize(query)

    if not query_tokens:
        return [(desc, row[1], 0.0) for desc, row in zip(descriptions, rows)][:limit]

    # BM25 parameters
    k1 = 1.5
    b = 0.75

    corpus = [_tokenize(d) for d in descriptions]
    avg_dl = sum(len(doc) for doc in corpus) / len(corpus) if corpus else 1.0
    n_docs = len(corpus)

    df: dict[str, int] = {}
    for token in query_tokens:
        df[token] = sum(1 for doc in corpus if token in doc)

    scores: List[float] = []
    for doc in corpus:
        doc_len = len(doc)
        tf_map: dict[str, int] = {}
        for t in doc:
            tf_map[t] = tf_map.get(t, 0) + 1

        score = 0.0
        for token in query_tokens:
            if token not in df or df[token] == 0:
                continue
            idf = math.log((n_docs - df[token] + 0.5) / (df[token] + 0.5) + 1.0)
            tf = tf_map.get(token, 0)
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_dl))
        scores.append(score)

    confidences = [r[1] for r in rows]
    combined = [(desc, conf, bm25 * conf)
                for desc, conf, bm25 in zip(descriptions, confidences, scores)]
    ranked = sorted(combined, key=lambda x: x[2], reverse=True)
    return ranked[:limit]


def create_mcp_server(db_path: str):
    mcp = FastMCP("gum")
    logger.info(f"Creating MCP server for database at {db_path}")
    db = connect(db_path)
    logger.info(f"Connected to database at {db_path}")
    # results = _query_db(db, "test")
    # print(results)

    @mcp.tool()
    async def get_user_context(
        query: Optional[str] = "",
    ) -> str:
        """
        A tool to retrieve context for a user query within a time window.
        Use this liberally, especially when something is underspecified or unclear.

        Args:
            query: The query text (will be pre-processed by a lexical
                retrieval model such as BM25). This is OPTIONAL. If the user asks 
                for something general (e.g. what am I doing, help me now), 
                then your query can be empty. Otherwise, try to be specific.

        Returns:
            A string containing the retrieved contextual information.
        """


        results = _query_db(
            db=db,
            query=query,
            limit=3
        )

        db.close()

        context_parts = []
        for result in results:
            context_parts.append(result[0])

        return "\n\n".join(context_parts)
    return mcp

def main(db_path: str):
    mcp = create_mcp_server(db_path)
    mcp.run()

if __name__ == "__main__":
    main('/Users/dorazhao/Library/Application Support/DARTBoard/app.db')