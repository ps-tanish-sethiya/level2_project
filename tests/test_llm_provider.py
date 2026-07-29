"""
Unit tests for the LLM Provider layer, specifically validating the Gemini -> Groq failover logic.
"""

import pytest
from unittest.mock import patch, MagicMock

from agent.llm_provider import DualLLMProvider, LLMResponse, LLMToolCall


def test_gemini_primary_success():
    provider = DualLLMProvider()
    
    mock_gemini_resp = LLMResponse(
        content="Diagnosis: Everything looks normal.",
        tool_calls=[],
        provider_used="gemini",
        error=None
    )
    
    with patch.object(provider, "_call_gemini", return_value=mock_gemini_resp) as mock_gemini:
        res = provider.chat(
            messages=[{"role": "user", "content": "Check status"}],
            tools=[]
        )
        assert res.provider_used == "gemini"
        assert res.content == "Diagnosis: Everything looks normal."
        mock_gemini.assert_called_once()


def test_gemini_rate_limit_failover_to_groq():
    """
    Test explicit failover: Mock a Gemini 429 rate limit exception and assert the call
    transparently succeeds via Groq.
    """
    provider = DualLLMProvider()
    
    mock_groq_resp = LLMResponse(
        content="Groq fallback response: Recommend merging PR.",
        tool_calls=[],
        provider_used="groq",
        error=None
    )
    
    # Simulate Gemini failing with HTTP 429 Rate Limit error
    with patch.object(provider, "_call_gemini", side_effect=Exception("HTTP 429 Rate Limit Exceeded")) as mock_gemini:
        with patch.object(provider, "_call_groq", return_value=mock_groq_resp) as mock_groq:
            res = provider.chat(
                messages=[{"role": "user", "content": "Is this PR safe?"}],
                tools=[]
            )
            assert res.provider_used == "groq"
            assert "Groq fallback" in res.content
            mock_gemini.assert_called_once()
            mock_groq.assert_called_once()


def test_gemini_timeout_failover_to_groq():
    """
    Test explicit failover: Mock a Gemini timeout and assert the call falls back to Groq.
    """
    provider = DualLLMProvider()
    
    mock_groq_resp = LLMResponse(
        content="Groq fallback response after Gemini timeout.",
        tool_calls=[],
        provider_used="groq",
        error=None
    )
    
    with patch.object(provider, "_call_gemini", side_effect=TimeoutError("Gemini call timed out after 15s")) as mock_gemini:
        with patch.object(provider, "_call_groq", return_value=mock_groq_resp) as mock_groq:
            res = provider.chat(
                messages=[{"role": "user", "content": "Check logs"}],
                tools=[]
            )
            assert res.provider_used == "groq"
            mock_gemini.assert_called_once()
            mock_groq.assert_called_once()


def test_both_providers_fail():
    """
    Test graceful structured error return when both Gemini and Groq fail.
    """
    provider = DualLLMProvider()
    
    with patch.object(provider, "_call_gemini", side_effect=Exception("Gemini Down")):
        with patch.object(provider, "_call_groq", side_effect=Exception("Groq Down")):
            res = provider.chat(
                messages=[{"role": "user", "content": "Check status"}],
                tools=[]
            )
            assert res.provider_used == "none"
            assert res.error is not None
            assert "Both LLM providers failed" in res.error
