---
name: dotnet-maintenance-report
description: Assess a local .NET workspace's NuGet dependencies vs. latest versions and migration difficulty, optionally comparing its architecture (mapping, EF config, DI, logging, etc.) against a locally provided Saritasa .NET boilerplate (desktop or web), then produce a Maintenance Report. Confirms optional steps with the user before running them.
---

# .NET Dependency Maintenance Report Analyzer

## Objective
Assess the local repo: outdated dependencies and migration difficulty for each (mandatory), plus optionally architectural drift vs. a locally provided Saritasa boilerplate. Produce a structured report.

## Inputs
* `target_repo`: the local workspace.
* `reference_repo` (only needed for optional Step 4): a **local folder path** to a Saritasa .NET boilerplate checkout (web or desktop), supplied by the user. If the user wants Step 4 but hasn't given a path, ask for it — do not guess a path or fetch from GitHub. If no path is available, Step 4 must be skipped.

## Workflow
Steps 1–3 and 5 are mandatory and run automatically. Steps 4 and 6 are optional.

After Step 3, pause and ask the user (via ask questions tool or plain question) whether to also run Step 4 (architecture/infrastructure drift vs. a local boilerplate folder), explaining what it adds. Options: run Step 4 now (requesting the boilerplate folder path if not yet given), or skip straight to Step 5 and generate the report without it. Note the user's choice in the Executive Summary.

After Step 5, pause and ask the user whether to also run Step 6 (deep .NET/EF Core breaking-changes investigation), explaining what it adds. Options: run Step 6 now, or skip it and generate the report without it. Note the user's choice in the Executive Summary.

### Step 1: Run the Audit Script (always first)
```powershell
./scripts/audit.ps1 -Path <target_solution>
```
Wraps `dotnet list package --outdated`/`--vulnerable`, returns the full markdown table (`Package`, `Current Version`, `Latest Version`, `Vulnerable`, `Projects`; same-latest-version rows collapsed, project names shown without full paths) and also saves it to a local `audit-report.md` file next to `target_repo`. In the report, only include the vulnerable rows from this table (any `Vulnerable: Yes` row is automatically High priority) plus a link to `audit-report.md` for the full list — don't paste the whole table into the report.

### Step 2: Discover Manifests & Project Type
Find `.csproj` files, `Directory.Packages.props` (CPM), `Directory.Build.props`, lock files. Note whether `target_repo` looks like a web or desktop project (SDK/UI framework references) — useful context if Step 4 runs later.

### Step 3: Verify Manifests & Framework/SDK Currency
Read manifests to confirm target framework(s) and whether versions are centrally managed vs. scattered (a smell). If `audit.ps1` can't run, inventory versions manually and mark uncertain ones "verify on nuget.org" — never invent a version.

Also check:
* TFM vs. latest .NET release. Determine the current latest/LTS releases and support status from the official [`releases-index.json`](https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/releases-index.json) (fetch it rather than relying on local `dotnet` tooling or guessing) — it lists each channel's `latest-release`, `latest-release-date`, `support-phase` (active/lts/eol/preview), and `eol-date`.
* `dotnet --list-sdks` / `global.json` pin, compared against the SDK version for the matching channel in `releases-index.json`.
* Support status (Current/LTS/out-of-support) per the `support-phase`/`eol-date` fields above.
Report this as its own finding even if all packages are current.

### Step 4 (optional, only if user opts in): Compare Architecture vs. Boilerplate
Run only if the user chose to include it. Read `reference_repo` (the local boilerplate folder path) with `list_dir`/`read_file`, survey it broadly (structure, `Program.cs`, DI modules, `.csproj`/`.props`) and compare to `target_repo`. Not limited to a fixed list — report whatever actually diverges. Typical areas: mapping (Mapperly/Mapster/AutoMapper/manual), EF config style, repository/UoW vs. direct `DbContext`, DI conventions, logging/observability, validation, caching, resilience (Polly), API style (minimal vs. controllers, MediatR/CQRS), messaging, testing stack, CPM adoption, containerization/CI, orchestration (Aspire), auth approach.

For each drift found, give: current approach (with file refs), boilerplate approach, migration path, effort tier (Low/Medium/High based on file/module count and whether it's incremental). Only report real divergences.

If the user skipped this step, omit "Infrastructure Drift" from the report and note it in the Executive Summary as skipped by user choice.

### Step 5: Migration Difficulty (dependency versions)
For each outdated/vulnerable package from Step 1, judge difficulty from actual usage, not just version delta:
* `grep_search` for call sites using the package's namespaces/types.
* Check whether APIs actually used changed/renamed/removed between versions (via changelog/release notes, or reason from public API surface if unavailable — state uncertainty).
* If the breaking changes don't touch what this repo actually uses, effort is lower than the changelog implies alone — say so.
* Note file/project count affected and whether changes are mechanical vs. redesign, incremental vs. atomic.

Include every outdated/vulnerable package in the table; add a detailed note only for packages with breaking changes that matter here.
* **Low:** patch/minor, no relevant breaking changes, or breaking changes exist but don't touch this repo's usage.
* **Medium:** a few call sites affected by renamed/changed APIs or config schema, small file count.
* **High:** major bump removing/redesigning APIs actually used, or affects many files/modules.
No time estimates — Low/Medium/High only.

### Step 6 (optional, only if user opts in): Deep Breaking-Changes Investigation
Run only if the user chose to include it. Goes beyond Step 5's reasoning by pulling the actual official breaking-change docs and checking each one against real usage in `target_repo`.

1. Run the discovery script to get the current list of breaking-changes index docs:
   ```powershell
   ./scripts/breaking-changes.ps1
   ```
   It queries the `dotnet/docs` and `dotnet/EntityFramework.Docs` repo trees on GitHub and returns every `breaking-changes.md` file found, with `FileName`, `RepoFullPath`, and `HtmlUrl`. Each of these is an **index page** containing only a short one-line description per breaking change plus a link to the fully detailed article — it is not the detailed content itself.
2. Scope which of those index files are relevant: match doc paths/versions against the TFM(s) found in Step 3 and the packages/versions from Step 1 (e.g. only inspect `core/compatibility` or EF docs covering versions between the repo's current and latest). Skip files clearly outside the relevant version range.
3. For each relevant index file, `fetch_webpage` its `HtmlUrl` and read the short descriptions listed there. Judge from the description alone whether each entry is plausibly relevant to this repo (matches a TFM, package, or area actually in use) — only for entries that look plausibly relevant, follow the detailed link the index gives for that entry and `fetch_webpage` it to get the full breaking-change details needed to judge applicability. Don't fetch detail pages for entries the index description already rules out.
4. For each breaking change entry found:
   * `grep_search` the target repo for the affected namespaces/types/APIs/config keys mentioned.
   * Decide if it actually affects `target_repo`: cite matching file(s)/line(s) if it does, or state why it doesn't apply if it doesn't.
   * Only entries confirmed (or plausibly, if uncertain) affecting this repo are kept; discard clearly inapplicable ones rather than listing them all.
5. Feed confirmed findings back into Step 5's per-package notes (add/refine "Breaking Changes Affecting This Project", cite the source doc URL, and adjust the Effort Tier if the deep research changes the assessment).

If the user skipped this step, note it in the Executive Summary as skipped by user choice and leave Step 5's notes as originally reasoned (without official doc citations).

## Output Format

```markdown
# 📊 .NET Dependency Maintenance Report

**Target Repository (local):** {target_repo}
**Reference Boilerplate:** {reference_repo local path | "N/A – user opted to skip Step 4"}
**Assessment Date:** {current_date}

## 1. Executive Summary
Overall health (Up to Date / Needs Maintenance / Outdated), vulnerable packages, TFM/SDK currency, key drift items (if Step 4 ran), top 3 priorities, note whether the user opted to skip Step 4.

## 2. Dependency Audit
{table of only the vulnerable packages from audit.ps1's output, plus a link to the full `audit-report.md`}

## 3. Target Framework & SDK Currency

| Project | Current TFM | Latest .NET | Support Status | SDK Pinned (global.json) |
| :--- | :--- | :--- | :--- | :--- |
| `MyProject.Api` | `net8.0` | `net9.0` | LTS (in support) | Not pinned |

## 4. Migration Difficulty

| Package | Current Version | Latest Version | Vulnerable | Migration Effort |
| :--- | :--- | :--- | :--- | :--- |
| `System.Text.Json` | 6.0.0 | 8.0.5 | **Yes** | **Low** |

Notes only for packages with relevant breaking changes:

### 🔹 Package: [name, current → latest]
* **Current Usage:** call sites/files, specific APIs used.
* **Breaking Changes Affecting This Project:** which known breaking changes touch this repo's usage vs. which don't apply. If Step 6 ran, cite the official doc URL(s) backing each claim.
* **Required Changes:** concrete edits needed.
* **Effort Tier & Rationale:** tier + why.

## 5. Infrastructure Drift vs. Boilerplate
_One entry per real divergence found; not limited to a fixed category list._

### 🔹 Concern: [e.g., Object Mapping]
* **Current Approach:** e.g. manual mapping across N classes.
* **Boilerplate Approach:** e.g. Mapperly, one mapper per aggregate.
* **Why It Matters:** consistency/onboarding/maintainability impact.
* **Migration Path:** incremental steps to adopt boilerplate approach.
* **Effort Tier & Rationale:** tier + why.

## 6. Recommended Next Steps
Numbered list, vulnerable packages first, then risk/effort ascending (quick wins first).
```

If the user skipped Step 6, omit doc citations from Section 4 notes and mention the skip in the Executive Summary.
