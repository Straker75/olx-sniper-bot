# 🚀 Deploy OLX Sniper Bot to Fly.io (24/7 Cloud)

## 📋 Prerequisites

1. **Fly.io CLI installed** - Download from [fly.io/docs/hands-on/install-flyctl/](https://fly.io/docs/hands-on/install-flyctl/)
2. **Fly.io account** - Sign up at [fly.io](https://fly.io)
3. **Your Discord webhook URL** - From your Discord server

## 🚀 Quick Deployment Steps

### 1. **Login to Fly.io**
```bash
fly auth login
```

### 2. **Initialize your app** (if not already done)
```bash
fly apps create olx-sniper-bot
```

### 3. **Set your environment variables**
```bash
# Set your OLX search URL
fly secrets set OLX_SEARCH_URL="https://www.olx.pl/oferty/q-iphone/"

# Set your Discord webhook URL
fly secrets set DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"

# Set polling interval (45 seconds)
fly secrets set POLL_INTERVAL="45"

# Set user agent (optional)
fly secrets set USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
```

### 4. **Deploy to Fly.io**
```bash
fly deploy
```

### 5. **Check if it's running**
```bash
fly status
fly logs
```

## 🔧 Configuration

### **Environment Variables (Secrets)**
Set these using `fly secrets set KEY="value"`:

- `OLX_SEARCH_URL` - Your OLX search URL
- `DISCORD_WEBHOOK_URL` - Your Discord webhook URL
- `POLL_INTERVAL` - Polling interval in seconds (default: 45)
- `USER_AGENT` - Browser user agent string

### **Example Commands**
```bash
# Set all secrets at once
fly secrets set \
  OLX_SEARCH_URL="https://www.olx.pl/oferty/q-iphone/" \
  DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1428608006811029504/Jjgdw6tDxuU2x0d2Ra72-s6pPwl6oOXEfSvusSFJkXCZQP_D1os7bsj5sUYOF8S2vVgP" \
  POLL_INTERVAL="45"
```

## 📊 Monitoring Your Bot

### **Check Status**
```bash
fly status
```

### **View Logs**
```bash
fly logs
```

### **Health Check**
Visit: `https://olx-sniper-bot.fly.dev/health`

### **Restart Bot**
```bash
fly apps restart olx-sniper-bot
```

## 🎯 What Happens After Deployment

✅ **Bot runs 24/7** in the cloud  
✅ **Auto-restarts** if it crashes  
✅ **Scales automatically** based on demand  
✅ **Sends Discord notifications** every 45 seconds  
✅ **Tracks seen listings** to avoid duplicates  
✅ **Health monitoring** available  

## 🔍 Troubleshooting

### **Bot not sending messages?**
1. Check your Discord webhook URL: `fly secrets list`
2. View logs: `fly logs`
3. Test webhook manually

### **Bot stopped working?**
1. Check status: `fly status`
2. Restart: `fly apps restart olx-sniper-bot`
3. View logs: `fly logs`

### **Update configuration?**
```bash
# Update secrets
fly secrets set POLL_INTERVAL="30"

# Redeploy
fly deploy
```

## 💰 Cost Estimate

- **Fly.io**: ~$5-10/month for basic usage
- **Much cheaper** than keeping your PC running 24/7
- **More reliable** than local setup

## 🎉 You're Done!

Your OLX Sniper Bot is now running 24/7 in the cloud! It will:
- Monitor OLX listings every 45 seconds
- Send beautiful Discord notifications
- Run continuously even when your PC is off
- Auto-restart if anything goes wrong

Check your Discord channel for notifications! 🚀
