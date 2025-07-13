"""
Complete API Access System for FastPing.It
==========================================

Provides programmatic access to your proxy service with:
- API key authentication
- Rate limiting per plan
- Usage tracking for billing
- Multiple endpoint types
- Real-time monitoring
"""

from flask import Flask, request, jsonify, g
from functools import wraps
import time
import hashlib
import hmac
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
import requests
from typing import Dict, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIManager:
    def __init__(self, whitelist_manager, customer_manager):
        self.whitelist_manager = whitelist_manager
        self.customer_manager = customer_manager
        self.init_api_database()
        
    def init_api_database(self):
        """Initialize API-specific database tables"""
        conn = sqlite3.connect('customer_resources.db')
        cursor = conn.cursor()
        
        # API keys table (extend existing customers table)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                key_name TEXT,
                permissions TEXT DEFAULT 'basic',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                expires_at TIMESTAMP,
                total_requests INTEGER DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
            )
        ''')
        
        # API usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage (
                usage_id TEXT PRIMARY KEY,
                api_key TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                request_size INTEGER DEFAULT 0,
                response_size INTEGER DEFAULT 0,
                response_time_ms REAL,
                status_code INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                billing_processed BOOLEAN DEFAULT 0,
                FOREIGN KEY (api_key) REFERENCES api_keys (api_key)
            )
        ''')
        
        # API rate limiting
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_rate_limits (
                api_key TEXT PRIMARY KEY,
                requests_count INTEGER DEFAULT 0,
                window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                daily_count INTEGER DEFAULT 0,
                daily_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # API endpoints configuration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_endpoints (
                endpoint_id TEXT PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                method TEXT NOT NULL,
                description TEXT,
                required_plan TEXT DEFAULT 'basic',
                rate_limit_override INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Create default API endpoints
        self.create_default_endpoints()
    
    def create_default_endpoints(self):
        """Create default API endpoints"""
        endpoints = [
            {
                'path': '/api/v1/ping',
                'method': 'GET',
                'description': 'Basic connectivity test - fastest response possible',
                'required_plan': 'basic',
                'rate_limit_override': None
            },
            {
                'path': '/api/v1/test',
                'method': 'GET,POST',
                'description': 'Full proxy test with headers and data analysis',
                'required_plan': 'basic',
                'rate_limit_override': None
            },
            {
                'path': '/api/v1/proxy',
                'method': 'GET,POST,PUT,DELETE',
                'description': 'Full proxy request to any destination',
                'required_plan': 'premium',
                'rate_limit_override': None
            },
            {
                'path': '/api/v1/stats',
                'method': 'GET',
                'description': 'Get your usage statistics and performance metrics',
                'required_plan': 'basic',
                'rate_limit_override': 10  # Lower rate limit for stats
            },
            {
                'path': '/api/v1/batch',
                'method': 'POST',
                'description': 'Process multiple requests in a single call',
                'required_plan': 'enterprise',
                'rate_limit_override': 5
            }
        ]
        
        conn = sqlite3.connect('customer_resources.db')
        cursor = conn.cursor()
        
        for endpoint in endpoints:
            endpoint_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT OR REPLACE INTO api_endpoints 
                (endpoint_id, path, method, description, required_plan, rate_limit_override)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (endpoint_id, endpoint['path'], endpoint['method'], 
                 endpoint['description'], endpoint['required_plan'], 
                 endpoint['rate_limit_override']))
        
        conn.commit()
        conn.close()
    
    def generate_api_key(self, customer_id: str, key_name: str = None) -> str:
        """Generate new API key for customer"""
        try:
            # Generate secure API key
            api_key = f"fpk_{uuid.uuid4().hex}"
            key_id = str(uuid.uuid4())
            
            conn = sqlite3.connect('customer_resources.db')
            cursor = conn.cursor()
            
            # Check if customer exists
            cursor.execute('SELECT plan_type FROM customers WHERE customer_id = ?', (customer_id,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return None
            
            plan_type = result[0]
            
            # Insert API key
            cursor.execute('''
                INSERT INTO api_keys 
                (key_id, customer_id, api_key, key_name, permissions)
                VALUES (?, ?, ?, ?, ?)
            ''', (key_id, customer_id, api_key, key_name or 'Default API Key', plan_type))
            
            conn.commit()
            conn.close()
            
            return api_key
            
        except Exception as e:
            logger.error(f"Error generating API key: {e}")
            return None
    
    def validate_api_key(self, api_key: str) -> Tuple[bool, Optional[Dict]]:
        """Validate API key and return customer info"""
        try:
            conn = sqlite3.connect('customer_resources.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ak.customer_id, ak.permissions, ak.is_active, 
                       c.plan_type, c.status, ak.expires_at
                FROM api_keys ak
                JOIN customers c ON ak.customer_id = c.customer_id
                WHERE ak.api_key = ?
            ''', (api_key,))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return False, None
            
            customer_id, permissions, is_active, plan_type, status, expires_at = result
            
            # Check if key is active
            if not is_active or status != 'active':
                return False, None
            
            # Check expiration
            if expires_at:
                expires_dt = datetime.fromisoformat(expires_at)
                if expires_dt < datetime.now():
                    return False, None
            
            return True, {
                'customer_id': customer_id,
                'permissions': permissions,
                'plan_type': plan_type
            }
            
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return False, None
    
    def check_rate_limit(self, api_key: str, endpoint: str, plan_type: str) -> Tuple[bool, Dict]:
        """Check if request is within rate limits"""
        try:
            # Get rate limits based on plan
            plan_limits = {
                'basic': {'per_minute': 100, 'per_day': 10000},
                'premium': {'per_minute': 500, 'per_day': 50000},
                'enterprise': {'per_minute': 2000, 'per_day': 200000}
            }
            
            limits = plan_limits.get(plan_type, plan_limits['basic'])
            
            # Check for endpoint-specific overrides
            conn = sqlite3.connect('customer_resources.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT rate_limit_override FROM api_endpoints 
                WHERE path = ? AND is_active = 1
            ''', (endpoint,))
            
            override_result = cursor.fetchone()
            if override_result and override_result[0]:
                limits['per_minute'] = override_result[0]
            
            # Get current usage
            cursor.execute('''
                SELECT requests_count, window_start, daily_count, daily_reset
                FROM api_rate_limits WHERE api_key = ?
            ''', (api_key,))
            
            result = cursor.fetchone()
            
            now = datetime.now()
            
            if result:
                requests_count, window_start_str, daily_count, daily_reset_str = result
                window_start = datetime.fromisoformat(window_start_str)
                daily_reset = datetime.fromisoformat(daily_reset_str)
                
                # Check if we need to reset windows
                if now - window_start > timedelta(minutes=1):
                    requests_count = 0
                    window_start = now
                
                if now - daily_reset > timedelta(days=1):
                    daily_count = 0
                    daily_reset = now
                
                # Check limits
                if requests_count >= limits['per_minute']:
                    conn.close()
                    return False, {
                        'error': 'Rate limit exceeded',
                        'limit': limits['per_minute'],
                        'window': 'per_minute',
                        'reset_at': (window_start + timedelta(minutes=1)).isoformat()
                    }
                
                if daily_count >= limits['per_day']:
                    conn.close()
                    return False, {
                        'error': 'Daily limit exceeded',
                        'limit': limits['per_day'],
                        'window': 'per_day',
                        'reset_at': (daily_reset + timedelta(days=1)).isoformat()
                    }
                
                # Update counters
                cursor.execute('''
                    UPDATE api_rate_limits 
                    SET requests_count = ?, window_start = ?, 
                        daily_count = ?, daily_reset = ?
                    WHERE api_key = ?
                ''', (requests_count + 1, window_start.isoformat(),
                     daily_count + 1, daily_reset.isoformat(), api_key))
                
            else:
                # First request for this API key
                cursor.execute('''
                    INSERT INTO api_rate_limits 
                    (api_key, requests_count, window_start, daily_count, daily_reset)
                    VALUES (?, ?, ?, ?, ?)
                ''', (api_key, 1, now.isoformat(), 1, now.isoformat()))
            
            conn.commit()
            conn.close()
            
            return True, {
                'remaining_minute': limits['per_minute'] - (requests_count + 1),
                'remaining_day': limits['per_day'] - (daily_count + 1),
                'reset_minute': (window_start + timedelta(minutes=1)).isoformat() if result else (now + timedelta(minutes=1)).isoformat(),
                'reset_day': (daily_reset + timedelta(days=1)).isoformat() if result else (now + timedelta(days=1)).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False, {'error': 'Rate limit check failed'}
    
    def log_api_usage(self, api_key: str, customer_id: str, endpoint: str, 
                     method: str, status_code: int, response_time_ms: float,
                     request_size: int = 0, response_size: int = 0):
        """Log API usage for billing and analytics"""
        try:
            usage_id = str(uuid.uuid4())
            
            conn = sqlite3.connect('customer_resources.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO api_usage 
                (usage_id, api_key, customer_id, endpoint, method, 
                 ip_address, user_agent, request_size, response_size,
                 response_time_ms, status_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (usage_id, api_key, customer_id, endpoint, method,
                 request.remote_addr, request.headers.get('User-Agent', ''),
                 request_size, response_size, response_time_ms, status_code))
            
            # Update API key last used
            cursor.execute('''
                UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP,
                total_requests = total_requests + 1
                WHERE api_key = ?
            ''', (api_key,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging API usage: {e}")

# Flask decorators for API authentication
def require_api_key(required_plan: str = 'basic'):
    """Decorator to require API key authentication"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_manager = g.get('api_manager')
            if not api_manager:
                return jsonify({'error': 'API system not initialized'}), 500
            
            start_time = time.time()
            
            # Get API key from header or query parameter
            api_key = request.headers.get('Authorization')
            if api_key and api_key.startswith('Bearer '):
                api_key = api_key[7:]  # Remove 'Bearer ' prefix
            else:
                api_key = request.args.get('api_key')
            
            if not api_key:
                return jsonify({
                    'error': 'API key required',
                    'message': 'Provide API key in Authorization header (Bearer token) or api_key parameter'
                }), 401
            
            # Validate API key
            is_valid, customer_info = api_manager.validate_api_key(api_key)
            if not is_valid:
                return jsonify({
                    'error': 'Invalid API key',
                    'message': 'API key is invalid, expired, or disabled'
                }), 401
            
            # Check plan requirements
            plan_hierarchy = {'basic': 0, 'premium': 1, 'enterprise': 2}
            customer_plan_level = plan_hierarchy.get(customer_info['plan_type'], 0)
            required_plan_level = plan_hierarchy.get(required_plan, 0)
            
            if customer_plan_level < required_plan_level:
                return jsonify({
                    'error': 'Insufficient plan',
                    'message': f'This endpoint requires {required_plan} plan or higher',
                    'current_plan': customer_info['plan_type'],
                    'upgrade_url': 'https://fastping.it/pricing'
                }), 403
            
            # Check rate limits
            endpoint_path = request.endpoint or request.path
            rate_ok, rate_info = api_manager.check_rate_limit(
                api_key, endpoint_path, customer_info['plan_type']
            )
            
            if not rate_ok:
                response = jsonify(rate_info)
                response.status_code = 429
                response.headers['Retry-After'] = '60'
                return response
            
            # Store info in g for use in endpoint
            g.api_key = api_key
            g.customer_info = customer_info
            g.rate_info = rate_info
            g.start_time = start_time
            
            # Execute the actual endpoint
            result = f(*args, **kwargs)
            
            # Log usage
            response_time = (time.time() - start_time) * 1000
            status_code = result.status_code if hasattr(result, 'status_code') else 200
            
            api_manager.log_api_usage(
                api_key, customer_info['customer_id'], endpoint_path,
                request.method, status_code, response_time
            )
            
            # Add rate limit headers to response
            if hasattr(result, 'headers'):
                result.headers['X-RateLimit-Remaining-Minute'] = str(rate_info.get('remaining_minute', 0))
                result.headers['X-RateLimit-Remaining-Day'] = str(rate_info.get('remaining_day', 0))
                result.headers['X-RateLimit-Reset-Minute'] = rate_info.get('reset_minute', '')
                result.headers['X-RateLimit-Reset-Day'] = rate_info.get('reset_day', '')
            
            return result
            
        return decorated_function
    return decorator

# API Endpoints
def create_api_endpoints(app, api_manager, whitelist_manager):
    """Create all API endpoints"""
    
    # Store API manager in app context
    @app.before_request
    def before_request():
        g.api_manager = api_manager
    
    @app.route('/api/v1/ping', methods=['GET'])
    @require_api_key('basic')
    def api_ping():
        """Ultra-fast ping endpoint"""
        return jsonify({
            'status': 'success',
            'message': 'pong',
            'timestamp': time.time(),
            'response_time_ms': (time.time() - g.start_time) * 1000,
            'server': 'FastPing.It'
        })
    
    @app.route('/api/v1/test', methods=['GET', 'POST'])
    @require_api_key('basic')
    def api_test():
        """Full proxy test endpoint"""
        start_time = g.start_time
        
        # Analyze the request
        headers_received = dict(request.headers)
        client_ip = request.remote_addr
        method = request.method
        
        # Get any data sent
        request_data = None
        if request.is_json:
            request_data = request.get_json()
        elif request.form:
            request_data = dict(request.form)
        
        response_data = {
            'status': 'success',
            'test_type': 'full_analysis',
            'request_info': {
                'method': method,
                'headers': headers_received,
                'client_ip': client_ip,
                'user_agent': request.headers.get('User-Agent'),
                'content_type': request.headers.get('Content-Type'),
                'content_length': request.headers.get('Content-Length')
            },
            'data_received': request_data,
            'server_info': {
                'server': 'FastPing.It',
                'processing_time_ms': (time.time() - start_time) * 1000,
                'timestamp': datetime.now().isoformat()
            },
            'customer_info': {
                'plan': g.customer_info['plan_type'],
                'remaining_requests_minute': g.rate_info.get('remaining_minute'),
                'remaining_requests_day': g.rate_info.get('remaining_day')
            }
        }
        
        return jsonify(response_data)
    
    @app.route('/api/v1/proxy', methods=['GET', 'POST', 'PUT', 'DELETE'])
    @require_api_key('premium')
    def api_proxy():
        """Full proxy request to external URL"""
        target_url = request.args.get('url') or (request.get_json() or {}).get('url')
        
        if not target_url:
            return jsonify({
                'error': 'Missing target URL',
                'message': 'Provide target URL in "url" parameter or JSON body'
            }), 400
        
        try:
            # Forward the request
            headers = dict(request.headers)
            headers.pop('Host', None)  # Remove host header
            headers.pop('Authorization', None)  # Remove API key
            
            response = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request.get_data(),
                params=request.args,
                timeout=30
            )
            
            # Return proxied response
            return jsonify({
                'status': 'success',
                'proxy_response': {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'content': response.text,
                    'content_length': len(response.content)
                },
                'request_info': {
                    'target_url': target_url,
                    'method': request.method,
                    'processing_time_ms': (time.time() - g.start_time) * 1000
                }
            })
            
        except Exception as e:
            return jsonify({
                'error': 'Proxy request failed',
                'message': str(e),
                'target_url': target_url
            }), 500
    
    @app.route('/api/v1/stats', methods=['GET'])
    @require_api_key('basic')
    def api_stats():
        """Get customer usage statistics"""
        customer_id = g.customer_info['customer_id']
        
        try:
            conn = sqlite3.connect('customer_resources.db')
            cursor = conn.cursor()
            
            # Get usage stats for last 30 days
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_requests,
                    AVG(response_time_ms) as avg_response_time,
                    COUNT(DISTINCT DATE(timestamp)) as active_days,
                    SUM(request_size + response_size) as total_bytes
                FROM api_usage 
                WHERE customer_id = ? AND timestamp > ?
            ''', (customer_id, thirty_days_ago))
            
            stats = cursor.fetchone()
            
            # Get rate limit status
            cursor.execute('''
                SELECT requests_count, daily_count FROM api_rate_limits 
                WHERE api_key = ?
            ''', (g.api_key,))
            
            rate_data = cursor.fetchone()
            
            conn.close()
            
            return jsonify({
                'status': 'success',
                'customer_id': customer_id,
                'plan': g.customer_info['plan_type'],
                'usage_stats_30d': {
                    'total_requests': stats[0] or 0,
                    'avg_response_time_ms': round(stats[1] or 0, 2),
                    'active_days': stats[2] or 0,
                    'total_bytes_transferred': stats[3] or 0
                },
                'current_limits': {
                    'requests_this_minute': rate_data[0] if rate_data else 0,
                    'requests_today': rate_data[1] if rate_data else 0,
                    'remaining_minute': g.rate_info.get('remaining_minute'),
                    'remaining_day': g.rate_info.get('remaining_day')
                },
                'generated_at': datetime.now().isoformat()
            })
            
        except Exception as e:
            return jsonify({
                'error': 'Failed to get stats',
                'message': str(e)
            }), 500
    
    @app.route('/api/v1/batch', methods=['POST'])
    @require_api_key('enterprise')
    def api_batch():
        """Process multiple requests in batch"""
        batch_data = request.get_json()
        
        if not batch_data or 'requests' not in batch_data:
            return jsonify({
                'error': 'Invalid batch format',
                'message': 'Send JSON with "requests" array'
            }), 400
        
        requests_list = batch_data['requests']
        if len(requests_list) > 10:  # Limit batch size
            return jsonify({
                'error': 'Batch too large',
                'message': 'Maximum 10 requests per batch',
                'received': len(requests_list)
            }), 400
        
        results = []
        
        for i, req_data in enumerate(requests_list):
            try:
                if 'url' not in req_data:
                    results.append({
                        'index': i,
                        'status': 'error',
                        'error': 'Missing URL'
                    })
                    continue
                
                # Process individual request
                response = requests.get(
                    req_data['url'],
                    timeout=10,
                    headers=req_data.get('headers', {})
                )
                
                results.append({
                    'index': i,
                    'status': 'success',
                    'url': req_data['url'],
                    'status_code': response.status_code,
                    'response_time_ms': response.elapsed.total_seconds() * 1000,
                    'content_length': len(response.content)
                })
                
            except Exception as e:
                results.append({
                    'index': i,
                    'status': 'error',
                    'url': req_data.get('url', 'unknown'),
                    'error': str(e)
                })
        
        return jsonify({
            'status': 'success',
            'batch_id': str(uuid.uuid4()),
            'total_requests': len(requests_list),
            'successful_requests': len([r for r in results if r['status'] == 'success']),
            'failed_requests': len([r for r in results if r['status'] == 'error']),
            'results': results,
            'processing_time_ms': (time.time() - g.start_time) * 1000
        })

# Management endpoints for customers
def create_management_endpoints(app, api_manager):
    """Create customer management endpoints"""
    
    @app.route('/api/account/keys', methods=['GET'])
    @require_api_key('basic')
    def list_api_keys():
        """List customer's API keys"""
        customer_id = g.customer_info['customer_id']
        
        conn = sqlite3.connect('customer_resources.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT api_key, key_name, created_at, last_used_at, total_requests, is_active
            FROM api_keys WHERE customer_id = ?
        ''', (customer_id,))
        
        keys = []
        for row in cursor.fetchall():
            keys.append({
                'api_key': row[0][:12] + '...' + row[0][-4:],  # Mask the key
                'key_name': row[1],
                'created_at': row[2],
                'last_used_at': row[3],
                'total_requests': row[4],
                'is_active': bool(row[5])
            })
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'api_keys': keys
        })
    
    @app.route('/api/account/keys', methods=['POST'])
    @require_api_key('basic')
    def create_api_key():
        """Create new API key"""
        data = request.get_json() or {}
        key_name = data.get('name', 'API Key')
        
        customer_id = g.customer_info['customer_id']
        new_key = api_manager.generate_api_key(customer_id, key_name)
        
        if new_key:
            return jsonify({
                'status': 'success',
                'api_key': new_key,
                'key_name': key_name,
                'message': 'Store this key securely - it cannot be retrieved again'
            })
        else:
            return jsonify({
                'error': 'Failed to create API key'
            }), 500

# Complete setup function
def setup_api_system(app, whitelist_manager, customer_manager):
    """Setup complete API system"""
    
    # Initialize API manager
    api_manager = APIManager(whitelist_manager, customer_manager)
    
    # Create all endpoints
    create_api_endpoints(app, api_manager, whitelist_manager)
    create_management_endpoints(app, api_manager)
    
    logger.info("🚀 Complete API system initialized!")
    
    return api_manager

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation | FastPing.It</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3a 50%, #2d2d5f 100%);
            color: #ffffff;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            min-height: 100vh;
            overflow-x: hidden;
        }

        .top-nav {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding: 1rem 2rem;
            z-index: 1000;
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #40e0ff, #4facfe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-decoration: none;
        }

        .nav-links {
            display: flex;
            gap: 2rem;
            list-style: none;
        }

        .nav-links a {
            color: #ccc;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.3s ease;
        }

        .nav-links a:hover, .nav-links a.active {
            color: #40e0ff;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 120px 2rem 2rem;
        }

        .header {
            text-align: center;
            margin-bottom: 4rem;
        }

        .page-title {
            font-size: clamp(2.5rem, 5vw, 4rem);
            font-weight: 800;
            background: linear-gradient(135deg, #40e0ff, #4facfe, #00f2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 1rem;
            text-shadow: 0 0 30px rgba(64, 224, 255, 0.3);
        }

        .page-subtitle {
            font-size: 1.3rem;
            color: #b3b3ff;
            font-weight: 300;
            line-height: 1.6;
        }

        .api-overview {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 2.5rem;
            margin-bottom: 3rem;
            position: relative;
            overflow: hidden;
        }

        .api-overview::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4, #feca57);
            background-size: 300% 100%;
            animation: gradient 3s ease infinite;
        }

        @keyframes gradient {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .section-title {
            font-size: 2rem;
            font-weight: 700;
            color: #40e0ff;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .content {
            color: #ccc;
            line-height: 1.8;
            font-size: 1.1rem;
        }

        .content p {
            margin-bottom: 1rem;
        }

        .content ul {
            margin: 1rem 0 1rem 2rem;
        }

        .content li {
            margin-bottom: 0.5rem;
        }

        .highlight-box {
            background: rgba(64, 224, 255, 0.1);
            border: 1px solid rgba(64, 224, 255, 0.3);
            border-radius: 15px;
            padding: 1.5rem;
            margin: 1.5rem 0;
        }

        .highlight-title {
            font-weight: 600;
            color: #40e0ff;
            margin-bottom: 0.5rem;
        }

        .endpoint-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 2rem;
            margin-bottom: 2rem;
            transition: all 0.3s ease;
        }

        .endpoint-card:hover {
            border-color: rgba(64, 224, 255, 0.5);
            box-shadow: 0 10px 30px rgba(64, 224, 255, 0.2);
        }

        .endpoint-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }

        .method-badge {
            padding: 0.5rem 1rem;
            border-radius: 25px;
            font-weight: 600;
            font-size: 0.9rem;
            text-transform: uppercase;
        }

        .method-get {
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
            border: 1px solid #00ff88;
        }

        .method-post {
            background: rgba(64, 224, 255, 0.2);
            color: #40e0ff;
            border: 1px solid #40e0ff;
        }

        .method-put {
            background: rgba(255, 165, 0, 0.2);
            color: #ffa500;
            border: 1px solid #ffa500;
        }

        .method-delete {
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
            border: 1px solid #ff6b6b;
        }

        .endpoint-path {
            font-family: 'Fira Code', 'Monaco', monospace;
            font-size: 1.3rem;
            color: #fff;
            font-weight: 600;
        }

        .plan-badge {
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .plan-basic {
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
        }

        .plan-premium {
            background: rgba(255, 165, 0, 0.2);
            color: #ffa500;
        }

        .plan-enterprise {
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
        }

        .code-block {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 1.5rem;
            margin: 1rem 0;
            overflow-x: auto;
            position: relative;
        }

        .code-block pre {
            margin: 0;
            font-family: 'Fira Code', 'Monaco', monospace;
            font-size: 0.9rem;
            line-height: 1.4;
        }

        .copy-button {
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background: rgba(64, 224, 255, 0.2);
            border: 1px solid #40e0ff;
            color: #40e0ff;
            padding: 0.3rem 0.8rem;
            border-radius: 5px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .copy-button:hover {
            background: rgba(64, 224, 255, 0.3);
        }

        .params-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 10px;
            overflow: hidden;
        }

        .params-table th,
        .params-table td {
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .params-table th {
            background: rgba(64, 224, 255, 0.1);
            color: #40e0ff;
            font-weight: 600;
        }

        .params-table td {
            color: #ccc;
        }

        .response-example {
            background: rgba(0, 255, 136, 0.05);
            border: 1px solid rgba(0, 255, 136, 0.2);
            border-radius: 10px;
            padding: 1.5rem;
            margin: 1rem 0;
        }

        .auth-section {
            background: rgba(255, 165, 0, 0.1);
            border: 1px solid rgba(255, 165, 0, 0.3);
            border-radius: 15px;
            padding: 2rem;
            margin: 2rem 0;
        }

        .floating-particles {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            overflow: hidden;
            z-index: 1;
        }

        .particle {
            position: absolute;
            width: 4px;
            height: 4px;
            background: rgba(64, 224, 255, 0.6);
            border-radius: 50%;
            animation: float 8s infinite ease-in-out;
        }

        .particle:nth-child(2n) {
            background: rgba(255, 107, 107, 0.6);
            animation-delay: -2s;
        }

        .particle:nth-child(3n) {
            background: rgba(78, 205, 196, 0.6);
            animation-delay: -4s;
        }

        @keyframes float {
            0%, 100% { transform: translateY(100vh) rotate(0deg); opacity: 0; }
            10%, 90% { opacity: 1; }
            50% { transform: translateY(-100px) rotate(180deg); }
        }

        @media (max-width: 768px) {
            .nav-links {
                display: none;
            }
            
            .container {
                padding: 100px 1rem 2rem;
            }
            
            .endpoint-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .endpoint-path {
                font-size: 1rem;
                word-break: break-all;
            }
            
            .params-table {
                font-size: 0.9rem;
            }
            
            .params-table th,
            .params-table td {
                padding: 0.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="floating-particles">
        <div class="particle" style="left: 10%; animation-delay: 0s;"></div>
        <div class="particle" style="left: 20%; animation-delay: -1s;"></div>
        <div class="particle" style="left: 30%; animation-delay: -2s;"></div>
        <div class="particle" style="left: 40%; animation-delay: -3s;"></div>
        <div class="particle" style="left: 50%; animation-delay: -4s;"></div>
        <div class="particle" style="left: 60%; animation-delay: -5s;"></div>
        <div class="particle" style="left: 70%; animation-delay: -6s;"></div>
        <div class="particle" style="left: 80%; animation-delay: -7s;"></div>
        <div class="particle" style="left: 90%; animation-delay: -8s;"></div>
    </div>

    <nav class="top-nav">
        <div class="nav-container">
            <a href="/" class="logo">FastPing.It</a>
            <ul class="nav-links">
                <li><a href="/">Home</a></li>
                <li><a href="/stats.html">Stats</a></li>
                <li><a href="/docs" class="active">API Docs</a></li>
                <li><a href="/about.html">About</a></li>
                <li><a href="/contact.html">Contact</a></li>
            </ul>
        </div>
    </nav>

    <div class="container">
        <div class="header">
            <h1 class="page-title">API Documentation</h1>
            <p class="page-subtitle">
                Programmatic access to the world's fastest proxy network. 
                Sub-40ms response times, 99.97% uptime, enterprise-grade security.
            </p>
        </div>

        <div class="api-overview">
            <h2 class="section-title">🚀 Getting Started</h2>
            <div class="content">
                <p>
                    The FastPing.It API provides lightning-fast proxy testing, request forwarding, 
                    and network analysis capabilities. All endpoints return JSON responses and support 
                    both REST and real-time access patterns.
                </p>
                
                <div class="highlight-box">
                    <div class="highlight-title">🔑 Authentication Required</div>
                    <p>All API endpoints require authentication using your API key. Get your key from your customer dashboard or contact support.</p>
                </div>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Base URL</h3>
                <div class="code-block">
                    <pre>https://fastping.it/api/v1</pre>
                    <button class="copy-button" onclick="copyToClipboard('https://fastping.it/api/v1')">Copy</button>
                </div>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Rate Limits by Plan</h3>
                <ul>
                    <li><strong>Basic Plan:</strong> 100 requests/minute, 10,000/day</li>
                    <li><strong>Premium Plan:</strong> 500 requests/minute, 50,000/day</li>
                    <li><strong>Enterprise Plan:</strong> 2,000 requests/minute, 200,000/day</li>
                </ul>
            </div>
        </div>

        <div class="auth-section">
            <h2 class="section-title">🔐 Authentication</h2>
            <div class="content">
                <p>Include your API key in the Authorization header as a Bearer token:</p>
                
                <div class="code-block">
                    <pre>Authorization: Bearer fpk_your_api_key_here</pre>
                    <button class="copy-button" onclick="copyToClipboard('Authorization: Bearer fpk_your_api_key_here')">Copy</button>
                </div>

                <p>Or include it as a query parameter:</p>
                
                <div class="code-block">
                    <pre>GET /api/v1/ping?api_key=fpk_your_api_key_here</pre>
                    <button class="copy-button" onclick="copyToClipboard('GET /api/v1/ping?api_key=fpk_your_api_key_here')">Copy</button>
                </div>
            </div>
        </div>

        <!-- Ping Endpoint -->
        <div class="endpoint-card">
            <div class="endpoint-header">
                <span class="method-badge method-get">GET</span>
                <span class="endpoint-path">/api/v1/ping</span>
                <span class="plan-badge plan-basic">Basic+</span>
            </div>
            
            <div class="content">
                <p><strong>Ultra-fast connectivity test</strong> - The fastest possible response to verify your connection and measure latency.</p>
                
                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Example Request</h4>
                <div class="code-block">
                    <pre>curl -H "Authorization: Bearer fpk_your_api_key" \
     https://fastping.it/api/v1/ping</pre>
                    <button class="copy-button" onclick="copyToClipboard('curl -H \"Authorization: Bearer fpk_your_api_key\" https://fastping.it/api/v1/ping')">Copy</button>
                </div>

                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Response</h4>
                <div class="response-example">
                    <pre>{
  "status": "success",
  "message": "pong",
  "timestamp": 1704067200.123,
  "response_time_ms": 12.5,
  "server": "FastPing.It"
}</pre>
                </div>
            </div>
        </div>

        <!-- Test Endpoint -->
        <div class="endpoint-card">
            <div class="endpoint-header">
                <span class="method-badge method-get">GET</span>
                <span class="method-badge method-post">POST</span>
                <span class="endpoint-path">/api/v1/test</span>
                <span class="plan-badge plan-basic">Basic+</span>
            </div>
            
            <div class="content">
                <p><strong>Full proxy analysis</strong> - Complete request/response analysis with headers, timing, and client information.</p>
                
                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Example Request</h4>
                <div class="code-block">
                    <pre>curl -X POST \
     -H "Authorization: Bearer fpk_your_api_key" \
     -H "Content-Type: application/json" \
     -d '{"test_data": "hello world"}' \
     https://fastping.it/api/v1/test</pre>
                    <button class="copy-button" onclick="copyToClipboard('curl -X POST -H \"Authorization: Bearer fpk_your_api_key\" -H \"Content-Type: application/json\" -d \'{\"test_data\": \"hello world\"}\' https://fastping.it/api/v1/test')">Copy</button>
                </div>

                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Response</h4>
                <div class="response-example">
                    <pre>{
  "status": "success",
  "test_type": "full_analysis",
  "request_info": {
    "method": "POST",
    "headers": {...},
    "client_ip": "203.0.113.1",
    "user_agent": "curl/7.68.0",
    "content_type": "application/json"
  },
  "data_received": {
    "test_data": "hello world"
  },
  "server_info": {
    "processing_time_ms": 15.2,
    "timestamp": "2024-01-01T12:00:00Z"
  },
  "customer_info": {
    "plan": "basic",
    "remaining_requests_minute": 99,
    "remaining_requests_day": 9999
  }
}</pre>
                </div>
            </div>
        </div>

        <!-- Proxy Endpoint -->
        <div class="endpoint-card">
            <div class="endpoint-header">
                <span class="method-badge method-get">GET</span>
                <span class="method-badge method-post">POST</span>
                <span class="method-badge method-put">PUT</span>
                <span class="method-badge method-delete">DELETE</span>
                <span class="endpoint-path">/api/v1/proxy</span>
                <span class="plan-badge plan-premium">Premium+</span>
            </div>
            
            <div class="content">
                <p><strong>Full proxy forwarding</strong> - Forward requests to any URL through our global proxy network with complete response capture.</p>
                
                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Parameters</h4>
                <table class="params-table">
                    <thead>
                        <tr>
                            <th>Parameter</th>
                            <th>Type</th>
                            <th>Required</th>
                            <th>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><code>url</code></td>
                            <td>string</td>
                            <td>Yes</td>
                            <td>Target URL to proxy the request to</td>
                        </tr>
                    </tbody>
                </table>

                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Example Request</h4>
                <div class="code-block">
                    <pre>curl -H "Authorization: Bearer fpk_your_api_key" \
     "https://fastping.it/api/v1/proxy?url=https://httpbin.org/get"</pre>
                    <button class="copy-button" onclick="copyToClipboard('curl -H \"Authorization: Bearer fpk_your_api_key\" \"https://fastping.it/api/v1/proxy?url=https://httpbin.org/get\"')">Copy</button>
                </div>

                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Response</h4>
                <div class="response-example">
                    <pre>{
  "status": "success",
  "proxy_response": {
    "status_code": 200,
    "headers": {
      "content-type": "application/json",
      "content-length": "312"
    },
    "content": "{\"args\": {}, \"headers\": {...}}",
    "content_length": 312
  },
  "request_info": {
    "target_url": "https://httpbin.org/get",
    "method": "GET",
    "processing_time_ms": 145.7
  }
}</pre>
                </div>
            </div>
        </div>

        <!-- Stats Endpoint -->
        <div class="endpoint-card">
            <div class="endpoint-header">
                <span class="method-badge method-get">GET</span>
                <span class="endpoint-path">/api/v1/stats</span>
                <span class="plan-badge plan-basic">Basic+</span>
            </div>
            
            <div class="content">
                <p><strong>Usage statistics</strong> - Get detailed usage analytics for your account including request counts, response times, and rate limit status.</p>
                
                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Example Request</h4>
                <div class="code-block">
                    <pre>curl -H "Authorization: Bearer fpk_your_api_key" \
     https://fastping.it/api/v1/stats</pre>
                    <button class="copy-button" onclick="copyToClipboard('curl -H \"Authorization: Bearer fpk_your_api_key\" https://fastping.it/api/v1/stats')">Copy</button>
                </div>

                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Response</h4>
                <div class="response-example">
                    <pre>{
  "status": "success",
  "customer_id": "cust_abc123",
  "plan": "premium",
  "usage_stats_30d": {
    "total_requests": 45230,
    "avg_response_time_ms": 38.5,
    "active_days": 28,
    "total_bytes_transferred": 2345678
  },
  "current_limits": {
    "requests_this_minute": 15,
    "requests_today": 1250,
    "remaining_minute": 485,
    "remaining_day": 48750
  },
  "generated_at": "2024-01-01T12:00:00Z"
}</pre>
                </div>
            </div>
        </div>

        <!-- Batch Endpoint -->
        <div class="endpoint-card">
            <div class="endpoint-header">
                <span class="method-badge method-post">POST</span>
                <span class="endpoint-path">/api/v1/batch</span>
                <span class="plan-badge plan-enterprise">Enterprise</span>
            </div>
            
            <div class="content">
                <p><strong>Batch processing</strong> - Process multiple requests simultaneously for maximum efficiency. Limited to 10 requests per batch.</p>
                
                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Request Body</h4>
                <div class="code-block">
                    <pre>{
  "requests": [
    {
      "url": "https://httpbin.org/get",
      "headers": {"Custom-Header": "value"}
    },
    {
      "url": "https://httpbin.org/status/200"
    }
  ]
}</pre>
                </div>

                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Example Request</h4>
                <div class="code-block">
                    <pre>curl -X POST \
     -H "Authorization: Bearer fpk_your_api_key" \
     -H "Content-Type: application/json" \
     -d '{"requests": [{"url": "https://httpbin.org/get"}]}' \
     https://fastping.it/api/v1/batch</pre>
                    <button class="copy-button" onclick="copyToClipboard('curl -X POST -H \"Authorization: Bearer fpk_your_api_key\" -H \"Content-Type: application/json\" -d \'{\"requests\": [{\"url\": \"https://httpbin.org/get\"}]}\' https://fastping.it/api/v1/batch')">Copy</button>
                </div>

                <h4 style="color: #40e0ff; margin: 1.5rem 0 1rem 0;">Response</h4>
                <div class="response-example">
                    <pre>{
  "status": "success",
  "batch_id": "batch_xyz789",
  "total_requests": 2,
  "successful_requests": 2,
  "failed_requests": 0,
  "results": [
    {
      "index": 0,
      "status": "success",
      "url": "https://httpbin.org/get",
      "status_code": 200,
      "response_time_ms": 142.3,
      "content_length": 312
    }
  ],
  "processing_time_ms": 156.7
}</pre>
                </div>
            </div>
        </div>

        <!-- Error Handling -->
        <div class="api-overview">
            <h2 class="section-title">⚠️ Error Handling</h2>
            <div class="content">
                <p>The API uses standard HTTP status codes and returns detailed error information in JSON format.</p>
                
                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Common Status Codes</h3>
                <ul>
                    <li><strong>200 OK:</strong> Request successful</li>
                    <li><strong>401 Unauthorized:</strong> Invalid or missing API key</li>
                    <li><strong>403 Forbidden:</strong> Insufficient plan level for endpoint</li>
                    <li><strong>429 Too Many Requests:</strong> Rate limit exceeded</li>
                    <li><strong>500 Internal Server Error:</strong> Server error</li>
                </ul>

                <h3 style="color: #40e0ff; margin: 2rem 0 1rem 0;">Error Response Format</h3>
                <div class="code-block">
                    <pre>{
  "error": "Rate limit exceeded",
  "message": "You have exceeded your rate limit of 100 requests per minute",
  "limit": 100,
  "window": "per_minute",
  "reset_at": "2024-01-01T12:01:00Z"
}</pre>
                </div>
            </div>
        </div>

        <!-- Rate Limit Headers -->
        <div class="api-overview">
            <h2 class="section-title">📊 Rate Limit Headers</h2>
            <div class="content">
                <p>All successful responses include rate limit information in the headers:</p>
                
                <div class="code-block">
                    <pre>X-RateLimit-Remaining-Minute: 85
X-RateLimit-Remaining-Day: 9547
X-RateLimit-Reset-Minute: 2024-01-01T12:01:00Z
X-RateLimit-Reset-Day: 2024-01-02T00:00:00Z</pre>
                </div>
            </div>
        </div>

        <!-- SDKs and Examples -->
        <div class="api-overview">
            <h2 class="section-title">💻 SDKs & Examples</h2>
            <div