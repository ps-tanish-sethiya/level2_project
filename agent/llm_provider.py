"""
LLM Provider Layer with Gemini 2.5 Flash as Primary and Groq Llama-3.3-70b as Fallback.
Provides transparent failover on 429, timeout, 5xx, or network errors with response normalization.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("devsentinel.agent.llm_provider")


class LLMToolCall(BaseModel):
    id: str = Field(..., description="Call identifier")
    name: str = Field(..., description="Name of tool to call")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for tool call")


class LLMResponse(BaseModel):
    content: Optional[str] = Field(None, description="Natural language response text")
    tool_calls: List[LLMToolCall] = Field(default_factory=list, description="Requested tool calls")
    provider_used: str = Field(..., description="Provider that processed the request ('gemini' or 'groq')")
    error: Optional[str] = Field(None, description="Error message if all providers failed")


class DualLLMProvider:
    """
    Dual-provider LLM manager handling transparent failover between Gemini and Groq.
    """
    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds
        self.gemini_key = os.getenv("GOOGLE_API_KEY", "")
        self.groq_key = os.getenv("GROQ_API_KEY", "")

    def _convert_tools_to_gemini(self, mcp_tools: List[Dict[str, Any]]) -> List[Any]:
        """Convert standard MCP tool dicts to Gemini declaration format."""
        declarations = []
        for t in mcp_tools:
            declarations.append({
                "name": t.get("name"),
                "description": t.get("description", ""),
                "parameters": t.get("parameters") or t.get("inputSchema") or {"type": "object", "properties": {}}
            })
        return declarations

    def _convert_tools_to_groq(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert standard MCP tool dicts to OpenAI/Groq function format."""
        groq_tools = []
        for t in mcp_tools:
            groq_tools.append({
                "type": "function",
                "function": {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters") or t.get("inputSchema") or {"type": "object", "properties": {}}
                }
            })
        return groq_tools

    def _call_gemini(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        import google.generativeai as genai
        
        if not self.gemini_key or self.gemini_key.startswith("your_"):
            raise ValueError("GOOGLE_API_KEY is not configured")
            
        genai.configure(api_key=self.gemini_key)
        gemini_tools = self._convert_tools_to_gemini(tools) if tools else None
        
        # Build model with system instruction if first message is system prompt
        system_instruction = None
        history = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role in ("user", "human"):
                history.append({"role": "user", "parts": [content]})
            elif role in ("assistant", "model"):
                parts = [content] if content else []
                # If assistant requested tool calls in previous history
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        parts.append({"function_call": {"name": tc["name"], "args": tc.get("args", {})}})
                history.append({"role": "model", "parts": parts})
            elif role == "tool":
                tool_name = msg.get("name", "tool")
                result_content = str(msg.get("content", ""))
                history.append({"role": "function", "parts": [{"function_response": {"name": tool_name, "response": {"result": result_content}}}]})

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction,
            tools=gemini_tools
        )

        # Call model with timeout safety
        start_time = time.time()
        response = model.generate_content(history)
        
        if time.time() - start_time > self.timeout_seconds:
            raise TimeoutError(f"Gemini API call exceeded timeout threshold of {self.timeout_seconds}s")
            
        # Parse Gemini response
        tool_calls = []
        text_content = ""
        
        candidate = response.candidates[0]
        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                text_content += part.text
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                args_dict = dict(fc.args) if fc.args else {}
                tool_calls.append(LLMToolCall(
                    id=f"call_gemini_{fc.name}_{int(time.time()*1000)}",
                    name=fc.name,
                    args=args_dict
                ))
                
        return LLMResponse(
            content=text_content if text_content else None,
            tool_calls=tool_calls,
            provider_used="gemini",
            error=None
        )

    def _call_groq(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        from groq import Groq
        import json
        
        if not self.groq_key or self.groq_key.startswith("your_"):
            raise ValueError("GROQ_API_KEY is not configured")
            
        client = Groq(api_key=self.groq_key, timeout=self.timeout_seconds)
        groq_tools = self._convert_tools_to_groq(tools) if tools else None
        
        # Prepare OpenAI/Groq messages format
        formatted_messages = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role in ("system", "user", "assistant"):
                formatted_messages.append({"role": role, "content": content or ""})
            elif role == "tool":
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", "call_1"),
                    "content": str(m.get("content", ""))
                })
                
        kwargs: Dict[str, Any] = {
            "model": "llama-3.3-70b-versatile",
            "messages": formatted_messages,
        }
        if groq_tools:
            kwargs["tools"] = groq_tools
            kwargs["tool_choice"] = "auto"
            
        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message
        
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                fn = tc.function
                try:
                    args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else fn.arguments
                except Exception:
                    args = {}
                tool_calls.append(LLMToolCall(
                    id=tc.id or f"call_groq_{fn.name}",
                    name=fn.name,
                    args=args or {}
                ))
                
        return LLMResponse(
            content=msg.content if msg.content else None,
            tool_calls=tool_calls,
            provider_used="groq",
            error=None
        )

    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> LLMResponse:
        """
        Execute chat query with Gemini primary and Groq fallback.
        """
        gemini_error_msg = None
        # Step 1: Attempt Gemini primary
        try:
            logger.info("Attempting primary LLM provider: Google Gemini (gemini-2.5-flash)...")
            res = self._call_gemini(messages=messages, tools=tools)
            logger.info("Call processed successfully by primary provider: Google Gemini")
            return res
        except Exception as gemini_err:
            gemini_error_msg = str(gemini_err)
            logger.warning(f"Primary provider (Gemini) failed: {gemini_err}. Initiating fallback to Groq...")

        # Step 2: Attempt Groq fallback
        try:
            logger.info("Attempting fallback LLM provider: Groq (llama-3.3-70b-versatile)...")
            res = self._call_groq(messages=messages, tools=tools)
            logger.info("Call processed successfully by fallback provider: Groq (llama-3.3-70b-versatile)")
            return res
        except Exception as groq_err:
            logger.error(f"Fallback provider (Groq) also failed: {groq_err}")
            return LLMResponse(
                content=None,
                tool_calls=[],
                provider_used="none",
                error=f"Both LLM providers failed. Gemini: {gemini_error_msg} | Groq: {str(groq_err)}"
            )
