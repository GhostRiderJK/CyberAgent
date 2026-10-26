"""Tests for JSON extraction from padded / truncated LLM replies."""
import pytest

from cyberagent.llm import LLMClient, LLMError


def test_plain_json():
    assert LLMClient._extract_json('{"a": 1, "b": [1,2,3]}') == {"a": 1, "b": [1, 2, 3]}


def test_fenced_json():
    assert LLMClient._extract_json('```json\n{"tool": "explain_flow", "args": {"x": 1}}\n```') == {
        "tool": "explain_flow", "args": {"x": 1}}


def test_padded_json():
    assert LLMClient._extract_json('Here is my choice: {"tool": "x"} hope that helps') == {"tool": "x"}


def test_truncated_inside_array_string_recovers_earlier_keys():
    text = '{"summary": "benign flow", "actions": ["monitor", "c'
    out = LLMClient._extract_json(text)
    assert out == {"summary": "benign flow"}


def test_truncated_first_string_raises():
    with pytest.raises(LLMError):
        LLMClient._extract_json('{"summary": "benign long text truncat')


def test_no_json_raises():
    with pytest.raises(LLMError):
        LLMClient._extract_json('The user wants me to investigate flow_id = 1 ...')
