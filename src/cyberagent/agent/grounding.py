"""
Grounding verifier for agent investigation reports.

Every claim the LLM makes in its narrative must be traceable to evidence
produced by the deterministic tools. The verifier enforces:

  1. The ML label is never overridden (predicted_class must equal the
     predict_proba result).
  2. Reported confidence matches the ML confidence (within tolerance).
  3. Every number in the narrative appears somewhere in the structured
     evidence (counts, confidences, ports, timings) - tolerance-matched.
  4. The narrative only references tools that were actually called.
  5. Any IP address the narrative quotes is present in the evidence or in
     the stored flow record - an invented endpoint is the most damaging
     kind of hallucination in a SOC report.

Failed checks are listed in the result's `grounding_check` so a human
analyst sees exactly which claim could not be grounded.
"""
import json
import re
from typing import Any, Dict, List, Optional

# Numbers like 0.98, 445, 1,234, 30 (min), 12.5%
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?%?")
# IPv4 literals quoted in prose, e.g. "traffic from 172.16.0.1 to 192.168.10.50"
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Tool references in prose, e.g. "explain_flow showed..."
_TOOL_REF_RE = re.compile(r"\b(predict_proba|explain_flow|find_related_flows|similar_known_attacks|lookup_attack_pattern)\b")


def _collect_evidence_numbers(evidence_store: Dict[str, Any], found: List[float]) -> None:
    """Recursively harvest every numeric value the tools returned."""
    if isinstance(evidence_store, dict):
        for v in evidence_store.values():
            _collect_evidence_numbers(v, found)
    elif isinstance(evidence_store, (list, tuple)):
        for v in evidence_store:
            _collect_evidence_numbers(v, found)
    elif isinstance(evidence_store, bool):
        pass
    elif isinstance(evidence_store, (int, float)):
        found.append(float(evidence_store))
    elif isinstance(evidence_store, str):
        for m in _NUM_RE.findall(evidence_store):
            try:
                pct = m.endswith("%")
                val = float(m.rstrip("%").replace(",", ""))
                found.append(val)
                if pct:
                    found.append(val / 100.0)
            except ValueError:
                pass


def _numbers_match(num: float, pool: List[float], rel_tol: float = 0.02, abs_tol: float = 0.01) -> bool:
    return any(abs(num - p) <= max(abs_tol, rel_tol * abs(p)) for p in pool)


def verify_grounding(
    narrative: str,
    llm_predicted_class: str,
    llm_confidence: float,
    ml_result: Dict[str, Any],
    evidence_store: Dict[str, Any],
    tools_called: List[str],
    known_identifiers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run all grounding checks; return {'passed': bool, 'checks': [...], 'ungrounded_numbers': [...]}.
    """
    checks: List[Dict[str, Any]] = []
    ml_class = ml_result.get("predicted_class")
    ml_conf = float(ml_result.get("confidence", 0.0))

    checks.append({
        "check": "ml_label_not_overridden",
        "passed": str(llm_predicted_class) == str(ml_class),
        "detail": f"LLM said '{llm_predicted_class}', ML said '{ml_class}'",
    })
    checks.append({
        "check": "confidence_grounded",
        "passed": abs(float(llm_confidence) - ml_conf) <= 0.05,
        "detail": f"LLM confidence {llm_confidence}, ML confidence {ml_conf:.3f}",
    })

    pool: List[float] = []
    _collect_evidence_numbers(evidence_store, pool)
    # Analysts quote signed values ("-0.58 SHAP") while the regex captures
    # digits only; compare magnitudes so signs don't create false negatives.
    pool = [abs(p) for p in pool]
    ungrounded: List[str] = []
    for token in _NUM_RE.findall(narrative or ""):
        try:
            pct = token.endswith("%")
            num = abs(float(token.rstrip("%").replace(",", "")))
        except ValueError:
            continue
        # Small integers appear structurally (page counts, ranks); require a
        # match only when the number is distinctive enough to be a real claim.
        if num < 10 and num == int(num):
            continue
        # "92%" and "0.92" are the same claim in different unit forms.
        grounded = _numbers_match(num, pool) or (pct and _numbers_match(num / 100.0, pool))
        if not grounded:
            ungrounded.append(token)
    checks.append({
        "check": "numbers_grounded",
        "passed": len(ungrounded) == 0,
        "detail": f"Ungrounded numbers: {ungrounded}" if ungrounded else "All reported figures trace to tool evidence",
    })

    bogus_refs = sorted({t for t in _TOOL_REF_RE.findall(narrative or "") if t not in tools_called})
    checks.append({
        "check": "tool_references_valid",
        "passed": len(bogus_refs) == 0,
        "detail": f"References to tools never called: {bogus_refs}" if bogus_refs else "All tool references valid",
    })

    # IPs are grounded against the raw evidence text plus the stored flow record, so a
    # quoted endpoint that no tool ever returned is reported rather than trusted.
    haystack = json.dumps(evidence_store, default=str) + " " + " ".join(known_identifiers or [])
    cited_ips = sorted({ip for ip in _IPV4_RE.findall(narrative or "") if ip not in ("0.0.0.0",)})
    ungrounded_ips = [ip for ip in cited_ips if ip not in haystack]
    checks.append({
        "check": "identifiers_grounded",
        "passed": len(ungrounded_ips) == 0,
        "detail": (f"IP addresses not found in any evidence: {ungrounded_ips}" if ungrounded_ips
                   else (f"All {len(cited_ips)} quoted endpoint(s) appear in the evidence" if cited_ips
                         else "No endpoint addresses claimed")),
    })

    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "ungrounded_numbers": ungrounded,
    }
