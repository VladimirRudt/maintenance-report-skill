param(
    [Parameter(Position=0)]
    [string]$Path,

    [Parameter(Position=1)]
    [string]$OutputPath
)

# Execute CLI commands with target path and JSON formatting
$outdatedJson = dotnet list $Path package --outdated --include-transitive --format json | ConvertFrom-Json
$vulnerableJson = dotnet list $Path package --vulnerable --include-transitive --format json | ConvertFrom-Json

$packagesMap = @{}

function Merge-PackageData($data, [bool]$isVulnerable) {
    if (-not $data.projects) { return }
    foreach ($project in $data.projects) {
        foreach ($fw in $project.frameworks) {
            $allPkgs = @()
            if ($fw.topLevelPackages) { $allPkgs += $fw.topLevelPackages }
            if ($fw.transitivePackages) { $allPkgs += $fw.transitivePackages }

            foreach ($pkg in $allPkgs) {
                $key = $pkg.id
                if (-not $packagesMap.ContainsKey($key)) {
                    $packagesMap[$key] = [ordered]@{
                        package        = $pkg.id
                        currentVersion = $pkg.resolvedVersion
                        latestVersion  = $pkg.latestVersion
                        isVulnerable   = $isVulnerable
                        projects       = [System.Collections.Generic.List[string]]::new()
                    }
                }

                $entry = $packagesMap[$key]
                if ($pkg.latestVersion) { $entry.latestVersion = $pkg.latestVersion }
                if ($isVulnerable) { $entry.isVulnerable = $true }
                # Use the project file name only, not its full/nested path
                $projectName = Split-Path -Leaf $project.path
                if (-not $entry.projects.Contains($projectName)) {
                    $entry.projects.Add($projectName)
                }
            }
        }
    }
}

Merge-PackageData -data $outdatedJson -isVulnerable $false
Merge-PackageData -data $vulnerableJson -isVulnerable $true

# Packages sharing the same latest version and a common name prefix are usually updated together
function Get-PackageNamespace([string]$packageId) {
    return ($packageId -split '\.')[0]
}

function Get-CommonPrefix([string[]]$packageIds) {
    $segmentLists = @($packageIds | ForEach-Object { , ($_ -split '\.') })
    $minSegments = ($segmentLists | ForEach-Object { $_.Count } | Measure-Object -Minimum).Minimum
    $commonSegments = @()
    for ($i = 0; $i -lt $minSegments; $i++) {
        $segment = $segmentLists[0][$i]
        if (($segmentLists | Where-Object { $_[$i] -ne $segment }).Count -gt 0) { break }
        $commonSegments += $segment
    }
    return $commonSegments -join '.'
}

$groupsMap = [ordered]@{}
foreach ($entry in $packagesMap.Values) {
    $namespace = Get-PackageNamespace $entry.package
    $groupKey = "$($entry.latestVersion)|$namespace"
    if (-not $groupsMap.Contains($groupKey)) {
        $groupsMap[$groupKey] = [ordered]@{
            currentVersion = [System.Collections.Generic.List[string]]::new()
            latestVersion  = $entry.latestVersion
            isVulnerable   = $false
            projects       = [System.Collections.Generic.List[string]]::new()
            packages       = [System.Collections.Generic.List[string]]::new()
        }
    }

    $group = $groupsMap[$groupKey]
    if (-not $group.currentVersion.Contains($entry.currentVersion)) { $group.currentVersion.Add($entry.currentVersion) }
    if ($entry.isVulnerable) { $group.isVulnerable = $true }
    $group.packages.Add($entry.package)
    foreach ($project in $entry.projects) {
        if (-not $group.projects.Contains($project)) { $group.projects.Add($project) }
    }
}

# Collapse single-value version lists and single-package groups for readability
$result = foreach ($group in $groupsMap.Values) {
    if ($group.currentVersion.Count -eq 1) { $group.currentVersion = $group.currentVersion[0] }

    $output = [ordered]@{
        currentVersion = $group.currentVersion
        latestVersion  = $group.latestVersion
        isVulnerable   = $group.isVulnerable
        projects       = $group.projects
    }
    if ($group.packages.Count -eq 1) {
        $output.package = $group.packages[0]
    } else {
        $output.prefix = Get-CommonPrefix $group.packages
        $output.includedPackages = $group.packages
    }
    $output
}

# Render as a markdown table, sorted by package/prefix name
$sorted = $result | Sort-Object { if ($_.package) { $_.package } else { "$($_.prefix).*" } }

function Format-VersionCell($version) {
    if ($version -is [System.Collections.Generic.List[string]]) { return ($version -join ', ') }
    return $version
}

function Build-Table($rows) {
    $tableLines = @()
    $tableLines += '| Package | Current Version | Latest Version | Vulnerable | Projects |'
    $tableLines += '| :--- | :--- | :--- | :--- | :--- |'
    foreach ($row in $rows) {
        $name = if ($row.package) { $row.package } else { "$($row.prefix).* ($($row.includedPackages -join ', '))" }
        $current = Format-VersionCell $row.currentVersion
        $vulnerable = if ($row.isVulnerable) { 'Yes' } else { 'No' }
        $projects = $row.projects -join ', '
        $tableLines += "| $name | $current | $($row.latestVersion) | $vulnerable | $projects |"
    }
    return $tableLines -join "`n"
}

# Resolve default output path next to the target (file or directory)
if (-not $OutputPath) {
    $resolvedTarget = Resolve-Path $Path -ErrorAction SilentlyContinue
    if ($resolvedTarget -and (Test-Path $resolvedTarget -PathType Leaf)) {
        $reportDir = Split-Path -Parent $resolvedTarget
    } elseif ($resolvedTarget) {
        $reportDir = $resolvedTarget
    } else {
        $reportDir = Get-Location
    }
    $OutputPath = Join-Path $reportDir 'audit-report.md'
}

$fullTable = if ($sorted.Count -eq 0) {
    "All packages are up to date and no vulnerabilities were found."
} else {
    Build-Table $sorted
}
"# Dependency Audit Report`n`n$fullTable" | Set-Content -Path $OutputPath -Encoding utf8

# Return all packages; the full list is also saved to $OutputPath for later reference
$fullTable
