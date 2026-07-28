from datetime import date
from decimal import Decimal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import select

from finance_agent.db.models import (
    Account,
    Category,
    CategoryRule,
    Statement,
    Transaction,
)
from finance_agent.subgraphs.categorization.graph import build_categorization_graph
from finance_agent.subgraphs.categorization.nodes import ClassificationResult

EMPTY_STATE = {"items": []}


class FakeStructuredModel:
    def __init__(self, result_or_exception):
        self._result_or_exception = result_or_exception

    async def ainvoke(self, _prompt):
        if isinstance(self._result_or_exception, Exception):
            raise self._result_or_exception
        return self._result_or_exception


class FakeChatModel:
    """Never call `with_structured_output` unless llm_classify actually has
    something to classify — used to prove rule-matched transactions skip
    the LLM entirely."""

    def __init__(self, result_or_exception=None):
        self._result_or_exception = result_or_exception

    def with_structured_output(self, _schema, method=None):
        if self._result_or_exception is None:
            raise AssertionError("LLM should not have been called")
        return FakeStructuredModel(self._result_or_exception)


async def _make_category(db_session, name: str, type_: str = "expense") -> Category:
    category = Category(name=name, score=50, type=type_)
    db_session.add(category)
    await db_session.flush()
    return category


async def _make_transaction(
    db_session,
    *,
    description: str,
    counterparty: str | None = None,
    amount: Decimal = Decimal("-10.00"),
) -> Transaction:
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()

    statement = Statement(
        account_id=account.id,
        drive_file_id="file-1",
        file_name="statement.pdf",
        checksum="abc123",
        status="processed",
    )
    db_session.add(statement)
    await db_session.flush()

    transaction = Transaction(
        statement_id=statement.id,
        txn_date=date(2026, 1, 1),
        amount=amount,
        description=description,
        counterparty=counterparty,
        review_status="auto",
    )
    db_session.add(transaction)
    await db_session.flush()
    return transaction


async def test_rule_match_skips_llm_when_rule_exists(db_session):
    category = await _make_category(db_session, "Jedzenie")
    transaction = await _make_transaction(
        db_session, description="ZABKA Z8412", counterparty=None
    )
    db_session.add(CategoryRule(match_key="zabka z8412", category_id=category.id))
    await db_session.flush()

    graph = build_categorization_graph(
        session=db_session,
        chat_model=FakeChatModel(),  # raises if ever called
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "rule-match-test"}}
    result = await graph.ainvoke(EMPTY_STATE, config)

    assert "__interrupt__" not in result or not result["__interrupt__"]
    await db_session.refresh(transaction)
    assert transaction.category_id == category.id
    assert transaction.category_source == "rule"
    assert transaction.category_confidence == Decimal("1.0")
    assert transaction.review_status == "auto"


async def test_llm_classify_above_threshold_is_auto(db_session):
    category = await _make_category(db_session, "Rozrywka")
    transaction = await _make_transaction(
        db_session, description="KINO HELIOS", counterparty=None
    )

    fake_model = FakeChatModel(
        ClassificationResult(category="Rozrywka", confidence=0.95)
    )
    graph = build_categorization_graph(
        session=db_session, chat_model=fake_model, checkpointer=InMemorySaver()
    )
    config = {"configurable": {"thread_id": "llm-above-threshold-test"}}
    result = await graph.ainvoke(EMPTY_STATE, config)

    assert "__interrupt__" not in result or not result["__interrupt__"]
    await db_session.refresh(transaction)
    assert transaction.category_id == category.id
    assert transaction.category_source == "llm"
    assert transaction.review_status == "auto"


async def test_llm_below_threshold_interrupts_and_resume_learns_rule(db_session):
    category = await _make_category(db_session, "Rozrywka")
    transaction = await _make_transaction(
        db_session, description="TAJEMNICZY SKLEP", counterparty=None
    )

    fake_model = FakeChatModel(
        ClassificationResult(category="Rozrywka", confidence=0.4)
    )
    graph = build_categorization_graph(
        session=db_session, chat_model=fake_model, checkpointer=InMemorySaver()
    )
    config = {"configurable": {"thread_id": "llm-below-threshold-test"}}

    paused = await graph.ainvoke(EMPTY_STATE, config)
    assert paused.get("__interrupt__")

    # Not yet persisted while paused.
    await db_session.refresh(transaction)
    assert transaction.category_id is None
    assert transaction.review_status == "auto"  # unchanged so far

    resumed = await graph.ainvoke(
        Command(resume={"decisions": {str(transaction.id): "Rozrywka"}}), config
    )
    assert not resumed.get("__interrupt__")

    await db_session.refresh(transaction)
    assert transaction.category_id == category.id
    assert transaction.category_source == "manual"
    assert transaction.review_status == "confirmed"

    rule = (
        await db_session.execute(
            select(CategoryRule).where(CategoryRule.match_key == "tajemniczy sklep")
        )
    ).scalar_one()
    assert rule.category_id == category.id


async def test_llm_exception_routes_to_needs_review_not_a_crash(db_session):
    await _make_category(db_session, "Rozrywka")
    transaction = await _make_transaction(
        db_session, description="BLAD MODELU", counterparty=None
    )

    fake_model = FakeChatModel(RuntimeError("model unavailable"))
    graph = build_categorization_graph(
        session=db_session, chat_model=fake_model, checkpointer=InMemorySaver()
    )
    config = {"configurable": {"thread_id": "llm-exception-test"}}

    paused = await graph.ainvoke(EMPTY_STATE, config)
    assert paused.get("__interrupt__")

    # Leave unconfirmed on resume.
    resumed = await graph.ainvoke(Command(resume={"decisions": {}}), config)
    assert not resumed.get("__interrupt__")

    await db_session.refresh(transaction)
    assert transaction.category_id is None
    assert transaction.review_status == "needs_review"


async def test_no_pending_transactions_completes_without_interrupt(db_session):
    graph = build_categorization_graph(
        session=db_session,
        chat_model=FakeChatModel(),
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "empty-test"}}
    result = await graph.ainvoke(EMPTY_STATE, config)

    assert "__interrupt__" not in result or not result["__interrupt__"]
    assert result["items"] == []
