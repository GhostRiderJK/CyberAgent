"""Tests for the grounding verifier used on LLM investigation reports."""
import pytest

from cyberagent.agent.grounding import verify_grounding


ML_RESULT = {"flow_id": 7, "predicted_class": "DDoS", "confidence": 0.92}
EVIDENCE = {
    "ml_prediction": ML_RESULT,
    "find_related_flows": [{"flow_id": 1}, {"flow_id": 2}, {"flow_id": 3}],
    "lookup_attack_pattern": {"description": "T1498 resource hijacking"},
}
TOOLS = ["predict_proba", "find_related_flows", "lookup_attack_pattern"]


def test_grounded_report_passes():
    result = verify_grounding(
        narrative="Detected DDoS with 92.0% confidence; 3 related flows observed in the window.",
        llm_predicted_class="DDoS",
        llm_confidence=0.92,
        ml_result=ML_RESULT,
        evidence_store=EVIDENCE,
        tools_called=TOOLS,
    )
    assert result["passed"] is True
    assert result["ungrounded_numbers"] == []


def test_overridden_label_fails():
    result = verify_grounding(
        narrative="This is clearly benign traffic.",
        llm_predicted_class="BENIGN",
        llm_confidence=0.92,
        ml_result=ML_RESULT,
        evidence_store=EVIDENCE,
        tools_called=TOOLS,
    )
    failed = {c["check"] for c in result["checks"] if not c["passed"]}
    assert "ml_label_not_overridden" in failed
    assert result["passed"] is False


def test_hallucinated_number_flagged():
    result = verify_grounding(
        narrative="DDoS attack involving 12345 bot IPs was observed.",
        llm_predicted_class="DDoS",
        llm_confidence=0.92,
        ml_result=ML_RESULT,
        evidence_store=EVIDENCE,
        tools_called=TOOLS,
    )
    assert "12345" in result["ungrounded_numbers"]
    assert result["passed"] is False


def test_signed_evidence_values_are_grounded():
    # Analysts quote "-0.58 SHAP" while evidence stores the signed float;
    # magnitude matching must ground it (live-eval regression, 2026-10-26).
    evidence = dict(EVIDENCE)
    evidence["explain_flow"] = {"shap_values": [-0.583, 4.52], "feature_values": [-0.685]}
    result = verify_grounding(
        narrative="Primary driver is ACK Flag Count (SHAP +4.52, standardized value -0.685); "
                  "Flow Duration contributes -0.58 SHAP.",
        llm_predicted_class="DDoS",
        llm_confidence=0.92,
        ml_result=ML_RESULT,
        evidence_store=evidence,
        tools_called=TOOLS + ["explain_flow"],
    )
    assert result["ungrounded_numbers"] == []


def test_fake_tool_reference_flagged():
    result = verify_grounding(
        narrative="pcap_downloader confirmed the payload.",
        llm_predicted_class="DDoS",
        llm_confidence=0.92,
        ml_result=ML_RESULT,
        evidence_store=EVIDENCE,
        tools_called=TOOLS,
    )
    failed = {c["check"] for c in result["checks"] if not c["passed"]}
    # Only real tool names are detected; freeform fake names are not a
    # grounding failure, but references to uncalled REAL tools are.
    assert "tool_references_valid" not in failed

    result2 = verify_grounding(
        narrative="explain_flow showed the top features.",
        llm_predicted_class="DDoS",
        llm_confidence=0.92,
        ml_result=ML_RESULT,
        evidence_store=EVIDENCE,
        tools_called=TOOLS,
    )
    failed2 = {c["check"] for c in result2["checks"] if not c["passed"]}
    assert "tool_references_valid" in failed2
