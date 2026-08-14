"""
ReAct (Reason -> Act -> Observe) Agent Engine for DevSentinel.
Coordinates LLM provider, MCP client tools, and human-in-the-loop safeguards.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

from agent.llm_provider import DualLLMProvider, LLMResponse
from agent.mcp_client import MCPClientWrapper
from agent.system_prompt import SYSTEM_PROMPT

logger = logging.getLogger("devsentinel.agent.engine")


class AgentStepLog(BaseModel):
    step_number: int
    thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    provider_used: str = "gemini"


class AgentRunResult(BaseModel):
    query: str
    final_answer: str
    steps: List[AgentStepLog] = Field(default_factory=list)
    total_tool_calls: int = 0
    provider_used: str = "gemini"
    capped: bool = False
    pending_incident_write: Optional[Dict[str, Any]] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    tokens_per_second: float = 0.0
    execution_time_seconds: float = 0.0


class DevSentinelAgent:
    """
    Goal-oriented ReAct Agent managing diagnosis trajectory and MCP tool invocations.
    """
    def __init__(self, max_iterations: int = 8):
        self.max_iterations = max_iterations
        self.llm = DualLLMProvider()
        self.mcp = MCPClientWrapper()

    def run(
        self,
        query: str,
        confirm_callback: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> AgentRunResult:
        """
        Execute ReAct loop for a natural language diagnosis query.
        
        Args:
            query: User's diagnosis prompt.
            confirm_callback: Optional callable for human confirmation on state-changing actions.
            
        Returns:
            AgentRunResult containing synthesized diagnosis and step-by-step trace.
        """
        import time
        t0 = time.time()
        logger.info(f"=== Starting Agent Trajectory for Query: '{query}' ===")
        
        available_tools = self.mcp.list_tools()
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ]
        
        steps: List[AgentStepLog] = []
        providers_used_set = set()
        pending_write = None
        
        accumulated_prompt_tokens = 0
        accumulated_completion_tokens = 0
        accumulated_total_tokens = 0
        accumulated_cost_usd = 0.0
        
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"--- ReAct Loop Iteration {iteration}/{self.max_iterations} ---")
            
            # Step 1: Call LLM provider layer
            llm_response: LLMResponse = self.llm.chat(messages=messages, tools=available_tools)
            
            accumulated_prompt_tokens += llm_response.prompt_tokens
            accumulated_completion_tokens += llm_response.completion_tokens
            accumulated_total_tokens += llm_response.total_tokens
            accumulated_cost_usd += llm_response.cost_usd
            
            if llm_response.provider_used != "none":
                providers_used_set.add(llm_response.provider_used)
                
            if llm_response.error:
                error_msg = f"Agent halted: {llm_response.error}"
                logger.error(error_msg)
                elapsed = time.time() - t0
                return AgentRunResult(
                    query=query,
                    final_answer=error_msg,
                    steps=steps,
                    total_tool_calls=len(steps),
                    provider_used="none",
                    capped=False,
                    prompt_tokens=accumulated_prompt_tokens,
                    completion_tokens=accumulated_completion_tokens,
                    total_tokens=accumulated_total_tokens,
                    total_cost_usd=round(accumulated_cost_usd, 7),
                    tokens_per_second=round(accumulated_completion_tokens / max(0.01, elapsed), 2),
                    execution_time_seconds=round(elapsed, 2)
                )

            # Check if LLM produced final text answer without requesting further tool calls
            if not llm_response.tool_calls:
                final_text = llm_response.content or "Diagnosis completed (no specific recommendations produced)."
                logger.info(f"Agent produced final synthesized answer at iteration {iteration}.")
                
                primary_provider = list(providers_used_set)[0] if providers_used_set else "gemini"
                elapsed = time.time() - t0
                tps = round(accumulated_completion_tokens / max(0.01, elapsed), 2)
                
                return AgentRunResult(
                    query=query,
                    final_answer=final_text,
                    steps=steps,
                    total_tool_calls=len(steps),
                    provider_used=primary_provider,
                    capped=False,
                    pending_incident_write=pending_write,
                    prompt_tokens=accumulated_prompt_tokens,
                    completion_tokens=accumulated_completion_tokens,
                    total_tokens=accumulated_total_tokens,
                    total_cost_usd=round(accumulated_cost_usd, 7),
                    tokens_per_second=tps,
                    execution_time_seconds=round(elapsed, 2)
                )

            # Step 2: Execute requested tool calls
            assistant_content = llm_response.content or ""
            
            # Record assistant turn in messages history for context retention
            messages.append({
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "args": tc.args}
                    for tc in llm_response.tool_calls
                ],
                "raw_gemini_content": getattr(llm_response, "raw_gemini_content", None)
            })

            from concurrent.futures import ThreadPoolExecutor

            def _exec_single_tool(tc):
                tool_name = tc.name
                tool_args = tc.args
                
                if tool_name == "log_new_incident":
                    if confirm_callback is not None:
                        logger.info("Triggering Human-in-the-Loop approval prompt for log_new_incident...")
                        approved = confirm_callback(tool_args)
                        if not approved:
                            return tc, {
                                "success": False,
                                "message": "User denied confirmation to execute log_new_incident. Action aborted.",
                                "error": "User rejected write action"
                            }
                obs = self.mcp.call_tool(tool_name=tool_name, arguments=tool_args)
                return tc, obs

            with ThreadPoolExecutor(max_workers=min(len(llm_response.tool_calls), 5)) as executor:
                tool_results = list(executor.map(_exec_single_tool, llm_response.tool_calls))

            for tc, obs in tool_results:
                logger.info(f"Iteration {iteration}: Tool executed -> {tc.name}")
                steps.append(AgentStepLog(
                    step_number=iteration,
                    thought=assistant_content,
                    tool_name=tc.name,
                    tool_args=tc.args,
                    observation=obs,
                    provider_used=llm_response.provider_used
                ))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": json.dumps(obs)
                })
                
        # If iteration limit hit
        logger.warning(f"ReAct loop reached maximum allowed iterations ({self.max_iterations}). Formulating best partial answer.")
        primary_provider = list(providers_used_set)[0] if providers_used_set else "gemini"
        elapsed = time.time() - t0
        return AgentRunResult(
            query=query,
            final_answer="Agent reached maximum tool call iterations. Please review the partial diagnostic step logs.",
            steps=steps,
            total_tool_calls=len(steps),
            provider_used=primary_provider,
            capped=True,
            pending_incident_write=pending_write,
            prompt_tokens=accumulated_prompt_tokens,
            completion_tokens=accumulated_completion_tokens,
            total_tokens=accumulated_total_tokens,
            total_cost_usd=round(accumulated_cost_usd, 7),
            tokens_per_second=round(accumulated_completion_tokens / max(0.01, elapsed), 2),
            execution_time_seconds=round(elapsed, 2)
        )
