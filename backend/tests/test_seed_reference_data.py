import json
from pathlib import Path

import pytest
from sqlalchemy import select

from finance_agent.db.models import Category, FixedCost
from scripts.seed_reference_data import seed

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


def _write_fixture_json(
    data_dir: Path, categories: list[dict], fixed_costs: list[dict]
) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "categories.json").write_text(json.dumps(categories), encoding="utf-8")
    (data_dir / "fixed_costs.json").write_text(
        json.dumps(fixed_costs), encoding="utf-8"
    )
    return data_dir


async def test_seed_creates_categories_and_fixed_costs(db_session, tmp_path):
    data_dir = _write_fixture_json(tmp_path, FAKE_CATEGORIES, FAKE_FIXED_COSTS)

    await seed(db_session, data_dir)
    await db_session.commit()

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


async def test_seed_is_idempotent_and_updates_changed_fields(db_session, tmp_path):
    data_dir = _write_fixture_json(tmp_path, FAKE_CATEGORIES, FAKE_FIXED_COSTS)
    await seed(db_session, data_dir)
    await db_session.commit()

    updated_categories = [
        {"name": "Groceries", "score": 42, "type": "expense"},
        FAKE_CATEGORIES[1],
    ]
    _write_fixture_json(tmp_path, updated_categories, FAKE_FIXED_COSTS)
    await seed(db_session, data_dir)
    await db_session.commit()

    all_categories = (await db_session.execute(select(Category))).scalars().all()
    all_fixed_costs = (await db_session.execute(select(FixedCost))).scalars().all()

    assert len(all_categories) == 2
    assert len(all_fixed_costs) == 1
    groceries = next(c for c in all_categories if c.name == "Groceries")
    assert groceries.score == 42


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
        tmp_path, FAKE_CATEGORIES, fixed_costs_with_unknown_category
    )

    with pytest.raises(ValueError, match="DoesNotExist"):
        await seed(db_session, data_dir)
