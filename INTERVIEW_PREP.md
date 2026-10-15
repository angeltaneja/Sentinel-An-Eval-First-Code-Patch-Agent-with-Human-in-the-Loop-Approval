# 🛡️ Sentinel — Interview Preparation Guide
> **"An Eval-First Code Patch Agent with Human-in-the-Loop Approval"**
> Everything you need to explain this project confidently in any interview.

---

## 📌 SECTION 1 — THE 30-SECOND PITCH
> *Use this when the interviewer says: "Tell me about this project in brief."*

**"Sentinel is an AI-powered agentic system I built that automatically reads GitHub issues, understands the codebase, generates a code fix (as a patch/diff), tests it inside an isolated Docker sandbox, and then pauses for a human to approve or reject before opening a pull request. The core philosophy is safety-first — the AI proposes, humans decide."**

---

## 📌 SECTION 2 — THE PROBLEM IT SOLVES

### The Problem:
When developers get a GitHub issue (a bug or feature request), they have to:
1. Read and understand the issue
2. Find the relevant code in the codebase
3. Write a fix
4. Run tests to make sure nothing broke
5. Create a pull request

This is **time-consuming and repetitive** — especially for small bugs.

### Why not just use a fully autonomous AI agent?
Because **fully autonomous agents are dangerous** — they can:
- Modify the wrong files
- Break existing tests without knowing
- Merge broken code directly to production
- Run unknown code on your machine

### Sentinel's Solution:
Sentinel automates steps 1–4 **but always pauses before step 5**.
A human reviews the AI's work, sees test results, and only then approves the merge.
**"The AI does the work. The human takes the decision."**

---

## 📌 SECTION 3 — HOW IT WORKS (Step by Step)

> *Use this when asked: "Walk me through how this system works."*

### Step 1: INGEST
- Sentinel reads a GitHub issue (title + body + comments)
- It fetches the repository metadata using the **GitHub API**
- Stores everything as structured state

### Step 2: PLAN
- An **LLM (GPT-4)** reads the issue and acts as a planner
- It decides: *"Which files are probably relevant? What is the strategy to fix this?"*
- Outputs a list of candidate files and a repair strategy

### Step 3: RETRIEVE
- Sentinel goes into the actual codebase
- It **parses code using Tree-sitter** (an AST parser) — not line by line, but function by function and class by class
- Then does **Hybrid Search**:
  - **BM25**: keyword matching (finds exact function names from the issue)
  - **Dense Embeddings**: semantic search (finds conceptually related code even if words differ)
  - **RRF (Reciprocal Rank Fusion)**: combines both scores into one ranked list
- Returns the **top-K most relevant code chunks**

### Step 4: GENERATE
- The LLM receives: the issue + the relevant code chunks
- It generates a **unified diff patch** (the same format as `git diff`)
- This patch describes exactly what lines to add/remove

### Step 5: SANDBOX
- The patch is applied inside an **isolated environment** (Docker container or temp directory)
- The repo's test suite is run (`pytest` or whatever the repo uses)
- The sandbox has: **no internet access, memory limits, CPU limits, time limits**
- Result: PASS or FAIL + full test output

### Step 6a: REPAIR (if tests fail)
- If tests fail AND retries < 3:
  - The LLM receives the test failure logs
  - It re-analyzes and generates a new, improved patch
  - Goes back to SANDBOX
- **Cycle detection**: If the same patch is generated twice, it immediately escalates

### Step 6b: ESCALATE (if can't fix)
- If retries exhausted (3 attempts) or patch is stuck in a loop
- Sentinel logs the failure with full context
- Ends with a failure report — **never silently fails**

### Step 7: EVALUATE
- Once tests PASS, Sentinel scores the patch on 3 dimensions:
  1. **Test Pass Rate** (60% weight) — did all tests pass?
  2. **Blast Radius** (25% weight) — how many lines/files were changed? (smaller = safer)
  3. **Static Analysis** (15% weight) — does the code pass linting (Ruff)?
- Produces a **quality scorecard**

### Step 8: HUMAN GATE (The most important step)
- The system **pauses completely** using LangGraph's `interrupt()` mechanism
- State is saved to **PostgreSQL** (so it can wait hours, days, or weeks)
- A human sees:
  - The syntax-highlighted diff
  - The evaluation scorecard (test results, blast radius, lint status)
  - The original issue
- Human types `approve` or `reject` (with optional rejection reason)

### Step 9: COMMIT (only if approved)
- Sentinel applies the patch to a new git branch
- Creates a **DRAFT Pull Request** on GitHub via the GitHub API
- Logs the entire operation

---

## 📌 SECTION 4 — TECHNOLOGIES USED (and WHY)

| Technology | What it is | Why Sentinel uses it |
|---|---|---|
| **LangGraph** | A graph-based AI orchestration framework | To build the state machine with nodes, edges, conditional routing, and interrupt/resume capability |
| **LangChain** | LLM toolkit | For structured LLM calls, prompt templates, and output parsers |
| **OpenAI GPT-4** | The LLM brain | For planning, patch generation, and repair reasoning |
| **Tree-sitter** | AST code parser | To split code into functions/classes (not just lines) for smarter retrieval |
| **BM25** | Keyword search algorithm | Finds exact code identifiers mentioned in the issue |
| **Dense Embeddings** | Semantic vector search | Finds conceptually related code even if exact words differ |
| **RRF** | Rank fusion algorithm | Combines BM25 + embedding ranks fairly into one list |
| **Docker** | Containerization | Isolated, sandboxed test execution with no network access |
| **PostgreSQL** | Relational database | Persists LangGraph state so the human gate can pause indefinitely |
| **Langfuse** | LLM observability platform | Traces every LLM call: tokens used, latency, cost, prompt versions |
| **Pydantic** | Data validation library | Validates all state objects and configuration settings |
| **Rich** | Terminal UI library | Beautiful CLI output with colored diffs and progress indicators |
| **Ruff** | Python linter | Static code analysis for the generated patches |
| **GitHub API** | REST API | Reads issues, creates branches, opens draft PRs |
| **Pytest** | Testing framework | Runs the repo's test suite inside the sandbox |

---

## 📌 SECTION 5 — KEY CONCEPTS TO EXPLAIN

### 1. What is a "Unified Diff / Patch"?
A unified diff is the standard format for showing code changes. You've seen it in GitHub's PR view — lines starting with `+` are added, `-` are removed. Sentinel generates this format so it can be applied cleanly with `git apply`.

### 2. What is AST-Aware Chunking?
AST = Abstract Syntax Tree. Instead of splitting code by 50 lines (which might cut a function in half), Tree-sitter parses the code and identifies complete logical units: functions, classes, methods. Sentinel retrieves these complete chunks — so the LLM always sees complete, meaningful code, never half a function.

### 3. What is Hybrid Search + RRF?
- **BM25 alone** misses semantically similar code (e.g., `calculate_tax` vs `compute_levy`)
- **Embeddings alone** miss exact keyword matches (e.g., a specific function name)
- **RRF** merges both ranked lists using the formula:
  `score = 1/(60 + rank_bm25) + 1/(60 + rank_embedding)`
- Result: the best of both worlds

### 4. What is the Human-in-the-Loop (HITL) gate?
It's a hard pause in the workflow. The system literally stops and cannot proceed until a human responds. LangGraph's `interrupt()` serializes the entire state to PostgreSQL, so it can wait indefinitely without losing data. This is what makes Sentinel safe — no code ever reaches GitHub without a human saying "yes."

### 5. What is Cycle Detection?
Each generated patch is hashed with SHA-256. If the same hash appears again (the LLM generated the identical patch twice), Sentinel knows it's stuck in a loop and escalates immediately instead of burning more LLM API tokens.

### 6. What is Blast Radius?
A measure of how much the patch changes. A patch that touches 50 files and adds 500 lines is riskier than one that changes 2 lines in 1 file. Sentinel penalizes large-blast-radius patches in its scoring — preferring minimal, surgical changes.

---

## 📌 SECTION 6 — ARCHITECTURE DIAGRAM

```
GitHub Issue
     |
     v
[INGEST] --> Fetch issue, repo metadata via GitHub API
     |
     v
[PLAN] --> LLM decides: which files? what strategy?
     |
     v
[RETRIEVE] --> Tree-sitter AST chunking + BM25 + Embeddings + RRF
     |
     v
[GENERATE] <-----------------------------------------
     |                                               |
     v                                               |
[SANDBOX] --> Docker: apply patch, run tests         |
     |                                               |
     +-- FAIL (retries < 3, no cycle) --> [REPAIR] --+
     |
     +-- FAIL (retries >= 3 OR cycle) --> [ESCALATE] --> END
     |
     v PASS
[EVALUATE] --> Scorecard: tests + blast radius + lint
     |
     v
[HUMAN GATE] --> interrupt() --> save to PostgreSQL --> wait for human
     |
     +-- REJECT --> Log reason --> END
     |
     v APPROVE
[COMMIT] --> git branch + patch + Draft PR via GitHub API
     |
     v
   END (Success)
```

---

## 📌 SECTION 7 — DESIGN DECISIONS (Impress the Interviewer)

### Q: Why LangGraph instead of just writing Python functions?
**A:** LangGraph gives us:
- A **persistent state machine** — state survives restarts, crashes, or the human waiting days to approve
- **Conditional routing** — different edges fire based on test results
- **Native interrupt/resume** — the human gate works without any custom infrastructure
- **Checkpointing** — PostgreSQL backed, so we never lose state

### Q: Why Docker for the sandbox?
**A:** Security. We're running LLM-generated code. We need:
- **Network isolation** (`--network none`) — prevents data exfiltration or unauthorized downloads
- **Resource limits** — prevents runaway processes from consuming all CPU/RAM
- **Filesystem isolation** — the container can only see the repo clone, nothing else on the host

### Q: Why not just use embeddings for retrieval?
**A:** Embeddings alone miss exact keyword matches — if the issue says "fix the `calculate_interest` function", embedding search might return conceptually similar functions but miss the exact one. BM25 catches exact matches. RRF combines both fairly.

### Q: Why SHA-256 for cycle detection?
**A:** It's deterministic and cheap. We hash the entire patch content. If the same hash appears in the repair loop history, we know the LLM has generated the exact same (failed) patch again — meaning more retries won't help. We escalate instead.

### Q: Why a DRAFT pull request?
**A:** Safety. A draft PR cannot be merged — it requires an explicit action from a human to mark it as "ready for review." This adds a second layer of safety beyond Sentinel's own human gate.

---

## 📌 SECTION 8 — EXPECTED INTERVIEW Q&A

### Q1: "What is the most challenging part you built?"
**A:** *"The hardest part was the retrieval system. Getting the right code context is critical — if the LLM sees the wrong code, its patch will be wrong no matter how good the model is. I implemented AST-aware chunking with Tree-sitter to preserve semantic boundaries, then built a hybrid BM25+embedding retrieval pipeline with RRF to combine both lexical and semantic signals. This was both algorithmically interesting and practically important."*

### Q2: "How do you ensure the AI doesn't do something harmful?"
**A:** *"Sentinel has multiple layers of guardrails: (1) The sandbox runs with no internet access and resource limits. (2) The repair loop has a hard cap at 3 retries. (3) Cycle detection prevents infinite loops. (4) The human approval gate is a hard stop — the system cannot proceed without a human approving. (5) Even after approval, only a DRAFT PR is created. These aren't soft suggestions — they're hard architectural constraints."*

### Q3: "Why use GPT-4 for planning and generation?"
**A:** *"GPT-4 has strong reasoning capabilities for the planning step — it needs to read an ambiguous GitHub issue and map it to specific files in a potentially large codebase. For generation, it needs to understand code context and produce a syntactically valid unified diff. Smaller models often fail at the diff format. However, the architecture is model-agnostic — you can swap in any LangChain-supported LLM."*

### Q4: "How does the system handle large codebases?"
**A:** *"Through AST-aware chunking and retrieval. We don't pass the entire codebase to the LLM — that would exceed context limits and add noise. Instead, we parse the repo into individual functions and classes, index them, and retrieve only the top-K most relevant chunks for the specific issue. The LLM only sees what it needs."*

### Q5: "What is LangGraph and why did you use it?"
**A:** *"LangGraph is an orchestration framework for building stateful, multi-step LLM workflows as directed graphs. Each node is a processing step, edges define the flow including conditional branching. I used it because it provides native support for: persistent state checkpointing to PostgreSQL, the interrupt/resume mechanism for the human gate, and cyclic graphs for the repair loop."*

### Q6: "What's the difference between this and just using ChatGPT to fix code?"
**A:** *"Three major differences: First, retrieval — ChatGPT doesn't have access to your private codebase; Sentinel intelligently retrieves the right context. Second, evaluation — ChatGPT can't run your tests in an isolated environment to verify the fix works; Sentinel does. Third, guardrails — Sentinel has a formal state machine with retry bounds, cycle detection, human approval, and audit logging. ChatGPT is a conversation; Sentinel is a production-grade pipeline."*

### Q7: "How does observability work?"
**A:** *"Every LLM call is traced via Langfuse — tokens used, latency, model version, prompt template version. Every state transition in the graph emits a structured JSON log event with the node name, execution time, and state delta. This means you can debug exactly what happened in any run, calculate cost per issue, and track quality over time."*

### Q8: "What would you improve if you had more time?"
**A:** *"A few things: First, add a vector database (like Qdrant or Weaviate) for scalable dense retrieval instead of in-memory embeddings. Second, add multi-file diff awareness — currently patches are applied atomically, but complex bugs might require coordinated changes across files. Third, add a feedback loop where approved patches are used to fine-tune or few-shot prompt the generation model over time."*

---

## 📌 SECTION 9 — WHAT TO SAY ON RESUME

**Project Title:**
> Sentinel — Eval-First Agentic Code Patch System with HITL Approval

**One-line description:**
> Built a production-grade LangGraph agentic pipeline that reads GitHub issues, retrieves relevant code via AST-aware hybrid search (BM25 + dense embeddings + RRF), generates unified diff patches, validates them in a network-isolated Docker sandbox, and enforces human approval before opening draft PRs.

**Resume Bullet Points:**
- Designed a 9-node LangGraph state machine with cyclic repair loop, SHA-256 cycle detection, and durable PostgreSQL checkpointing
- Implemented AST-aware code chunking using Tree-sitter and hybrid retrieval (BM25 + embeddings + RRF) for accurate context selection
- Built a hardened Docker sandbox runner with `--network none`, memory caps, CPU limits, and wall-clock timeout guards for safe code execution
- Integrated Langfuse for full LLM observability: token tracking, latency tracing, and cost monitoring per run
- Engineered a human-in-the-loop approval gate using LangGraph's `interrupt()` backed by PostgreSQL — state persists indefinitely without data loss

**Tech stack to list:**
`Python` · `LangGraph` · `LangChain` · `OpenAI GPT-4` · `Tree-sitter` · `BM25` · `Docker` · `PostgreSQL` · `Pydantic` · `Langfuse` · `GitHub API` · `Ruff` · `Pytest`

---

## 📌 SECTION 10 — QUICK CHEATSHEET

| Question | One-line Answer |
|---|---|
| What is Sentinel? | An AI agent that fixes GitHub issues, tests the fix, and waits for human approval before merging |
| What is eval-first? | Validation (sandbox + tests) happens BEFORE any human sees the patch — not after |
| What is HITL? | Human-in-the-Loop — a hard pause where a human must approve before the system can continue |
| What is RRF? | Reciprocal Rank Fusion — merges BM25 and embedding search ranks into one score |
| Why AST chunking? | So code is split at logical boundaries (functions/classes), not arbitrary line numbers |
| Why Docker sandbox? | Isolated execution — no internet, resource limits, can't touch host system |
| What is blast radius? | A measure of how many files/lines the patch touches — smaller is safer |
| What stops infinite loops? | SHA-256 cycle detection + hard 3-retry cap |
| Why PostgreSQL? | Persists LangGraph state so the human gate can pause for days without losing data |
| What if all retries fail? | Sentinel escalates with a full failure report — never silently fails |

---

*Good luck with your interview! You built something impressive — own it with confidence.* 🚀
