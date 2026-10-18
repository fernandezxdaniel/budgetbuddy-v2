"""Generate period-aware guidance from the user's 50/30/20 budget and actuals."""
import math

_ORDER = {"danger": 0, "warning": 1, "info": 2, "good": 3}


def peso(amount):
    return f"\u20b1{amount:,.2f}"


def _recommendation(level, title, message):
    return {"level": level, "title": title, "message": message}


def generate(result):
    income = result["income"]
    categories = result["categories"]
    metrics = result["metrics"]
    period = result["period"]
    period_name = f"this {period['days']}-day period" if period["set"] else "this period"

    if income <= 0:
        return [_recommendation(
            "info",
            "Set income for this period",
            "Enter the income available for these dates. BudgetBuddy uses the 50/30/20 rule "
            "to set maximum targets for needs, wants, and savings.",
        )]
    if result["items_count"] == 0:
        return [_recommendation(
            "info",
            "Plan your 50/30/20 targets",
            f"For {period_name}, your targets are {peso(categories['needs']['limit'])} for needs (50%), "
            f"{peso(categories['wants']['limit'])} for wants (30%), and "
            f"{peso(categories['savings']['limit'])} for savings (20%). Add category items "
            "and record actual amounts to track this period.",
        )]

    needs, wants, savings = (
        categories["needs"],
        categories["wants"],
        categories["savings"],
    )
    spending_left = metrics["spending_left"]
    recommendations = []

    if result["totals"]["balance"] < 0:
        recommendations.append(_recommendation(
            "danger",
            "Spending is above this period's income",
            f"Recorded spending and savings exceed income by {peso(-result['totals']['balance'])}. "
            "Pause non-essential purchases and review the entries before changing your plan.",
        ))
    if needs["actual"] > needs["limit"]:
        recommendations.append(_recommendation(
            "warning",
            "Needs exceeded the 50% target",
            f"Needs spending is {peso(needs['actual'] - needs['limit'])} above the "
            f"{peso(needs['limit'])} 50% target for this period. Review essential costs "
            "and check that every entry is accurate.",
        ))
    elif needs["left"] < 0:
        recommendations.append(_recommendation(
            "info",
            "Needs exceeded the planned budget",
            f"Needs are {peso(-needs['left'])} above the selected {peso(needs['budget'])} "
            f"budget, but remain within the 50% income target of {peso(needs['limit'])}.",
        ))
    if wants["actual"] > wants["limit"]:
        recommendations.append(_recommendation(
            "warning",
            "Wants exceeded the 30% target",
            f"Wants spending is {peso(wants['actual'] - wants['limit'])} above the "
            f"{peso(wants['limit'])} 30% target for this period. Reduce optional purchases "
            "and check that every entry is accurate.",
        ))
    elif wants["left"] < 0:
        recommendations.append(_recommendation(
            "info",
            "Wants exceeded the planned budget",
            f"Wants are {peso(-wants['left'])} above the selected {peso(wants['budget'])} "
            f"budget, but remain within the 30% income target of {peso(wants['limit'])}.",
        ))
    elif wants["budget"] > 0 and wants["percent_used"] >= 80:
        recommendations.append(_recommendation(
            "info",
            "Wants budget is nearly used",
            f"You have used {wants['percent_used']}% of the wants budget, with "
            f"{peso(wants['left'])} remaining for {period_name}.",
        ))

    if not savings["entered"]:
        recommendations.append(_recommendation(
            "warning",
            "Savings have not been recorded",
            f"Record any amount saved during {period_name}. The 20% savings target is "
            f"{peso(savings['limit'])}; you can budget up to this amount for savings.",
        ))
    elif savings["actual"] < savings["limit"]:
        remaining_savings_target = savings["limit"] - savings["actual"]
        if period["days_left"] > 0:
            daily_target = remaining_savings_target / period["days_left"]
            tip = (
                f"Meeting the remaining {peso(remaining_savings_target)} 20% target would require about "
                f"{peso(daily_target)} per remaining day."
            )
        else:
            tip = f"The period ended {peso(remaining_savings_target)} short of its 20% savings target."
        recommendations.append(_recommendation(
            "info",
            "Savings are below the 20% target",
            f"You recorded {peso(savings['actual'])} in savings against the "
            f"{peso(savings['limit'])} 20% target for {period_name}. {tip}",
        ))
    else:
        recommendations.append(_recommendation(
            "good",
            "20% savings target reached",
            f"You recorded {peso(savings['actual'])} in savings, meeting or exceeding "
            f"the {peso(savings['limit'])} target for {period_name}.",
        ))

    if period["active"] and period["days_left"] > 0 and period["elapsed"] > 0:
        if metrics["projected_spending"] > metrics["spending_budget"] and spending_left >= 0:
            message = (
                f"At the current pace, needs and wants could reach about "
                f"{peso(metrics['projected_spending'])}, above the combined "
                f"{peso(metrics['spending_budget'])} budget. About "
                f"{peso(metrics['daily_allowance'])} per remaining day would keep recorded "
                "spending within the budget."
            )
            recommendations.append(_recommendation(
                "warning", "Spending is on pace to exceed its budget", message
            ))

    if period["elapsed"] >= 3 and metrics["spent_total"] > 0:
        share = metrics["peak_amount"] / metrics["spent_total"]
        if share >= 0.4:
            recommendations.append(_recommendation(
                "info",
                "One day accounts for much of your spending",
                f"{peso(metrics['peak_amount'])} on {metrics['peak_day']} accounts for "
                f"{round(share * 100)}% of recorded needs and wants in this period. "
                "Check that the entry is accurate and plan for similar costs.",
            ))

    if (
        not any(item["level"] in ("danger", "warning") for item in recommendations)
        and needs["actual"] <= needs["budget"]
        and wants["actual"] <= wants["budget"]
        and savings["actual"] >= savings["limit"]
    ):
        recommendations.append(_recommendation(
            "good",
            "Your recorded spending is within plan",
            f"Needs and wants are within their 50% and 30% targets, and savings meet "
            f"the 20% target. {peso(max(spending_left, 0))} of the combined spending "
            "budget remains.",
        ))

    recommendations.sort(key=lambda item: _ORDER[item["level"]])
    return recommendations[:6]
