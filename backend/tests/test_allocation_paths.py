from dataclasses import replace

from app.core.appliance_allocator import Item, Problem, exhaustive, solve, validate


def test_nested_graph_path_budgets_are_enforced_by_solver_validator_and_oracle():
    problem = Problem(items=(
        Item("critical", 700, "district", "a", "critical", path=("source", "branch")),
        Item("optional", 500, "district", "b", "optional", path=("source", "branch")),
        Item("other", 400, "district", "c", "optional", path=("source", "other")),
    ), source_capacity_w=2000, feeder_limits_w={"district": 2000},
        feeder_available={"district": True}, class_order=("critical", "optional"),
        edge_limits_w={"source": 1500, "branch": 1000, "other": 400})
    plan = solve(problem)
    assert plan.status == "OPTIMAL"
    assert plan.served == exhaustive(problem) == {"critical", "other"}
    assert validate(problem, {"critical", "optional"}) == ["edge branch: 1200 W exceeds 1000 W"]
    missing = replace(problem, edge_limits_w={"source": 1500, "branch": 1000})
    assert "other" not in solve(missing).served
    assert any("unconfigured edge" in error for error in validate(missing, {"other"}))
