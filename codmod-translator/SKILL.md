---
name: codmod-translator
description: >-
  Reviews or generates any Google Cloud Migration Center App Modernization Assessment (codmod) report,
  asks the user which modernization strategy, compute target, and supporting Google Cloud services to pursue
  based on the report's recommendations, constructs a tailored 4-phase refactor-and-deploy prompt,
  and executes it with /goal thoroughness.
---

# CodMod Translator (`codmod-translator`)

This skill translates any Google Cloud Migration Center App Modernization Assessment (`codmod`) report into an interactive, end-to-end code modernization and Google Cloud deployment workflow.

> [!IMPORTANT]
> **Resolving Skill Paths**: Always resolve helper scripts and reference files relative to **this `SKILL.md` file's directory** (`<SKILL_DIR>`), so the skill works whether installed in a workspace or globally.

---

## Workflow Steps

### Step 1: Locate (or Generate) and Extract the `codmod` Report

1. **Locate or generate the report**:
   - Check the user's prompt or workspace for existing `codmod` reports (`*.html`, `*.md`, `*.json`). If multiple reports exist and the user didn't specify one, ask which to use via `ask_question`.
   - If no report exists, use `ask_question` to confirm the assessment command (`codmod create`, `codmod create full`, `codmod create data-layer`, or `codmod create custom`, plus any `--intent` or `--force-include` regex if the repo uses non-default file extensions). Run `codmod create --estimate-cost -c <codebase>` first when supported, then generate the report.

2. **Extract a clean Markdown digest using [extract_codmod_report.py](./scripts/extract_codmod_report.py)**:
   - Never read raw `.html` reports directly with `view_file`.
   - Extract the summary slice into `./modernization-plan/report-extracts/`:
     ```bash
     python3 "<SKILL_DIR>/scripts/extract_codmod_report.py" "<report_path>" --summary-only --output ./modernization-plan/report-extracts/codmod-summary.md
     ```
   - Read `./modernization-plan/report-extracts/codmod-summary.md` with `view_file`.

3. **Summarize findings**: Give the user a 3–4 bullet summary (detected architecture/stack, key challenges, and recommended strategies) and immediately call `ask_question` in Step 2.

---

### Step 2: Ask the User for Their Desired Modernization Path (`ask_question`)

Populate the `ask_question` options dynamically from the **actual recommendations** in `./modernization-plan/report-extracts/codmod-summary.md`:

1. **Question 1 — Modernization Strategy & Compute Target**:
   - Options derived from the report's *Suggested Modernization Strategies*, *Migration Target Platforms*, *Cloud Migration* sections, or *Modernization Opportunities*. Prefix the report's primary recommendation with `(Recommended)`.
2. **Question 2 — Supporting Google Cloud Services**:
   - Options derived from the report's recommended data, storage, orchestration, and integration services (plus an option for *Code / Container Refactoring Only* without provisioning external cloud backing services).
3. **Question 3 — Execution Mode**:
   - `(Recommended) Construct the prompt AND execute the full refactor-to-deploy workflow now`
   - `Construct and save the /goal prompt to modernization-plan/modernization-execution-plan.md for review first`

---

### Step 3: Extract Selected Section & Write `modernization-plan/modernization-execution-plan.md`

1. **Extract any deferred target-specific section**:
   - If the report lists a dedicated section in *Report Structure & Available Sections* for the user's chosen target (e.g., under `Cloud Migration`), extract it:
     ```bash
     python3 "<SKILL_DIR>/scripts/extract_codmod_report.py" "<report_path>" --section "<Selected Section>" --output ./modernization-plan/report-extracts/codmod-selected-path.md
     ```
   - Read `./modernization-plan/report-extracts/codmod-selected-path.md` (if extracted) and read [gcp-deployment-patterns.md](./references/gcp-deployment-patterns.md).

2. **Generate `./modernization-plan/modernization-execution-plan.md`**:
   - If the **Google Developer Knowledge MCP** (`search_documents` / `get_document`) is available in the environment, query it to verify current `gcloud` CLI flags, IAM roles, and SDK patterns for the user's selected Google Cloud services.
   - Follow the 4-phase structure and guardrails in [gcp-deployment-patterns.md](./references/gcp-deployment-patterns.md), tailored strictly to the repository and the user's Step 2 selections.

---

### Step 4: Execute or Pause

1. **Always display the copy-pasteable `/goal` command**:
   ```text
   /goal Execute @modernization-plan/modernization-execution-plan.md end-to-end
   ```

2. **Run or wait based on Step 2**:
   - If the user chose **review first**, link to `modernization-plan/modernization-execution-plan.md` and wait for confirmation.
   - If the user chose **execute now**, verify the target codebase is present in the workspace (if only the report file is present, ask the user for the codebase path or repository URL), then execute Phases 1–4 of `modernization-plan/modernization-execution-plan.md` end-to-end.
