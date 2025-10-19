# 🚀 Deploy OLX Sniper Bot to Railway (FREE 24/7)

## 📋 Prerequisites

1. **Railway account** - Sign up at [railway.app](https://railway.app)
2. **GitHub account** - For code hosting
3. **Your Discord webhook URL**

## 🚀 Quick Deployment Steps

### 1. **Push Code to GitHub**
```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "OLX Sniper Bot for Railway"

# Create GitHub repository and push
# Go to github.com, create new repo, then:
git remote add origin https://github.com/YOUR_USERNAME/olx-sniper-bot.git
git push -u origin main
```

### 2. **Deploy to Railway**
1. Go to [railway.app](https://railway.app)
2. Click **"Deploy from GitHub repo"**
3. Select your repository
4. Railway will automatically detect and deploy

### 3. **Set Environment Variables**
In Railway dashboard, go to **Variables** tab and add:

```
OLX_SEARCH_URL=https://www.olx.pl/oferty/q-iphone/?search%5Border%5D=created_at:desc
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
POLL_INTERVAL=45
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36
PORT=8080
```

### 4. **Deploy**
Railway will automatically build and deploy your bot!

## ✅ **What You Get:**

- **🆓 FREE 24/7 hosting** (500 hours/month)
- **🔄 Auto-restart** if bot crashes
- **📊 Monitoring** and logs
- **🌐 Public URL** for health checks
- **⚡ Fast deployment** (2-3 minutes)

## 🎯 **Railway vs Fly.io:**

| Feature | Railway (Free) | Fly.io (Paid) |
|---------|----------------|---------------|
| **Cost** | FREE | ~$4-5/month |
| **Uptime** | 24/7 | 24/7 |
| **Auto-restart** | ✅ | ✅ |
| **Monitoring** | ✅ | ✅ |
| **SSL** | ✅ | ✅ |

## 🔧 **Management:**

- **Dashboard**: railway.app/dashboard
- **Logs**: View in Railway dashboard
- **Restart**: Click restart button
- **Update**: Push to GitHub (auto-deploys)

## 🎉 **Result:**

Your bot will run 24/7 for FREE on Railway's infrastructure!

## 🆘 **If Railway Doesn't Work:**

### **Alternative: Keep PC Running**
- **Cost**: ~$5-10/month electricity
- **Reliability**: 100% (your control)
- **Setup**: Use the Windows service we created earlier

### **Alternative: Raspberry Pi**
- **Cost**: ~$50 one-time + $1/month electricity
- **Runs 24/7** at home
- **Very low power consumption**

**Railway is your best free option!** 🚀
