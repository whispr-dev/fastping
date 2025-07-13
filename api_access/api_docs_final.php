<div class="content">
                <p>We provide SDKs and examples in multiple programming languages to get you started quickly.</p>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">JavaScript/Node.js</h3>
                <div class="code-block">
                    <pre>const axios = require('axios');

const client = axios.create({
  baseURL: 'https://fastping.it/api/v1',
  headers: {
    'Authorization': 'Bearer fpk_your_api_key'
  }
});

// Quick ping test
async function ping() {
  try {
    const response = await client.get('/ping');
    console.log('Response time:', response.data.response_time_ms + 'ms');
    return response.data;
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

// Full test with data
async function test(data) {
  try {
    const response = await client.post('/test', data);
    return response.data;
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

// Proxy a request
async function proxy(targetUrl) {
  try {
    const response = await client.get('/proxy', {
      params: { url: targetUrl }
    });
    return response.data;
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}</pre>
                    <button class="copy-button" onclick="copyToClipboard(this.previousElementSibling.textContent)">Copy</button>
                </div>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Python</h3>
                <div class="code-block">
                    <pre>import requests
import json

class FastPingClient:
    def __init__(self, api_key):
        self.base_url = 'https://fastping.it/api/v1'
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def ping(self):
        """Quick connectivity test"""
        response = requests.get(f'{self.base_url}/ping', headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def test(self, data=None):
        """Full proxy test"""
        response = requests.post(
            f'{self.base_url}/test', 
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def proxy(self, target_url, method='GET', data=None):
        """Proxy request to target URL"""
        params = {'url': target_url}
        
        if method.upper() == 'GET':
            response = requests.get(f'{self.base_url}/proxy', 
                                  headers=self.headers, params=params)
        else:
            response = requests.post(f'{self.base_url}/proxy',
                                   headers=self.headers, params=params, json=data)
        
        response.raise_for_status()
        return response.json()
    
    def get_stats(self):
        """Get usage statistics"""
        response = requests.get(f'{self.base_url}/stats', headers=self.headers)
        response.raise_for_status()
        return response.json()

# Usage example
client = FastPingClient('fpk_your_api_key')

# Quick ping
result = client.ping()
print(f"Response time: {result['response_time_ms']}ms")

# Get stats
stats = client.get_stats()
print(f"Requests today: {stats['current_limits']['requests_today']}")</pre>
                    <button class="copy-button" onclick="copyToClipboard(this.previousElementSibling.textContent)">Copy</button>
                </div>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">PHP</h3>
                <div class="code-block">
                    <pre><?php
class FastPingClient {
    private $baseUrl = 'https://fastping.it/api/v1';
    private $apiKey;
    
    public function __construct($apiKey) {
        $this->apiKey = $apiKey;
    }
    
    private function makeRequest($endpoint, $method = 'GET', $data = null) {
        $url = $this->baseUrl . $endpoint;
        
        $headers = [
            'Authorization: Bearer ' . $this->apiKey,
            'Content-Type: application/json'
        ];
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        
        if ($method === 'POST' && $data) {
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($httpCode !== 200) {
            throw new Exception("HTTP Error: $httpCode");
        }
        
        return json_decode($response, true);
    }
    
    public function ping() {
        return $this->makeRequest('/ping');
    }
    
    public function test($data = null) {
        return $this->makeRequest('/test', 'POST', $data);
    }
    
    public function proxy($targetUrl) {
        return $this->makeRequest('/proxy?url=' . urlencode($targetUrl));
    }
    
    public function getStats() {
        return $this->makeRequest('/stats');
    }
}

// Usage
$client = new FastPingClient('fpk_your_api_key');

try {
    $result = $client->ping();
    echo "Response time: " . $result['response_time_ms'] . "ms\n";
    
    $stats = $client->getStats();
    echo "Requests today: " . $stats['current_limits']['requests_today'] . "\n";
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}
?></pre>
                    <button class="copy-button" onclick="copyToClipboard(this.previousElementSibling.textContent)">Copy</button>
                </div>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">cURL Examples</h3>
                <div class="code-block">
                    <pre># Quick ping test
curl -H "Authorization: Bearer fpk_your_api_key" \
     https://fastping.it/api/v1/ping

# POST test with JSON data
curl -X POST \
     -H "Authorization: Bearer fpk_your_api_key" \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}' \
     https://fastping.it/api/v1/test

# Proxy a GET request
curl -H "Authorization: Bearer fpk_your_api_key" \
     "https://fastping.it/api/v1/proxy?url=https://httpbin.org/get"

# Get usage statistics
curl -H "Authorization: Bearer fpk_your_api_key" \
     https://fastping.it/api/v1/stats

# Batch processing
curl -X POST \
     -H "Authorization: Bearer fpk_your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
       "requests": [
         {"url": "https://httpbin.org/get"},
         {"url": "https://httpbin.org/status/200"}
       ]
     }' \
     https://fastping.it/api/v1/batch</pre>
                    <button class="copy-button" onclick="copyToClipboard(this.previousElementSibling.textContent)">Copy</button>
                </div>
            </div>
        </div>

        <!-- Webhooks -->
        <div class="api-overview">
            <h2 class="section-title">🔔 Webhooks</h2>
            <div class="content">
                <p>Get real-time notifications about your account activity, rate limit warnings, and system status updates.</p>
                
                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Available Events</h3>
                <ul>
                    <li><strong>rate_limit_warning:</strong> Triggered at 80% of your rate limit</li>
                    <li><strong>rate_limit_exceeded:</strong> Triggered when rate limit is exceeded</li>
                    <li><strong>quota_warning:</strong> Triggered at 90% of monthly quota</li>
                    <li><strong>quota_exceeded:</strong> Triggered when monthly quota is exceeded</li>
                    <li><strong>service_degradation:</strong> Triggered during performance issues</li>
                </ul>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Webhook Payload Example</h3>
                <div class="code-block">
                    <pre>{
  "event": "rate_limit_warning",
  "timestamp": "2024-01-01T12:00:00Z",
  "customer_id": "cust_abc123",
  "data": {
    "current_usage": 80,
    "limit": 100,
    "window": "per_minute",
    "reset_at": "2024-01-01T12:01:00Z"
  }
}</pre>
                </div>

                <div class="highlight-box">
                    <div class="highlight-title">🔧 Configure Webhooks</div>
                    <p>Contact support to configure webhook endpoints for your account. We'll send a verification challenge to confirm your endpoint.</p>
                </div>
            </div>
        </div>

        <!-- Support -->
        <div class="api-overview">
            <h2 class="section-title">💬 Support & Resources</h2>
            <div class="content">
                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Need Help?</h3>
                <ul>
                    <li><strong>Email Support:</strong> <a href="mailto:api-support@fastping.it" style="color: #40e0ff;">api-support@fastping.it</a></li>
                    <li><strong>Status Page:</strong> <a href="https://status.fastping.it" style="color: #40e0ff;">status.fastping.it</a></li>
                    <li><strong>GitHub Examples:</strong> <a href="https://github.com/fastping/examples" style="color: #40e0ff;">github.com/fastping/examples</a></li>
                    <li><strong>Community Discord:</strong> <a href="https://discord.gg/fastping" style="color: #40e0ff;">discord.gg/fastping</a></li>
                </ul>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">API Versioning</h3>
                <p>
                    We use semantic versioning for our API. The current version is <strong>v1</strong>. 
                    We maintain backward compatibility and provide at least 6 months notice before 
                    deprecating any endpoints.
                </p>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Service Level Agreement</h3>
                <ul>
                    <li><strong>Uptime:</strong> 99.97% guaranteed uptime</li>
                    <li><strong>Response Time:</strong> Sub-40ms global average</li>
                    <li><strong>Support Response:</strong> &lt;24h for all plans, &lt;4h for Enterprise</li>
                    <li><strong>Rate Limiting:</strong> Fair usage policy with generous limits</li>
                </ul>

                <div class="highlight-box">
                    <div class="highlight-title">🚀 Ready to Get Started?</div>
                    <p>
                        Sign up for a free account to get your API key and start building with the 
                        world's fastest proxy network. Basic plans start at just $29.99/month.
                    </p>
                    <p style="margin-top: 1rem;">
                        <a href="/pricing" style="color: #40e0ff; font-weight: 600;">View Pricing →</a>
                    </p>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div style="text-align: center; margin-top: 4rem; padding: 2rem; color: #666;">
            <p>FastPing.It API Documentation • Last updated: January 2024</p>
            <p style="margin-top: 0.5rem;">
                <a href="/" style="color: #40e0ff;">Home</a> • 
                <a href="/stats.html" style="color: #40e0ff;">Stats</a> • 
                <a href="/about.html" style="color: #40e0ff;">About</a> • 
                <a href="/contact.html" style="color: #40e0ff;">Contact</a>
            </p>
        </div>
    </div>

    <script>
        // Copy to clipboard functionality
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                // Show success feedback
                event.target.textContent = 'Copied!';
                event.target.style.background = 'rgba(0, 255, 136, 0.3)';
                
                setTimeout(() => {
                    event.target.textContent = 'Copy';
                    event.target.style.background = 'rgba(64, 224, 255, 0.2)';
                }, 2000);
            }).catch(function(err) {
                console.error('Failed to copy: ', err);
                event.target.textContent = 'Failed';
                setTimeout(() => {
                    event.target.textContent = 'Copy';
                }, 2000);
            });
        }

        // Add particle effects
        function createParticle() {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.left = Math.random() * 100 + '%';
            particle.style.animationDelay = Math.random() * 8 + 's';
            document.querySelector('.floating-particles').appendChild(particle);
            
            setTimeout(() => {
                particle.remove();
            }, 8000);
        }

        // Create particles periodically
        setInterval(createParticle, 2000);

        // Smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });

        // Highlight current section in navigation (if you add a TOC)
        window.addEventListener('scroll', function() {
            // Add scroll effects if needed
        });

        console.log('📚 FastPing.It API Documentation loaded');
        console.log('🔗 Ready to integrate? Get your API key at https://fastping.it/dashboard');
    </script>
</body>
</html>