param(
    # Pass -Framework when the target repo is (or includes) classic .NET Framework
    # projects: swaps the .NET Core/5+ "breaking-changes.md" index pages for the
    # dotnet/docs migration-guide docs that cover Framework retargeting/compat instead.
    [switch]$Framework
)

if ($Framework) {
    $uri = "https://api.github.com/repos/dotnet/docs/git/trees/main?recursive=1"
    $response = Invoke-RestMethod -Uri $uri -Method Get -Headers @{ "User-Agent" = "PowerShellScript"; "Accept" = "application/vnd.github+json" }
    $response.tree | Where-Object { $_.type -eq "blob" -and $_.path -like "docs/framework/migration-guide/*" -and $_.path -like "*.md" } | ForEach-Object {
        "FileName     : $(Split-Path $_.path -Leaf)"
        "RepoFullPath : $($_.path)"
        "HtmlUrl      : https://github.com/dotnet/docs/blob/main/$($_.path)"
    }
    return
}

$uri = "https://api.github.com/repos/dotnet/docs/git/trees/main?recursive=1"
$response = Invoke-RestMethod -Uri $uri -Method Get -Headers @{ "User-Agent" = "PowerShellScript"; "Accept" = "application/vnd.github+json" }
$response.tree | Where-Object { $_.type -eq "blob" -and (Split-Path $_.path -Leaf) -eq "breaking-changes.md" } | ForEach-Object {
    "FileName     : $(Split-Path $_.path -Leaf)"
    "RepoFullPath : $($_.path)"
    "HtmlUrl      : https://github.com/dotnet/docs/blob/main/$($_.path)"
}

$uri = "https://api.github.com/repos/dotnet/EntityFramework.Docs/git/trees/main?recursive=1"
$response = Invoke-RestMethod -Uri $uri -Method Get -Headers @{ "User-Agent" = "PowerShellScript"; "Accept" = "application/vnd.github+json" }
$response.tree | Where-Object { $_.type -eq "blob" -and (Split-Path $_.path -Leaf) -eq "breaking-changes.md" } | ForEach-Object {
    "FileName     : $(Split-Path $_.path -Leaf)"
    "RepoFullPath : $($_.path)"
    "HtmlUrl      : https://github.com/dotnet/EntityFramework.Docs/blob/main/$($_.path)"
}
