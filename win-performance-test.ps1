# FastPing Performance Test Script
# Save as: fastping-speedtest.ps1

param(
    [int]$Requests = 20,
    [string]$ApiKey = "ak_071ccfc7cb6beb451eb6b6987be806ff",
    [string]$BaseUrl = "http://161.35.248.233"
)

Write-Host "🚀 FastPing Performance Test" -ForegroundColor Green
Write-Host "Testing $Requests requests per endpoint..." -ForegroundColor Yellow
Write-Host ""

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [hashtable]$Headers = @{},
        [int]$Count = 20
    )
    
    Write-Host "📊 Testing: $Name" -ForegroundColor Cyan
    $times = @()
    $errors = 0
    
    for ($i = 1; $i -le $Count; $i++) {
        try {
            $time = Measure-Command { 
                if ($Headers.Count -gt 0) {
                    $response = curl -H "Authorization: $($Headers.Authorization)" $Url -s
                } else {
                    $response = curl $Url -s
                }
            }
            $times += $time.TotalMilliseconds
            Write-Host "." -NoNewline -ForegroundColor Green
        } catch {
            $errors++
            Write-Host "X" -NoNewline -ForegroundColor Red
        }
        
        if ($i % 10 -eq 0) { Write-Host " $i/$Count" }
    }
    
    Write-Host ""
    
    if ($times.Count -gt 0) {
        $avg = ($times | Measure-Object -Average).Average
        $min = ($times | Measure-Object -Minimum).Minimum
        $max = ($times | Measure-Object -Maximum).Maximum
        
        Write-Host "   ✅ Average: $([math]::Round($avg, 2))ms" -ForegroundColor Green
        Write-Host "   ⚡ Fastest: $([math]::Round($min, 2))ms" -ForegroundColor Green
        Write-Host "   🐌 Slowest: $([math]::Round($max, 2))ms" -ForegroundColor Yellow
        Write-Host "   ❌ Errors:  $errors/$Count" -ForegroundColor $(if($errors -gt 0){"Red"}else{"Green"})
        
        return @{
            Name = $Name
            Average = $avg
            Min = $min
            Max = $max
            Errors = $errors
            Success = $Count - $errors
        }
    } else {
        Write-Host "   ❌ All requests failed!" -ForegroundColor Red
        return @{
            Name = $Name
            Average = 0
            Min = 0
            Max = 0
            Errors = $Count
            Success = 0
        }
    }
    
    Write-Host ""
}

# Test Results Storage
$results = @()

# Test 1: Health Check
$results += Test-Endpoint -Name "Health Check" -Url "$BaseUrl/health" -Count $Requests

# Test 2: Proxy Test (Whitelisted)
$results += Test-Endpoint -Name "Proxy Test" -Url "$BaseUrl/proxy-test" -Count $Requests

# Test 3: JSON Format
$results += Test-Endpoint -Name "JSON Format" -Url "$BaseUrl/json" -Count $Requests

# Test 4: HTML Format  
$results += Test-Endpoint -Name "HTML Format" -Url "$BaseUrl/html" -Count $Requests

# Test 5: API Ping (Authenticated)
$headers = @{ Authorization = "Bearer $ApiKey" }
$results += Test-Endpoint -Name "API Ping" -Url "$BaseUrl/api/v1/ping" -Headers $headers -Count $Requests

# Test 6: API Proxy Test (Authenticated)
$results += Test-Endpoint -Name "API Proxy Test" -Url "$BaseUrl/api/v1/proxy-test" -Headers $headers -Count $Requests

# Summary Report
Write-Host "📈 PERFORMANCE SUMMARY" -ForegroundColor Magenta
Write-Host "=====================" -ForegroundColor Magenta

$table = $results | ForEach-Object {
    [PSCustomObject]@{
        Endpoint = $_.Name
        'Avg (ms)' = [math]::Round($_.Average, 1)
        'Min (ms)' = [math]::Round($_.Min, 1)
        'Max (ms)' = [math]::Round($_.Max, 1)
        'Success Rate' = "$($_.Success)/$($_.Success + $_.Errors)"
        Rating = if ($_.Average -lt 50) { "🚀 Excellent" } 
                elseif ($_.Average -lt 100) { "✅ Good" }
                elseif ($_.Average -lt 200) { "⚠️ Acceptable" }
                else { "🐌 Slow" }
    }
}

$table | Format-Table -AutoSize

# Overall Performance Rating
$avgAll = ($results | Where-Object {$_.Success -gt 0} | ForEach-Object {$_.Average} | Measure-Object -Average).Average
Write-Host "🎯 OVERALL AVERAGE: $([math]::Round($avgAll, 1))ms" -ForegroundColor $(
    if ($avgAll -lt 50) { "Green" }
    elseif ($avgAll -lt 100) { "Green" }
    elseif ($avgAll -lt 200) { "Yellow" }
    else { "Red" }
)

# Performance Recommendations
Write-Host ""
Write-Host "💡 RECOMMENDATIONS:" -ForegroundColor Blue
if ($avgAll -lt 50) {
    Write-Host "   🏆 OUTSTANDING! Your service is blazing fast!" -ForegroundColor Green
} elseif ($avgAll -lt 100) {
    Write-Host "   ✅ EXCELLENT! Production-ready performance." -ForegroundColor Green
} elseif ($avgAll -lt 200) {
    Write-Host "   ⚠️ GOOD but could be faster. Consider optimizations." -ForegroundColor Yellow
} else {
    Write-Host "   🔧 NEEDS OPTIMIZATION! Consider caching, CDN, or server upgrades." -ForegroundColor Red
}

# Test different load levels
Write-Host ""
Write-Host "🔥 STRESS TEST (10 concurrent requests)" -ForegroundColor Red

$stressResults = @()
for ($i = 1; $i -le 10; $i++) {
    $job = Start-Job -ScriptBlock {
        param($url)
        $time = Measure-Command { curl $using:BaseUrl/proxy-test -s }
        return $time.TotalMilliseconds
    } -ArgumentList $BaseUrl
    $stressResults += $job
}

$stressTimes = @()
foreach ($job in $stressResults) {
    $result = Receive-Job $job -Wait
    $stressTimes += $result
    Remove-Job $job
}

$stressAvg = ($stressTimes | Measure-Object -Average).Average
Write-Host "   📊 Concurrent Average: $([math]::Round($stressAvg, 1))ms" -ForegroundColor $(
    if ($stressAvg -lt 100) { "Green" } else { "Yellow" }
)

Write-Host ""
Write-Host "✅ Speed test complete!" -ForegroundColor Green