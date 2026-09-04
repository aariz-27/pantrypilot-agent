from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    ROOT / "CURRENT_STATUS.md",
    ROOT / "DECISION_REGISTER.md",
    ROOT / "APPROVAL_GATES.md",
    ROOT / "PROJECT_HISTORY.md",
    ROOT / "SPRINT_BOARD.md",
    ROOT / "CLAUDE.md",
    ROOT / "AGENTS.md",
    ROOT / "docs" / "AI_DELIVERY_OPERATING_MODEL.md",
    ROOT / "docs" / "TECHNICAL_ARCHITECTURE.md",
    ROOT / "docs" / "SYSTEM_CONTEXT.md",
    ROOT / "docs" / "DATA_ARCHITECTURE.md",
    ROOT / "docs" / "DATA_INTEGRITY_POLICY.md",
    ROOT / "docs" / "PERFORMANCE_RELIABILITY_POLICY.md",
    ROOT / "docs" / "QUALITY_SECURITY_TEST_STRATEGY.md",
    ROOT / "docs" / "THREAT_MODEL.md",
    ROOT / "docs" / "SECURITY_ACCEPTANCE_MATRIX.md",
    ROOT / "docs" / "API_INTEGRATION_STANDARDS.md",
    ROOT / "docs" / "MASTER_REMEDIATION_REGISTER.md",
    ROOT / "docs" / "REQUIREMENTS_TRACEABILITY.md",
    ROOT / "docs" / "STATUS_UPDATE_WORKFLOW.md",
    ROOT / "docs" / "MIGRATION_RELEASE_POLICY.md",
    ROOT / "docs" / "OBSERVABILITY_OPERATIONS.md",
    ROOT / "docs" / "governance" / "decision_triggers.json",
    ROOT / "docs" / "governance" / "review_checklist.json",
    ROOT / "docs" / "traceability" / "tickets" / "TICKET_TEMPLATE.json",
    ROOT / ".github" / "pull_request_template.md",
]


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def check_required_files() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_FILES if not path.exists()]

    if missing:
        fail("Missing required files:\n- " + "\n- ".join(missing))

    print("[PASS] Required governance files exist")


def check_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")
    except OSError as exc:
        fail(f"Unable to read {path.relative_to(ROOT)}: {exc}")


def check_decision_triggers() -> None:
    path = ROOT / "docs" / "governance" / "decision_triggers.json"
    data = check_json(path)

    if not isinstance(data, list):
        fail("decision_triggers.json must contain a JSON array")

    required_fields = {
        "decision_id",
        "trigger_kind",
        "trigger_ref",
        "trigger_text",
        "state",
        "blocking_scope",
        "verification_note",
    }

    for index, trigger in enumerate(data):
        if not isinstance(trigger, dict):
            fail(f"Decision trigger #{index + 1} is not an object")

        missing = required_fields - trigger.keys()
        if missing:
            fail(
                f"Decision trigger #{index + 1} missing fields: "
                + ", ".join(sorted(missing))
            )

    print("[PASS] Decision trigger registry is structurally valid")


def check_review_checklist() -> None:
    path = ROOT / "docs" / "governance" / "review_checklist.json"
    data = check_json(path)

    if not isinstance(data, dict):
        fail("review_checklist.json must contain a JSON object")

    review_order = data.get("review_order")

    if not isinstance(review_order, list) or len(review_order) != 15:
        fail("review_checklist.json must contain exactly 15 review areas")

    expected_order = list(range(1, 16))
    actual_order = [item.get("order") for item in review_order]

    if actual_order != expected_order:
        fail("review checklist order must be exactly 1 through 15")

    areas = [item.get("area") for item in review_order]

    if "escape_paths" not in areas:
        fail("review checklist must contain mandatory escape_paths review")

    print("[PASS] Independent review checklist is structurally valid")


def check_ticket_template() -> None:
    path = ROOT / "docs" / "traceability" / "tickets" / "TICKET_TEMPLATE.json"
    data = check_json(path)

    if not isinstance(data, dict):
        fail("TICKET_TEMPLATE.json must contain a JSON object")

    required_fields = {
        "ticket_id",
        "title",
        "status",
        "authorized",
        "objective",
        "in_scope",
        "out_of_scope",
        "requirements",
        "decisions",
        "affected_modules",
        "allowed_paths",
        "acceptance_criteria",
        "required_tests",
        "review_required",
        "completion_evidence",
    }

    missing = required_fields - data.keys()

    if missing:
        fail(
            "TICKET_TEMPLATE.json missing fields: "
            + ", ".join(sorted(missing))
        )

    if data.get("authorized") is not False:
        fail("Ticket template must default authorized=false")

    review_required = data.get("review_required", {})

    expected_review_flags = {
        "claude_self_review": True,
        "chatgpt_independent_review": True,
        "founder_merge": True,
    }

    if review_required != expected_review_flags:
        fail("Ticket template review_required contract is incorrect")

    print("[PASS] Ticket template is structurally valid")


def check_agent_pointer() -> None:
    path = ROOT / "AGENTS.md"

    text = path.read_text(encoding="utf-8")

    if "docs/AGENTS.md" not in text:
        fail("Root AGENTS.md must point to docs/AGENTS.md")

    print("[PASS] Root AGENTS.md points to canonical agent contract")


def main() -> None:
    print("PantryPilot governance validation")
    print("=" * 34)

    check_required_files()
    check_decision_triggers()
    check_review_checklist()
    check_ticket_template()
    check_agent_pointer()

    print("=" * 34)
    print("[PASS] Governance validation completed successfully")


if __name__ == "__main__":
    main()
