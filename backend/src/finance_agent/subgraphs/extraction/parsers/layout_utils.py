"""Bank-agnostic helpers for parsing PDFs that have visually-aligned
columns but no ruling lines (so `pdfplumber.extract_tables()` finds
nothing — confirmed empirically against a real PKO BP "Historia rachunku"
export). Column x0 thresholds themselves are bank-specific and stay local
to each parser module (e.g. `pko_bp.py`); only the row-clustering mechanics
are shared here.
"""

from finance_agent.subgraphs.extraction.parsers.base import Word


def cluster_words_into_rows(words: list[Word], tolerance: float = 2.5) -> list[dict]:
    """Group `extract_words()` output into visual rows by `top` position.

    Returns rows sorted top-to-bottom, each `{"top": float, "words": [Word]}`
    with words sorted left-to-right. `tolerance` accounts for small
    sub-pixel `top` differences between words on the same visual line.
    """
    rows: list[dict] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        for row in rows:
            if abs(row["top"] - word["top"]) <= tolerance:
                row["words"].append(word)
                break
        else:
            rows.append({"top": word["top"], "words": [word]})
    return rows
