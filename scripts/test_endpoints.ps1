# FeedSpine API Endpoint Test Script
# Run against localhost:8300 (docker) or localhost:8765 (local dev)

param(
    [string]$BaseUrl = "http://localhost:8300",
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "FeedSpine API Endpoint Test Suite" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$results = @()

function Test-Endpoint {
    param(
        [string]$Method,
        [string]$Path,
        [string]$Description,
        [hashtable]$Body = $null,
        [int]$ExpectedStatus = 200
    )
    
    $url = "$BaseUrl$Path"
    $result = @{
        Method = $Method
        Path = $Path
        Description = $Description
        Status = $null
        Success = $false
        Response = $null
        Error = $null
    }
    
    try {
        $params = @{
            Uri = $url
            Method = $Method
            ContentType = "application/json"
        }
        
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json -Depth 10)
        }
        
        $response = Invoke-RestMethod @params
        $result.Status = 200
        $result.Success = $true
        $result.Response = $response
        
        $statusIcon = "✓"
        $color = "Green"
        Write-Host "$statusIcon $Method $Path - $Description" -ForegroundColor $color
        
        if ($Verbose -and $response) {
            $response | ConvertTo-Json -Depth 3 -Compress | Write-Host -ForegroundColor DarkGray
        }
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $result.Status = $statusCode
        $result.Error = $_.Exception.Message
        
        if ($statusCode -eq $ExpectedStatus) {
            $result.Success = $true
            $statusIcon = "✓"
            $color = "Green"
        } else {
            $statusIcon = "✗"
            $color = "Red"
        }
        
        Write-Host "$statusIcon $Method $Path - $Description (HTTP $statusCode)" -ForegroundColor $color
        
        if ($Verbose) {
            Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor DarkGray
        }
    }
    
    return $result
}

Write-Host "--- Health Endpoints ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/" -Description "Root/welcome"
$results += Test-Endpoint -Method "GET" -Path "/health" -Description "Health check"
$results += Test-Endpoint -Method "GET" -Path "/health/live" -Description "Liveness probe"
$results += Test-Endpoint -Method "GET" -Path "/health/ready" -Description "Readiness probe"

Write-Host "`n--- Records Endpoints ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/records" -Description "List records"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/records/by-key/test-key" -Description "Get record by key" -ExpectedStatus 404

Write-Host "`n--- Feeds Endpoints ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/feeds" -Description "List feeds"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/health/feeds" -Description "Feed health summary"

Write-Host "`n--- Stats Endpoints ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/stats" -Description "Stats overview"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/stats/summary" -Description "Stats summary"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/stats/collection" -Description "Collection stats"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/stats/records" -Description "Record stats"

Write-Host "`n--- Runs Endpoints ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/runs" -Description "List runs"

Write-Host "`n--- Schedule Endpoints ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/schedules/" -Description "List schedules"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/schedules/due" -Description "Due schedules"

Write-Host "`n--- Enrichment Endpoints ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/enrich/enrichers" -Description "List enrichers"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/enrich/jobs" -Description "List enrich jobs"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/enrich/stats" -Description "Enrichment stats"

Write-Host "`n--- Storage Endpoints ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/storage/status" -Description "Storage status"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/storage/backends" -Description "Available backends"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/storage/health" -Description "Storage health"

Write-Host "`n--- Feed Timeline ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/feed" -Description "Unified feed timeline"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/feed/sources" -Description "Feed sources"

Write-Host "`n--- Syndication ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/syndication/rss" -Description "RSS feed"
$results += Test-Endpoint -Method "GET" -Path "/api/v1/syndication/atom" -Description "Atom feed"

Write-Host "`n--- Search ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/search?q=test" -Description "Search records"

Write-Host "`n--- Observations ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/observations" -Description "List observations"

Write-Host "`n--- Sightings ---" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Path "/api/v1/sightings" -Description "List sightings"

# Summary
$passed = ($results | Where-Object { $_.Success }).Count
$failed = ($results | Where-Object { -not $_.Success }).Count
$total = $results.Count

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total:  $total" -ForegroundColor White
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host "Score:  $([math]::Round($passed / $total * 100, 1))%" -ForegroundColor $(if ($failed -gt 0) { "Yellow" } else { "Green" })

if ($failed -gt 0) {
    Write-Host "`nFailed endpoints:" -ForegroundColor Red
    $results | Where-Object { -not $_.Success } | ForEach-Object {
        Write-Host "  - $($_.Method) $($_.Path): HTTP $($_.Status)" -ForegroundColor Red
    }
}

exit $failed
