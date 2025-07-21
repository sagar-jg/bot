# WhatsApp Bot API

A production-ready FastAPI-based WhatsApp chatbot with advanced conversation tracking, feedback collection, and comprehensive deployment automation using PM2.

## 🚀 Features

- **FastAPI Backend**: High-performance async API with automatic documentation
- **WhatsApp Integration**: Complete WhatsApp Business API integration
- **AI-Powered Responses**: CrewAI and OpenAI integration for intelligent responses
- **Database Management**: PostgreSQL with conversation history and feedback tracking
- **Vector Search**: Pinecone integration for advanced document retrieval
- **Production Ready**: PM2 process management with monitoring and auto-restart
- **Docker Support**: Complete containerization with Docker Compose
- **Nginx Reverse Proxy**: Load balancing and SSL termination
- **Monitoring & Logging**: Comprehensive logging and health checks
- **Backup & Recovery**: Automated backup system

## 📁 Project Structure

```
bot/
├── api/                      # FastAPI application
│   ├── main.py               # Main application file
│   ├── db.py                 # Database models and operations
│   ├── schemas.py            # Pydantic schemas
│   └── whatsapp_service.py   # WhatsApp business logic
├── config/                   # Configuration files
│   ├── production.json       # Production settings
│   ├── development.json      # Development settings
│   └── .env.example          # Environment variables template
├── scripts/                  # Deployment and management scripts
│   ├── deploy.sh             # Main deployment script
│   ├── start.sh              # Application startup script
│   ├── stop.sh               # Application stop script
│   ├── restart.sh            # Application restart script
│   ├── monitor.sh            # Interactive monitoring dashboard
│   ├── backup.sh             # Backup creation script
│   ├── health_check.sh       # Health monitoring script
│   ├── update.sh             # Application update script
│   ├── logs.sh               # Log management script
│   ├── setup_db.sh           # Database initialization
│   └── init.sql              # SQL initialization script
├── nginx/                    # Nginx configuration
│   └── nginx.conf            # Reverse proxy configuration
├── logs/                     # Application logs (created automatically)
├── data/                     # Application data
│   ├── backups/              # Automated backups
│   └── uploads/              # File uploads
├── ecosystem.config.js       # PM2 configuration
├── docker-compose.yml       # Docker orchestration
├── Dockerfile               # Container definition
└── requirements.txt         # Python dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js (for PM2)
- PostgreSQL (optional, can use Docker)
- Git

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/sagar-jg/bot.git
cd bot

# Copy environment configuration
cp config/.env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Install Dependencies

```bash
# Install PM2 globally
npm install -g pm2

# Make scripts executable
chmod +x scripts/*.sh
```

### 3. Deploy

```bash
# Run the deployment script
bash scripts/deploy.sh
```

That's it! The deployment script will:
- Create virtual environment
- Install Python dependencies
- Setup database
- Start the application with PM2
- Run health checks

## 🔧 Management Commands

### Application Management

```bash
# Deploy application
bash scripts/deploy.sh

# Start application
bash scripts/start.sh

# Stop application
bash scripts/stop.sh

# Restart application
bash scripts/restart.sh

# Update application
bash scripts/update.sh
```

### Monitoring & Maintenance

```bash
# Interactive monitoring dashboard
bash scripts/monitor.sh

# View logs
bash scripts/logs.sh

# Health check
bash scripts/health_check.sh

# Create backup
bash scripts/backup.sh

# PM2 commands
pm2 status
pm2 logs whatsapp-bot-api
pm2 monit
pm2 restart whatsapp-bot-api
```

### Log Management

```bash
# View all logs
bash scripts/logs.sh

# Follow logs in real-time
bash scripts/logs.sh -f

# View specific log type
bash scripts/logs.sh -t app     # Application logs
bash scripts/logs.sh -t pm2     # PM2 logs
bash scripts/logs.sh -t error   # Error logs

# List all log files
bash scripts/logs.sh -l

# Clean old logs
bash scripts/logs.sh -c

# Show log file sizes
bash scripts/logs.sh -s
```

## 🐳 Docker Deployment

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f whatsapp-bot

# Stop all services
docker-compose down

# Update and restart
docker-compose pull && docker-compose up -d
```

### Services Included

- **WhatsApp Bot API**: Main application
- **PostgreSQL**: Database
- **Redis**: Caching (optional)
- **Nginx**: Reverse proxy and load balancer

## 📋 Environment Configuration

### Required Environment Variables

```env
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/bot_db

# WhatsApp
WHATSAPP_TOKEN=your_whatsapp_token
WHATSAPP_VERIFY_TOKEN=your_verify_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

# AI Services
OPENAI_API_KEY=your_openai_api_key
CREWAI_API_KEY=your_crewai_api_key
PINECONE_API_KEY=your_pinecone_api_key

# Server
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
```

See `config/.env.example` for all available options.

## 📊 API Endpoints

### Main Endpoints

- **POST** `/whatsapp/query` - Process WhatsApp messages
- **POST** `/feedback` - Submit user feedback
- **GET** `/conversation/{user_id}` - Get conversation history
- **GET** `/health` - Health check endpoint
- **GET** `/analytics/feedback` - Feedback analytics
- **GET** `/docs` - API documentation (Swagger UI)

### Example Request

```bash
# Send a message
curl -X POST "http://localhost:8000/whatsapp/query" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "message": "Hello, how can you help me?"
  }'

# Check health
curl http://localhost:8000/health
```

## 📊 Monitoring & Analytics

### Built-in Monitoring

1. **Health Checks**: Automated health monitoring
2. **Performance Metrics**: Response time and success rate tracking
3. **Database Analytics**: Conversation and feedback analytics
4. **Log Analysis**: Structured logging with rotation
5. **Resource Monitoring**: CPU, memory, and disk usage

### Monitoring Dashboard

```bash
# Launch interactive monitoring
bash scripts/monitor.sh
```

Provides:
- Real-time system stats
- Application health status
- PM2 process information
- Recent log entries
- Quick management actions

## 🔒 Security Features

- **Rate Limiting**: Configurable request rate limits
- **CORS Protection**: Cross-origin request management
- **Input Validation**: Pydantic schema validation
- **Health Checks**: Regular system health monitoring
- **Log Security**: Sensitive data filtering in logs
- **Environment Isolation**: Environment-specific configurations

## 💾 Backup & Recovery

### Automated Backups

```bash
# Create backup
bash scripts/backup.sh

# Backups include:
# - Database dump
# - Configuration files
# - Application logs
# - Uploaded files
```

### Backup Features

- Automatic compression
- Retention policy (keeps last 10 backups)
- Incremental backups for large datasets
- Easy restoration process

## 🔄 Update Process

```bash
# Automated update with backup
bash scripts/update.sh
```

The update process:
1. Creates backup
2. Pulls latest code
3. Updates dependencies
4. Runs migrations
5. Restarts application
6. Performs health checks

## 🛠️ Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Kill process on port 8000
   sudo lsof -t -i:8000 | xargs kill -9
   ```

2. **Database Connection Issues**
   ```bash
   # Check database status
   bash scripts/setup_db.sh
   ```

3. **PM2 Process Issues**
   ```bash
   # Restart PM2
   pm2 restart whatsapp-bot-api
   # Or full reset
   pm2 delete all && bash scripts/deploy.sh
   ```

4. **Log Analysis**
   ```bash
   # Check error logs
   bash scripts/logs.sh -t error
   # Monitor in real-time
   bash scripts/logs.sh -f
   ```

### Debug Mode

```bash
# Set environment to development
export ENVIRONMENT=development
bash scripts/start.sh
```

## 📈 Performance Optimization

### Production Settings

- **Uvicorn Workers**: Multiple worker processes
- **Database Pool**: Connection pooling for PostgreSQL
- **Caching**: Redis integration for response caching
- **Compression**: Gzip compression for API responses
- **Static Files**: Nginx serving for static content

### Monitoring Recommendations

- Set up external monitoring (Pingdom, UptimeRobot)
- Configure log aggregation (ELK stack, Splunk)
- Monitor database performance
- Set up alerting for critical errors

## 👥 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License.

## 💆‍♂️ Support

For support:
1. Check the troubleshooting section
2. Review the logs: `bash scripts/logs.sh -t error`
3. Open an issue on GitHub
4. Check the health endpoint: `curl http://localhost:8000/health`

---

**Happy Coding! 🚀**
