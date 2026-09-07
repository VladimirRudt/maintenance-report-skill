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
