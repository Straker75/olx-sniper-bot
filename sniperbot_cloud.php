<?php

require __DIR__ . '/vendor/autoload.php';

use GuzzleHttp\Client;
use Symfony\Component\DomCrawler\Crawler;

// Get environment variables from Fly.io secrets
$searchUrl = rtrim($_ENV['OLX_SEARCH_URL'] ?? '', '/');
$webhookUrl = $_ENV['DISCORD_WEBHOOK_URL'] ?? '';
$pollInterval = intval($_ENV['POLL_INTERVAL'] ?? 45);
$userAgent = $_ENV['USER_AGENT'] ?? 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36';
$seenFile = $_ENV['SEEN_FILE'] ?? '/tmp/seen.json';

if (!$searchUrl || !$webhookUrl) {
    error_log("Missing required environment variables: OLX_SEARCH_URL and DISCORD_WEBHOOK_URL");
    exit(1);
}

// Setup HTTP client
$client = new Client([
    'headers' => [
        'User-Agent' => $userAgent,
        'Accept-Language' => 'en-US,en;q=0.9'
    ],
    'timeout' => 20,
]);

// Load seen listings from JSON file
$seen = [];
if (file_exists($seenFile)) {
    try {
        $seenData = file_get_contents($seenFile);
        $seen = json_decode($seenData, true) ?: [];
    } catch (Exception $e) {
        error_log("Error loading seen file: " . $e->getMessage());
        $seen = [];
    }
}

// Helper functions
function saveSeen($seen, $seenFile) {
    try {
        file_put_contents($seenFile, json_encode($seen, JSON_PRETTY_PRINT));
    } catch (Exception $e) {
        error_log("Error saving seen file: " . $e->getMessage());
    }
}

function fetchListings(Client $client, string $url): array {
    try {
        $resp = $client->get($url);
        $html = (string)$resp->getBody();
    } catch (Exception $e) {
        error_log("Fetch error: " . $e->getMessage());
        return [];
    }

    $crawler = new Crawler($html);
    $listings = [];

    // Find anchors that contain "/oferta/" in the href
    $crawler->filter('a[href*="/oferta/"]')->each(function (Crawler $node) use (&$listings) {
        $href = $node->attr('href') ?: '';
        if (!$href) return;

        // Normalize OLX internal links
        if (strpos($href, 'http') !== 0) {
            $href = 'https://www.olx.pl' . $href;
        }

        // Extract ID from URL
        $id = null;
        if (preg_match('/\/oferta\/[^\/]+-([0-9a-zA-Z]+)\b/', $href, $matches)) {
            $id = $matches[1];
        } else {
            $id = md5($href); // fallback
        }

        // Title
        $title = '';
        try {
            $titleNode = $node->filter('h6')->first();
            if ($titleNode->count()) {
                $title = trim($titleNode->text());
            } else {
                $title = $node->attr('title') ?: trim($node->text());
            }
        } catch (Exception $e) {
            $title = trim($node->text());
        }

        // Price
        $price = '';
        try {
            $priceNode = $node->filter('.price, .offer-price')->first();
            if ($priceNode->count()) {
                $price = trim($priceNode->text());
            }
        } catch (Exception $e) {
            $price = '';
        }

        // Image
        $img = null;
        try {
            $imgNode = $node->filter('img')->first();
            if ($imgNode->count()) {
                $img = $imgNode->attr('src') ?: $imgNode->attr('data-src') ?: null;
            }
        } catch (Exception $e) {
            $img = null;
        }

        $listings[] = [
            'id' => $id,
            'title' => $title ?: 'No title',
            'url' => $href,
            'price' => $price ?: '—',
            'img' => $img
        ];
    });

    // Remove duplicates by id
    $unique = [];
    foreach ($listings as $listing) {
        if (!isset($unique[$listing['id']])) {
            $unique[$listing['id']] = $listing;
        }
    }

    return array_values($unique);
}

// Send to Discord webhook
function notifyDiscord(string $webhookUrl, array $listing, Client $client) {
    $data = [
        "content" => "🚀 **New listing found on OLX!**",
        "username" => "OLX Sniper Bot (Cloud)",
        "embeds" => [[
            "title" => $listing['title'],
            "url" => $listing['url'],
            "description" => "💰 **Price:** " . $listing['price'] . "\n\n🔗 **Click the title above to view the offer!**",
            "color" => 3066993, // Green color for new listings
            "timestamp" => date('c'),
            "footer" => [
                "text" => "OLX Sniper Bot (Cloud) • Click title to open offer"
            ],
            "fields" => [
                [
                    "name" => "💰 Price",
                    "value" => $listing['price'],
                    "inline" => true
                ],
                [
                    "name" => "🔗 Direct Link",
                    "value" => "[Open on OLX](" . $listing['url'] . ")",
                    "inline" => true
                ]
            ]
        ]]
    ];

    // Add image if available
    if (!empty($listing['img'])) {
        $data['embeds'][0]['image'] = ['url' => $listing['img']];
        $data['embeds'][0]['thumbnail'] = ['url' => $listing['img']];
    }

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
        error_log("Error sending webhook for listing {$listing['id']}");
        return false;
    } else {
        error_log("✅ Sent notification for: {$listing['title']}");
        return true;
    }
}

// Health check endpoint
function healthCheck() {
    http_response_code(200);
    header('Content-Type: application/json');
    echo json_encode([
        'status' => 'healthy',
        'timestamp' => date('c'),
        'service' => 'OLX Sniper Bot'
    ]);
    exit;
}

// Handle health check requests
if (isset($_GET['health']) || $_SERVER['REQUEST_URI'] === '/health') {
    healthCheck();
}

// Main loop
error_log("[" . date('c') . "] Starting OLX sniper bot (Cloud). Polling {$searchUrl} every {$pollInterval}s");

while (true) {
    try {
        error_log("[" . date('c') . "] Polling " . $searchUrl);
        
        $listings = fetchListings($client, $searchUrl);
        if (empty($listings)) {
            error_log("[" . date('c') . "] No listings parsed or error.");
        } else {
            $newCount = 0;
            
            foreach ($listings as $listing) {
                if (!in_array($listing['id'], $seen)) {
                    $newCount++;
                    error_log("[" . date('c') . "] New listing: {$listing['title']} ({$listing['id']})");
                    
                    $success = notifyDiscord($webhookUrl, $listing, $client);
                    if ($success) {
                        $seen[] = $listing['id'];
                        saveSeen($seen, $seenFile);
                        
                        // Brief pause between posts to avoid rate limits
                        sleep(1);
                    } else {
                        error_log("[" . date('c') . "] Failed to notify Discord for {$listing['id']}");
                    }
                }
            }
            
            if ($newCount === 0) {
                error_log("[" . date('c') . "] No new listings found.");
            } else {
                error_log("[" . date('c') . "] Found {$newCount} new listings.");
            }
        }
    } catch (Exception $e) {
        error_log("[" . date('c') . "] Unexpected error: " . $e->getMessage());
    }

    // Sleep with jitter to avoid perfect periodicity
    $jitter = rand(0, intval(max(1, $pollInterval * 0.2)));
    sleep(max(1, $pollInterval + $jitter - intval($pollInterval * 0.1)));
}
