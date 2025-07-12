from pythonping import ping

def do_ping(host: str, timeout: float = 1.0) -> float:
    """Return round-trip time in ms or -1 on failure."""
    try:
        resp = ping(host, count=1, timeout=timeout, size=32)
        return resp.rtt_avg_ms if resp.success() else -1.0
    except Exception:
        return -1.0
