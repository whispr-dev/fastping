$ $$ $times = @()
for ($i=1; $i -le 10; $i++) {
    $time = Measure-Command {
        curl -H "Authorization: Bearer ak_071ccfc7cb6beb451eb6b6987be806ff" http://161.35.248.233/api/v1/ping                                                                                             }
    $times += $time.TotalMilliseconds
    Write-Host "Request $i : $($time.TotalMilliseconds)ms"
}
Write-Host "Average: $(($times | Measure-Object -Average).Average)ms"