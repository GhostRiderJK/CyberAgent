"""
Investigation agent for CyberAgent.
LLM-driven agent loop: the model chooses which investigation tools to call,
the deterministic tools gather evidence, and a grounding verifier audits the
final report against that evidence. The LLM never labels traffic - the ML
prediction is authoritative and cannot be overridden.
"""
import time
import json
import inspect
from typing import Dict, Any, List, Optional, Tuple, Union
from cyberagent.investigation import (
    predict_proba,
    explain_flow,
    find_related_flows,
    similar_known_attacks,
    lookup_attack_pattern
)
from cyberagent.logging_setup import logger
from cyberagent.llm import get_llm, LLMError
from cyberagent.agent.grounding import verify_grounding

# Maximum tool calls per event as per requirements
MAX_TOOL_CALLS = 6

# Tool definitions for validation
AVAILABLE_TOOLS = {
    'predict_proba': predict_proba,
    'explain_flow': explain_flow,
    'find_related_flows': find_related_flows,
    'similar_known_attacks': similar_known_attacks,
    'lookup_attack_pattern': lookup_attack_pattern
}

TOOL_DOCS = """Available tools (call at most one per step):
- explain_flow(flow_id): top contributing features for this flow.
- find_related_flows(flow_id, time_window_minutes): flows near this one in time/space.
- similar_known_attacks(flow_id, k): closest labelled attack exemplars.
- lookup_attack_pattern(label): MITRE ATT&CK description for a class.
Respond with ONE JSON object, no prose:
  {"thought": "...", "tool": "<tool name>", "args": {...}}
or when the evidence is sufficient:
  {"thought": "...", "tool": null, "args": {}}
flow_id is fixed to the value given; the ML prediction shown is authoritative."""

FALLBACK_PLAN = ['explain_flow', 'find_related_flows', 'similar_known_attacks', 'lookup_attack_pattern']

class InvestigationAgent:
    """
    Controlled agent loop: LLM-planned tool use over deterministic tools,
    with a fixed fallback plan when no LLM backend is configured.
    """

    def __init__(self):
        self.tool_call_history: List[Dict[str, Any]] = []
        self.investigation_results: Dict[str, Any] = {}
        self.start_time: Optional[float] = None
        self._on_event: Optional[callable] = None

    # ---- LLM-driven tool selection ----------------------------------------

    def _normalize_args(self, tool: str, flow_id, ml_result: Dict[str, Any], raw_args: Dict[str, Any]) -> Dict[str, Any]:
        """Force flow_id/label to trusted values and sanitize LLM-supplied kwargs."""
        norm = dict(raw_args)
        if tool == 'lookup_attack_pattern':
            norm = {'label': ml_result.get('predicted_class', 'BENIGN')}
        else:
            norm['flow_id'] = flow_id
        if tool == 'find_related_flows':
            norm.setdefault('time_window_minutes', 30)
        if tool == 'similar_known_attacks':
            norm.setdefault('k', 5)
        try:
            sig = inspect.signature(AVAILABLE_TOOLS[tool])
            norm = {k: v for k, v in norm.items() if k in sig.parameters}
        except (TypeError, ValueError):
            pass
        return norm

    def _select_next_tool(self, flow_id: Union[int, str], ml_result: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Ask the LLM which tool to call next. None means done or LLM unavailable."""
        llm = get_llm()
        if not llm.available:
            return None
        done_tools = [c['tool'] for c in self.tool_call_history]
        messages = [
            {"role": "system", "content": "You are a network-security investigation planner. "
                                          "Never invent labels or numbers; only gather evidence with the tools. "
                                          + TOOL_DOCS},
            {"role": "user", "content": f"flow_id = {flow_id}\n"
                                        f"ML prediction (authoritative): {json.dumps({k: ml_result[k] for k in ('predicted_class', 'confidence') if k in ml_result})}\n"
                                        f"Tools already called: {done_tools}\n"
                                        f"Tool calls remaining: {MAX_TOOL_CALLS - len(self.tool_call_history)}\n"
                                        f"Choose the next most informative uncalled tool, or null if evidence suffices."},
        ]
        try:
            reply = llm.chat_json(messages, max_tokens=4000)
        except LLMError as e:
            logger.warning(f"LLM tool selection failed, falling back to plan: {e}")
            return None

        tool = reply.get("tool")
        if not tool or tool not in AVAILABLE_TOOLS or tool == 'predict_proba' or tool in done_tools:
            return None
        args = self._normalize_args(tool, flow_id, ml_result, reply.get("args") or {})
        logger.info(f"LLM chose tool {tool} (thought: {str(reply.get('thought'))[:120]})")
        return tool, args

    def _safe_call(self, tool: str, flow_id, ml_result: Dict[str, Any], raw_args: Optional[Dict[str, Any]] = None) -> None:
        kwargs = self._normalize_args(tool, flow_id, ml_result, raw_args or {})
        try:
            result = AVAILABLE_TOOLS[tool](**kwargs)
            self._record_tool_call(tool, kwargs, result)
            self.investigation_results[tool] = result
            logger.info(f"Tool {tool} returned result")
            if self._on_event:
                self._on_event({"event": "tool_call", "tool": tool,
                                "kwargs": {k: str(v) for k, v in kwargs.items()},
                                "status": "completed", "timestamp": time.time()})
        except Exception as e:
            logger.error(f"Error calling tool {tool}: {e}")
            self.investigation_results.setdefault('tool_errors', {})[tool] = str(e)
            if self._on_event:
                self._on_event({"event": "tool_call", "tool": tool,
                                "kwargs": {k: str(v) for k, v in kwargs.items()},
                                "status": "failed", "timestamp": time.time()})

    def get_tool_call_events(self) -> List[Dict[str, Any]]:
        """Structured timeline of tool calls for UI progress display."""
        return [
            {
                "event": "tool_call",
                "tool": c["tool"],
                "kwargs": {k: str(v) for k, v in c["kwargs"].items()},
                "status": "completed",
                "timestamp": c["timestamp"],
            }
            for c in self.tool_call_history
        ]

    def _run_fallback_plan(self, flow_id, ml_result: Dict[str, Any]) -> None:
        """Deterministic investigation plan used without an LLM backend."""
        for tool in FALLBACK_PLAN:
            if len(self.tool_call_history) >= MAX_TOOL_CALLS:
                break
            self._safe_call(tool, flow_id, ml_result)
            if self._should_stop_early():
                break

    def investigate_flow(self, flow_id: Union[int, str],
                         on_event: Optional[callable] = None) -> Dict[str, Any]:
        """
        Main investigation loop for a given flow.

        Args:
            flow_id: The flow ID to investigate
            on_event: optional callback receiving {'event':'tool_call',...} dicts

        Returns:
            Investigation result following the Pydantic schema
        """
        self.start_time = time.time()
        self.tool_call_history = []
        self.investigation_results = {}
        self._on_event = on_event

        logger.info(f"Starting investigation for flow_id: {flow_id}")

        # Step 1: Get initial ML prediction (always authoritative)
        try:
            ml_result = predict_proba(flow_id)
            self._record_tool_call('predict_proba', {'flow_id': flow_id}, ml_result)
            self.investigation_results['ml_prediction'] = ml_result
        except Exception as e:
            logger.error(f"Failed to get ML prediction for flow {flow_id}: {e}")
            # Return a basic error result
            return self._create_error_result(flow_id, str(e))

        # Step 2: Evidence gathering - LLM-planned when configured, else fixed plan
        llm = get_llm()
        if llm.available:
            attempts = 0
            while len(self.tool_call_history) < MAX_TOOL_CALLS and attempts < MAX_TOOL_CALLS + 2:
                attempts += 1
                choice = self._select_next_tool(flow_id, ml_result)
                if choice is None:
                    break
                tool, kwargs = choice
                if self._is_repeat_call(tool, kwargs):
                    continue
                self._safe_call(tool, flow_id, ml_result, kwargs)
            if len(self.tool_call_history) < 2:
                logger.warning("LLM gathered too little evidence; completing with deterministic plan")
                self._run_fallback_plan(flow_id, ml_result)
        else:
            logger.info("No LLM backend configured (mock); using deterministic investigation plan")
            self._run_fallback_plan(flow_id, ml_result)

        # Step 3: Synthesize final verdict (with LLM report + grounding audit)
        verdict = self._synthesize_verdict(flow_id)

        logger.info(f"Investigation completed for flow {flow_id} in {time.time() - self.start_time:.2f}s")
        return verdict

    # ---- LLM report generation -------------------------------------------

    def _narrative_from_llm(self, ml_pred: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ask the LLM for an analyst report; None when no backend is configured."""
        llm = get_llm()
        if not llm.available:
            return None
        compact = {k: v for k, v in self.investigation_results.items() if k != 'ml_prediction'}
        messages = [
            {"role": "system", "content": "You are a SOC analyst. Write an investigation report "
                                          "strictly from the evidence JSON given. Do not change the ML label. "
                                          "Use only numbers present in the evidence. Reply with ONE JSON object: "
                                          "{\"summary\": str, \"severity\": \"Low|Medium|High\", "
                                          "\"recommended_actions\": [str]}"},
            {"role": "user", "content": json.dumps({"ml_prediction": {
                "predicted_class": ml_pred.get('predicted_class'),
                "confidence": ml_pred.get('confidence')},
                "evidence": compact}, default=str)[:6000]},
        ]
        try:
            return llm.chat_json(messages, max_tokens=8000)
        except LLMError as e:
            logger.warning(f"LLM report generation failed: {e}")
            return None

    def _create_error_result(self, flow_id: Union[int, str], error: str) -> Dict[str, Any]:
        """Create an error result when investigation cannot proceed."""
        return {
            'verdict': f"Investigation failed: {error}",
            'predicted_class': 'UNKNOWN',
            'severity': 'Unknown',
            'confidence': 0.0,
            'needs_human_review': True,
            'evidence': [],
            'mitre_technique': 'Not available',
            'recommended_actions': ['Check flow ID and retry', 'Contact system administrator'],
            'limitations': [f"Initial error: {error}"]
        }

    def _record_tool_call(self, tool_name: str, kwargs: Dict[str, Any], result: Any) -> None:
        """Record a tool call for history and repeat prevention."""
        call_record = {
            'tool': tool_name,
            'kwargs': kwargs.copy(),
            'result': result,
            'timestamp': time.time()
        }
        self.tool_call_history.append(call_record)

    def _is_repeat_call(self, tool_name: str, kwargs: Dict[str, Any]) -> bool:
        """Check if we've already called this tool with the same arguments."""
        for call in self.tool_call_history:
            if call['tool'] == tool_name and call['kwargs'] == kwargs:
                return True
        return False

    def _should_stop_early(self) -> bool:
        """
        Determine if we have enough information to stop the investigation early.
        In a real implementation, this would be based on LLM judgment.
        For now, we use a simple heuristic: if we have an explanation and related flows, we might stop.
        """
        # Simple heuristic: stop if we have both explanation and related flows
        has_explanation = 'explain_flow' in self.investigation_results
        has_related = 'find_related_flows' in self.investigation_results
        return has_explanation and has_related

    def _synthesize_verdict(self, flow_id: Union[int, str]) -> Dict[str, Any]:
        """
        Synthesize the final investigation verdict from all collected information.

        Returns:
            Dictionary following the Pydantic schema:
            {
                "verdict": "...",
                "predicted_class": "...",
                "severity": "...",
                "confidence": 0.0,
                "needs_human_review": true,
                "evidence": [],
                "mitre_technique": "...",
                "recommended_actions": [],
                "limitations": []
            }
        """
        # Start with the ML prediction as base
        ml_pred = self.investigation_results.get('ml_prediction', {})
        predicted_class = ml_pred.get('predicted_class', 'UNKNOWN')
        confidence = ml_pred.get('confidence', 0.0)

        # Determine severity based on class and confidence
        severity = self._determine_severity(predicted_class, confidence)

        # Determine if human review is needed
        needs_human_review = self._determine_needs_human_review(predicted_class, confidence)

        # Collect evidence from tool calls
        evidence = self._collect_evidence()

        # Determine MITRE technique
        mitre_technique = self._determine_mitre_technique(predicted_class)

        # Generate recommended actions
        recommended_actions = self._generate_recommended_actions(predicted_class, severity, needs_human_review)

        # Determine limitations
        limitations = self._determine_limitations()

        # Overall verdict (could be more sophisticated)
        verdict = self._determine_overall_verdict(predicted_class, confidence, evidence)

        # LLM analyst report, audited by the grounding verifier before it is trusted
        grounding = {"passed": True, "checks": [
            {"check": "llm_not_used", "passed": True,
             "detail": "No LLM backend: verdict built from deterministic tool evidence only"}
        ], "ungrounded_numbers": []}

        report = self._narrative_from_llm(ml_pred)
        if report:
            narrative = str(report.get('summary', ''))
            grounding = verify_grounding(
                narrative=narrative,
                llm_predicted_class=predicted_class,
                llm_confidence=confidence,
                ml_result=ml_pred,
                evidence_store=dict(self.investigation_results),
                tools_called=[c['tool'] for c in self.tool_call_history],
            )
            if narrative:
                verdict = f"{verdict} | Analyst report: {narrative}"
            if report.get('severity') in ('Low', 'Medium', 'High'):
                severity = report['severity']
            if isinstance(report.get('recommended_actions'), list) and report['recommended_actions']:
                recommended_actions = [str(a) for a in report['recommended_actions']][:5]
            if not grounding['passed']:
                needs_human_review = True
                bad = [c['detail'] for c in grounding['checks'] if not c['passed']]
                limitations.append(f"Grounding verifier failed: {'; '.join(bad)}")

        result = {
            'verdict': verdict,
            'predicted_class': predicted_class,
            'severity': severity,
            'confidence': confidence,
            'needs_human_review': needs_human_review,
            'evidence': evidence,
            'mitre_technique': mitre_technique,
            'recommended_actions': recommended_actions,
            'limitations': limitations,
            'grounding_check': grounding,
            'tool_call_events': self.get_tool_call_events()
        }

        return result

    def _determine_severity(self, predicted_class: str, confidence: float) -> str:
        """Determize severity based on predicted class and confidence."""
        # Map from config or use defaults
        severity_map = {
            'BENIGN': 'Low',
            'Bot': 'High',
            'DDoS': 'High',
            'DoS GoldenEye': 'High',
            'DoS Hulk': 'High',
            'DoS Slowhttptest': 'Medium',
            'DoS slowloris': 'Medium',
            'FTP-Patator': 'Medium',
            'PortScan': 'Low',
            'SSH-Patator': 'Medium',
            'Web Attack': 'High',
            'Infiltration': 'High',
            'Heartbleed': 'High'
        }

        base_severity = severity_map.get(predicted_class, 'Medium')
        # Adjust based on confidence - low confidence might reduce severity
        if confidence < 0.7:
            if base_severity == 'High':
                return 'Medium'
            elif base_severity == 'Medium':
                return 'Low'
        return base_severity

    def _determine_needs_human_review(self, predicted_class: str, confidence: float) -> bool:
        """Determine if human review is needed."""
        # Always review if confidence is low
        if confidence < 0.6:
            return True
        # Review for certain high-impact classes regardless of confidence
        high_impact = ['Bot', 'DDoS', 'Infiltration', 'Heartbleed', 'Web Attack']
        if predicted_class in high_impact:
            return True
        # Review if we had tool call errors or incomplete information
        if len(self.tool_call_history) < 2:  # We didn't get to run enough tools
            return True
        return False

    def _collect_evidence(self) -> List[Dict[str, Any]]:
        """Collect evidence from tool calls for the final verdict."""
        evidence = []

        for call in self.tool_call_history:
            tool_name = call['tool']
            result = call['result']

            if tool_name == 'predict_proba':
                evidence.append({
                    'source_tool': 'predict_proba',
                    'source_value': f"Predicted class: {result.get('predicted_class')} with confidence {result.get('confidence'):.3f}"
                })
            elif tool_name == 'explain_flow':
                # Extract top features from explanation
                top_features = result.get('top_features', [])
                if top_features:
                    top_feat = top_features[0]
                    evidence.append({
                        'source_tool': 'explain_flow',
                        'source_value': f"Top feature: {top_feat.get('feature')} (SHAP: {top_feat.get('shap_value'):.3f})"
                    })
            elif tool_name == 'find_related_flows':
                count = len(result) if isinstance(result, list) else 0
                evidence.append({
                    'source_tool': 'find_related_flows',
                    'source_value': f"Found {count} related flows"
                })
            elif tool_name == 'similar_known_attacks':
                count = len(result) if isinstance(result, list) else 0
                evidence.append({
                    'source_tool': 'similar_known_attacks',
                    'source_value': f"Found {count} similar known attacks"
                })
            elif tool_name == 'lookup_attack_pattern':
                desc = result.get('description', 'No description')
                evidence.append({
                    'source_tool': 'lookup_attack_pattern',
                    'source_value': f"Attack pattern: {desc}"
                })

        return evidence

    def _determine_mitre_technique(self, predicted_class: str) -> str:
        """Determine MITRE technique based on predicted class."""
        mitre_map = {
            'BENIGN': 'None',
            'Bot': 'T1059.003',
            'DDoS': 'T1498',
            'DoS GoldenEye': 'T1498',
            'DoS Hulk': 'T1498',
            'DoS Slowhttptest': 'T1498',
            'DoS slowloris': 'T1498',
            'FTP-Patator': 'T1021.001',
            'PortScan': 'T1046',
            'SSH-Patator': 'T1021.004',
            'Web Attack': 'T1190',
            'Infiltration': 'T1071',
            'Heartbleed': 'T1190'
        }
        return mitre_map.get(predicted_class, 'Not available')

    def _generate_recommended_actions(self, predicted_class: str, severity: str, needs_human_review: bool) -> List[str]:
        """Generate recommended actions based on investigation results."""
        actions = []

        if needs_human_review:
            actions.append("Escalate to human analyst for review")

        if predicted_class != 'BENIGN':
            actions.append(f"Block traffic associated with {predicted_class} patterns")
            actions.append("Collect additional forensic evidence")

        if severity in ['High', 'Medium']:
            actions.append("Increase monitoring for similar traffic patterns")

        # Add generic actions
        actions.append("Document incident for future reference")
        actions.append("Update intrusion detection signatures if applicable")

        return actions[:5]  # Limit to top 5 actions

    def _determine_limitations(self) -> List[str]:
        """Determine limitations of the investigation."""
        limitations = []

        if len(self.tool_call_history) < MAX_TOOL_CALLS:
            limitations.append(f"Investigation stopped early after {len(self.tool_call_history)} tool calls")

        if self.tool_call_history:
            errors = self.investigation_results.get('tool_errors', {})
            if errors:
                limitations.append(f"Encountered {len(errors)} tool execution errors: {', '.join(errors)}")

        # Add general limitations
        limitations.append("Limited to predefined tool set")
        limitations.append("Dependent on quality and completeness of training data")
        limitations.append("MITRE mapping is based on simplified heuristics")

        return limitations

    def _determine_overall_verdict(self, predicted_class: str, confidence: float, evidence: List[Dict[str, Any]]) -> str:
        """Determine the overall verdict string."""
        if predicted_class == 'BENIGN':
            if confidence > 0.9:
                return "Benign traffic - no threat detected"
            else:
                return "Likely benign traffic - low confidence prediction"
        else:
            if confidence > 0.9:
                return f"Malicious traffic detected: {predicted_class}"
            else:
                return f"Suspicious traffic detected: {predicted_class} (requires further investigation)"

# Convenience function for external use
def investigate_flow(flow_id: Union[int, str], on_event: Optional[callable] = None) -> Dict[str, Any]:
    """
    Convenience function to investigate a flow.

    Args:
        flow_id: The flow ID to investigate
        on_event: optional live progress callback for tool calls

    Returns:
        Investigation result following the Pydantic schema
    """
    agent = InvestigationAgent()
    return agent.investigate_flow(flow_id, on_event=on_event)

if __name__ == "__main__":
    # Simple test
    logger.info("Testing investigation agent...")
    try:
        # Test with a sample flow ID (assuming flow IDs start from 0)
        test_flow_id = 0
        print(f"Testing investigation agent for flow {test_flow_id}:")
        result = investigate_flow(test_flow_id)
        print(f"Verdict: {result.get('verdict')}")
        print(f"Predicted class: {result.get('predicted_class')}")
        print(f"Confidence: {result.get('confidence'):.4f}")
        print(f"Severity: {result.get('severity')}")
        print(f"Needs human review: {result.get('needs_human_review')}")
        print(f"Evidence count: {len(result.get('evidence', []))}")
        print(f"MITRE technique: {result.get('mitre_technique')}")
        print(f"Recommended actions: {len(result.get('recommended_actions', []))}")
        print(f"Limitations: {len(result.get('limitations', []))}")
        print("Investigation agent test completed successfully!")
    except Exception as e:
        logger.error(f"Error in investigation agent test: {e}")
        print(f"Test failed with error: {e}")