"""
Ultra-Fast Customer Dashboard for Premium Pingback Service
=========================================================

Designed for thousands of concurrent customers with:
- JWT token authentication (no sessions = no memory bloat)
- Redis caching for microsecond lookups
- Minimal HTML/CSS for blazing fast loading
- Real-time stats from usage logs
- CDN-ready static assets
"""

from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import redis
import sqlite3
import jwt
import hashlib
import time
from datetime import datetime, timedelta
from functools import wraps
import json
from typing import Optional, Dict, Any
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)  # Generate secure secret

# Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 1  # Different DB from whitelist system
DB_PATH = 'whitelist.db'  # Same DB as whitelist system
JWT_EXPIRY_HOURS = 24

# Initialize Redis
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    print("⚠️ Redis not available - dashboard will be slower")

class CustomerDashboard:
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.init_customer_auth()
    
    def init_customer_auth(self):
        """Initialize customer authentication table"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_auth (
                customer_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_customer_account(self, customer_id: str, email: str, password: str) -> tuple[bool, str]:
        """Create new customer account with auto-generated API key"""
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            api_key = f"pk_{secrets.token_hex(16)}"
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO customer_auth (customer_id, email, password_hash, api_key)
                VALUES (?, ?, ?, ?)
            ''', (customer_id, email, password_hash, api_key))
            
            conn.commit()
            conn.close()
            
            return True, api_key
            
        except Exception as e:
            print(f"Error creating customer account: {e}")
            return False, str(e)
    
    def authenticate_customer(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate customer and return customer data"""
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT customer_id, email, api_key 
                FROM customer_auth 
                WHERE email = ? AND password_hash = ? AND is_active = 1
            ''', (email, password_hash))
            
            result = cursor.fetchone()
            
            if result:
                customer_id, email, api_key = result
                
                # Update last login
                cursor.execute('''
                    UPDATE customer_auth SET last_login = CURRENT_TIMESTAMP 
                    WHERE customer_id = ?
                ''', (customer_id,))
                
                conn.commit()
                conn.close()
                
                return {
                    'customer_id': customer_id,
                    'email': email,
                    'api_key': api_key
                }
            
            conn.close()
            return None
            
        except Exception as e:
            print(f"Authentication error: {e}")
            return None
    
    def get_customer_config(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer's IP whitelist configuration"""
        cache_key = f"customer_config:{customer_id}"
        
        # Try cache first
        if REDIS_AVAILABLE:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ip_address, plan_type, rate_limit, created_at, expires_at, notes
                FROM ip_whitelist 
                WHERE customer_id = ? AND is_active = 1
            ''', (customer_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            config_data = {
                'customer_id': customer_id,
                'ips': [],
                'total_ips': len(results)
            }
            
            for row in results:
                ip_address, plan_type, rate_limit, created_at, expires_at, notes = row
                config_data['ips'].append({
                    'ip_address': ip_address,
                    'plan_type': plan_type,
                    'rate_limit': rate_limit,
                    'created_at': created_at,
                    'expires_at': expires_at,
                    'notes': notes or ''
                })
            
            # Cache the result
            if REDIS_AVAILABLE:
                redis_client.setex(cache_key, self.cache_timeout, json.dumps(config_data))
            
            return config_data
            
        except Exception as e:
            print(f"Error getting customer config: {e}")
            return None
    
    def get_customer_stats(self, customer_id: str, days: int = 7) -> Dict[str, Any]:
        """Get customer usage statistics"""
        cache_key = f"customer_stats:{customer_id}:{days}"
        
        # Try cache first
        if REDIS_AVAILABLE:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Get stats for last N days
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN success = 1 THEN 1 END) as successful_requests,
                    AVG(response_time_ms) as avg_response_time,
                    MIN(response_time_ms) as min_response_time,
                    MAX(response_time_ms) as max_response_time,
                    COUNT(DISTINCT DATE(timestamp)) as active_days
                FROM usage_logs 
                WHERE customer_id = ? 
                AND timestamp >= datetime('now', '-{} days')
            '''.format(days), (customer_id,))
            
            stats = cursor.fetchone()
            
            # Get daily breakdown
            cursor.execute('''
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as requests,
                    AVG(response_time_ms) as avg_response_time
                FROM usage_logs 
                WHERE customer_id = ? 
                AND timestamp >= datetime('now', '-{} days')
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            '''.format(days), (customer_id,))
            
            daily_stats = cursor.fetchall()
            conn.close()
            
            if stats:
                total_requests, successful_requests, avg_response_time, min_response_time, max_response_time, active_days = stats
                
                stats_data = {
                    'total_requests': total_requests or 0,
                    'successful_requests': successful_requests or 0,
                    'success_rate': (successful_requests / total_requests * 100) if total_requests > 0 else 0,
                    'avg_response_time': round(avg_response_time or 0, 2),
                    'min_response_time': round(min_response_time or 0, 2),
                    'max_response_time': round(max_response_time or 0, 2),
                    'active_days': active_days or 0,
                    'daily_breakdown': [
                        {
                            'date': row[0],
                            'requests': row[1],
                            'avg_response_time': round(row[2] or 0, 2)
                        } for row in daily_stats
                    ]
                }
                
                # Cache for shorter time due to changing data
                if REDIS_AVAILABLE:
                    redis_client.setex(cache_key, 60, json.dumps(stats_data))  # 1 minute cache
                
                return stats_data
            
            return {'total_requests': 0, 'successful_requests': 0, 'success_rate': 0}
            
        except Exception as e:
            print(f"Error getting customer stats: {e}")
            return {'error': str(e)}

# Initialize dashboard
dashboard = CustomerDashboard()

def token_required(f):
    """JWT token authentication decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            # Check for token in cookies (for web dashboard)
            token = request.cookies.get('auth_token')
        
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_customer = data['customer_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_customer, *args, **kwargs)
    
    return decorated

# Minimal Dashboard HTML Template
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Premium Pingback Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --primary: #1a73e8;
            --primary-dark: #1557b0;
            --bg-light: #f8f9fa;
            --text-muted: #666;
            transition: all 0.8s ease;
        }
        
        /* Theme color definitions */
        .theme-blue { --primary: #1a73e8; --primary-dark: #1557b0; }
        .theme-purple { --primary: #7c3aed; --primary-dark: #5b21b6; }
        .theme-green { --primary: #059669; --primary-dark: #047857; }
        .theme-orange { --primary: #ea580c; --primary-dark: #c2410c; }
        .theme-pink { --primary: #e11d48; --primary-dark: #be185d; }
        .theme-teal { --primary: #0891b2; --primary-dark: #0e7490; }
        .theme-indigo { --primary: #4f46e5; --primary-dark: #3730a3; }
        .theme-red { --primary: #dc2626; --primary-dark: #b91c1c; }
        
        body { 
            font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
            margin: 0; padding: 20px; background: #f5f5f5;
            transition: all 0.8s ease;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { 
            background: white; border-radius: 8px; padding: 20px; margin: 20px 0; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.8s ease;
        }
        .header { 
            background: var(--primary); color: white; padding: 20px; 
            border-radius: 8px; margin-bottom: 20px;
            transition: all 0.8s ease;
        }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .stat-box { 
            text-align: center; padding: 20px; background: var(--bg-light); 
            border-radius: 8px; transition: all 0.8s ease;
        }
        .stat-number { 
            font-size: 2em; font-weight: bold; color: var(--primary);
            transition: all 0.8s ease;
        }
        .stat-label { color: var(--text-muted); margin-top: 5px; }
        .ip-list { list-style: none; padding: 0; }
        .ip-item { 
            background: var(--bg-light); margin: 10px 0; padding: 15px; 
            border-radius: 8px; display: flex; justify-content: space-between; align-items: center;
            transition: all 0.8s ease;
        }
        .plan-badge { 
            background: var(--primary); color: white; padding: 4px 8px; 
            border-radius: 4px; font-size: 0.8em;
            transition: all 0.8s ease;
        }
        .refresh-btn { 
            background: var(--primary); color: white; border: none; 
            padding: 10px 20px; border-radius: 4px; cursor: pointer;
            transition: all 0.8s ease;
        }
        .refresh-btn:hover { background: var(--primary-dark); }
        .api-key { 
            font-family: monospace; background: var(--bg-light); 
            padding: 10px; border-radius: 4px; word-break: break-all;
            transition: all 0.8s ease;
        }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { 
            background: var(--bg-light);
            transition: all 0.8s ease;
        }
        
        /* Theme indicator */
        .theme-indicator {
            position: fixed; top: 20px; right: 20px; 
            background: var(--primary); color: white;
            padding: 8px 12px; border-radius: 20px; font-size: 0.8em;
            opacity: 0.8; transition: all 0.8s ease;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div class="theme-indicator" id="themeIndicator">🎨 Blue Ocean</div>
    
    <div class="container">
        <div class="header">
            <h1>🚀 Premium Pingback Dashboard</h1>
            <p>Customer: {{ customer_data.email }} | ID: {{ customer_data.customer_id }}</p>
        </div>
        
        <div class="card">
            <h2>📊 Usage Statistics (Last 7 Days)</h2>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-number">{{ stats.total_requests }}</div>
                    <div class="stat-label">Total Requests</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{{ "%.1f"|format(stats.success_rate) }}%</div>
                    <div class="stat-label">Success Rate</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{{ stats.avg_response_time }}ms</div>
                    <div class="stat-label">Avg Response Time</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{{ stats.active_days }}</div>
                    <div class="stat-label">Active Days</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>🔐 Your Whitelisted IPs</h2>
            {% if config.ips %}
            <ul class="ip-list">
                {% for ip in config.ips %}
                <li class="ip-item">
                    <div>
                        <strong>{{ ip.ip_address }}</strong>
                        <div style="color: #666; font-size: 0.9em;">{{ ip.notes }}</div>
                    </div>
                    <div>
                        <span class="plan-badge">{{ ip.plan_type.upper() }}</span>
                        <span style="margin-left: 10px;">{{ ip.rate_limit }}/min</span>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p>No IPs configured yet. Contact sales@yourservice.com to get started!</p>
            {% endif %}
        </div>
        
        <div class="card">
            <h2>🔑 API Access</h2>
            <p><strong>Your API Key:</strong></p>
            <div class="api-key">{{ customer_data.api_key }}</div>
            <p style="color: #666; font-size: 0.9em;">Use this key for programmatic access to your stats.</p>
        </div>
        
        {% if stats.daily_breakdown %}
        <div class="card">
            <h2>📈 Daily Breakdown</h2>
            <table>
                <thead>
                    <tr><th>Date</th><th>Requests</th><th>Avg Response Time</th></tr>
                </thead>
                <tbody>
                    {% for day in stats.daily_breakdown %}
                    <tr>
                        <td>{{ day.date }}</td>
                        <td>{{ day.requests }}</td>
                        <td>{{ day.avg_response_time }}ms</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
        
        <div class="card">
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh Data</button>
            <button class="refresh-btn" onclick="logout()" style="background: #dc3545; margin-left: 10px;">🚪 Logout</button>
        </div>
    </div>
    
    <script>
        // Theme cycling system
        const themes = [
            { name: 'Blue Ocean', class: 'theme-blue', emoji: '🌊' },
            { name: 'Purple Storm', class: 'theme-purple', emoji: '⚡' },
            { name: 'Forest Green', class: 'theme-green', emoji: '🌲' },
            { name: 'Sunset Orange', class: 'theme-orange', emoji: '🌅' },
            { name: 'Rose Pink', class: 'theme-pink', emoji: '🌹' },
            { name: 'Ocean Teal', class: 'theme-teal', emoji: '🏝️' },
            { name: 'Cosmic Indigo', class: 'theme-indigo', emoji: '🌌' },
            { name: 'Fire Red', class: 'theme-red', emoji: '🔥' }
        ];
        
        let currentThemeIndex = 0;
        
        function cycleTheme() {
            // Remove all theme classes
            document.body.className = '';
            
            // Add new theme class
            const theme = themes[currentThemeIndex];
            document.body.classList.add(theme.class);
            
            // Update theme indicator
            const indicator = document.getElementById('themeIndicator');
            indicator.innerHTML = `${theme.emoji} ${theme.name}`;
            
            // Move to next theme
            currentThemeIndex = (currentThemeIndex + 1) % themes.length;
        }
        
        function logout() {
            document.cookie = 'auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
            window.location.href = '/login';
        }
        
        // Initialize with first theme
        cycleTheme();
        
        // Cycle themes every 45 seconds (slightly less than a minute for more dynamic feel)
        setInterval(cycleTheme, 45000);
        
        // Auto-refresh data every 30 seconds (separate from theme cycling)
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
'''

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Premium Pingback Login</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .login-card { background: white; border-radius: 8px; padding: 40px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
        .header { text-align: center; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; color: #333; }
        input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        .login-btn { background: #1a73e8; color: white; border: none; padding: 12px; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; }
        .login-btn:hover { background: #1557b0; }
        .error { color: #dc3545; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="header">
            <h1>🚀 Premium Pingback</h1>
            <p>Customer Dashboard Login</p>
        </div>
        
        <form method="post">
            <div class="form-group">
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required>
            </div>
            
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" class="login-btn">🔐 Login</button>
            
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
        </form>
    </div>
</body>
</html>
'''

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        customer_data = dashboard.authenticate_customer(email, password)
        
        if customer_data:
            # Create JWT token
            token = jwt.encode(
                {
                    'customer_id': customer_data['customer_id'],
                    'email': customer_data['email'],
                    'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
                },
                app.config['SECRET_KEY'],
                algorithm='HS256'
            )
            
            response = redirect(url_for('dashboard_home'))
            response.set_cookie('auth_token', token, max_age=JWT_EXPIRY_HOURS*3600, httponly=True)
            return response
        else:
            return render_template_string(LOGIN_HTML, error="Invalid credentials")
    
    return render_template_string(LOGIN_HTML)

@app.route('/dashboard')
@token_required
def dashboard_home(current_customer):
    # Get customer data
    config = dashboard.get_customer_config(current_customer)
    stats = dashboard.get_customer_stats(current_customer)
    
    # Get customer auth data for API key
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT email, api_key FROM customer_auth WHERE customer_id = ?', (current_customer,))
    result = cursor.fetchone()
    conn.close()
    
    customer_data = {
        'customer_id': current_customer,
        'email': result[0] if result else 'Unknown',
        'api_key': result[1] if result else 'No API key'
    }
    
    return render_template_string(DASHBOARD_HTML, 
                                customer_data=customer_data,
                                config=config or {'ips': []},
                                stats=stats)

# API Endpoints for programmatic access
@app.route('/api/stats')
@token_required
def api_stats(current_customer):
    days = request.args.get('days', 7, type=int)
    stats = dashboard.get_customer_stats(current_customer, days)
    return jsonify(stats)

@app.route('/api/config')
@token_required
def api_config(current_customer):
    config = dashboard.get_customer_config(current_customer)
    return jsonify(config)

# Admin route to create test customer
@app.route('/admin/create_customer', methods=['POST'])
def create_customer():
    customer_id = request.form.get('customer_id')
    email = request.form.get('email')
    password = request.form.get('password')
    
    success, result = dashboard.create_customer_account(customer_id, email, password)
    
    if success:
        return jsonify({'success': True, 'api_key': result})
    else:
        return jsonify({'success': False, 'error': result}), 400

@app.route('/')
def home():
    return redirect(url_for('login'))

if __name__ == '__main__':
    print("🚀 Starting Customer Dashboard...")
    print("📊 Login at: http://localhost:8080/login")
    print("🔧 Create customer: POST /admin/create_customer")
    
    app.run(host='0.0.0.0', port=5060, debug=True)

