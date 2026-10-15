# 🛡️ Sentinel: An Eval-First Code Patch Agent with Human-in-the-Loop Approval

> **A production-grade, stateful proposal engine with guardrails designed for safety, determinism, and engineering discipline.**

---

## 🎯 Mission & Philosophy

Sentinel is an eval-first agentic system that reads GitHub issues, retrieves relevant code context using AST-aware hybrid search, generates unified diff patches, validates them inside an isolated Docker sandbox, and presents a multi-dimensional evaluation scorecard at a durable **Human Approval Gate** before opening a draft pull request.

**Sentinel is NOT an autonomous agent.** It is a **proposal engine with guardrails**.
Every risky action is bounded, logged, and gated by human verification.

---

## 🏗️ Core Architecture & Topology

Sentinel is built as a stateful LangGraph state machine with cyclic repair capability and durable PostgreSQL checkpointing:

```
[START]
   │
   ▼
[INGEST]      ── Fetches target GitHub issue, issue comments & repo metadata
   │
   ▼
[PLAN]        ── LLM analyzes scope, proposes candidate files, test targets & strategy
   │
   ▼
[RETRIEVE]    ── AST-aware chunking (Tree-sitter) + Hybrid Search (BM25 + Dense + RRF)
   │
   ▼
[GENERATE] ◄──┐ Unified diff patch generation
   │          │
   ▼          │
[SANDBOX]     │ Ephemeral isolated container/process (--network none, resource limits)
   │          │ Applies patch via `git apply`, runs repo test suite
   ├── (tests FAIL & retries < 3 & diff not identical) ──► [REPAIR] ──┘
   ├── (tests FAIL & retries >= 3 OR duplicate diff)   ──► [ESCALATE] ──► [END] (Failure Logged)
   │
   ▼ (tests PASS)
[EVALUATE]    ── Multi-dimensional scorecard: test pass rate, blast radius, lint diagnostics
   │
   ▼
[HUMAN GATE]  ── LangGraph interrupt(); state serialized to Postgres checkpointer
   │             Human reviews syntax-highlighted diff + evaluation scorecard
   ├── (Rejected)  ──► Log rejection reason ──► [END]
   │
   ▼ (Approved)
[COMMIT]      ── Applies patch, commits to branch, opens DRAFT Pull Request via GitHub API
   │
   ▼
 [END]
```

---

## 🔑 Key Engineering Disciplines

### 1. AST-Aware Hybrid Retrieval (`RETRIEVE`)
- **Syntactic Boundaries**: Code is parsed into functions, classes, and methods using Tree-sitter rather than arbitrary line slices.
- **Dual Retrieval & RRF**:
  - **BM25**: Lexical exact matching with code identifier tokenization (camelCase & snake_case sub-tokenization).
  - **Dense Embeddings**: Semantic representation capturing issue intent.
  - **Reciprocal Rank Fusion**: Aggregates lexical and semantic ranks via:
    $$RRF(d) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$$

### 2. Hardened Network-Isolated Sandbox (`SANDBOX`)
- **Docker Air-Gapping**: Executed with `--network none` to prevent unauthorized outbound network requests or exfiltration.
- **Resource Constraints**: Capped CPU cores (`--cpus 2.0`), memory caps (`--memory 2g`), and wall-clock timeout guards.
- **Pluggable Architecture**:
  - `DockerSandboxRunner`: Hardened container runner for production.
  - `LocalProcessSandboxRunner`: Isolated temporary directory clone fallback for local dev & testing without a running Docker daemon.

### 3. Bounded Repair Loop & Diff Cycle Detection (`REPAIR` & `ESCALATE`)
- Hard cap at **3 retries**.
- **SHA-256 Diff Fingerprinting**: Each generated patch is fingerprinted. If an identical diff or repetitive cycle is detected, Sentinel immediately aborts to `[ESCALATE]` to avoid burning LLM tokens or entering infinite loops.

### 4. Durable State Persistence & HITL (`HUMAN GATE`)
- State serialized via LangGraph's native `interrupt()` backed by **PostgreSQL checkpointer** (`PostgresSaver`).
- Pauses indefinitely with zero loss of state; can resume days or weeks later upon human approval.

### 5. Multi-Dimensional Evaluation Scorecard (`EVALUATE`)
Patch quality is evaluated along three dimensions:
- **Test Pass Rate (60% weight)**: Verification that tests pass exit code 0.
- **Blast Radius (25% weight)**: Normalized penalty based on LOC added/deleted and number of files touched.
- **Static Analysis (15% weight)**: AST syntax check and Ruff linter diagnostics.

### 6. Full Observability & Auditability
- **Langfuse Integration**: Every generation, token count, latency, and prompt version traced.
- **Structured JSON Logging**: Every node transition and duration emitted as structured events.

---

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/your-org/sentinel.git
cd sentinel
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -e .
```

### 2. Start PostgreSQL & Langfuse Stack (Docker Compose)
```bash
docker compose up -d
```

### 3. Configure Environment
```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, GITHUB_TOKEN, POSTGRES_URI, and LANGFUSE keys
```

### 4. Run Sentinel via Interactive CLI
```bash
sentinel run --repo owner/my-repo --issue 42 --path ./local_repo
```

### 5. Run Test Suite
```bash
pytest -v
```

---

## 🧪 Test Coverage
Sentinel includes comprehensive unit and integration tests covering:
- AST parsing across Python & JavaScript.
- BM25 lexical tokenization and RRF rank fusion.
- Diff cycle detection and retry bounding.
- Sandbox patch application and test runners.
- End-to-end LangGraph state machine pause at `human_gate` and resumption.
