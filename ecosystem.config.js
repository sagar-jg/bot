module.exports = {
  apps: [
    {
      name: 'whatsapp-bot-api',
      script: 'scripts/start.sh',
      interpreter: '/bin/bash',
      cwd: '/path/to/your/bot',  // Update this path
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'development',
        ENVIRONMENT: 'development',
        PORT: 8000
      },
      env_production: {
        NODE_ENV: 'production',
        ENVIRONMENT: 'production',
        PORT: 8000
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: 'logs/pm2-error.log',
      out_file: 'logs/pm2-out.log',
      log_file: 'logs/pm2-combined.log',
      time: true,
      // Health check configuration
      health_check_grace_period: 3000,
      health_check_fatal_exceptions: true,
      // Advanced PM2 features
      min_uptime: '10s',
      max_restarts: 10,
      restart_delay: 4000,
      // Monitoring
      pmx: true,
      source_map_support: false,
      // Process management
      kill_timeout: 5000,
      listen_timeout: 8000,
      // Environment specific overrides
      env_staging: {
        NODE_ENV: 'staging',
        ENVIRONMENT: 'staging',
        PORT: 8001
      }
    }
  ],

  deploy: {
    production: {
      user: 'ubuntu',  // Update with your server user
      host: 'your-server-ip',  // Update with your server IP
      ref: 'origin/main',
      repo: 'https://github.com/sagar-jg/bot.git',
      path: '/home/ubuntu/bot',  // Update path as needed
      'pre-deploy-local': '',
      'post-deploy': 'source ~/.bashrc && npm install && pm2 reload ecosystem.config.js --env production',
      'pre-setup': '',
      'ssh_options': 'ForwardAgent=yes'
    },
    staging: {
      user: 'ubuntu',
      host: 'your-staging-server-ip',
      ref: 'origin/develop',
      repo: 'https://github.com/sagar-jg/bot.git',
      path: '/home/ubuntu/bot-staging',
      'post-deploy': 'source ~/.bashrc && npm install && pm2 reload ecosystem.config.js --env staging'
    }
  }
};