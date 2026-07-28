"""Last-resort fallback parser (docs/04-spec-transaction-extraction.md):
naive "date + amount on one line" heuristic, used only when no bank-specific
parser matches. Deliberately low-fidelity — no `counterparty`,
`running_balance`, or `raw_details`.
"""

import re
from datetime import date
from decimal import Decimal

from finance_agent.subgraphs.extraction.parsers.base import RawTransaction, Word

_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<description>.*?)\s+"
    r"(?P<amount>[+-]\d[\d ]*,\d{2})\s*$"
)


class GenericLineParser:
    def matches(self, _first_page_text: str) -> bool:
        return True

    def parse(
        self, text: str, _words_per_page: list[list[Word]]
    ) -> list[RawTransaction]:
        transactions: list[RawTransaction] = []
        for line in text.splitlines():
            match = _LINE_RE.match(line.strip())
            if not match:
                continue
            amount = Decimal(match.group("amount").replace(" ", "").replace(",", "."))
            transactions.append(
                RawTransaction(
                    txn_date=date.fromisoformat(match.group("date")),
                    amount=amount,
                    description=match.group("description").strip(),
                    counterparty=None,
                    running_balance=None,
                    raw_details={},
                )
            )
        return transactions
