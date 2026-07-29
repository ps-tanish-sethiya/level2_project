# DevSentinel — Problem Statement & Solution Document

## Executive Summary

When CI pipelines fail or Pull Requests introduce security risks, developers face fragmented diagnostic workflows—searching build logs, querying vulnerability databases, and attempting to recall past incidents. **DevSentinel** automates build and PR risk diagnosis by unifying live external APIs (GitHub Actions, OSV.dev, PyPI, GitHub Status) with local data stores (SQLite incident database and a local RAG vector store).

---

## 🎯 Target Problem

In modern software development:
1. **CI Build Logs are Messy**: Raw logs contain hundreds of lines of noise, hiding the actual failure cause.
2. **Security Vulnerability Gaps**: Dependencies pushed in PRs often contain known CVEs that go unflagged until production deployment.
3. **Memory Loss Across Teams**: Repeated build failures (flaky tests, expired certificates) are repeatedly debugged from scratch because historical resolution knowledge remains unindexed.

---

## 💡 DevSentinel Solution

DevSentinel introduces an agentic assistant backed by a custom Model Context Protocol (MCP) server:
- **Autonomous Tool Selection**: The ReAct agent dynamically queries GitHub Actions API, OSV.dev, PyPI registry, local vector store, and SQLite incident logs.
- **Evidence-Grounded Diagnoses**: All findings explicitly state whether evidence originated from live APIs, vector KB, or SQLite memory.
- **Human-in-the-Loop Control**: State-changing writes (`log_new_incident`) require explicit operator confirmation before execution.
- **Dual LLM Resilience**: Built with Gemini 2.5 Flash as primary and Groq Llama-3.3-70b as transparent fallback ($0 total cost).

---

## 📌 Note on Demo Repository Prop

The `demo-target-repo` described in `demo_repo_setup/` is a minimal, self-created prop whose sole purpose is to generate real live GitHub Actions API data and test OSV.dev vulnerability queries. The engineering deliverable evaluated is the MCP server, agent architecture, and test suite.
