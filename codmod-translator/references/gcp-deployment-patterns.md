# 4-Phase Modernization & Deployment Plan Blueprint

Use this structure and these operational guardrails when generating `./modernization-plan/modernization-execution-plan.md` in Step 3. Derive all languages, frameworks, architecture changes, and Google Cloud services directly from the `codmod` report and the target repository.

---

## Plan Structure (`modernization-execution-plan.md`)

Write the file as a self-contained, copy-pasteable `/goal` prompt with this structure:

```markdown
/goal Act as a Senior Cloud Architect and Modernization Engineer. Execute the selected modernization strategy from @modernization-plan/report-extracts/codmod-summary.md [and @modernization-plan/report-extracts/codmod-selected-path.md] end-to-end across all four phases below. Do not stop until the modernized workload and its supporting services are deployed and verified on Google Cloud.
```

### Phase 1: Code, Data Layer, & Architecture Refactoring
- **Ground in Exact Files**: List the specific source files, configs, and scripts cited in the report's footnotes/tables (verified against the repository workspace) and the concrete changes required for each.
- **Apply Report Recommendations**: Implement the runtime/dependency upgrades, dependency locking, data-access changes, or component decoupling (e.g., separating synchronous UI/API layers from asynchronous background/batch jobs) recommended by the selected strategy.
- **Cloud-Native Readiness**:
  - Externalize hardcoded configuration, connection strings, and credentials to environment variables and **Secret Manager**.
  - Replace local mutable filesystem dependencies with the selected cloud storage or database services.
  - Ensure network services bind to `0.0.0.0:${PORT:-8080}`, emit structured logs to `stdout`/`stderr`, and handle `SIGTERM` gracefully.

### Phase 2: Containerization, Manifests, & Local Build Verification
- Create or update build and deployment artifacts (`Dockerfile`, `.dockerignore`, multi-service manifests, pipeline definitions, or VM startup scripts) matching the target runtime and compute platform from the report.
- Verify that the application builds, compiles, or passes syntax/container checks locally before provisioning cloud infrastructure.

### Phase 3: GCP Environment Discovery & Supporting Infrastructure
- **Discover Before Creating**: Always inspect the active project and region first (`gcloud config get-value project`, existing Artifact Registry repos, storage buckets, database instances, clusters, or services) to reuse pre-existing resources and avoid naming collisions.
- **Idempotent Setup**:
  - Enable only the Google Cloud APIs required by the selected compute target and backing services.
  - Create a dedicated Service Account with least-privilege IAM roles scoped strictly to the services used by the workload.
  - Provision (or reuse) the selected backing services idempotently (`describe || create`) and seed any sample/initial datasets required for verification.
  - If the repository already contains infrastructure scripts or IaC cited in the report, make them idempotent and adapt them rather than duplicating resources.

### Phase 4: Target Deployment, Self-Healing, & Verification
- **Deploy to Selected Compute Target**: Build and deploy the workload to the user's chosen Google Cloud target, wired to the Service Account, secrets, and backing services provisioned in Phase 3.
- **Just-in-Time Official Docs (MCP)**: Whenever **Google Developer Knowledge MCP** tools (`search_documents` / `get_document`) are available, use them to verify the latest `gcloud` CLI flags, IAM roles, and client SDK patterns or to troubleshoot unfamiliar cloud errors rather than guessing flags from training data.
- **Self-Healing Loop**: If any build, deployment, startup, or batch job fails, pull the relevant cloud build or runtime logs, fix the root cause in code or configuration, and redeploy until healthy.
- **Org-Policy-Safe Verification**:
  - If public access (`--allow-unauthenticated`) is blocked by an Organization Policy (`constraints/iam.allowedPolicyMemberDomains`), do not fail the deployment. Grant invoker permissions to the active identity and verify endpoints using `Authorization: Bearer $(gcloud auth print-identity-token)` (or document local proxy access such as `gcloud run services proxy`).
- **End-to-End Validation**: Exercise the primary application routes, UI, or batch/pipeline jobs end-to-end and conclude with a summary table mapping the `codmod` report's findings to the implemented code changes and live Google Cloud resources.
