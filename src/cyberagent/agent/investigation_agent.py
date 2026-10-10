"""
Investigation agent for CyberAgent.
Implements a controlled hand-written agent loop that uses investigation tools
to investigate ML-detected flows.
"""
import time
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from cyberagent.investigation import (
    predict_proba,
    explain_flow,
    find_related_flows,
    similar_known_attacks,
    lookup_attack_pattern
)
from cyberagent.logging_setup import logger

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

class InvestigationAgent:
    """
    Hand-written investigation agent loop.
    """

    def __init__(self):
        self.tool_call_history: List[Dict[str, Any]] = []
        self.investigation_results: Dict[str, Any] = {}
        self.start_time: Optional[float] = None

    def investigate_flow(self, flow_id: Union[int, str]) -> Dict[str, Any]:
        """
        Main investigation loop for a given flow.

        Args:
            flow_id: The flow ID to investigate

        Returns:
            Investigation result following the Pydantic schema
        """
        self.start_time = time.time()
        self.tool_call_history = []
        self.investigation_results = {}

        logger.info(f"Starting investigation for flow_id: {flow_id}")

        # Step 1: Get initial ML prediction
        try:
            ml_result = predict_proba(flow_id)
            self._record_tool_call('predict_proba', {'flow_id': flow_id}, ml_result)
            self.investigation_results['ml_prediction'] = ml_result
        except Exception as e:
            logger.error(f"Failed to get ML prediction for flow {flow_id}: {e}")
            # Return a basic error result
            return self._create_error_result(flow_id, str(e))

        # Step 2: Agent loop - decide which tools to call
        # In a real implementation, this would use an LLM to decide.
        # For now, we use a predefined sequence that demonstrates the capabilities.
        # The agent should not exceed MAX_TOOL_CALLS.

        # Define a simple investigation strategy (this would be LLM-driven in practice)
        investigation_plan = [
            ('explain_flow', {'flow_id': flow_id}),
            ('find_related_flows', {'flow_id': flow_id, 'time_window_minutes': 30}),
            ('similar_known_attacks', {'flow_id': flow_id, 'k': 5}),
            ('lookup_attack_pattern', {'label': ml_result.get('predicted_class', 'BENIGN')})
        ]

        # Execute the plan, but respect MAX_TOOL_CALLS and avoid repeats
        tool_index = 0
        while tool_index < len(investigation_plan) and len(self.tool_call_history) < MAX_TOOL_CALLS:
            tool_name, kwargs = investigation_plan[tool_index]

            # Check if we've already called this tool with the same arguments
            if self._is_repeat_call(tool_name, kwargs):
                logger.info(f"Skipping repeat call to {tool_name} with args {kwargs}")
                tool_index += 1
                continue

            try:
                # Call the tool
                tool_func = AVAILABLE_TOOLS[tool_name]
                result = tool_func(**kwargs)

                # Record the call
                self._record_tool_call(tool_name, kwargs, result)

                # Store result for later use
                self.investigation_results[tool_name] = result

                logger.info(f"Tool {tool_name} returned result for flow {flow_id}")

                # Check if we have enough information to make a verdict early
                # (This is a simplification - in reality, the LLM would decide when to stop)
                if self._should_stop_early():
                    break

            except Exception as e:
                logger.error(f"Error calling tool {tool_name} for flow {flow_id}: {e}")
                # Try once more with a fallback or continue to next tool
                # For now, we'll just continue to the next tool
                pass

            tool_index += 1

        # Step 3: Synthesize final verdict
        verdict = self._synthesize_verdict(flow_id)

        logger.info(f"Investigation completed for flow {flow_id} in {time.time() - self.start_time:.2f}s")
        return verdict

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

        result = {
            'verdict': verdict,
            'predicted_class': predicted_class,
            'severity': severity,
            'confidence': confidence,
            'needs_human_review': needs_human_review,
            'evidence': evidence,
            'mitre_technique': mitre_technique,
            'recommended_actions': recommended_actions,
            'limitations': limitations
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
            # Check if we had any errors
            error_count = sum(1 for call in self.tool_call_history if isinstance(call['result'], Exception))
            if error_count > 0:
                limitations.append(f"Encountered {error_count} tool execution errors")

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
def investigate_flow(flow_id: Union[int, str]) -> Dict[str, Any]:
    """
    Convenience function to investigate a flow.

    Args:
        flow_id: The flow ID to investigate

    Returns:
        Investigation result following the Pydantic schema
    """
    agent = InvestigationAgent()
    return agent.investigate_flow(flow_id)

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