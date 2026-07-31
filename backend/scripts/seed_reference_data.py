"""Seed ACCOUNTS/CATEGORIES/FIXED_COSTS from data/local/*.json.

Usage: uv run python scripts/seed_reference_data.py

Reads the real, gitignored data/local/accounts.json, categories.json and
fixed_costs.json (see docs/01-spec-data-model.md's "Przechowywanie realnej
zawartości" section) and upserts them into the Postgres tables via the
SQLAlchemy models. Safe to re-run: existing rows are matched by their
natural key (name for categories/fixed costs; accounts.json holds at most
one entry, matched against the single existing Account row if any) and
updated in place rather than duplicated.
"""

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finance_agent.db.models import Account, Category, FixedCost, InvestmentSettings
from finance_agent.db.session import async_session_factory

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_LOCAL_DIR = REPO_ROOT / "data" / "local"


class AccountSeed(BaseModel):
    display_name: str
    bank_name: str


class CategorySeed(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    type: Literal["income", "expense", "transfer"]


class FixedCostSeed(BaseModel):
    name: str
    category: str
    expected_amount: Decimal
    frequency: Literal["monthly", "quarterly", "yearly"]


class InvestmentSettingsSeed(BaseModel):
    risk_profile: Literal["conservative", "balanced", "aggressive"]
    safety_buffer_amount: Decimal
    instruments: list[Literal["etf", "term_deposit", "savings_account"]]


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        example = path.with_suffix(".example" + path.suffix)
        raise FileNotFoundError(
            f"{path} not found. This holds real reference data and is gitignored — "
            f"create it yourself (see {example.name} for the expected shape, and "
            f"docs/01-spec-data-model.md's 'Przechowywanie realnej zawartości' section)."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_accounts(data_dir: Path) -> list[AccountSeed]:
    raw = _load_json(data_dir / "accounts.json")
    return [AccountSeed.model_validate(item) for item in raw]


def load_categories(data_dir: Path) -> list[CategorySeed]:
    raw = _load_json(data_dir / "categories.json")
    return [CategorySeed.model_validate(item) for item in raw]


def load_fixed_costs(data_dir: Path) -> list[FixedCostSeed]:
    raw = _load_json(data_dir / "fixed_costs.json")
    return [FixedCostSeed.model_validate(item) for item in raw]


def load_investment_settings(data_dir: Path) -> list[InvestmentSettingsSeed]:
    raw = _load_json(data_dir / "investment_settings.json")
    return [InvestmentSettingsSeed.model_validate(item) for item in raw]


async def upsert_accounts(session: AsyncSession, accounts: list[AccountSeed]) -> None:
    if len(accounts) > 1:
        raise ValueError(
            "accounts.json musi zawierać co najwyżej jedno konto — "
            f"znaleziono {len(accounts)}."
        )
    if not accounts:
        return

    seed = accounts[0]
    existing = (await session.execute(select(Account))).scalars().first()
    if existing is None:
        session.add(Account(display_name=seed.display_name, bank_name=seed.bank_name))
    else:
        existing.display_name = seed.display_name
        existing.bank_name = seed.bank_name

    await session.flush()


async def upsert_categories(
    session: AsyncSession, categories: list[CategorySeed]
) -> None:
    existing = {c.name: c for c in (await session.execute(select(Category))).scalars()}

    for seed in categories:
        category = existing.get(seed.name)
        if category is None:
            session.add(Category(name=seed.name, score=seed.score, type=seed.type))
        else:
            category.score = seed.score
            category.type = seed.type

    await session.flush()


async def upsert_fixed_costs(
    session: AsyncSession, fixed_costs: list[FixedCostSeed]
) -> None:
    category_by_name = {
        c.name: c for c in (await session.execute(select(Category))).scalars()
    }
    existing = {
        fc.name: fc for fc in (await session.execute(select(FixedCost))).scalars()
    }

    for seed in fixed_costs:
        category = category_by_name.get(seed.category)
        if category is None:
            raise ValueError(
                f"Fixed cost '{seed.name}' references unknown category '{seed.category}' — "
                "add it to categories.json first."
            )

        fixed_cost = existing.get(seed.name)
        if fixed_cost is None:
            session.add(
                FixedCost(
                    name=seed.name,
                    category_id=category.id,
                    expected_amount=seed.expected_amount,
                    frequency=seed.frequency,
                )
            )
        else:
            fixed_cost.category_id = category.id
            fixed_cost.expected_amount = seed.expected_amount
            fixed_cost.frequency = seed.frequency

    await session.flush()


async def upsert_investment_settings(
    session: AsyncSession, settings_list: list[InvestmentSettingsSeed]
) -> None:
    if len(settings_list) > 1:
        raise ValueError(
            "investment_settings.json musi zawierać co najwyżej jeden wpis — "
            f"znaleziono {len(settings_list)}."
        )
    if not settings_list:
        return

    seed = settings_list[0]
    existing = (await session.execute(select(InvestmentSettings))).scalars().first()
    if existing is None:
        session.add(
            InvestmentSettings(
                risk_profile=seed.risk_profile,
                safety_buffer_amount=seed.safety_buffer_amount,
                instruments=seed.instruments,
            )
        )
    else:
        existing.risk_profile = seed.risk_profile
        existing.safety_buffer_amount = seed.safety_buffer_amount
        existing.instruments = seed.instruments

    await session.flush()


async def seed(session: AsyncSession, data_dir: Path = DEFAULT_DATA_LOCAL_DIR) -> None:
    await upsert_accounts(session, load_accounts(data_dir))
    await upsert_categories(session, load_categories(data_dir))
    await upsert_fixed_costs(session, load_fixed_costs(data_dir))
    await upsert_investment_settings(session, load_investment_settings(data_dir))


async def main() -> None:
    async with async_session_factory() as session:
        try:
            await seed(session)
        except Exception:
            await session.rollback()
            raise
        await session.commit()

        account_count = (await session.execute(select(Account))).scalars().all()
        category_count = (await session.execute(select(Category))).scalars().all()
        fixed_cost_count = (await session.execute(select(FixedCost))).scalars().all()
        print(
            f"Seeded {len(account_count)} accounts, {len(category_count)} categories, "
            f"{len(fixed_cost_count)} fixed costs."
        )


if __name__ == "__main__":
    asyncio.run(main())
