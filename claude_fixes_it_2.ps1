# Proper Docker Compose File Creation
# Run these commands in your terminal

# 1. Navigate to the right directory
cd ~/fastping.it.com/fastping-it

# 2. Backup the broken docker-compose.yml
cp docker-compose.yml docker-compose.yml.broken.$(date +%Y%m%d_%H%M%S)

# 3. Create a NEW docker-compose.yml file (don't paste this in terminal!)
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  fastping:
    build: .
    container_name: fastping-it_fastping_1
    ports:
      - "9876:9876"
    volumes:
      - ./ultimate_fastping_app.py:/app/ultimate_fastping_app.py
      - ./fastping.db:/app/fastping.db
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=your-secret-key-here
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9876/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    container_name: fastping-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - fastping
    restart: unless-stopped

networks:
  default:
    name: fastping-network
EOF

# 4. Verify the file was created correctly
echo "=== Checking created file ==="
ls -la docker-compose.yml
echo ""

# 5. Test YAML syntax
echo "=== Testing YAML syntax ==="
python3 -c "
import yaml
try:
    with open('docker-compose.yml', 'r') as f:
        yaml.safe_load(f)
    print('✅ YAML syntax is valid')
except yaml.YAMLError as e:
    print(f'❌ YAML Error: {e}')
"

# 6. Validate with docker-compose
echo "=== Validating with Docker Compose ==="
docker-compose config

# 7. Start the services
echo "=== Starting services ==="
docker-compose up -d

# 8. Check status
echo "=== Checking status ==="
docker-compose ps

# 9. Test health
echo "=== Testing health ==="
sleep 10
curl -s http://localhost:9876/health | python3 -m json.tool