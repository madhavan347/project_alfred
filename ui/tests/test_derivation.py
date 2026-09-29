"""Pure derivations: available actions, the lifecycle journey, approval, and agent descriptions."""

from alfred.config.models import AgentConfig, CommandConfig
from alfred.domain.constants import (
    ExecutionMode,
    LifecyclePhase,
    PlanningState,
    RunStatus,
    TaskStatus,
    WorktreeMode,
)
from alfred.domain.models import AgentRun, Task

from alfred_ui.agents import cli_label, delivers_prompt, describe_agent, detect_model, placeholders
from alfred_ui.snapshot import approved_since_last_work, available_actions, derive_task, journey


def make_task(**fields: object) -> Task:
    values: dict[str, object] = {
        "task_number": 1,
        "title": "Task",
        "description": "d",
        "branch_name": "feature/x",
        "assigned_agent_alias": "fake",
    }
    values.update(fields)
    return Task(**values)  # type: ignore[arg-type]


def make_run(status: RunStatus, **fields: object) -> AgentRun:
    values: dict[str, object] = {
        "run_id": "r1",
        "task_number": 1,
        "agent_alias": "fake",
        "runtime_target": "local",
        "run_status": status,
        "session_name": "p-1-fake",
    }
    values.update(fields)
    return AgentRun(**values)  # type: ignore[arg-type]


def event(kind: str, index: int = 0) -> dict[str, object]:
    return {"index": index, "event_type": kind, "actor": "manager", "details": "", "timestamp": "t"}


def enabled(actions: dict[str, dict[str, object]]) -> set[str]:
    return {name for name, state in actions.items() if state["enabled"]}


def test_pending_task_can_be_triggered_but_not_merged() -> None:
    actions = available_actions(make_task(), None, [], False, [])
    assert {"trigger", "assign", "reassign", "block", "hold", "start", "consolidate"} <= enabled(
        actions
    )
    assert actions["merge"]["reason"] == "Merge needs MR in Review; status is Pending"
    assert actions["review"]["enabled"] is False
    assert actions["reopen"]["reason"] == "No earlier run to reopen; trigger the task instead"
    assert actions["stop"]["reason"] == "No active run to stop"


def test_running_task_blocks_delivery_until_the_run_ends() -> None:
    run = make_run(RunStatus.RUNNING)
    task = make_task(status=TaskStatus.IN_REVIEW)
    actions = available_actions(task, run, [run], True, [])
    assert (
        actions["trigger"]["reason"] == "A running run is active; stop it before triggering again"
    )
    assert actions["merge"]["reason"] == "Finish or stop the running run first"
    assert {"stop", "complete", "event"} <= enabled(actions)


def test_queued_run_can_be_dispatched_again() -> None:
    run = make_run(RunStatus.QUEUED)
    actions = available_actions(make_task(status=TaskStatus.QUEUED), run, [run], False, [])
    assert actions["trigger"]["enabled"] is True


def test_plan_awaiting_approval() -> None:
    task = make_task(
        execution_mode=ExecutionMode.PLAN_EXECUTION,
        planning_state=PlanningState.STARTED,
        status=TaskStatus.RUNNING,
    )
    run = make_run(RunStatus.RUNNING, phase="plan")
    actions = available_actions(task, run, [run], False, [])
    assert actions["continue"]["enabled"] is True
    idle = available_actions(task, None, [run], False, [])
    assert idle["trigger"]["reason"] == "The plan is awaiting approval; approve it to continue"
    assert idle["continue"]["reason"] == "No active planning run"
    direct = available_actions(make_task(), None, [], False, [])
    assert direct["continue"]["reason"] == "Only plan-execution tasks have a plan to approve"


def test_merge_deploy_archive_sequence() -> None:
    reviewed = make_task(status=TaskStatus.IN_REVIEW)
    assert available_actions(reviewed, None, [], False, [])["merge"]["reason"].startswith(
        "Record a review"
    )
    assert available_actions(reviewed, None, [], True, [])["merge"]["enabled"] is True
    merged = make_task(
        status=TaskStatus.IN_REVIEW, lifecycle_phase=LifecyclePhase.TESTING_DEPLOYMENT
    )
    actions = available_actions(merged, None, [], True, [])
    assert actions["merge"]["reason"] == "Already merged"
    assert {"deploy", "archive"} <= enabled(actions)
    assert actions["consolidate"]["enabled"] is False
    done = make_task(status=TaskStatus.COMPLETED, lifecycle_phase=LifecyclePhase.ARCHIVED)
    finished = available_actions(done, None, [], False, [])
    assert finished["trigger"]["reason"] == "The task is finished"
    assert finished["assign"]["enabled"] is False


def test_worktree_actions() -> None:
    disabled = make_task(worktree_mode=WorktreeMode.DISABLED, branch_name="")
    assert available_actions(disabled, None, [], False, [])["worktree_create"]["enabled"] is False
    clean = [{"repository": "app", "dirty": False}]
    dirty = [{"repository": "app", "dirty": True}]
    assert (
        available_actions(make_task(), None, [], False, clean)["commit"]["reason"]
        == "No uncommitted changes"
    )
    assert available_actions(make_task(), None, [], False, dirty)["commit"]["enabled"] is True
    run = make_run(RunStatus.RUNNING)
    busy = available_actions(make_task(), run, [run], False, dirty)
    assert busy["remove_worktrees"]["enabled"] is False


def test_approval_resets_on_later_work() -> None:
    assert approved_since_last_work([event("RUN_COMPLETED"), event("REVIEW_APPROVED")]) is True
    assert approved_since_last_work([event("REVIEW_APPROVED"), event("PROGRESS")]) is False
    assert approved_since_last_work([event("REVIEW_APPROVED"), event("STATUS_BLOCKED")]) is False
    assert approved_since_last_work([event("REVIEW_APPROVED"), event("SYNC_APPLIED")]) is True
    assert approved_since_last_work([]) is False


def test_journey_for_plan_and_consolidated_tasks() -> None:
    planned = make_task(
        execution_mode=ExecutionMode.PLAN_EXECUTION, planning_state=PlanningState.PENDING
    )
    steps = journey(planned, [], [], False)
    assert [step["key"] for step in steps][:4] == ["created", "assigned", "dispatched", "plan"]
    assert steps[2] == {"key": "dispatched", "label": "Planning started", "state": "current"}
    blocked = journey(make_task(status=TaskStatus.BLOCKED), [], [], False)
    assert blocked[2]["state"] == "blocked"
    consolidated = journey(
        make_task(status=TaskStatus.CONSOLIDATED, lifecycle_phase=LifecyclePhase.CONSOLIDATED),
        [],
        [],
        False,
    )
    assert consolidated[-1] == {"key": "consolidated", "label": "Consolidated", "state": "done"}
    assert {step["state"] for step in consolidated[2:-1]} == {"skipped"}


def test_derive_task_collects_agents_and_session() -> None:
    run = make_run(RunStatus.RUNNING)
    events = [
        {**event("AGENT_ASSIGNED"), "details": "Agent changed from unassigned to other."},
        {**event("AGENT_ASSIGNED", 1), "details": "Agent changed from other to fake."},
        {**event("PROGRESS", 2), "actor": "agent:fake"},
    ]
    derived = derive_task(
        make_task(status=TaskStatus.IN_PROGRESS),
        [run],
        events,
        [],
        sessions={},
        agents={"fake": {"cli": "Python script", "model": "", "runtime_target": "local"}},
        worktrees=[],
        knowledge=2,
        queued=False,
        completion_pending=True,
    )
    assert [agent["alias"] for agent in derived["agents"]] == ["fake", "other"]
    assert derived["agents"][0]["roles"] == ["assigned", "ran", "reported"]
    assert derived["agents"][1]["roles"] == ["was assigned"]
    assert derived["agents"][1]["configured"] is False
    assert derived["session"]["alive"] is False
    assert derived["knowledge_count"] == 2
    assert derived["completion_pending"] is True


def test_agent_description() -> None:
    agent = AgentConfig(
        alias="claude",
        runtime_target="claude-code",
        commands=CommandConfig(
            direct=("claude",),
            plan=("claude", "--model", "opus", "{prompt}"),
            execution=("claude", "--model=sonnet", "{prompt_file}", "{workdir}"),
        ),
    )
    described = describe_agent(agent)
    assert described["cli"] == "Claude Code"
    assert described["model"] == "sonnet"
    assert described["prompt_delivery"] == {
        "direct": "paste",
        "plan": "argument",
        "execution": "argument",
    }
    assert described["placeholders"]["execution"] == ["prompt_file", "workdir"]
    assert described["unknown_placeholders"] == {}
    assert detect_model(["codex", "-c", 'model="gpt-5"']) == "gpt-5"
    assert detect_model(["agy", "-m", "gemini"]) == "gemini"
    assert detect_model(["tail"]) == ""
    assert cli_label(["/usr/bin/python3", "tool.py"]) == "Python script (tool.py)"
    assert cli_label(["python3.12"]) == "Python"
    assert cli_label([]) == ""
    assert cli_label(["custom-agent"]) == "custom-agent"
    assert placeholders(["{bad"]) == set()
    assert delivers_prompt(["x", "{prompt}"]) is True
