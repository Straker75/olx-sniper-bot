# Use official PHP image with Apache
FROM php:8.2-apache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    libpng-dev \
    libonig-dev \
    libxml2-dev \
    zip \
    unzip \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions
RUN docker-php-ext-install pdo pdo_sqlite mbstring exif pcntl bcmath gd

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Set working directory
WORKDIR /var/www/html

# Copy composer files
COPY composer.json composer.lock ./

# Install PHP dependencies
RUN composer install --no-dev --optimize-autoloader

# Copy application files
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /var/www/html/data && \
    chown -R www-data:www-data /var/www/html && \
    chmod -R 755 /var/www/html

# Create a startup script
RUN echo '#!/bin/bash\n\
# Start the bot in background\n\
php sniperbot_cloud.php &\n\
BOT_PID=$!\n\
\n\
# Start PHP built-in server in foreground\n\
php -S 0.0.0.0:8080 -t . &\n\
SERVER_PID=$!\n\
\n\
# Wait for either process to exit\n\
wait -n\n\
\n\
# If server exits, kill the bot\n\
kill $BOT_PID 2>/dev/null\n\
\n\
# If bot exits, kill server\n\
kill $SERVER_PID 2>/dev/null\n\
' > /start.sh && chmod +x /start.sh

# Expose port 8080
EXPOSE 8080

# Use the startup script
CMD ["/start.sh"]
