"""
DevOps AI Agent Benchmark & Evaluation Testbench
Evaluates DevSentinel Agent across:
1. Tool Call Selection Accuracy (%)
2. Average Execution Latency (seconds)
3. Task Completion Success Rate (%)
4. Provider Resilience & Fallback Handling
"""

import sys
import os
import time
import json
from typing import List, Dict, Any

# Ensure stdout and stderr handle UTF-8 safely on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.agent import DevSentinelAgent, AgentRunResult

# Benchmark Test Suite: Query, Expected Tool(s), Intent Category
BENCHMARK_SUITE = [
    {
        "id": "TC-01",
        "category": "Build Telemetry",
        "query": "Check the latest GitHub Actions build status for the repository",
        "expected_tools": ["get_build_status"]
    },
    {
        "id": "TC-02",
        "category": "Build Failure Diagnosis",
        "query": "What is issue in current repository?",
        "expected_tools": ["get_build_status"]
    },
    {
        "id": "TC-03",
        "category": "Code Quality Audit",
        "query": "check SonarCloud code quality for repository",
        "expected_tools": ["check_code_quality"]
    },
    {
        "id": "TC-04",
        "category": "Security Vulnerability Scan",
        "query": "Is PyYAML 5.1 safe to use or does it have CVE security flaws?",
        "expected_tools": ["check_dependency_vulnerabilities"]
    },
    {
        "id": "TC-05",
        "category": "Service Outage Lookup",
        "query": "Is GitHub API experiencing any system outage or degradation?",
        "expected_tools": ["check_service_status"]
    },
    {
        "id": "TC-06",
        "category": "Package Metadata Lookup",
        "query": "Get package version and license details for PyYAML on PyPI",
        "expected_tools": ["get_package_info"]
    },
    {
        "id": "TC-07",
        "category": "Knowledge Base Lookup",
        "query": "Search local knowledge base for AttributeError NoneType solutions",
        "expected_tools": ["search_error_kb"]
    },
    {
        "id": "TC-08",
        "category": "Incident History Lookup",
        "query": "Show past resolved incidents related to null shipping address",
        "expected_tools": ["get_past_incidents"]
    }
]


def run_evaluation_benchmark():
    print("================================================================================")
    print("           🛡️ DevOps AI Agent v2.0 - Evaluation Benchmark Testbench")
    print("================================================================================\n")
    
    agent = DevSentinelAgent(max_iterations=5)
    results = []
    
    total_queries = len(BENCHMARK_SUITE)
    correct_tool_calls = 0
    successful_runs = 0
    latencies: List[float] = []

    for test_case in BENCHMARK_SUITE:
        tc_id = test_case["id"]
        category = test_case["category"]
        query = test_case["query"]
        expected_tools = test_case["expected_tools"]
        
        print(f"Running [{tc_id}] [{category}]: '{query}'...")
        
        t0 = time.time()
        try:
            res: AgentRunResult = agent.run(query=query)
            elapsed = time.time() - t0
            latencies.append(elapsed)
            
            # Extract invoked tool names
            executed_tools = [s.tool_name for s in res.steps if s.tool_name]
            
            # Check tool call selection accuracy
            tool_matched = any(tool in executed_tools for tool in expected_tools)
            if tool_matched:
                correct_tool_calls += 1
                
            task_success = bool(res.final_answer and len(res.final_answer) > 50)
            if task_success:
                successful_runs += 1

            status_str = "PASSED 🟢" if (tool_matched and task_success) else "FAILED 🔴"
            print(f"  └─ Status: {status_str} | Latency: {elapsed:.2f}s | Tools Executed: {executed_tools}\n")
            
            results.append({
                "id": tc_id,
                "category": category,
                "latency_s": round(elapsed, 2),
                "tool_accuracy": tool_matched,
                "task_success": task_success,
                "executed_tools": executed_tools
            })
        except Exception as err:
            elapsed = time.time() - t0
            print(f"  └─ Status: ERROR 🔴 ({err})\n")
            results.append({
                "id": tc_id,
                "category": category,
                "latency_s": round(elapsed, 2),
                "tool_accuracy": False,
                "task_success": False,
                "error": str(err)
            })

    # Summary Metrics Calculation
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    tool_acc_pct = (correct_tool_calls / total_queries) * 100
    task_succ_pct = (successful_runs / total_queries) * 100

    print("================================================================================")
    print("                         📊 EVALUATION METRICS REPORT")
    print("================================================================================")
    print(f" Total Benchmark Queries Evaluated  : {total_queries}")
    print(f" Tool Call Selection Accuracy       : {tool_acc_pct:.1f}% ({correct_tool_calls}/{total_queries})")
    print(f" Task Completion Success Rate       : {task_succ_pct:.1f}% ({successful_runs}/{total_queries})")
    print(f" Mean Time To Diagnosis (MTTD)      : {avg_latency:.2f} seconds")
    print("================================================================================\n")

    # Save Evaluation Artifact Report
    eval_report_path = os.path.join(os.path.dirname(__file__), "evaluation_report.json")
    with open(eval_report_path, "w", encoding="utf-8") as f:
        json.dump({
            "metrics": {
                "total_queries": total_queries,
                "tool_selection_accuracy_pct": round(tool_acc_pct, 1),
                "task_success_rate_pct": round(task_succ_pct, 1),
                "mean_latency_seconds": round(avg_latency, 2)
            },
            "detailed_results": results
        }, f, indent=2)
    print(f"Evaluation artifact saved to: {eval_report_path}")

if __name__ == "__main__":
    run_evaluation_benchmark()
