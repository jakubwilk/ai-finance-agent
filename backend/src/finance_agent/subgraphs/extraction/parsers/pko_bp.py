"""Parser for PKO BP's "Historia rachunku" (transaction history) export.

Column x0 thresholds and the overall approach were derived empirically
against a real sample export (see PLAN.md step 3 / docs/04): the
transaction-table pages have no ruling lines, so `pdfplumber.extract_tables()`
finds nothing there — parsing goes through `extract_words()` positions
instead (`layout_utils.cluster_words_into_rows`).
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from finance_agent.subgraphs.extraction.parsers.base import RawTransaction, Word
from finance_agent.subgraphs.extraction.parsers.layout_utils import (
    cluster_words_into_rows,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Amounts over 999 use a thousands separator that isn't necessarily a plain
# ASCII space in the PDF's actual encoding (e.g. U+00A0 non-breaking space,
# U+202F narrow no-break space) — confirmed against a real "kwota" value
# that crashed `Decimal(...)` despite looking like plain digits. Python's
# `\s` already matches all Unicode whitespace, unlike a literal `" "`
# replace.
_WHITESPACE_RE = re.compile(r"\s+")
_CURRENCY_SUFFIX_RE = re.compile(r"\s*(PLN|z[łl])\s*$", re.IGNORECASE)
# Guards the kwota/saldo continuation-row merge in `parse()` against
# grabbing stray non-numeric text that happens to land in the same x0
# column range — e.g. a repeated table header or a footer/summary row
# ("Suma obciążeń", a page-break header re-print, etc.) that `current`
# isn't reset for until the next date row. Confirmed against a real export
# where a footer row's label text ("obciążeń") fell in the kwota column
# and was misread as that transaction's amount. `\s` already matches all
# Unicode whitespace, so no need to enumerate thousands-separator variants
# here either.
_AMOUNT_CANDIDATE_RE = re.compile(
    r"^[+\-]?[\d\s]+([.,]\d+)?\s*(PLN|z[łl])?$",
    re.IGNORECASE,
)


def _looks_like_amount(value: str) -> bool:
    return bool(_AMOUNT_CANDIDATE_RE.match(value.strip()))


# A wide right-aligned amount (4+ digits before the decimal, using a
# thousands-separator space) can be wide enough that its left edge (x0)
# crosses the kwota column's lower bound (450) and the whole value lands in
# the `opis` bucket instead — confirmed against a real export where a
# transaction's `kwota` came back empty while its `opis` held exactly one
# value shaped like an amount. Unlike `_AMOUNT_CANDIDATE_RE` above, the
# decimal part here is mandatory (2 digits) precisely so this doesn't
# misfire on some other purely-numeric continuation text landing in opis
# (e.g. an account number split across rows) that happens not to contain a
# decimal comma/period at all.
_LEAKED_AMOUNT_RE = re.compile(
    r"^[+\-]?[\d\s]+[.,]\d{2}\s*(PLN|z[łl])?$",
    re.IGNORECASE,
)


def _reclaim_amount_from_opis(line: dict[str, str]) -> None:
    """Move a leaked amount (see `_LEAKED_AMOUNT_RE`) from `opis` to `kwota`
    in place, when `kwota` is otherwise empty for this row."""
    opis = line.get("opis", "").strip()
    if opis and not line.get("kwota", "").strip() and _LEAKED_AMOUNT_RE.match(opis):
        line["kwota"] = opis
        line["opis"] = ""


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


def _safe_ascii_repr(value: str) -> str:
    """ASCII-only escaped repr — a stray non-ASCII character (e.g. a
    Unicode minus-sign variant) could otherwise fail to print on a
    Windows console using a legacy codepage, turning a helpful
    `ValueError` into a *second*, more confusing `UnicodeEncodeError`.
    """
    return value.encode("unicode_escape").decode("ascii")


def _parse_amount(value: str) -> Decimal:
    cleaned = _CURRENCY_SUFFIX_RE.sub("", value.strip())
    cleaned = _WHITESPACE_RE.sub("", cleaned)
    cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        # Digits redacted (real amounts, docs/CLAUDE.md rule 6) — this
        # exposes the *shape* of whatever's left after cleanup (stray
        # symbols, an unexpected minus-sign variant, wrong decimal point,
        # concatenated columns...) without ever logging a real number.
        redacted_cleaned = re.sub(r"\d", "#", cleaned)
        redacted_original = re.sub(r"\d", "#", value)
        raise ValueError(
            "Could not parse amount as Decimal after cleanup: "
            f"{_safe_ascii_repr(redacted_cleaned)!r} (original, digits "
            f"redacted: {_safe_ascii_repr(redacted_original)!r})"
        ) from exc


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


# Standard PKO BP footer/summary boilerplate that follows the last real
# transaction on the statement's final page — confirmed against a real
# export whose (digit-redacted) diagnostic showed a "Liczba obciążeń /
# Suma obciążeń / Liczba uznań / Suma uznań" summary table, a legal
# disclaimer citing the Banking Law Act ("... Ustawy Prawo Bankowe ...", "z
# późniejszymi zmianami)."), the account number, a "data wydruku:" print
# date, and a repeated column-header row (for what turned out to be a
# final page with no further transactions). None of this has a
# `data_operacji` matching `_DATE_RE`, so without this check it silently
# got merged into the last real transaction's opis/typ_transakcji as
# "continuation lines" (this content uses a different column layout than
# the transaction table, so its kwota/saldo values land in the opis
# column instead), leaving that transaction's own kwota/saldo empty and
# crashing `_parse_amount`.
_FOOTER_MARKERS = (
    "Liczba obciążeń",
    "Suma obciążeń",
    "Liczba uznań",
    "Suma uznań",
    "Ustawy Prawo Bankowe",
    "data wydruku",
)
_TABLE_HEADER_LABELS = {
    "Data operacji",
    "Data waluty",
    "Typ transakcji",
    "Opis",
    "Kwota",
    "Saldo",
}


def _is_non_transaction_row(line: dict[str, str]) -> bool:
    """True for a repeated page header or the statement's trailing
    footer/summary section (see `_FOOTER_MARKERS` above) — either means
    the row must NOT be merged into `current` as a continuation line."""
    values = [v.strip() for v in line.values() if v.strip()]
    if not values:
        return False
    if all(v in _TABLE_HEADER_LABELS for v in values):
        return True
    full_text = " ".join(values)
    return any(marker in full_text for marker in _FOOTER_MARKERS)


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
                _reclaim_amount_from_opis(line)

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
                    if _is_non_transaction_row(line):
                        transactions.append(_finalize(current))
                        current = None
                        continue
                    if "typ_transakcji" in line:
                        current["typ_lines"].append(line["typ_transakcji"])
                    if "opis" in line:
                        current["opis_lines"].append(line["opis"])
                    # `kwota`/`saldo` can land on a continuation row too —
                    # confirmed against a real export where a transaction's
                    # amount came back empty on the date row itself (the
                    # row-clustering split what's logically one entry
                    # across two rows, same as already handled above for
                    # typ_transakcji/opis). Only take the first non-empty
                    # value seen, and only if it actually looks like an
                    # amount — a footer/header row's stray text can also
                    # land in this column range and must not be mistaken
                    # for the transaction's amount (see
                    # `_AMOUNT_CANDIDATE_RE`'s docstring above).
                    if not current["kwota"]:
                        candidate = line.get("kwota", "").strip()
                        if candidate and _looks_like_amount(candidate):
                            current["kwota"] = candidate
                    if not current["saldo"]:
                        candidate = line.get("saldo", "").strip()
                        if candidate and _looks_like_amount(candidate):
                            current["saldo"] = candidate

        if current is not None:
            transactions.append(_finalize(current))

        return transactions


def _finalize(current: dict) -> RawTransaction:
    fields = _parse_opis_lines(current["opis_lines"])
    description = fields.pop("Tytuł", "")
    typ_transakcji = " ".join(t for t in current["typ_lines"] if t).strip()

    raw_details = {_normalize_key(label): value for label, value in fields.items()}
    raw_details["typ_transakcji"] = typ_transakcji

    try:
        amount = _parse_amount(current["kwota"])
    except ValueError as exc:
        # An empty/unparsable `kwota` with non-empty `opis`/`typ_transakcji`
        # text is a strong signal the amount word never landed in the
        # kwota x0 column at all — e.g. a right-aligned longer number (more
        # digits => further-left x0) can drift past the column's lower
        # bound into the `opis` bucket instead of being missing outright.
        # Surfacing the *other* columns' (digit-redacted) content alongside
        # the original error lets that be confirmed/ruled out from the
        # traceback alone, without asking for the real statement.
        redacted_opis = re.sub(r"\d", "#", " | ".join(current["opis_lines"]))
        redacted_typ = re.sub(r"\d", "#", " | ".join(current["typ_lines"]))
        raise ValueError(
            f"{exc} | opis columns seen for this transaction (digits "
            f"redacted): {_safe_ascii_repr(redacted_opis)!r} | "
            f"typ_transakcji columns seen (digits redacted): "
            f"{_safe_ascii_repr(redacted_typ)!r}"
        ) from exc

    return RawTransaction(
        txn_date=date.fromisoformat(current["txn_date"]),
        amount=amount,
        description=description,
        counterparty=fields.get("Odbiorca") or fields.get("Nadawca"),
        running_balance=(_parse_amount(current["saldo"]) if current["saldo"] else None),
        raw_details=raw_details,
    )
