from datetime import date
from decimal import Decimal

from sqlalchemy import select

from finance_agent.db.models import (
    Account,
    InvestmentRecommendation,
    InvestmentSettings,
    Statement,
    Transaction,
)
from finance_agent.subgraphs.investment.graph import build_investment_graph
from finance_agent.subgraphs.investment.nodes import AllocationResult

EMPTY_STATE = {
    "statement_id": None,
    "surplus": None,
    "safety_buffer": None,
    "trend": None,
    "proposal": None,
}


class FakeStructuredModel:
    def __init__(self, result_or_exception):
        self._result_or_exception = result_or_exception

    async def ainvoke(self, _prompt):
        if isinstance(self._result_or_exception, Exception):
            raise self._result_or_exception
        return self._result_or_exception


class FakeChatModel:
    """Never call `with_structured_output` unless generate_allocation_proposal
    actually has an investable amount to propose — used to prove the
    zero-surplus/no-settings paths skip the LLM entirely.
    """

    def __init__(self, result_or_exception=None):
        self._result_or_exception = result_or_exception

    def with_structured_output(self, _schema, method=None):
        if self._result_or_exception is None:
            raise AssertionError("LLM should not have been called")
        return FakeStructuredModel(self._result_or_exception)


VALID_LLM_RESULT = AllocationResult(
    etf_percent=50.0,
    term_deposit_percent=30.0,
    savings_account_percent=20.0,
    rationale="test allocation",
)


async def _make_account(db_session) -> Account:
    account = Account(display_name="Test Account", bank_name="Test Bank")
    db_session.add(account)
    await db_session.flush()
    return account


async def _make_processed_statement(
    db_session,
    account: Account,
    *,
    period_end: date,
    closing_balance: Decimal = Decimal("1000.00"),
    drive_file_id: str,
) -> Statement:
    statement = Statement(
        account_id=account.id,
        drive_file_id=drive_file_id,
        file_name="statement.pdf",
        checksum="abc123",
        status="processed",
        period_start=date(period_end.year, period_end.month, 1),
        period_end=period_end,
        opening_balance=Decimal("0.00"),
        closing_balance=closing_balance,
    )
    db_session.add(statement)
    await db_session.flush()
    return statement


async def _make_transaction(
    db_session, statement: Statement, *, amount: Decimal
) -> Transaction:
    transaction = Transaction(
        statement_id=statement.id,
        txn_date=statement.period_end,
        amount=amount,
        description="test",
        review_status="auto",
    )
    db_session.add(transaction)
    await db_session.flush()
    return transaction


async def _make_investment_settings(
    db_session,
    *,
    risk_profile: str = "balanced",
    safety_buffer_amount: Decimal,
    instruments: list[str] | None = None,
) -> InvestmentSettings:
    settings_row = InvestmentSettings(
        risk_profile=risk_profile,
        safety_buffer_amount=safety_buffer_amount,
        instruments=instruments or ["etf", "term_deposit", "savings_account"],
    )
    db_session.add(settings_row)
    await db_session.flush()
    return settings_row


async def test_safety_buffer_reduces_investable_amount_when_binding(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        closing_balance=Decimal("1000.00"),
        drive_file_id="file-1",
    )
    await _make_transaction(db_session, statement, amount=Decimal("500.00"))
    await _make_investment_settings(db_session, safety_buffer_amount=Decimal("900.00"))

    graph = build_investment_graph(
        session=db_session, chat_model=FakeChatModel(VALID_LLM_RESULT)
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["safety_buffer"]["current_balance"] == "1000.00"
    assert result["safety_buffer"]["investable_amount"] == "100.00"
    assert result["safety_buffer"]["buffer_binding"] is True
    assert result["proposal"]["amount"] == "100.00"


async def test_safety_buffer_does_not_reduce_when_headroom_sufficient(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        closing_balance=Decimal("1000.00"),
        drive_file_id="file-1",
    )
    await _make_transaction(db_session, statement, amount=Decimal("500.00"))
    await _make_investment_settings(db_session, safety_buffer_amount=Decimal("100.00"))

    graph = build_investment_graph(
        session=db_session, chat_model=FakeChatModel(VALID_LLM_RESULT)
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["safety_buffer"]["investable_amount"] == "500.00"
    assert result["safety_buffer"]["buffer_binding"] is False


async def test_non_positive_surplus_skips_llm(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        drive_file_id="file-1",
    )
    await _make_transaction(db_session, statement, amount=Decimal("100.00"))
    await _make_transaction(db_session, statement, amount=Decimal("-200.00"))
    await _make_investment_settings(db_session, safety_buffer_amount=Decimal("100.00"))

    graph = build_investment_graph(session=db_session, chat_model=FakeChatModel())
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["safety_buffer"]["investable_amount"] == "0"
    assert result["proposal"]["amount"] == "0"
    assert result["proposal"]["rationale"] == "Brak nadwyżki do zainwestowania"


async def test_trend_anomaly_caps_proposal_at_historical_average(db_session):
    account = await _make_account(db_session)
    for i, period_end in enumerate(
        [date(2025, 12, 24), date(2025, 12, 31), date(2026, 1, 7)]
    ):
        previous_statement = await _make_processed_statement(
            db_session,
            account,
            period_end=period_end,
            closing_balance=Decimal("10000.00"),
            drive_file_id=f"file-old-{i}",
        )
        await _make_transaction(
            db_session, previous_statement, amount=Decimal("100.00")
        )

    current_statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        closing_balance=Decimal("10000.00"),
        drive_file_id="file-current",
    )
    await _make_transaction(db_session, current_statement, amount=Decimal("500.00"))
    await _make_investment_settings(db_session, safety_buffer_amount=Decimal("0.00"))

    graph = build_investment_graph(
        session=db_session, chat_model=FakeChatModel(VALID_LLM_RESULT)
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["trend"]["is_anomaly"] is True
    assert result["safety_buffer"]["investable_amount"] == "500.00"
    # capped at the historical average (100.00), not the raw 500.00 surplus.
    assert result["proposal"]["amount"] == "100.00"


async def test_insufficient_history_when_only_one_statement(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        drive_file_id="file-1",
    )
    await _make_transaction(db_session, statement, amount=Decimal("100.00"))
    await _make_investment_settings(db_session, safety_buffer_amount=Decimal("0.00"))

    graph = build_investment_graph(
        session=db_session, chat_model=FakeChatModel(VALID_LLM_RESULT)
    )
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["trend"]["trend_note"] == "insufficient_history"
    assert result["trend"]["is_anomaly"] is False


async def test_llm_valid_split_used_for_allocation(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        closing_balance=Decimal("10000.00"),
        drive_file_id="file-1",
    )
    await _make_transaction(db_session, statement, amount=Decimal("300.00"))
    await _make_investment_settings(db_session, safety_buffer_amount=Decimal("0.00"))

    graph = build_investment_graph(
        session=db_session, chat_model=FakeChatModel(VALID_LLM_RESULT)
    )
    result = await graph.ainvoke(EMPTY_STATE)

    allocation = result["proposal"]["allocation"]
    assert allocation["etf"] == "150.00"
    assert allocation["term_deposit"] == "90.00"
    assert allocation["savings_account"] == "60.00"


async def test_llm_failure_falls_back_to_equal_split(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        closing_balance=Decimal("10000.00"),
        drive_file_id="file-1",
    )
    await _make_transaction(db_session, statement, amount=Decimal("300.00"))
    await _make_investment_settings(db_session, safety_buffer_amount=Decimal("0.00"))

    graph = build_investment_graph(
        session=db_session, chat_model=FakeChatModel(RuntimeError("LLM down"))
    )
    result = await graph.ainvoke(EMPTY_STATE)

    allocation = result["proposal"]["allocation"]
    assert allocation == {
        "etf": "100.00",
        "term_deposit": "100.00",
        "savings_account": "100.00",
    }
    assert "równy podział domyślny" in result["proposal"]["rationale"]


async def test_no_investment_settings_seeded_is_noop(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        drive_file_id="file-1",
    )
    await _make_transaction(db_session, statement, amount=Decimal("300.00"))

    graph = build_investment_graph(session=db_session, chat_model=FakeChatModel())
    result = await graph.ainvoke(EMPTY_STATE)

    assert result["safety_buffer"] is None
    assert result["proposal"] is None

    recommendations = (
        (await db_session.execute(select(InvestmentRecommendation))).scalars().all()
    )
    assert recommendations == []


async def test_persists_recommendation_row(db_session):
    account = await _make_account(db_session)
    statement = await _make_processed_statement(
        db_session,
        account,
        period_end=date(2026, 1, 14),
        closing_balance=Decimal("10000.00"),
        drive_file_id="file-1",
    )
    await _make_transaction(db_session, statement, amount=Decimal("300.00"))
    await _make_investment_settings(db_session, safety_buffer_amount=Decimal("0.00"))

    graph = build_investment_graph(
        session=db_session, chat_model=FakeChatModel(VALID_LLM_RESULT)
    )
    await graph.ainvoke(EMPTY_STATE)

    recommendation = (
        await db_session.execute(select(InvestmentRecommendation))
    ).scalar_one()
    assert recommendation.report_id is None
    assert recommendation.surplus_amount == Decimal("300.00")
    assert recommendation.allocation_proposal["etf"] == "150.00"
