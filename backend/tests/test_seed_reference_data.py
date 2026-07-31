import json
from pathlib import Path

import pytest
from sqlalchemy import select

from finance_agent.db.models import (
    Account,
    Category,
    FixedCost,
    InvestmentSettings,
)
from scripts.seed_reference_data import seed

FAKE_ACCOUNTS = [
    {"display_name": "Personal", "bank_name": "Fake Bank"},
]

FAKE_CATEGORIES = [
    {"name": "Groceries", "score": 90, "type": "expense"},
    {"name": "Salary", "score": 100, "type": "income"},
]

FAKE_FIXED_COSTS = [
    {
        "name": "Rent",
        "category": "Groceries",
        "expected_amount": 1200.00,
        "frequency": "monthly",
    },
]

FAKE_INVESTMENT_SETTINGS = [
    {
        "risk_profile": "balanced",
        "safety_buffer_amount": 5000.00,
        "instruments": ["etf", "term_deposit"],
    },
]


def _write_fixture_json(
    data_dir: Path,
    accounts: list[dict] = FAKE_ACCOUNTS,
    categories: list[dict] = FAKE_CATEGORIES,
    fixed_costs: list[dict] = FAKE_FIXED_COSTS,
    investment_settings: list[dict] = FAKE_INVESTMENT_SETTINGS,
) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "accounts.json").write_text(json.dumps(accounts), encoding="utf-8")
    (data_dir / "categories.json").write_text(json.dumps(categories), encoding="utf-8")
    (data_dir / "fixed_costs.json").write_text(
        json.dumps(fixed_costs), encoding="utf-8"
    )
    (data_dir / "investment_settings.json").write_text(
        json.dumps(investment_settings), encoding="utf-8"
    )
    return data_dir


async def test_seed_creates_accounts_categories_and_fixed_costs(db_session, tmp_path):
    data_dir = _write_fixture_json(tmp_path)

    await seed(db_session, data_dir)
    await db_session.commit()

    account = (await db_session.execute(select(Account))).scalar_one()
    assert account.display_name == "Personal"
    assert account.bank_name == "Fake Bank"

    categories = {
        c.name: c for c in (await db_session.execute(select(Category))).scalars()
    }
    assert categories["Groceries"].score == 90
    assert categories["Groceries"].type == "expense"
    assert categories["Salary"].score == 100

    fixed_costs = {
        fc.name: fc for fc in (await db_session.execute(select(FixedCost))).scalars()
    }
    rent = fixed_costs["Rent"]
    assert rent.category_id == categories["Groceries"].id
    assert rent.frequency == "monthly"

    investment_settings = (
        await db_session.execute(select(InvestmentSettings))
    ).scalar_one()
    assert investment_settings.risk_profile == "balanced"
    assert investment_settings.safety_buffer_amount == 5000.00
    assert investment_settings.instruments == ["etf", "term_deposit"]


async def test_seed_is_idempotent_and_updates_changed_fields(db_session, tmp_path):
    data_dir = _write_fixture_json(tmp_path)
    await seed(db_session, data_dir)
    await db_session.commit()

    updated_accounts = [
        {"display_name": "Renamed", "bank_name": "Fake Bank"},
    ]
    updated_categories = [
        {"name": "Groceries", "score": 42, "type": "expense"},
        FAKE_CATEGORIES[1],
    ]
    updated_investment_settings = [
        {
            "risk_profile": "aggressive",
            "safety_buffer_amount": 8000.00,
            "instruments": ["etf"],
        },
    ]
    _write_fixture_json(
        tmp_path,
        updated_accounts,
        updated_categories,
        FAKE_FIXED_COSTS,
        updated_investment_settings,
    )
    await seed(db_session, data_dir)
    await db_session.commit()

    all_accounts = (await db_session.execute(select(Account))).scalars().all()
    all_categories = (await db_session.execute(select(Category))).scalars().all()
    all_fixed_costs = (await db_session.execute(select(FixedCost))).scalars().all()
    all_investment_settings = (
        (await db_session.execute(select(InvestmentSettings))).scalars().all()
    )

    assert len(all_accounts) == 1
    assert len(all_categories) == 2
    assert len(all_fixed_costs) == 1
    assert len(all_investment_settings) == 1
    assert all_accounts[0].display_name == "Renamed"
    groceries = next(c for c in all_categories if c.name == "Groceries")
    assert groceries.score == 42
    assert all_investment_settings[0].risk_profile == "aggressive"
    assert all_investment_settings[0].safety_buffer_amount == 8000.00


async def test_seed_raises_on_more_than_one_investment_settings_entry(
    db_session, tmp_path
):
    two_settings = [
        FAKE_INVESTMENT_SETTINGS[0],
        {
            "risk_profile": "conservative",
            "safety_buffer_amount": 1000.00,
            "instruments": ["savings_account"],
        },
    ]
    data_dir = _write_fixture_json(tmp_path, investment_settings=two_settings)

    with pytest.raises(ValueError, match="co najwyżej jeden wpis"):
        await seed(db_session, data_dir)


async def test_seed_raises_on_unknown_category_reference(db_session, tmp_path):
    fixed_costs_with_unknown_category = [
        {
            "name": "Internet",
            "category": "DoesNotExist",
            "expected_amount": 50.00,
            "frequency": "monthly",
        }
    ]
    data_dir = _write_fixture_json(
        tmp_path, fixed_costs=fixed_costs_with_unknown_category
    )

    with pytest.raises(ValueError, match="DoesNotExist"):
        await seed(db_session, data_dir)


async def test_seed_raises_on_more_than_one_account_in_source(db_session, tmp_path):
    two_accounts = [
        FAKE_ACCOUNTS[0],
        {"display_name": "Business", "bank_name": "Fake Biz Bank"},
    ]
    data_dir = _write_fixture_json(tmp_path, accounts=two_accounts)

    with pytest.raises(ValueError, match="co najwyżej jedno konto"):
        await seed(db_session, data_dir)
