"""Node factories for the categorization subgraph (docs/06-spec-categorization.md).

Same DI pattern as every other subgraph in this repo. `make_human_review`
is deliberately session-free: per the langgraph-human-in-the-loop skill,
side effects before `interrupt()` re-run on every resume, so no DB access
happens until after a decision comes back — and even then, the actual
writes live in `make_persist_category`, not here.
"""

import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal

from langgraph.types import interrupt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Category, CategoryRule, Transaction
from finance_agent.subgraphs.categorization.state import (
    CategorizationItem,
    CategorizationState,
)

Node = Callable[[CategorizationState], Awaitable[dict]]

DEFAULT_THRESHOLD = Decimal("0.85")


class ClassificationResult(BaseModel):
    category: str = Field(
        description="One of the provided category names, exactly as given"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in this classification, 0-1"
    )


def _match_key(counterparty: str | None, description: str) -> str:
    key = counterparty if counterparty else description
    return key.strip().lower()


def make_rule_match(session: AsyncSession) -> Node:
    async def _rule_match(_state: CategorizationState) -> dict:
        transactions = (
            (
                await session.execute(
                    select(Transaction).where(Transaction.category_id.is_(None))
                )
            )
            .scalars()
            .all()
        )
        if not transactions:
            return {"items": []}

        match_keys = {_match_key(t.counterparty, t.description) for t in transactions}
        rules = (
            (
                await session.execute(
                    select(CategoryRule).where(CategoryRule.match_key.in_(match_keys))
                )
            )
            .scalars()
            .all()
        )
        rule_by_key = {r.match_key: r for r in rules}

        category_ids = {r.category_id for r in rules}
        categories = (
            (
                await session.execute(
                    select(Category).where(Category.id.in_(category_ids))
                )
            )
            .scalars()
            .all()
            if category_ids
            else []
        )
        category_name_by_id = {c.id: c.name for c in categories}

        items: list[CategorizationItem] = []
        for t in transactions:
            key = _match_key(t.counterparty, t.description)
            rule = rule_by_key.get(key)
            if rule is not None:
                items.append(
                    CategorizationItem(
                        transaction_id=str(t.id),
                        match_key=key,
                        counterparty=t.counterparty,
                        description=t.description,
                        amount=str(t.amount),
                        category_id=str(rule.category_id),
                        category_name=category_name_by_id.get(rule.category_id),
                        category_source="rule",
                        category_confidence=1.0,
                        review_status="auto",
                    )
                )
            else:
                items.append(
                    CategorizationItem(
                        transaction_id=str(t.id),
                        match_key=key,
                        counterparty=t.counterparty,
                        description=t.description,
                        amount=str(t.amount),
                        category_id=None,
                        category_name=None,
                        category_source=None,
                        category_confidence=None,
                        review_status="needs_review",
                    )
                )
        return {"items": items}

    return _rule_match


def make_llm_classify(session: AsyncSession, chat_model) -> Node:
    async def _llm_classify(state: CategorizationState) -> dict:
        to_classify = [item for item in state["items"] if item["category_id"] is None]
        if not to_classify:
            return {"items": state["items"]}

        categories = (await session.execute(select(Category))).scalars().all()
        if not categories:
            return {"items": state["items"]}

        category_by_name = {c.name: c for c in categories}
        category_list_text = "\n".join(f"- {c.name} ({c.type})" for c in categories)
        structured_model = chat_model.with_structured_output(
            ClassificationResult, method="function_calling"
        )

        updated_by_id: dict[str, CategorizationItem] = {}
        for item in to_classify:
            prompt = (
                "Przypisz poniższą transakcję do jednej z dostępnych kategorii.\n\n"
                f"Dostępne kategorie:\n{category_list_text}\n\n"
                f"Opis transakcji: {item['description']}\n"
                f"Kontrahent: {item['counterparty'] or 'brak'}\n"
                f"Kwota: {item['amount']}\n"
            )
            try:
                result = await structured_model.ainvoke(prompt)
                category = category_by_name.get(result.category)
                if category is None:
                    confidence, category_id, category_name = 0.0, None, None
                else:
                    confidence = result.confidence
                    category_id = str(category.id)
                    category_name = category.name
            except Exception:  # noqa: BLE001 -- any LLM/parsing failure means low confidence, not a crashed batch (docs/12 fallback)
                confidence, category_id, category_name = 0.0, None, None

            updated_by_id[item["transaction_id"]] = {
                **item,
                "category_id": category_id,
                "category_name": category_name,
                "category_source": "llm",
                "category_confidence": confidence,
            }

        items = [
            updated_by_id.get(item["transaction_id"], item) for item in state["items"]
        ]
        return {"items": items}

    return _llm_classify


def make_confidence_gate(threshold: Decimal = DEFAULT_THRESHOLD) -> Node:
    threshold_float = float(threshold)

    async def _confidence_gate(state: CategorizationState) -> dict:
        items = []
        for item in state["items"]:
            if item["category_source"] == "llm":
                confidence = item["category_confidence"] or 0.0
                review_status = (
                    "auto" if confidence >= threshold_float else "needs_review"
                )
                items.append({**item, "review_status": review_status})
            else:
                items.append(item)
        return {"items": items}

    return _confidence_gate


def make_human_review() -> Node:
    async def _human_review(state: CategorizationState) -> dict:
        needs_review = [
            item for item in state["items"] if item["review_status"] == "needs_review"
        ]
        if not needs_review:
            return {}

        pending_reviews = [
            {
                "transaction_id": item["transaction_id"],
                "description": item["description"],
                "counterparty": item["counterparty"],
                "amount": item["amount"],
                "suggested_category": item["category_name"],
                "suggested_confidence": item["category_confidence"],
            }
            for item in needs_review
        ]
        human_response = interrupt({"pending_reviews": pending_reviews})
        decisions = (
            human_response.get("decisions", {})
            if isinstance(human_response, dict)
            else {}
        )

        updated_by_id: dict[str, CategorizationItem] = {}
        for item in needs_review:
            category_name = decisions.get(item["transaction_id"])
            if category_name is None:
                continue  # left as needs_review, unconfirmed
            updated_by_id[item["transaction_id"]] = {
                **item,
                "category_name": category_name,
                "category_source": "manual",
                "review_status": "confirmed",
            }

        items = [
            updated_by_id.get(item["transaction_id"], item) for item in state["items"]
        ]
        return {"items": items}

    return _human_review


def make_persist_category(session: AsyncSession) -> Node:
    async def _persist_category(state: CategorizationState) -> dict:
        unresolved_names = {
            item["category_name"]
            for item in state["items"]
            if item["category_source"] == "manual"
            and item["category_id"] is None
            and item["category_name"]
        }
        category_by_name = {}
        if unresolved_names:
            categories = (
                (
                    await session.execute(
                        select(Category).where(Category.name.in_(unresolved_names))
                    )
                )
                .scalars()
                .all()
            )
            category_by_name = {c.name: c for c in categories}

        for item in state["items"]:
            category_id = item["category_id"]
            if (
                item["category_source"] == "manual"
                and category_id is None
                and item["category_name"]
            ):
                category = category_by_name.get(item["category_name"])
                if category is not None:
                    category_id = str(category.id)

            transaction = await session.get(
                Transaction, uuid.UUID(item["transaction_id"])
            )
            transaction.review_status = item["review_status"]

            if category_id is None:
                continue

            transaction.category_id = uuid.UUID(category_id)
            transaction.category_source = item["category_source"]
            transaction.category_confidence = (
                Decimal(str(item["category_confidence"]))
                if item["category_confidence"] is not None
                else None
            )

            if item["category_source"] == "manual":
                existing_rule = (
                    await session.execute(
                        select(CategoryRule).where(
                            CategoryRule.match_key == item["match_key"]
                        )
                    )
                ).scalar_one_or_none()
                if existing_rule is None:
                    session.add(
                        CategoryRule(
                            match_key=item["match_key"],
                            category_id=uuid.UUID(category_id),
                        )
                    )
                else:
                    existing_rule.category_id = uuid.UUID(category_id)

        await session.flush()
        return {"items": state["items"]}

    return _persist_category
