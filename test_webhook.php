<?php

require __DIR__ . '/vendor/autoload.php';

use Dotenv\Dotenv;

$dotenv = Dotenv::createImmutable(__DIR__, 'ini.env');
$dotenv->safeLoad();

$webhookUrl = $_ENV['DISCORD_WEBHOOK_URL'] ?? '';

if (!$webhookUrl) {
    echo "❌ DISCORD_WEBHOOK_URL not set in .env file\n";
    exit(1);
}

// Test webhook with sample data
$data = [
    "content" => "🧪 Test message from OLX Sniper Bot",
    "username" => "OLX Sniper Test",
    "embeds" => [[
        "title" => "Test Listing - iPhone 15 Pro",
        "url" => "https://www.olx.pl/oferty/q-iphone/",
        "description" => "Price: 4500 PLN\nThis is a test message to verify webhook functionality.",
        "color" => 5814783,
        "timestamp" => date('c')
    ]]
];

$options = [
    "http" => [
        "header"  => "Content-Type: application/json",
        "method"  => "POST",
        "content" => json_encode($data),
    ],
];

$context = stream_context_create($options);
$result = file_get_contents($webhookUrl, false, $context);

if ($result === FALSE) {
    echo "❌ Error sending test webhook\n";
    echo "Check your DISCORD_WEBHOOK_URL in the .env file\n";
} else {
    echo "✅ Test webhook sent successfully!\n";
    echo "Check your Discord channel for the test message.\n";
}
