# Universal Google Cloud Modernization & Deployment Blueprints

Use these blueprints when constructing the **4-Phase Refactor-to-Deploy Prompt** (`modernization-execution-plan.md`) in Step 3 of the `codmod-translator` skill. Adapt the phases to match **only** the languages, compute targets, and supporting services relevant to the repository and the user's selected path.

---

## 1. Phase 1 Blueprints: Application, Data, or Pipeline Refactoring

Always incorporate the exact file paths and line/package references from the `codmod` report's **Codebase Files Cited in Report Footnotes** into Phase 1 so the executing agent knows the exact files to edit.

### A. Legacy Monolith Modernization (`.NET`, `Java`, `C/C++`)
- **.NET (`MICROSOFT_MODERNIZATION`)**:
  - Upgrade `.csproj` to SDK-style targeting modern LTS `.NET 8` (`net8.0`) or `.NET 10` (`net10.0`).
  - Migrate `EntityFramework` (EF6) -> `Microsoft.EntityFrameworkCore` (`Npgsql.EntityFrameworkCore.PostgreSQL` for PostgreSQL/AlloyDB or `Microsoft.EntityFrameworkCore.SqlServer` for SQL Server).
  - Replace `web.config` / `ConfigurationManager` with `appsettings.json` + environment variables; ensure startup DB schema creation (`EnsureCreated()`) and seeding.
- **Java (`JAVA_LEGACY_TO_MODERN` / `WILDFLY_LEGACY_TO_MODERN`)**:
  - Upgrade `pom.xml` / `build.gradle` to **Java 21 LTS** and `jakarta.*` namespaces (Spring Boot 3.x / Quarkus 3.x / Jakarta EE 10).
  - Externalize JNDI datasources to environment variables (`SPRING_DATASOURCE_URL`, etc.) and Cloud SQL Socket Factory.
- **C/C++ (`ARM_MIGRATION`)**:
  - Replace x86-specific intrinsics (`<immintrin.h>`) with portable code, Arm NEON (`<arm_neon.h>`), or `SIMDe`, and update `CMakeLists.txt`/`Makefile` for `linux/arm64`.

### B. Cloud-Native Web, API & Microservices (`Python`, `Node.js`, `Go`, `PHP`, `Ruby`)
- Externalize all hardcoded URLs, project IDs, bucket names, and credentials to environment variables and **Google Cloud Secret Manager**.
- Ensure the HTTP server binds to `0.0.0.0:${PORT:-8080}` (e.g., `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`, `gunicorn`, `node`, or `go` `http.ListenAndServe(":"+port, nil)`).
- Emit structured JSON logs to `stdout`/`stderr` for automatic **Cloud Logging** ingestion.
- Handle `SIGTERM` for graceful shutdown.
- If the report recommends **Service Decomposition** (e.g., extracting background jobs, batch tasks, or domain microservices) and the user selected it:
  - Extract long-running batch tasks into **Cloud Run Jobs** or **Cloud Run Functions**.
  - Secure service-to-service calls using OIDC identity tokens (`google-auth` / metadata server).

### C. AI / LLM & MLOps Workloads (e.g., Python + vLLM / PyTorch / Cloud Run Jobs -> Vertex AI)
When the report assesses an AI/ML repository (such as a script-driven LLM blueprint using `train_lora.py`, `generate_dataset.py`, `vLLM`, `FastAPI` proxy, or `OpenWebUI`):
- **Path 1 — Managed Vertex AI MLOps Modernization**:
  - Refactor manual shell-script orchestration (`deploy_*.sh`) into a declarative **Vertex AI Pipeline** (`kfp` / `google-cloud-aiplatform` pipeline definition) covering data synthesis, training, evaluation, registration, and endpoint deployment.
  - Refactor fine-tuning scripts (`train_lora.py`) to run as **Vertex AI Custom Training Jobs** (supporting Spot VMs and **Vertex AI Experiments** metric logging) and register trained models/LoRA adapters in the **Vertex AI Model Registry**.
  - Update model serving or the frontend routing proxy (`auth-proxy/main.py`) to route inference requests to a **Vertex AI Prediction Endpoint** (or pull the production-tagged model version from Vertex AI Model Registry).
  - Optionally load synthesized JSONL datasets into **BigQuery** for validation and versioning.
- **Path 2 — Serverless Cloud Run / Multi-Container Optimization**:
  - Preserve and harden the **Cloud Run Services** (including multi-container sidecar manifests like `service.yaml` with `openwebui` + `auth-proxy`, or GPU-enabled `vllm` services using GCS FUSE `--add-volume` / `--add-volume-mount`) and **Cloud Run Jobs**.
  - Consolidate disparate `setup_*.sh` / `deploy_*.sh` scripts into reproducible **Cloud Build** (`cloudbuild.yaml`) pipelines with Secret Manager bindings (`secretEnv`).

---

## 2. Phase 2 Blueprints: Containerization & Local Verification

- **Multi-Stage `Dockerfile`** (if not already present or if runtime was upgraded):
  - **.NET**: `mcr.microsoft.com/dotnet/sdk:8.0` -> `mcr.microsoft.com/dotnet/aspnet:8.0`
  - **Java**: `maven:3.9-eclipse-temurin-21` -> `eclipse-temurin:21-jre-jammy`
  - **Python**: `python:3.12-slim` (or `pytorch/pytorch` / `vllm/vllm-openai` for GPU ML workloads)
  - **Node.js**: `node:20-alpine` (build) -> `node:20-alpine` (runtime)
  - **Go**: `golang:1.22` (build) -> `gcr.io/distroless/base-debian12`
- **Multi-Component Repos**:
  - If the repo has multiple `Dockerfile`s or `cloudbuild.yaml` files (e.g., `src/train/`, `src/finetuning/`, `src/serve/`, `src/frontend/`), verify each component's container build or declarative manifest (`service.yaml`).

---

## 3. Phase 3 Blueprints: Environment Discovery & Supporting Google Cloud Infrastructure

The generated prompt MUST instruct Antigravity to **discover existing resources first** (to avoid collisions and reuse pre-provisioned infrastructure) and then provision all supporting Google Cloud services required by the selected path.

### A. Environment Discovery & API Enablement
```bash
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="${REGION:-us-central1}"
export APP_NAME="<app-slug>"
export REPO_NAME="${APP_NAME}-repo"
export SA_NAME="${APP_NAME}-sa"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Enable core APIs (add aiplatform.googleapis.com, bigquery.googleapis.com, sqladmin.googleapis.com, container.googleapis.com as needed)
gcloud services enable \
  iam.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="${PROJECT_ID}"

# Inspect existing resources before creating new ones
gcloud artifacts repositories list --location="${REGION}" --project="${PROJECT_ID}"
gcloud run services list --region="${REGION}" --project="${PROJECT_ID}"
```

### B. Dedicated Service Account & Least-Privilege IAM
Grant only the roles needed by the workload's backing services:
- **Cloud SQL**: `roles/cloudsql.client`
- **Secret Manager**: `roles/secretmanager.secretAccessor`
- **Cloud Storage / GCS FUSE**: `roles/storage.objectAdmin`
- **Vertex AI / Gemini / MLOps**: `roles/aiplatform.user`
- **BigQuery**: `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`
- **Service-to-Service Cloud Run Invoker**: `roles/run.invoker`
- **Observability**: `roles/logging.logWriter`, `roles/cloudtrace.agent`, `roles/monitoring.metricWriter`

### C. Supporting Backing Services (Include Only What the App Uses)

1. **Artifact Registry**:
   ```bash
   gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" --project="${PROJECT_ID}" || \
   gcloud artifacts repositories create "${REPO_NAME}" --repository-format=docker --location="${REGION}" --project="${PROJECT_ID}"
   ```

2. **Cloud SQL (PostgreSQL / SQL Server / MySQL) or AlloyDB** *(for database-backed apps)*:
   - Check `gcloud sql instances list --project="${PROJECT_ID}"` first.
   - Provision `POSTGRES_15` (`--tier=db-custom-1-3840`) or `SQLSERVER_2022_STANDARD` (`--tier=db-custom-2-7680`), create the database, and export `INSTANCE_CONNECTION_NAME`.

3. **Cloud Storage Buckets & GCS FUSE** *(for static assets, datasets, or model weights)*:
   ```bash
   gcloud storage buckets describe "gs://${PROJECT_ID}-${APP_NAME}-data" || \
   gcloud storage buckets create "gs://${PROJECT_ID}-${APP_NAME}-data" --location="${REGION}" --uniform-bucket-level-access --project="${PROJECT_ID}"
   ```

4. **Secret Manager** *(for DB connection strings, API keys, `HF_TOKEN`, etc.)*:
   ```bash
   printf "%s" "${SECRET_VALUE}" | gcloud secrets create "${SECRET_NAME}" --data-file=- --replication-policy="automatic" --project="${PROJECT_ID}" || \
   printf "%s" "${SECRET_VALUE}" | gcloud secrets versions add "${SECRET_NAME}" --data-file=- --project="${PROJECT_ID}"
   ```

5. **Existing Repo Setup Scripts**:
   - If the repository already includes infrastructure scripts cited in the report (e.g., `scripts/setup_iam.sh`, `scripts/setup_storage.sh`, `scripts/setup_network.sh`), inspect them, make them idempotent, and execute or adapt them rather than duplicating conflicting resource names.

---

## 4. Phase 4 Blueprints: Target Compute Deployment & Org-Policy-Safe Verification

### A. Deploy to Target Compute
- **Cloud Run Service (Single Container)**:
  - Build with `gcloud builds submit --tag "${IMAGE_URI}"` and deploy with `gcloud run deploy "${APP_NAME}" --image="${IMAGE_URI}" --region="${REGION}" --service-account="${SA_EMAIL}"` (plus `--add-cloudsql-instances` or `--add-volume` / `--add-volume-mount` for GCS FUSE as applicable).
- **Cloud Run Multi-Container / Knative Manifest (`service.yaml`)**:
  - Replace template variables and deploy with `gcloud run services replace service.yaml --region="${REGION}"`.
- **Cloud Run Jobs**:
  - Deploy with `gcloud run jobs deploy "${JOB_NAME}" --image="${IMAGE_URI}" --region="${REGION}"` and test execution with `gcloud run jobs execute "${JOB_NAME}" --region="${REGION}" --wait`.
- **Vertex AI Pipelines / Custom Training / Endpoints**:
  - Compile the pipeline (`dsl.compiler.Compiler().compile(...)`), submit via `aiplatform.PipelineJob(...).submit()` or `gcloud ai custom-jobs create`, and verify endpoint readiness via `gcloud ai endpoints list --region="${REGION}"`.
- **Google Kubernetes Engine (GKE)**:
  - Create/connect to GKE Autopilot or Standard cluster, apply Kubernetes manifests (`Deployment`, `Service`, `Job`), and wait for external IP readiness.

### B. Org-Policy Resilience (`--allow-unauthenticated` Fallback)
- Attempt `--allow-unauthenticated` if public demo access is desired.
- **If an Organization Policy (`constraints/iam.allowedPolicyMemberDomains`) blocks `allUsers`**:
  - Do not fail! Grant `roles/run.invoker` to the active user account and test all endpoints using an identity token:
    ```bash
    TOKEN="$(gcloud auth print-identity-token)"
    curl -s -H "Authorization: Bearer ${TOKEN}" "${SERVICE_URL}"
    ```
  - Or start `gcloud run services proxy "${APP_NAME}" --region="${REGION}" --port=8080` for local browser testing.

### C. Self-Healing & Verification Loop
- If any build, job, or service startup fails, inspect logs (`gcloud builds log`, `gcloud beta run services logs read`, or `gcloud ai custom-jobs stream-logs`), fix the code/config, and redeploy until healthy.
- Verify every primary route or pipeline stage identified in the `codmod` report and output a final summary mapping each report recommendation to the implemented code changes and live Google Cloud resources.
