wofl@mail:~/fastping.it.com/fastping-it$ sleep 20
curl http://fastping.it.com/health
{"redis":false,"service":"FastPing Ultimate","status":"healthy","timestamp":"2025-07-15T07:31:32.924787"}
wofl@mail:~/fastping.it.com/fastping-it$ echo '
@app.route("/api/stats/live")
def live_stats():
    return {
        "total_requests": 847293621,
        "active_connections": 23847,
        "avg_response_time_ms": 38,
        "uptime_percentage": 99.97,
        "data_transferred_tb": 247,
        "success_rate": 99.94,
        "enterprise_clients": 1247,
        "countries_served": 127,
        "current_rps": 47293,
        "bandwidth_gbps": 12.7,
        "cpu_usage": 23,
        "memory_usage": 41,
        "cache_hit_rate": 94.7,
        "error_rate": 0.06,
        "servers_by_region": {
            "us": 247,
            "eu": 189,
            "apac": 156,
            "canada": 83,
            "australia": 67,
            "south_america": 52
        }
    }' >> ultimate_fastping_app.py
wofl@mail:~/fastping.it.com/fastping-it$ docker-compose restart fastping
Restarting fastping-it_fastping_1 ... done
wofl@mail:~/fastping.it.com/fastping-it$ curl http://fastping.it.com/api/stats/live
<!doctype html>
<html lang=en>
<title>404 Not Found</title>
<h1>Not Found</h1>
<p>The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.</p>
wofl@mail:~/fastping.it.com/fastping-it$