<?php
// Simple health check endpoint for Fly.io
header('Content-Type: application/json');
echo json_encode([
    'status' => 'healthy',
    'timestamp' => date('c'),
    'service' => 'OLX Sniper Bot',
    'version' => '1.0.0',
    'message' => 'Bot is running in the cloud!'
]);
?>
