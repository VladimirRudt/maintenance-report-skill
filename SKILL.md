---
name: dotnet-maintenance-report
description: Assess the local .NET workspace's NuGet dependencies against their latest available versions and, if a boilerplate repository is configured, compare the architectural approaches/technologies used (mapping, EF configuration, DI, logging, etc.) against that reference project, then produce a Maintenance Report showing outdated libraries, infrastructure drift from the boilerplate, and how difficult each upgrade/migration would be.
---

# .NET Dependency Maintenance Report Analyzer

## Objective
Evaluate the current state of the local .NET repository (the workspace this skill is run in): which dependencies are outdated, which architectural approaches/technologies diverge from the team's boilerplate/reference project (when available), and how difficult it would be to migrate each one to its latest version or to the boilerplate's approach. Produce a structured Maintenance Report.

## Inputs Required
* `target_repo`: the local workspace/repository being assessed. Use local file tools (`list_dir`, `file_search`, `grep_search`, `read_file`) directly against the workspace — no cloning needed.
* `reference_repo` (optional): `owner/boilerplate-repo-name` — the team's remote boilerplate/reference project whose architectural approaches (not just package versions) represent the desired baseline. Only usable if a GitHub MCP tool (or equivalent remote repo access) is configured.
  * Before Step 4, check whether such a tool is available (e.g. via `tool_search` for GitHub MCP tools). If none is configured or `reference_repo` is not supplied, skip Step 4 entirely — state this limitation explicitly in the report's Executive Summary.

## Workflow Steps

### Step 1: Run the Audit Script (mandatory starting point)
Always start the analysis by running [scripts/audit.ps1](scripts/audit.ps1) against `target_repo`, e.g.:
```powershell
./scripts/audit.ps1 -Path <target_solution>
```
This wraps `dotnet list package --outdated` and `--vulnerable` and returns a JSON array of package groups, each with `package`/`prefix`, `currentVersion`, `latestVersion`, `isVulnerable`, and affected `projects`. Use this JSON as the authoritative source for current vs. latest versions and vulnerability flags — do not re-derive these by hand. Treat any `isVulnerable: true` entry as an automatic High priority regardless of migration effort tier.

### Step 2: Discover Dependency Manifests
Use local file tools (`file_search` / `list_dir`) in the workspace to locate the manifests backing the audit results, for context on how versions are declared:
1. All `.csproj` files and any `Directory.Packages.props` (Central Package Management).
2. `Directory.Build.props` for shared/global settings (e.g., `<TargetFramework>`, analyzers).
3. Lock files (`packages.lock.json`) if present, for exact resolved versions.

### Step 3: Cross-check the Manifests
Use `read_file` to read the manifests found in Step 2 and confirm/enrich the audit script's inventory with:
* Target framework(s) per project.
* Whether versions are centrally managed or scattered per-project (a maintenance smell on its own).
If `audit.ps1` cannot run (e.g. `dotnet` unavailable), fall back to manually inventorying versions from these manifests and flag versions as "verify on nuget.org" when the latest version is uncertain — never fabricate a specific version number.

### Step 4: Compare Architectural Approaches Against Reference Boilerplate (optional, requires remote repo access)
If `reference_repo` is supplied and a GitHub MCP (or equivalent) tool is available, inspect it to identify which *technologies and patterns* it uses across the codebase, then compare those approaches against `target_repo` — this is about technology choice and pattern alignment, not raw package version numbers. Do not limit the comparison to a fixed checklist; survey both repos broadly (project structure, folder conventions, `Program.cs`/`Startup.cs`, DI registration modules, `.csproj`/`.props` files) and report on whatever concerns actually diverge. Common examples across different layers include, but are not limited to:
* **Data Access:** object mapping (`Mapperly`/`Mapster`/`AutoMapper`/manual), EF Core configuration style (fluent `IEntityTypeConfiguration<T>` vs. data annotations), repository/unit-of-work patterns vs. direct `DbContext` usage, migration conventions.
* **Cross-Cutting Infrastructure:** DI container usage and registration conventions, logging/observability stack (structured logging, OpenTelemetry vs. ad-hoc logging), validation approach (`FluentValidation` vs. data annotations vs. hand-rolled), caching strategy, resilience/retry policies (`Polly` vs. none).
* **API & Messaging:** minimal APIs vs. controllers, API versioning approach, request/response contract patterns (MediatR/CQRS vs. direct service calls), messaging/eventing infrastructure (message bus choice, outbox pattern presence).
* **Testing & Quality:** test framework choice (xUnit/NUnit/MSTest), mocking library, integration test setup (Testcontainers vs. in-memory), analyzer/linting configuration.
* **Build, Deployment & Orchestration:** solution/project layout, Central Package Management adoption, containerization approach (Dockerfile conventions), CI pipeline structure, orchestration (.NET Aspire vs. none).
* **Authentication & Authorization:** auth middleware/library choice, policy-based vs. role-based authorization conventions.
* Identify each divergence you actually find as an **infrastructure drift** item: what pattern the boilerplate uses, what pattern `target_repo` currently uses, and why the drift matters (maintainability, consistency across teams, onboarding cost). Only report concerns where a real difference exists — do not force every category above into the output.

For each infrastructure drift item, outline a remediation path:
* **Current Approach:** technology/pattern in `target_repo` with representative file references.
* **Target Approach:** technology/pattern used in the boilerplate.
* **Migration Path:** concrete steps to move from current to target (e.g., introduce the new library, migrate mapping profiles incrementally per module, run both side-by-side during transition, remove the old dependency once call sites are migrated).
* **Effort Tier:** Low/Medium/High, based on how many files/modules touch the diverging pattern and whether the migration can be done incrementally or requires a big-bang cutover.

If no remote tool is configured or `reference_repo` is omitted, skip this step and omit the "Infrastructure Drift" section from the report.

### Step 5: Migration Difficulty Analysis (dependency versions)
For each outdated or out-of-sync package (from the Step 1 audit results), estimate migration difficulty by inspecting actual usage (`grep_search` / `read_file` on call sites of that package's APIs in the local `target_repo`):
* **Low Effort:** Patch/minor bump, no known breaking changes, version-only update in the manifest.
* **Medium Effort:** Minor/major bump with a few call-site signature changes, config schema updates, or renamed APIs affecting a handful of files.
* **High Effort:** Major version bump with breaking API/behavioral changes, obsolete API removal, or changes that ripple across many files/modules (e.g., logging framework replacement, DI container change, serializer swap).
Base the effort tier on: number of files referencing the package, whether the package's changelog/release notes indicate breaking changes, and whether the API surface used by the repo has changed.

## Output Format Template

Generate the final maintenance report strictly using the following format:

```markdown
# 📊 .NET Dependency Maintenance Report

**Target Repository (local):** {target_repo}
**Reference Boilerplate:** {reference_repo | "N/A – no boilerplate configured, compared against latest NuGet versions only"}
**Assessment Date:** {current_date}

## 1. Executive Summary
Overall health rating (Up to Date / Needs Maintenance / Outdated), any vulnerable packages requiring urgent action, key infrastructure drift items, the top 3 priorities, and a note if boilerplate comparison was skipped (no `reference_repo` or no remote repo tool configured).

## 2. Dependency Version Matrix

| Package | Current Version | Latest Version | Vulnerable | Status | Migration Effort |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `Serilog` | 2.10.0 | 4.1.0 | No | ❌ Outdated | **Medium (2-4h)** |
| `OpenTelemetry` | 1.6.0 | 1.9.0 | No | ⚠️ Minor Drift | **Low (<1h)** |
| `MediatR` | 12.0.0 | 12.0.0 | No | ✅ Up to Date | **None** |
| `System.Text.Json` | 6.0.0 | 8.0.5 | ⚠️ **Yes** | ❌ Vulnerable & Outdated | **Low (<1h)** |

## 3. Migration Difficulty Breakdown

### 🔹 Package: [e.g., Serilog 2.10.0 → 4.1.0]
* **Current Usage:** N files reference `ILogger`/`Log.*` APIs affected by the bump.
* **Breaking Changes:** List known breaking changes from release notes (e.g., sink configuration API changes).
* **Required Changes:** Manifest version bump; update sink registration in `Program.cs`; update configuration schema in `appsettings.json`.
* **Effort Tier & Rationale:** Medium — isolated to logging bootstrap and config, no domain logic impact.

## 4. Infrastructure Drift vs. Boilerplate

_List one entry per divergence actually found; concerns can span data access, DI, logging, validation, API style, testing, build/deploy, auth, or anything else that differs — not limited to the example below._

### 🔹 Concern: [e.g., Object Mapping]
* **Current Approach (target_repo):** Manual mapping methods scattered across N service classes.
* **Boilerplate Approach:** `Mapperly` source-generated mappers with one `*Mapper` class per aggregate.
* **Why It Matters:** Inconsistent mapping logic increases bug risk and diverges from team conventions, raising onboarding cost.
* **Migration Path:** Introduce `Mapperly`, migrate one module's mappings at a time behind existing method signatures, remove manual mapping code once verified.
* **Effort Tier & Rationale:** Medium — mechanical but touches many files; can be done incrementally per module.

## 5. Recommended Next Steps
Numbered list of prioritized tasks (dependency upgrades and infrastructure drift remediation combined), vulnerable packages first, then ordered by risk/effort ascending (quick wins first).
```
