"""Coverage screen: plan, visit cost estimates, spending, FSA/HSA, and employer benefits. No Gemini."""

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends

from data import store
from deps import get_user_id
from models import (
    BenefitAccount,
    Coverage,
    CoverageTip,
    EmployerBenefit,
    InsurancePlan,
    Progress,
    SpendCategory,
    Spending,
    VisitCost,
    YearTotal,
)

router = APIRouter(tags=["coverage"])

DISCLAIMER = "Costs are estimates from your plan. Your insurer has the final say."
CATEGORIES = [("copay", "Copays"), ("deductible", "Deductible"), ("coinsurance", "Coinsurance"), ("prescription", "Prescriptions")]


def _rule_for(rules: list[dict[str, Any]], *names: str | None) -> dict[str, Any] | None:
    """First cost rule whose services match any of the names (specialty or visit type), case-insensitively."""
    wanted = [n.casefold() for n in names if n]
    for rule in rules:
        if any(s.casefold() == w for s in rule["services"] for w in wanted):
            return rule
    return None


def _deductible_used(ins: dict[str, Any], year: int) -> float:
    """Deductible paid so far this plan year, from claims."""
    return sum(c["you_paid"] for c in ins["claims"] if c["category"] == "deductible" and c["date"].startswith(str(year)))


def estimate(ins: dict[str, Any], rule: dict[str, Any] | None, in_network: bool, deductible_left: float) -> tuple[float | None, str]:
    """Estimated cost and a plain-language reason for one visit."""
    plan = ins["plan"]
    if not in_network:
        return float(plan["out_of_network_estimate"]), "Out of network estimate"
    if rule is None:
        return None, "Check with your insurer"
    if rule["kind"] == "free":
        return 0.0, rule["label"]
    if rule["kind"] == "copay":
        return float(rule["amount"]), rule["label"]
    # Deductible: the allowed rate until the deductible is met, then coinsurance.
    rate, coins = float(rule["rate"]), plan["coinsurance_pct"] / 100
    if deductible_left >= rate:
        return rate, "Deductible not met yet"
    if deductible_left > 0:
        return round(deductible_left + coins * (rate - deductible_left), 2), f"Rest of your deductible plus {plan['coinsurance_pct']}%"
    return round(coins * rate, 2), f"{plan['coinsurance_pct']}% coinsurance"


def _pay_with(ins: dict[str, Any], cost: float | None) -> str | None:
    """Which account can pay a medical cost, if any. Dependent care FSAs cannot."""
    if not cost:
        return None
    types = {a["type"] for a in ins["accounts"]}
    return "HSA" if "hsa" in types else "FSA" if "health_fsa" in types else None


def build_coverage(user_id: str) -> Coverage:
    """Assemble the Coverage response for one persona."""
    data = store.get_user(user_id)
    ins = data["insurance"]
    plan = ins["plan"]
    year = plan["plan_year"]
    family = {f["id"]: f["name"] for f in data["profile"].get("family") or []}
    providers = {p["name"]: p for p in data.get("providers", [])}
    rules = ins["cost_rules"]
    deductible_left = max(0.0, plan["deductible"] - _deductible_used(ins, year))

    upcoming = []
    for appt in sorted(data.get("appointments", {}).get("upcoming", []), key=lambda a: a["datetime"]):
        rule = _rule_for(rules, appt["specialty"])
        in_network = providers.get(appt["provider"], {}).get("in_network", True)  # unknown providers assumed in network
        cost, label = estimate(ins, rule, in_network, deductible_left)
        upcoming.append(VisitCost(
            appointment_id=appt["id"],
            title=rule["visit_name"] if rule else appt["specialty"],
            specialty=appt["specialty"],
            provider=appt["provider"],
            for_person=appt["for_person"],
            for_name=family.get(appt["for_person"]),
            datetime=appt["datetime"],
            cost=cost,
            cost_label=label,
            plan=rule["plan"] if rule else None,
            in_network=in_network,
            pay_with=_pay_with(ins, cost),
        ))

    spending = _spending(ins, year)
    return Coverage(
        plan=InsurancePlan(
            insurer=plan["insurer"], name=plan["name"], type=plan["type"], employer=plan["employer"],
            member_id=plan["member_id"], group_number=plan["group_number"], plan_year=year, resets_on=plan["resets_on"],
            covers=[data["profile"]["name"] if p == "self" else family.get(p, p) for p in plan["covered"]],
            **plan["coverage"],
        ),
        upcoming=upcoming,
        tips=_tips(data, ins, deductible_left),
        spending=spending,
        accounts=[_account(a) for a in ins["accounts"]],
        employer_benefits=[_benefit(b) for b in ins["employer_benefits"]],
        ask_suggestions=ins.get("ask_suggestions", []),
        disclaimer=DISCLAIMER,
    )


def _spending(ins: dict[str, Any], year: int) -> Spending:
    """Out-of-pocket totals by category this year, and by year."""
    by_year: dict[int, float] = defaultdict(float)
    by_cat: dict[str, float] = defaultdict(float)
    for c in ins["claims"]:
        y = int(c["date"][:4])
        by_year[y] += c["you_paid"]
        if y == year:
            by_cat[c["category"]] += c["you_paid"]
    plan = ins["plan"]
    total = by_year.get(year, 0.0)
    return Spending(
        year=year,
        total=total,
        by_category=[SpendCategory(category=k, label=label, amount=by_cat.get(k, 0.0)) for k, label in CATEGORIES],
        by_year=[YearTotal(year=y, total=t) for y, t in sorted(by_year.items(), reverse=True)],
        premiums=float(plan.get("premiums_paid", {}).get(str(year), 0)),
        deductible=Progress(used=by_cat.get("deductible", 0.0), limit=plan["deductible"]),
        out_of_pocket=Progress(used=total, limit=plan["out_of_pocket_max"]),
    )


def _tips(data: dict[str, Any], ins: dict[str, Any], deductible_left: float) -> list[CoverageTip]:
    """Up to 2 tips from suggested appointments: in vs out of network first, then free preventive care."""
    family = {f["id"]: f["name"] for f in data["profile"].get("family") or []}
    providers = data.get("providers", [])
    network_tips, free_tips = [], []
    for s in data.get("appointments", {}).get("suggested", []):
        rule = _rule_for(ins["cost_rules"], s["specialty"])
        who = family.get(s.get("for_person", "self"))
        name = rule["visit_name"] if rule else s["specialty"]
        title = f"{name} for {who}" if who else name
        options = [p for p in providers if p["specialty"].casefold() == s["specialty"].casefold()]
        inside = sorted((p for p in options if p["in_network"]), key=lambda p: -p["rating"])
        outside = [p for p in options if not p["in_network"]]
        if inside and outside:
            in_cost, _ = estimate(ins, rule, True, deductible_left)
            out_cost, _ = estimate(ins, rule, False, deductible_left)
            network_tips.append(CoverageTip(
                title=title,
                text=f"{inside[0]['name']} is in network: ${in_cost:,.0f}. {outside[0]['name']} is out of network: about ${out_cost:,.0f}.",
            ))
        elif rule and rule["kind"] == "free":
            reward = next((b for b in ins["employer_benefits"] if b.get("linked_service", "").casefold() == s["specialty"].casefold()), None)
            text = f"{rule['label']}, so you pay $0."
            if reward:
                text += f" Your employer benefit: {reward['detail']}."
            free_tips.append(CoverageTip(title=f"{title} is free", text=text))
    return (network_tips + free_tips)[:2]


def _account(a: dict[str, Any]) -> BenefitAccount:
    """FSA balance is what is left of the election; HSA balance is stored as is."""
    if a["type"] == "hsa":
        contributed = a.get("contributed", {})
        return BenefitAccount(
            type="hsa", name=a["name"], balance=a["balance"], annual_limit=a.get("annual_limit"),
            contributed_you=contributed.get("you"), contributed_employer=contributed.get("employer"), note=a["note"],
        )
    return BenefitAccount(
        type=a["type"], name=a["name"], balance=a["elected"] - a["spent"], elected=a["elected"], spent=a["spent"],
        use_by=a.get("use_by"), grace_until=a.get("grace_until"), note=a["note"],
    )


def _benefit(b: dict[str, Any]) -> EmployerBenefit:
    """Turn a seeded benefit into a display label like "2 of 10 used" or "$250 of $600 used"."""
    label = b.get("status_text")
    if not label and b["status"] == "in_use" and "limit" in b:
        used, limit = b["used"], b["limit"]
        label = f"${used:,} of ${limit:,} used" if b.get("unit") == "dollars" else f"{used} of {limit} used"
    if not label:
        label = {"available": "Available", "not_started": "Not started", "plan_ahead": "Plan ahead", "in_use": "In use"}[b["status"]]
    return EmployerBenefit(name=b["name"], detail=b["detail"], status=b["status"], status_label=label)


def service_costs(user_id: str) -> list[dict[str, Any]]:
    """In-network cost estimate for every visit type the plan lists, for Em's coverage answers."""
    ins = store.get(user_id, "insurance")
    plan = ins["plan"]
    deductible_left = max(0.0, plan["deductible"] - _deductible_used(ins, plan["plan_year"]))
    costs = []
    for rule in ins["cost_rules"]:
        cost, label = estimate(ins, rule, True, deductible_left)
        costs.append({"visit": rule["visit_name"], "services": rule["services"], "plan": rule["plan"], "cost": cost, "why": label})
    return costs


@router.get("/insurance")
def get_insurance(user_id: str = Depends(get_user_id)) -> Coverage:
    """Return the Coverage screen data for this persona."""
    return build_coverage(user_id)
