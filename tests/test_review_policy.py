"""The human-review policy must state the rule that fired.

"Needs Human Review = Yes" next to a 100.00% confidence looks like a bug to an
analyst unless the reason is visible, so each rule returns its own explanation.
"""
from types import SimpleNamespace

from cyberagent.agent.investigation_agent import InvestigationAgent

REVIEW_RULE = InvestigationAgent._determine_needs_human_review


def agent_with_tool_calls(n: int) -> SimpleNamespace:
    """Only tool_call_history is read, so a stub self keeps the test off the ML stack."""
    return SimpleNamespace(tool_call_history=[{"tool": "predict_proba"}] * n)


def call_rule(pred_class: str, confidence: float, calls: int = 4):
    return REVIEW_RULE(agent_with_tool_calls(calls), pred_class, confidence)


def test_high_impact_class_is_reviewed_even_at_full_confidence():
    needs_review, reason = call_rule("DDoS", 0.9998)
    assert needs_review is True
    assert "high-impact" in reason
    assert "DDoS" in reason


def test_low_confidence_states_the_number_it_compared():
    needs_review, reason = call_rule("BENIGN", 0.51)
    assert needs_review is True
    assert "0.51" in reason


def test_thin_evidence_reports_how_many_tools_ran():
    needs_review, reason = call_rule("BENIGN", 0.95, calls=1)
    assert needs_review is True
    assert "1 evidence tool call" in reason


def test_confident_well_evidenced_benign_flow_needs_no_review():
    needs_review, reason = call_rule("BENIGN", 0.95)
    assert needs_review is False
    assert reason == ""
