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

        // Title - try multiple selectors for OLX
        $title = '';
        try {
            // Try different title selectors
            $titleSelectors = ['h6', 'h3', 'h4', '.css-16v5mdi', '.css-1oarkqv', '[data-cy="l-card-title"]', '.offer-title'];
            foreach ($titleSelectors as $selector) {
                $titleNode = $node->filter($selector)->first();
                if ($titleNode->count()) {
                    $title = trim($titleNode->text());
                    if ($title) break;
                }
            }
            
            // Fallback to node text or title attribute
            if (!$title) {
                $title = $node->attr('title') ?: trim($node->text());
            }
            
            // Clean up title - remove HTML tags, CSS classes, and extra whitespace
            $title = strip_tags($title);
            $title = preg_replace('/\s+/', ' ', $title);
            $title = preg_replace('/[^\w\s\-\.\,\!\?\(\)]/', '', $title); // Remove special chars except basic punctuation
            $title = trim($title);
            
            // Limit title length
            if (strlen($title) > 100) {
                $title = substr($title, 0, 97) . '...';
            }
        } catch (Exception $e) {
            $title = trim(strip_tags($node->text()));
        }

        // Price - try multiple selectors for OLX
        $price = '';
        try {
            // Try different price selectors
            $priceSelectors = ['.price', '.offer-price', '.css-1oarkqv', '[data-cy="l-card-price"]', '.css-10b0gli', '.css-1sw7q4x'];
            foreach ($priceSelectors as $selector) {
                $priceNode = $node->filter($selector)->first();
                if ($priceNode->count()) {
                    $price = trim($priceNode->text());
                    if ($price) break;
                }
            }
            
            // Try to find price in the same container (fallback)
            if (!$price) {
                try {
                    // Look for price in the same container as the link
                    $container = $node->closest('div, article, section');
                    if ($container->count()) {
                        $priceNode = $container->filter('.price, .offer-price')->first();
                        if ($priceNode->count()) {
                            $price = trim($priceNode->text());
                        }
                    }
                } catch (Exception $e) {
                    // If all else fails, try to extract price from the link text itself
                    $linkText = trim($node->text());
                    if (preg_match('/(\d+\s*(?:zł|PLN|€|\$))/i', $linkText, $matches)) {
                        $price = $matches[1];
                    }
                }
            }
            
            // Clean up price - remove HTML tags, CSS classes, and format properly
            $price = strip_tags($price);
            $price = preg_replace('/\s+/', ' ', $price);
            
            // Extract only price with currency (remove extra text)
            if (preg_match('/(\d+(?:\s*\d+)*(?:,\d+)?\s*(?:zł|PLN|€|\$))/i', $price, $matches)) {
                $price = $matches[1];
            }
            
            // Clean up price format
            $price = preg_replace('/[^\d\s,\.złPLN€\$]/', '', $price);
            $price = trim($price);
            
            // If no currency found, add zł as default
            if ($price && !preg_match('/(zł|PLN|€|\$)/i', $price)) {
                $price .= ' zł';
            }
        } catch (Exception $e) {
            $price = '';
        }

        // Location - try to extract from OLX listing
        $location = '';
        try {
            // Try different location selectors for OLX
            $locationSelectors = ['.css-veheph', '.css-17o22yg', '.css-1a4brun', '[data-cy="l-card-location"]', '.location', '.offer-location'];
            foreach ($locationSelectors as $selector) {
                $locationNode = $node->filter($selector)->first();
                if ($locationNode->count()) {
                    $location = trim($locationNode->text());
                    if ($location) break;
                }
            }
            
            // Try to find location in the same container
            if (!$location) {
                $container = $node->closest('div, article, section');
                if ($container->count()) {
                    $locationNode = $container->filter('.css-veheph, .css-17o22yg, .location')->first();
                    if ($locationNode->count()) {
                        $location = trim($locationNode->text());
                    }
                }
            }
            
            // Clean up location
            $location = strip_tags($location);
            $location = preg_replace('/\s+/', ' ', $location);
            $location = trim($location);
            
            // If no location found, use default
            if (!$location) {
                $location = 'Brak';
            }
        } catch (Exception $e) {
            $location = 'Brak';
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

        // Comprehensive debug logging
        error_log("=== DEBUG LISTING {$id} ===");
        error_log("Raw HTML node: " . substr($node->html(), 0, 200) . "...");
        error_log("Extracted Title: '{$title}'");
        error_log("Extracted Price: '{$price}'");
        error_log("Extracted Location: '{$location}'");
        error_log("Extracted Image: '{$img}'");
        error_log("Extracted URL: '{$href}'");
        error_log("Final listing data: " . json_encode([
            'id' => $id,
            'title' => $title ?: 'No title',
            'url' => $href,
            'price' => $price ?: '—',
            'location' => $location,
            'img' => $img
        ], JSON_PRETTY_PRINT));
        error_log("=== END DEBUG ===");

        $listings[] = [
            'id' => $id,
            'title' => $title ?: 'No title',
            'url' => $href,
            'price' => $price ?: '—',
            'location' => $location,
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

// Send to Discord webhook with retry logic
function notifyDiscord(string $webhookUrl, array $listing, Client $client) {
    // Clean and validate data
    $title = substr($listing['title'], 0, 256); // Discord title limit
    $price = substr($listing['price'], 0, 100); // Reasonable price limit
    $url = $listing['url'];
    
    // Ensure URL is valid
    if (!filter_var($url, FILTER_VALIDATE_URL)) {
        error_log("Invalid URL for listing {$listing['id']}: {$url}");
        return false;
    }
    
    $data = [
        "content" => "",
        "username" => "OLX Sniper Bot",
        "embeds" => [[
            "title" => "Ogłoszenia - Sprzedam, kupię na OLX.pl",
            "url" => $url,
            "color" => 3066993, // Green color
            "timestamp" => date('c'),
            "description" => "📌 " . strtolower($title ?: "iPhone listing") . "\n💰 Cena: " . ($price ?: "Cena do uzgodnienia") . "\n📍 Lokalizacja: " . ($listing['location'] ?? 'Warszawa') . "\n📦 Dostawa: TAK\n🔗 Link do ogłoszenia",
            "thumbnail" => [
                "url" => "https://www.olx.pl/favicon.ico"
            ]
        ]],
        "components" => [[
            "type" => 1,
            "components" => [[
                "type" => 2,
                "style" => 5,
                "label" => "KUP TERAZ",
                "url" => $url,
                "emoji" => [
                    "name" => "🔗"
                ]
            ]]
        ]]
    ];

    // Add image if available and valid
    if (!empty($listing['img']) && filter_var($listing['img'], FILTER_VALIDATE_URL)) {
        $data['embeds'][0]['thumbnail'] = ['url' => $listing['img']];
    }

    // Debug Discord notification data
    error_log("=== DISCORD NOTIFICATION DEBUG ===");
    error_log("Listing ID: " . $listing['id']);
    error_log("Discord payload: " . json_encode($data, JSON_PRETTY_PRINT));
    error_log("=== END DISCORD DEBUG ===");

    // Retry logic for rate limiting
    $maxRetries = 3;
    $retryDelay = 5; // seconds
    
    for ($attempt = 1; $attempt <= $maxRetries; $attempt++) {
        $options = [
            "http" => [
                "header"  => "Content-Type: application/json",
                "method"  => "POST",
                "content" => json_encode($data),
                "timeout" => 30
            ],
        ];
        
        $context = stream_context_create($options);
        $result = file_get_contents($webhookUrl, false, $context);

        if ($result !== FALSE) {
            error_log("✅ Sent notification for: {$listing['title']}");
            return true;
        }
        
        $error = error_get_last();
        $errorMsg = $error['message'] ?? 'Unknown error';
        
        // Check if it's a rate limit error
        if (strpos($errorMsg, '429') !== false) {
            error_log("Rate limited, waiting {$retryDelay}s before retry {$attempt}/{$maxRetries} for listing {$listing['id']}");
            sleep($retryDelay);
            $retryDelay *= 2; // Exponential backoff
            continue;
        }
        
        // For other errors, log and break
        error_log("Error sending webhook for listing {$listing['id']} (attempt {$attempt}): {$errorMsg}");
        break;
    }
    
    return false;
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
if (isset($_GET['health']) || (isset($_SERVER['REQUEST_URI']) && $_SERVER['REQUEST_URI'] === '/health')) {
    healthCheck();
}

// Main loop
error_log("[" . date('c') . "] Starting OLX sniper bot (Cloud). Polling {$searchUrl} every {$pollInterval}s");

// First run: mark all current listings as seen (don't notify)
$isFirstRun = true;

while (true) {
    try {
        error_log("[" . date('c') . "] Polling " . $searchUrl);
        
        $listings = fetchListings($client, $searchUrl);
        if (empty($listings)) {
            error_log("[" . date('c') . "] No listings parsed or error.");
        } else {
            $newCount = 0;
            $currentListingIds = [];
            
            // Collect all current listing IDs
            foreach ($listings as $listing) {
                $currentListingIds[] = $listing['id'];
            }
            
            // On first run, mark all current listings as seen
            if ($isFirstRun) {
                error_log("[" . date('c') . "] First run - marking " . count($currentListingIds) . " current listings as seen");
                $seen = array_unique(array_merge($seen, $currentListingIds));
                saveSeen($seen, $seenFile);
                $isFirstRun = false;
                error_log("[" . date('c') . "] First run complete. Future runs will only show new listings.");
                continue;
            }
            
            // Check for new listings
            foreach ($listings as $listing) {
                if (!in_array($listing['id'], $seen)) {
                    $newCount++;
                    error_log("[" . date('c') . "] NEW listing: {$listing['title']} ({$listing['id']})");
                    
                    $success = notifyDiscord($webhookUrl, $listing, $client);
                    if ($success) {
                        $seen[] = $listing['id'];
                        saveSeen($seen, $seenFile);
                        
                        // Longer pause between posts to avoid Discord rate limits
                        sleep(5);
                    } else {
                        error_log("[" . date('c') . "] Failed to notify Discord for {$listing['id']}");
                    }
                }
            }
            
            // Clean up old seen IDs (keep only recent ones)
            if (count($seen) > 1000) {
                $seen = array_slice($seen, -500); // Keep only last 500
                saveSeen($seen, $seenFile);
                error_log("[" . date('c') . "] Cleaned up old seen listings. Kept " . count($seen) . " recent ones.");
            }
            
            if ($newCount === 0) {
                error_log("[" . date('c') . "] No new listings found. Total listings: " . count($listings));
            } else {
                error_log("[" . date('c') . "] Found {$newCount} new listings out of " . count($listings) . " total.");
            }
        }
    } catch (Exception $e) {
        error_log("[" . date('c') . "] Unexpected error: " . $e->getMessage());
    }

    // Sleep with jitter to avoid perfect periodicity
    $jitter = rand(0, intval(max(1, $pollInterval * 0.2)));
    sleep(max(1, $pollInterval + $jitter - intval($pollInterval * 0.1)));
}
