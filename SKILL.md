---
name: dotnet-maintenance-report
description: Assess the local .NET workspace's NuGet dependencies against their latest available versions and compare the architectural approaches/technologies used (mapping, EF configuration, DI, logging, etc.) against the appropriate Saritasa .NET boilerplate (desktop or web), then produce a Maintenance Report showing outdated libraries, infrastructure drift from the boilerplate, and how difficult each upgrade/migration would be.
---

# .NET Dependency Maintenance Report Analyzer

## Objective
Evaluate the current state of the local .NET repository (the workspace this skill is run in): which dependencies are outdated, which architectural approaches/technologies diverge from the relevant Saritasa boilerplate reference project, and how difficult it would be to migrate each one to its latest version or to the boilerplate's approach. Produce a structured Maintenance Report.

## Inputs Required
* `target_repo`: the local workspace/repository being assessed. Use local file tools (`list_dir`, `file_search`, `grep_search`, `read_file`) directly against the workspace — no cloning needed.
* `reference_repo`: the boilerplate to compare against. Defaults to one of the two Saritasa .NET boilerplates below, selected automatically unless the user specifies otherwise:
  * **Web** projects (ASP.NET Core APIs, MVC, Blazor, web services): [`saritasa-nest/saritasa-dotnet-boilerplate-web`](https://github.com/saritasa-nest/saritasa-dotnet-boilerplate-web)
  * **Desktop** projects (WPF, WinForms, MAUI, Avalonia): [`saritasa-nest/saritasa-dotnet-boilerplate-desktop`](https://github.com/saritasa-nest/saritasa-dotnet-boilerplate-desktop)
  * Determine which applies by inspecting `target_repo`'s project SDKs/output types in Step 2 (e.g. `Microsoft.NET.Sdk.Web`, `UseWpf`, `UseWindowsForms`, `Microsoft.Maui` references). If the workspace contains both, or the type is ambiguous, ask the user which boilerplate to use.
  * Comparing against a boilerplate requires a GitHub MCP tool (or equivalent remote repo access).
  * Before Step 4, check whether such a tool is available (e.g. via `tool_search` for GitHub MCP tools). If none is configured, skip Step 4 entirely — state this limitation explicitly in the report's Executive Summary.

## Workflow Steps

### Step 1: Run the Audit Script (mandatory starting point)
Always start the analysis by running [scripts/audit.ps1](scripts/audit.ps1) against `target_repo`, e.g.:
```powershell
./scripts/audit.ps1 -Path <target_solution>
```
This wraps `dotnet list package --outdated` and `--vulnerable` and returns a markdown table with columns `Package`, `Current Version`, `Latest Version`, `Vulnerable`, and `Projects` (rows sharing the same latest version and package-name prefix are collapsed into one grouped row). Include this table verbatim in the report's Executive Summary section as-is — do not reformat, re-summarize, or re-derive the version/vulnerability data by hand. Treat any row with `Vulnerable: Yes` as an automatic High priority regardless of migration effort tier.

### Step 2: Discover Dependency Manifests & Determine Project Type
Use local file tools (`file_search` / `list_dir`) in the workspace to locate the manifests backing the audit results, for context on how versions are declared:
1. All `.csproj` files and any `Directory.Packages.props` (Central Package Management).
2. `Directory.Build.props` for shared/global settings (e.g., `<TargetFramework>`, analyzers).
3. Lock files (`packages.lock.json`) if present, for exact resolved versions.

While reading these, also determine whether `target_repo` is a **web** or **desktop** project (SDK type, `Sdk="Microsoft.NET.Sdk.Web"`, `UseWpf`/`UseWindowsForms`, MAUI/Avalonia references, ASP.NET Core package references) to select the matching Saritasa boilerplate (see Inputs Required) for Step 4.

### Step 3: Cross-check the Manifests & Verify .NET SDK Currency
Use `read_file` to read the manifests found in Step 2 and confirm/enrich the audit script's inventory with:
* Target framework(s) per project.
* Whether versions are centrally managed or scattered per-project (a maintenance smell on its own).
If `audit.ps1` cannot run (e.g. `dotnet` unavailable), fall back to manually inventorying versions from these manifests and flag versions as "verify on nuget.org" when the latest version is uncertain — never fabricate a specific version number.

Also check whether `target_repo` is on the latest .NET version:
* Read each `<TargetFramework>`/`<TargetFrameworks>` value and compare against the latest released .NET (e.g. `net8.0` vs. `net9.0`); if unsure of the current latest release, say so explicitly rather than guessing.
* Run `dotnet --version` (and `dotnet --list-sdks` if useful) to check the SDK installed/pinned via `global.json`, and flag if `global.json` pins an SDK older than what's installed or than the latest available.
* Note whether the current target framework is still in support (Current vs. LTS vs. out-of-support) since running an out-of-support TFM is itself a maintenance risk independent of individual package versions.
* Record this as its own finding ("Target Framework / SDK") even if no packages are outdated, since project-wide framework currency matters as much as individual dependencies.

### Step 4: Compare Architectural Approaches Against Reference Boilerplate (requires remote repo access)
If a GitHub MCP (or equivalent) tool is available, inspect the `reference_repo` selected in Step 2 (Saritasa web or desktop boilerplate, or a user-specified override) to identify which *technologies and patterns* it uses across the codebase, then compare those approaches against `target_repo` — this is about technology choice and pattern alignment, not raw package version numbers. Do not limit the comparison to a fixed checklist; survey both repos broadly (project structure, folder conventions, `Program.cs`/`Startup.cs`, DI registration modules, `.csproj`/`.props` files) and report on whatever concerns actually diverge. Common examples across different layers include, but are not limited to:
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

If no remote repo tool is configured, skip this step and omit the "Infrastructure Drift" section from the report, noting in the Executive Summary that boilerplate comparison could not be performed.

### Step 5: Migration Difficulty Analysis (dependency versions)
For each outdated or out-of-sync package (from the Step 1 audit results), estimate migration difficulty by inspecting how *this specific project* actually uses the package — do not assign a generic tier from the version jump alone:
* Use `grep_search` to find every call site referencing the package's namespaces/types/APIs in `target_repo`.
* For each call site, determine whether the specific API/overload/type used has changed, been renamed, or been removed between the current and latest version (check release notes/changelog/breaking-change docs for that package; if unavailable, reason from the package's public API surface and state the uncertainty).
* If none of the APIs actually used by `target_repo` changed (e.g. the breaking changes are in an area the project never touches), the practical effort is lower than the package's changelog would suggest on its own — note this explicitly.
* Count how many files/projects are affected, whether the changes are mechanical (find/replace) vs. requiring redesign, and whether the update can be rolled out incrementally per file or requires touching everything atomically.
Always include every outdated/vulnerable package in the difficulty table, but only add a detailed migration note underneath the table for packages that have breaking changes to address — skip notes for packages that are a simple version-only bump.
* **Low Effort:** Patch/minor bump, no known breaking changes, version-only update in the manifest, or breaking changes exist upstream but don't touch any API actually used by `target_repo`.
* **Medium Effort:** Minor/major bump where a handful of call sites use APIs affected by renamed/changed signatures, config schema updates, or a small number of files need edits.
* **High Effort:** Major version bump where APIs actually used by `target_repo` were removed/redesigned, or the affected call sites are spread across many files/modules (e.g., logging framework replacement, DI container change, serializer swap).
Do not estimate effort in hours or any other time unit — use only the Low/Medium/High tier, since time estimates from an LLM are unreliable.

## Output Format Template

Generate the final maintenance report strictly using the following format:

```markdown
# 📊 .NET Dependency Maintenance Report

**Target Repository (local):** {target_repo}
**Reference Boilerplate:** {reference_repo, e.g. "saritasa-nest/saritasa-dotnet-boilerplate-web"} | "N/A – no remote repo tool configured"}
**Assessment Date:** {current_date}

## 1. Executive Summary
Overall health rating (Up to Date / Needs Maintenance / Outdated), any vulnerable packages requiring urgent action, .NET target framework/SDK currency, key infrastructure drift items, the top 3 priorities, and a note if boilerplate comparison was skipped (no remote repo tool configured).

## 2. Dependency Audit (raw `scripts/audit.ps1` output)

{Paste the markdown table produced by scripts/audit.ps1 verbatim here.}

## 3. Target Framework & SDK Currency

| Project | Current TFM | Latest .NET | Support Status | SDK Pinned (global.json) |
| :--- | :--- | :--- | :--- | :--- |
| `MyProject.Api` | `net8.0` | `net9.0` | LTS (in support) | Not pinned |

Note any project on an out-of-support TFM or an SDK pin older than what's installed/available.

## 4. Migration Difficulty

| Package | Current Version | Latest Version | Vulnerable | Migration Effort |
| :--- | :--- | :--- | :--- | :--- |
| `Serilog` | 2.10.0 | 4.1.0 | No | **Medium** |
| `OpenTelemetry` | 1.6.0 | 1.9.0 | No | **Low** |
| `MediatR` | 12.0.0 | 12.0.0 | No | **None** |
| `System.Text.Json` | 6.0.0 | 8.0.5 | **Yes** | **Low** |

Add a note below the table only for packages that have breaking changes to address; skip notes for simple version-only bumps.

### 🔹 Package: [e.g., Serilog 2.10.0 → 4.1.0]
* **Current Usage:** N call sites across M files reference `ILogger`/`Log.*` APIs; list the specific APIs used (e.g. `LoggerConfiguration.WriteTo.File(...)`).
* **Breaking Changes Affecting This Project:** Of the package's known breaking changes, which ones touch APIs actually used here (e.g. the sink configuration API this project calls was renamed) vs. which are irrelevant (e.g. a removed API this project never called).
* **Required Changes:** Update sink registration in `Program.cs`; update configuration schema in `appsettings.json`.
* **Effort Tier & Rationale:** Medium — isolated to logging bootstrap and config, no domain logic impact; only 2 of the package's 5 breaking changes affect this repo's call sites.

## 5. Infrastructure Drift vs. Boilerplate

_List one entry per divergence actually found; concerns can span data access, DI, logging, validation, API style, testing, build/deploy, auth, or anything else that differs — not limited to the example below._

### 🔹 Concern: [e.g., Object Mapping]
* **Current Approach (target_repo):** Manual mapping methods scattered across N service classes.
* **Boilerplate Approach:** `Mapperly` source-generated mappers with one `*Mapper` class per aggregate.
* **Why It Matters:** Inconsistent mapping logic increases bug risk and diverges from team conventions, raising onboarding cost.
* **Migration Path:** Introduce `Mapperly`, migrate one module's mappings at a time behind existing method signatures, remove manual mapping code once verified.
* **Effort Tier & Rationale:** Medium — mechanical but touches many files; can be done incrementally per module.

## 6. Recommended Next Steps
Numbered list of prioritized tasks (dependency upgrades, TFM/SDK updates, and infrastructure drift remediation combined), vulnerable packages first, then ordered by risk/effort ascending (quick wins first).
```
