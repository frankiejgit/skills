---
name: codmod-translator
description: >-
  Reviews or generates any Google Cloud Migration Center App Modernization Assessment (codmod) report,
  asks the user which modernization strategy, compute target, and supporting Google Cloud services to pursue
  based on the report's actual recommendations, constructs a tailored end-to-end refactor-and-deploy prompt,
  and executes it with /goal thoroughness. Works with any repository, language, architecture, or codmod report type.
---

# CodMod Translator (`codmod-translator`)

This skill translates **any** Google Cloud Migration Center App Modernization Assessment (`codmod`) report into an interactive, end-to-end code modernization and Google Cloud deployment workflow. It is completely repository- and language-agnostic and supports:
- **Any `codmod` report variant**: Full reports (`codmod create full`), Standard/Summary reports (`codmod create`), Data-Layer reports (`codmod create data-layer`), and `.html`, `.md`, or `.json` formats.
- **Any workload & tech stack**: Legacy monoliths (`.NET`, `Java`, `C/C++`), web/API microservices (`Python`, `Node.js`, `Go`, `PHP`, `Ruby`), and AI/MLOps pipelines (`vLLM`, `PyTorch`, `Vertex AI`, `Cloud Run Jobs`).

> [!IMPORTANT]
> **Resolving Skill Paths**: Whenever you run the helper script or read reference files, resolve their paths relative to **this `SKILL.md` file's directory** (`<SKILL_DIR>`), so the skill works whether installed in a workspace (`.agents/skills/codmod-translator/`) or globally (`~/.gemini/config/skills/codmod-translator/`).

---

## Workflow Steps

Always follow these four steps in order:

### Step 1: Locate (or Generate) and Extract the `codmod` Report

1. **Locate the report**:
   - Check the user's prompt or current workspace for `codmod` report files (`*.html`, `*.md`, `*.json`).
   - **If multiple reports exist** in the workspace and the user did not specify which one to use, ask the user which report to analyze using `ask_question` (or inspect both summaries briefly and let them pick).
   - **If no report exists**:
     - Use `ask_question` to ask the user whether to run a **Standard Assessment** (`codmod create`) or a **Full Assessment** (`codmod create full`) and whether to apply a specific `--intent` (`MICROSOFT_MODERNIZATION`, `JAVA_LEGACY_TO_MODERN`, `WILDFLY_LEGACY_TO_MODERN`, `ARM_MIGRATION`, `CLOUD_TO_CLOUD`, or none/general).
     - Run a cost estimate first (`codmod create --estimate-cost -c <codebase>`) and then generate the report.

2. **Extract a clean Markdown digest using [extract_codmod_report.py](./scripts/extract_codmod_report.py)**:
   - **Never** read a multi-megabyte raw `.html` `codmod` report directly with `view_file`.
   - Save all intermediate extracted report slices inside `./modernization-plan/report-extracts/`.
   - Run the extraction script with `--summary-only`:
     ```bash
     python3 "<SKILL_DIR>/scripts/extract_codmod_report.py" "<report_path>" --summary-only --output ./modernization-plan/report-extracts/codmod-summary.md
     ```
   - Read `./modernization-plan/report-extracts/codmod-summary.md` using `view_file`. The script automatically extracts:
     - **Report Metadata** (`Project`, `Report ID`, `Generated`, and the CLI command/codebase path used to generate the report).
     - **Report Structure & Available Sections** (whether categorized under `Cloud Migration` in a `full` report, or flat sections like `Modernization Opportunities` and `Migration Overview` in a standard report).
     - **Codebase Files Cited in Report Footnotes** (an exact inventory of the source files, scripts, and configs referenced by `codmod`).
     - **Executive Summary, Architecture, Technology Stack, Challenges, Opportunities, and Migration Overview**.

3. **Briefly summarize the findings** for the user (3–4 concise bullets covering the detected architecture/stack, key challenges or opportunities, and the modernization strategies/targets proposed in the report) before immediately calling `ask_question` in Step 2.

---

### Step 2: Ask the User for Their Desired Modernization Path (`ask_question`)

Dynamically construct the `ask_question` options from the **actual strategies and service recommendations** extracted in `./modernization-plan/report-extracts/codmod-summary.md` (do not hardcode options that aren't relevant to the report):

1. **Question 1 — Modernization Strategy & Target Architecture**:
   - Populate options from the report's **Cloud Migration** sections (e.g., `Modernize to Cloud Run`, `Modernize to Kubernetes Engine`, `Shift to Compute Engine`) **AND/OR** the report's **Suggested Modernization Strategies** / **Modernization Opportunities** (e.g., *Strategy 2: High-Benefit — Modernize to Managed Vertex AI MLOps Pipelines & Endpoints*, *Strategy 1: Optimize Existing Cloud Run Serverless Architecture*, *Decompose Monolith into Cloud Run Microservices & Cloud Functions*).
   - Put the report's highest-benefit recommended strategy first with `(Recommended)`.

2. **Question 2 — Supporting Google Cloud Services & Data/Storage Layer**:
   - Populate options from the report's **Shifting External Dependencies** / **External & Cloud Service Dependencies** / **Recommended Service Integrations** tables (and allow multi-select or bundle selection as appropriate):
     - *For Database-backed apps*: e.g., `(Recommended) Cloud SQL for PostgreSQL + Secret Manager + Artifact Registry`, `Cloud SQL for SQL Server + Secret Manager + Artifact Registry`, `AlloyDB for PostgreSQL + Secret Manager`.
     - *For AI / MLOps / Data apps*: e.g., `(Recommended) Vertex AI Pipelines + Vertex AI Model Registry & Endpoints + BigQuery + GCS + Secret Manager`, `Cloud Run GPU Services/Jobs + GCS FUSE + Artifact Registry + Secret Manager + Cloud Monitoring`.
     - *For Stateless / Local-Only testing*: `Container / Code Refactoring Only (Skip provisioning external cloud backing services)`.

3. **Question 3 — Execution Mode**:
   - `(Recommended) Construct the prompt AND execute the full refactor-to-deploy workflow now`
   - `Construct and save the /goal prompt to modernization-plan/modernization-execution-plan.md for review/demo first`

---

### Step 3: Extract Full Path Details & Construct `modernization-plan/modernization-execution-plan.md`

Once the user selects their options:

1. **Load any remaining section details into `./modernization-plan/report-extracts/`**:
   - If the report is a `full` report with a dedicated section for the chosen target (e.g., `Modernize to Cloud Run`, `Modernize to Kubernetes Engine`, `Shift to Compute Engine`) or `APIs and Endpoints` / `Security and Compliance`, extract them using [extract_codmod_report.py](./scripts/extract_codmod_report.py):
     ```bash
     python3 "<SKILL_DIR>/scripts/extract_codmod_report.py" "<report_path>" --section "<Selected Section>" --output ./modernization-plan/report-extracts/codmod-selected-path.md
     python3 "<SKILL_DIR>/scripts/extract_codmod_report.py" "<report_path>" --section "APIs and Endpoints" --output ./modernization-plan/report-extracts/codmod-endpoints.md
     ```
   - Read `./modernization-plan/report-extracts/codmod-selected-path.md` (if applicable) and consult [gcp-deployment-patterns.md](./references/gcp-deployment-patterns.md).

2. **Write the tailored `/goal` prompt to `./modernization-plan/modernization-execution-plan.md`**:
   - Use `write_to_file` to create `modernization-plan/modernization-execution-plan.md`.
   - Structure it as a self-contained, copy-pasteable `/goal` prompt tailored specifically to the codebase and chosen strategy:
     - **Header**: Starts with `/goal Act as a Senior Cloud Architect and Modernization Engineer...` and references the extracted report files in `@modernization-plan/report-extracts/codmod-summary.md` and `@modernization-plan/report-extracts/codmod-selected-path.md`.
     - **Phase 1 — Code, Data Layer, or Pipeline Refactoring**:
       - Explicitly lists the exact files from **Codebase Files Cited in Report Footnotes** (e.g., `.csproj`, `Startup.cs`, `pom.xml`, `src/finetuning/train_lora.py`, `src/frontend/auth-proxy/main.py`, `scripts/*.sh`) and the concrete changes required for each.
       - Enforces runtime, port binding (`0.0.0.0:${PORT:-8080}`), structured logging, and externalized configuration/secrets.
     - **Phase 2 — Containerization, Manifests & Build Verification**:
       - `Dockerfile`(s), `.dockerignore`, Knative `service.yaml`, Kubernetes manifests, or Vertex AI KFP pipeline compilation, plus local build/syntax verification.
     - **Phase 3 — GCP Environment Discovery & Supporting Services Provisioning**:
       - Discovers existing GCP resources first (`gcloud artifacts repositories list`, `gcloud run services list`, `gcloud sql instances list`, `gcloud storage buckets list`) to reuse or avoid collisions.
       - Enables required GCP APIs, creates a least-privilege Service Account + IAM bindings, and provisions all selected supporting services (Artifact Registry, Cloud SQL / AlloyDB / GCS buckets / BigQuery / Secret Manager / Vertex AI).
     - **Phase 4 — Target Deployment, Self-Healing & End-to-End Verification**:
       - Builds and deploys the workload (Cloud Run Services/Jobs, Vertex AI Pipelines/Endpoints, GKE, or Compute Engine) wired to the supporting services.
       - Includes a self-healing loop (inspect Cloud Build / Cloud Run / Vertex AI logs on failure, fix code/config, and redeploy).
       - Includes Org-Policy-safe verification (tests public URLs or falls back to `Authorization: Bearer $(gcloud auth print-identity-token)` if `--allow-unauthenticated` is restricted).

---

### Step 4: Run with `/goal` Execution

1. **Always display the exact `/goal` command** in your response:
   ```text
   /goal Execute @modernization-plan/modernization-execution-plan.md end-to-end
   ```

2. **Execute or Pause Based on Step 2 Selection**:
   - If the user chose **"Construct and save the `/goal` prompt... for review/demo first"**, link to `modernization-plan/modernization-execution-plan.md` and wait for their go-ahead.
   - If the user chose **"Construct the prompt AND execute the full refactor-to-deploy workflow now"**:
     - Check whether the target application's source code is in the workspace (using the codebase path from the report's `Command Line Options` or `Codebase Files Cited in Report Footnotes`). If only the HTML report is present in the folder, ask the user for the path/repo URL of the source codebase to clone or open.
     - Once the source code is accessible, immediately execute **Phases 1 through 4** of `modernization-plan/modernization-execution-plan.md` end-to-end without stopping until the live deployment is verified.
