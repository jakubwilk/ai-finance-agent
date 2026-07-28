"""Parser for PKO BP's "Historia rachunku" (transaction history) export.

Column x0 thresholds and the overall approach were derived empirically
against a real sample export (see PLAN.md step 3 / docs/04): the
transaction-table pages have no ruling lines, so `pdfplumber.extract_tables()`
finds nothing there — parsing goes through `extract_words()` positions
instead (`layout_utils.cluster_words_into_rows`).
"""

import re
from datetime import date
from decimal import Decimal

from finance_agent.subgraphs.extraction.parsers.base import RawTransaction, Word
from finance_agent.subgraphs.extraction.parsers.layout_utils import (
    cluster_words_into_rows,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Empirically confirmed column boundaries (x0, in PDF points) for this
# export's transaction table.
_COLUMNS = (
    ("data_operacji", 0, 85),
    ("data_waluty", 85, 133),
    ("typ_transakcji", 133, 200),
    ("opis", 200, 450),
    ("kwota", 450, 512),
    ("saldo", 512, 10_000),
)


def _column_for(x0: float) -> str:
    for name, lo, hi in _COLUMNS:
        if lo <= x0 < hi:
            return name
    return "unknown"


def _parse_amount(value: str) -> Decimal:
    return Decimal(value.strip().replace(" ", "").replace(",", "."))


def _parse_opis_lines(lines: list[str]) -> dict[str, str]:
    """Parse `Opis` column lines as `label : value` pairs. A line without a
    colon continues the previously-seen label's value (long titles/addresses
    wrap across lines with no repeated label)."""
    fields: dict[str, str] = {}
    last_label: str | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if ":" in line:
            label, _, value = line.partition(":")
            label = label.strip()
            value = value.strip()
            fields[label] = value
            last_label = label
        elif last_label is not None:
            fields[last_label] = f"{fields[last_label]} {line}".strip()
    return fields


def _normalize_key(label: str) -> str:
    return label.lower().replace(" ", "_")


class PkoBpHistoriaRachunkuParser:
    def matches(self, first_page_text: str) -> bool:
        return (
            "Powszechna Kasa Oszczędności" in first_page_text
            and "HISTORIA RACHUNKU" in first_page_text
        )

    def parse(
        self, _text: str, words_per_page: list[list[Word]]
    ) -> list[RawTransaction]:
        transactions: list[RawTransaction] = []
        current: dict | None = None

        for page_words in words_per_page:
            for row in cluster_words_into_rows(page_words):
                by_column: dict[str, list[str]] = {}
                for word in row["words"]:
                    by_column.setdefault(_column_for(word["x0"]), []).append(
                        word["text"]
                    )
                line = {col: " ".join(vals) for col, vals in by_column.items()}

                data_operacji = line.get("data_operacji", "").strip()
                if _DATE_RE.match(data_operacji):
                    if current is not None:
                        transactions.append(_finalize(current))
                    current = {
                        "txn_date": data_operacji,
                        "typ_lines": [line.get("typ_transakcji", "")],
                        "opis_lines": [line.get("opis", "")],
                        "kwota": line.get("kwota", "").strip(),
                        "saldo": line.get("saldo", "").strip(),
                    }
                elif current is not None:
                    if "typ_transakcji" in line:
                        current["typ_lines"].append(line["typ_transakcji"])
                    if "opis" in line:
                        current["opis_lines"].append(line["opis"])

        if current is not None:
            transactions.append(_finalize(current))

        return transactions


def _finalize(current: dict) -> RawTransaction:
    fields = _parse_opis_lines(current["opis_lines"])
    description = fields.pop("Tytuł", "")
    typ_transakcji = " ".join(t for t in current["typ_lines"] if t).strip()

    raw_details = {_normalize_key(label): value for label, value in fields.items()}
    raw_details["typ_transakcji"] = typ_transakcji

    return RawTransaction(
        txn_date=date.fromisoformat(current["txn_date"]),
        amount=_parse_amount(current["kwota"]),
        description=description,
        counterparty=fields.get("Odbiorca") or fields.get("Nadawca"),
        running_balance=(_parse_amount(current["saldo"]) if current["saldo"] else None),
        raw_details=raw_details,
    )
