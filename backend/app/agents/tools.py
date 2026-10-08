"""Tools as the LLM sees them, and how code runs them.

The LLM only sees each tool's name, description and parameters. Values the LLM must not
control (the logged-in customer) are filled in from graph state here, at execution time.
"""

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, Field

from app.tools.account import find_plans, get_my_account, get_outages, get_roaming_rate
from app.tools.calculator import calculate
from app.tools.currency import convert_currency
from app.tools.kb import search_support_docs
from app.tools.roaming import compare_roaming_options


class SearchDocsArgs(BaseModel):
    query: str = Field(description="What to look up in the support docs, e.g. 'which zone is Japan in'")


class OutagesArgs(BaseModel):
    area: str | None = Field(None, description="City or area. Omit to use the customer's own area.")


class NoArgs(BaseModel):
    pass


class FindPlansArgs(BaseModel):
    zone: int | None = Field(None, description="Only plans that include this roaming zone (1-4)")
    min_data_gb: int | None = Field(None, description="Only plans with at least this much monthly data")


class RoamingRateArgs(BaseModel):
    zone: int = Field(description="Roaming zone number 1-4")


class CompareTripArgs(BaseModel):
    zone: int = Field(description="Roaming zone number 1-4 of the destination")
    days: int = Field(description="Trip length in days")
    gb_per_day: float | None = Field(
        None, description="Only if the customer stated their own data use; otherwise omit")


class CalculatorArgs(BaseModel):
    expression: str = Field(description="Arithmetic using + - * / ( ) min max round, e.g. '18 / 30 * 10 * 129'")


class CurrencyArgs(BaseModel):
    amount: float
    from_currency: str = Field(description="ISO code, e.g. SEK")
    to_currency: str = Field(description="ISO code, e.g. EUR")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[dict, BaseModel], object]   # (graph state, validated args) -> result

    def schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.args.model_json_schema(),
        }}


SUPPORT_TOOLS = [
    ToolSpec("search_support_docs",
             "Search the operator's support documents: roaming zones and which countries are in "
             "them, fair use, Travel Pass conditions, billing, refunds, troubleshooting, contact info.",
             SearchDocsArgs, lambda state, a: search_support_docs(a.query)),
    ToolSpec("get_outages", "Known network outages for an area.",
             OutagesArgs, lambda state, a: get_outages(a.area or state["customer_area"])),
]

ANALYST_TOOLS = [
    ToolSpec("get_my_account",
             "The logged-in customer's account: plan, included zones, data used and left, typical usage.",
             NoArgs, lambda state, a: get_my_account(state["customer_id"])),
    ToolSpec("find_plans", "List plans with monthly price, data and included roaming zones.",
             FindPlansArgs, lambda state, a: find_plans(a.zone, a.min_data_gb)),
    ToolSpec("get_roaming_rate",
             "Pay-as-you-go price per GB and available Travel Passes for a roaming zone number.",
             RoamingRateArgs, lambda state, a: get_roaming_rate(a.zone)),
    ToolSpec("compare_roaming_options",
             "Compare every way to cover a trip's data in a zone (pay-as-you-go, Travel Passes, plan "
             "upgrades) with total cost in SEK, cheapest first. Use this for any trip cost question.",
             CompareTripArgs,
             lambda state, a: compare_roaming_options(state["customer_id"], a.zone, a.days, a.gb_per_day)),
    ToolSpec("cost_calculator", "Evaluate arithmetic. Use it for every computed figure.",
             CalculatorArgs, lambda state, a: calculate(a.expression)),
    ToolSpec("convert_currency", "Convert money between currencies at today's ECB rate.",
             CurrencyArgs, lambda state, a: convert_currency(a.amount, a.from_currency, a.to_currency)),
]


def run_tool(spec: ToolSpec, state: dict, raw_args: dict) -> object:
    """Validate the LLM's arguments and run the tool. Never raises: errors become results."""
    try:
        return spec.run(state, spec.args.model_validate(raw_args or {}))
    except Exception as exc:  # a bad argument or a tool bug must not crash the turn
        return {"error": f"{type(exc).__name__}: {exc}"}


def is_error(result: object) -> bool:
    return isinstance(result, dict) and "error" in result
