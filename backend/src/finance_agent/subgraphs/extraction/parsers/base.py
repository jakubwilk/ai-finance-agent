"""Parser interface for transaction extraction (docs/04-spec-transaction-extraction.md).

Strategy pattern: each bank/layout gets its own `StatementParser`
implementation; the generic fallback (`generic.GenericLineParser`) always
matches and is tried last.
"""

from datetime import date
from decimal import Decimal
from typing import Protocol

from typing_extensions import TypedDict

Word = dict  # pdfplumber's extract_words() word dict: {"text", "x0", "top", ...}


class RawTransaction(TypedDict):
    txn_date: date
    amount: Decimal
    description: str
    counterparty: str | None
    running_balance: Decimal | None
    raw_details: dict[str, str]


class StatementParser(Protocol):
    def matches(self, first_page_text: str) -> bool:
        """Cheap check on the first page's plain text to identify the
        bank/layout (docs/04's `detect_layout` step)."""
        ...

    def parse(
        self, text: str, words_per_page: list[list[Word]]
    ) -> list[RawTransaction]:
        """`text` is all pages' extracted text concatenated; `words_per_page`
        is `page.extract_words()` per page. Parsers use whichever they need
        — positional parsers (see `pko_bp.py`) need `words_per_page`, plain
        regex parsers (see `generic.py`) only need `text`.
        """
        ...
