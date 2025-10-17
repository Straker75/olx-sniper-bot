@echo off
echo ========================================
echo    OLX Sniper Bot - Fly.io Deployment
echo ========================================
echo.

REM Check if fly CLI is installed
fly version >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ Fly CLI not found!
    echo Please install Fly CLI first:
    echo https://fly.io/docs/hands-on/install-flyctl/
    pause
    exit /b 1
)

echo ✅ Fly CLI found
echo.

REM Check if logged in
fly auth whoami >nul 2>&1
if %errorLevel% neq 0 (
    echo Please login to Fly.io first:
    fly auth login
    echo.
)

echo Setting up environment variables...
echo.

REM Set environment variables
echo Setting OLX_SEARCH_URL...
fly secrets set OLX_SEARCH_URL="https://www.olx.pl/oferty/q-iphone/"

echo Setting DISCORD_WEBHOOK_URL...
fly secrets set DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1428608006811029504/Jjgdw6tDxuU2x0d2Ra72-s6pPwl6oOXEfSvusSFJkXCZQP_D1os7bsj5sVgP"

echo Setting POLL_INTERVAL...
fly secrets set POLL_INTERVAL="45"

echo Setting USER_AGENT...
fly secrets set USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

echo.
echo 🚀 Deploying to Fly.io...
fly deploy

if %errorLevel% == 0 (
    echo.
    echo ✅ Deployment successful!
    echo.
    echo Your bot is now running 24/7 in the cloud!
    echo.
    echo Useful commands:
    echo   fly status     - Check bot status
    echo   fly logs       - View bot logs
    echo   fly apps restart olx-sniper-bot - Restart bot
    echo.
) else (
    echo.
    echo ❌ Deployment failed!
    echo Check the error messages above.
    echo.
)

pause
