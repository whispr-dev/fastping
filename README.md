# FastPing Service - Complete Operations Manual

## Quick Reference

Service URL: http://161.35.248.233
Admin Dashboard: http://161.35.248.233/admin/stats
Customer Dashboard: http://161.35.248.233/dashboard
API Base: http://161.35.248.233/api/v1/

## Service Management

### Start/Stop/Restart Service
```bash
# SSH into server
ssh wofl@161.35.248.233
cd ~/fastping.it.com/fastping-it

# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart specific service
docker-compose restart fastping

# View service status
docker-compose ps

# View logs
docker-compose logs fastping
docker-compose logs fastping --tail 50
```

### Emergency Service Reset
```bash
# Nuclear restart (if things go wrong)
docker-compose down
docker system prune -f
docker volume prune -f
sudo systemctl restart docker
docker-compose up -d
```

### Update Code
```bash
# From local machine - upload new code
scp "D:/code/fastping/fastping-it/ultimate_fastping_app.py" wofl@161.35.248.233:/home/wofl/fastping.it.com/fastping-it/

# On server - rebuild and restart
ssh wofl@161.35.248.233
cd ~/fastping.it.com/fastping-it
docker-compose build --no-cache
docker-compose up -d
```

## Customer Management

### Create New Customer
```bash
# Create customer with automatic IP allocation
curl -X POST http://localhost:9876/admin/create_test_customer -H "Content-Type: application/json" -d '{"email":"customer@example.com","plan_type":"enterprise"}'

# Response includes: customer_id, api_key, allocated_ips
```

### View All Customers
```bash
# Web interface
curl http://localhost:9876/admin/stats

# Via database query
docker-compose exec fastping python -c "
import sys
sys.path.append('/app')
from ultimate_fastping_app import *

with app.app_context():
    customers = Customer.query.all()
    for c in customers:
        print(f'ID: {c.id} | Email: {c.email} | Plan: {c.plan_type} | API Key: {c.api_key}')
"
```

### Create Dashboard Login for Customer
```bash
# Give existing customer dashboard access
curl -X POST http://localhost:9876/admin/create_dashboard_account -d "customer_id=CUSTOMER_ID_HERE&email=customer@example.com&password=securepassword"
```

## IP Whitelisting

### Add IP to Whitelist (Automatic via Customer Creation)
```bash
# When you create a customer, IP is automatically allocated and whitelisted
curl -X POST http://localhost:9876/admin/create_test_customer -H "Content-Type: application/json" -d '{"email":"user@example.com","plan_type":"enterprise"}'
```

### Manually Add IP to Resource Pool
```bash
# Add new IP to available pool
docker-compose exec fastping python -c "
import sys
sys.path.append('/app')
from ultimate_fastping_app import *
import uuid

with app.app_context():
    new_ip = ResourcePool(
        id='manual_' + str(uuid.uuid4()),
        ip_address='YOUR_NEW_IP_HERE',
        resource_type='ip_only',
        reserved_for_plan='enterprise'
    )
    db.session.add(new_ip)
    db.session.commit()
    print('Added IP to pool!')
"
```

### Check IP Whitelist Status
```bash
# Check if IP is whitelisted
curl http://161.35.248.233/proxy-test
# Success = whitelisted, "Access denied" = not whitelisted

# View all allocated IPs
docker-compose exec fastping python -c "
import sys
sys.path.append('/app')
from ultimate_fastping_app import *

with app.app_context():
    allocations = ResourceAllocation.query.filter_by(is_active=True).all()
    for alloc in allocations:
        customer = Customer.query.get(alloc.customer_id)
        print(f'IP: {alloc.ip_address} | Customer: {customer.email if customer else \"Unknown\"} | Plan: {customer.plan_type if customer else \"Unknown\"}')
"
```

## Dashboard Access

### Admin Dashboard
```bash
# View admin statistics
curl http://161.35.248.233/admin/stats

# Or open in browser:
# http://161.35.248.233/admin/stats
```

### Customer Dashboard
```bash
# Login page
curl http://161.35.248.233/dashboard/login

# Direct browser access:
# URL: http://161.35.248.233/dashboard/login
# Use customer email + password set via create_dashboard_account
```

## API Usage

### Basic API Ping
```bash
# Using API key authentication
curl -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/ping

# Different formats
curl -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/ping?format=text
curl -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/ping?format=xml
curl -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/ping?format=html
```

### Proxy Detection API
```bash
# Full proxy analysis
curl -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/proxy-test

# Different formats
curl -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/proxy-test?format=text
curl -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/proxy-test?format=xml
```

### Whitelisted IP Endpoints (No API key needed)
```bash
# Basic proxy test (requires whitelisted IP)
curl http://161.35.248.233/proxy-test

# Format-specific endpoints
curl http://161.35.248.233/text
curl http://161.35.248.233/json
curl http://161.35.248.233/xml
curl http://161.35.248.233/html
```

## Troubleshooting

### Check Service Health
```bash
# Health check
curl http://161.35.248.233/health

# Detailed status
docker-compose ps
docker-compose logs fastping --tail 20

# Check if ports are listening
netstat -tulpn | grep 9876
netstat -tulpn | grep 80
```

### Common Issues and Fixes

#### "Access denied" for proxy-test
```bash
# Your IP isn't whitelisted - create customer to get whitelisted
curl -X POST http://localhost:9876/admin/create_test_customer -H "Content-Type: application/json" -d '{"email":"your@email.com","plan_type":"enterprise"}'
```

#### 404 errors
```bash
# Check if FastPing is running
curl http://localhost:9876/health

# If not working, restart service
docker-compose restart fastping
```

#### "Invalid API key"
```bash
# Get correct API key from customer creation response
# Or check admin dashboard: http://161.35.248.233/admin/stats
```

#### Dashboard login fails
```bash
# Ensure dashboard account exists
curl -X POST http://localhost:9876/admin/create_dashboard_account -d "customer_id=CUSTOMER_ID&email=user@example.com&password=newpassword"
```

#### Container won't start
```bash
# Check Docker logs
docker-compose logs fastping

# Force rebuild
docker-compose build --no-cache
docker-compose up -d

# Nuclear option
docker-compose down
docker system prune -f
docker-compose up -d
```

## Monitoring and Maintenance

### View Usage Statistics
```bash
# Admin dashboard stats
curl http://161.35.248.233/admin/stats

# Database query for detailed stats
docker-compose exec fastping python -c "
import sys
sys.path.append('/app')
from ultimate_fastping_app import *

with app.app_context():
    total_customers = Customer.query.count()
    total_requests = UsageLog.query.count()
    active_allocations = ResourceAllocation.query.filter_by(is_active=True).count()
    
    print(f'Total Customers: {total_customers}')
    print(f'Total Requests: {total_requests}')
    print(f'Active IP Allocations: {active_allocations}')
"
```

### Performance Testing
```bash
# Install hey load testing tool
curl -L https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64 -o hey
chmod +x hey
sudo mv hey /usr/local/bin/

# Test API performance
hey -n 100 -c 10 -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/ping

# Test whitelisted endpoint performance
hey -n 100 -c 10 http://161.35.248.233/proxy-test
```

### Database Backup
```bash
# Backup SQLite database
docker-compose exec fastping cp /app/fastping.db /app/fastping_backup_$(date +%Y%m%d).db

# Copy backup to host
docker cp fastping-it_fastping_1:/app/fastping_backup_$(date +%Y%m%d).db ./
```

## Important File Locations

### On Server
- Project Directory: /home/wofl/fastping.it.com/fastping-it/
- Main App: /home/wofl/fastping.it.com/fastping-it/ultimate_fastping_app.py
- Docker Compose: /home/wofl/fastping.it.com/fastping-it/docker-compose.yml
- Nginx Config: /home/wofl/fastping.it.com/fastping-it/nginx.conf

### In Container
- App File: /app/ultimate_fastping_app.py
- Database: /app/fastping.db
- Logs: docker-compose logs fastping

## Quick Commands Cheat Sheet

```bash
# SSH to server
ssh wofl@161.35.248.233

# Create customer + get API key
curl -X POST http://localhost:9876/admin/create_test_customer -H "Content-Type: application/json" -d '{"email":"user@example.com","plan_type":"enterprise"}'

# Test API
curl -H "Authorization: Bearer YOUR_API_KEY" http://161.35.248.233/api/v1/ping

# Test proxy detection
curl http://161.35.248.233/proxy-test

# Check admin stats
curl http://161.35.248.233/admin/stats

# Restart service
docker-compose restart fastping

# View logs
docker-compose logs fastping --tail 20

# Check health
curl http://161.35.248.233/health
```

## Dashboard Features

### Customer Dashboard Color Themes
- Automatically cycles through 8 beautiful themes every 45 seconds
- Themes: Blue Ocean, Purple Storm, Forest Green, Sunset Orange, Rose Pink, Ocean Teal, Cosmic Indigo, Fire Red
- Auto-refreshes data every 30 seconds

### Available Dashboard Data
- Real-time usage statistics (last 7 days)
- Success rate and response times
- Whitelisted IP addresses
- API key management
- Daily usage breakdown
- Rate limits and quotas

### Manually Whitelist Specific IP
```bash
# Add specific IP to existing customer
docker-compose exec fastping python -c "
import sys
sys.path.append('/app')
from ultimate_fastping_app import *
from datetime import datetime, timedelta
import uuid

with app.app_context():
    # Get existing customer
    customer = Customer.query.filter_by(email='customer@example.com').first()
    if customer:
        # Create allocation for specific IP
        allocation = ResourceAllocation(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            ip_address='NEW_IP_ADDRESS_HERE',
            resource_type='ip_only',
            expires_at=datetime.utcnow() + timedelta(days=365),
            is_active=True
        )
        db.session.add(allocation)
        db.session.commit()
        print(f'Added IP to customer {customer.email}')
    else:
        print('Customer not found')
"
```

### Create Customer with Custom IP
```bash
# Create customer then manually assign specific IP
curl -X POST http://localhost:9876/admin/create_test_customer -H "Content-Type: application/json" -d '{"email":"newuser@example.com","plan_type":"enterprise"}'

# Then run the manual whitelist command above with the new customer email
```

### Mail Server Management
```bash
# Check if mailserver is running
docker-compose ps | grep mailserver

# View mailserver logs
docker-compose logs mailserver

# Create email accounts
./setup.sh email add admin@fastping.it.com your_password
./setup.sh email add ping@fastping.it.com ping_password

# Configure DKIM
./setup.sh config dkim

# Test mail connectivity
telnet mail.fastping.it.com 587
```

## Security Key Generation

### Generate Secure Keys
```bash
# Generate SECRET_KEY
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# Generate multiple keys
python3 -c "
import secrets
print('SECRET_KEY=' + secrets.token_hex(32))
print('BACKUP_KEY=' + secrets.token_hex(32))
"

# Using OpenSSL
openssl rand -hex 32
```

### Set Environment Variables
```bash
# Create .env file
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" > .env
echo "DATABASE_URL=sqlite:///fastping.db" >> .env

# Restart services to load new keys
docker-compose restart fastping
```

## Monthly Billing Cron Job
```bash
# Open crontab editor
crontab -e

# Add this line for monthly billing on 1st at 2 AM
0 2 1 * * curl -X POST https://yourservice.com/api/billing/process-overages

# Verify cron job was added
crontab -l

# Check if cron service is running
sudo systemctl status cron
```

That's your complete FastPing operations manual - CLEAN and copy-pasteable!