<?php

require __DIR__ . '/vendor/autoload.php';

use GuzzleHttp\Client;
use Symfony\Component\DomCrawler\Crawler;
use Dotenv\Dotenv;

$dotenv = Dotenv::createImmutable(__DIR__);
$dotenv->safeLoad();

$searchUrl = rtrim($_ENV['OLX_SEARCH_URL'] ?? '', '/');
$webhookUrl = $_ENV['DISCORD_WEBHOOK_URL'] ?? '';
$pollInterval = intval($_ENV['POLL_INTERVAL'] ?? 30);
$userAgent = $_ENV['USER_AGENT'] ?? 'OlxSniperBot/1.0 (+https://example.com)';
$dbPath = $_ENV['DB_PATH'] ?? __DIR__ . '/seen.sqlite';

if (!$searchUrl || !$webhookUrl) {
    fwrite(STDERR, "Set OLX_SEARCH_URL and DISCORD_WEBHOOK_URL in .env\n");
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

// Setup SQLite
$pdo = new PDO('sqlite:' . $dbPath);
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$pdo->exec('CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, title TEXT, url TEXT, price TEXT, seen_at INTEGER)');

// Helper to check/insert seen
function isSeen(PDO $pdo, string $id): bool {
    $stmt = $pdo->prepare('SELECT 1 FROM seen WHERE id = :id LIMIT 1');
    $stmt->execute([':id' => $id]);
    return (bool)$stmt->fetchColumn();
}
function markSeen(PDO $pdo, array $row) {
    $stmt = $pdo->prepare('INSERT OR IGNORE INTO seen (id, title, url, price, seen_at) VALUES (:id, :title, :url, :price, :seen_at)');
    $stmt->execute([
        ':id' => $row['id'],
        ':title' => $row['title'],
        ':url' => $row['url'],
        ':price' => $row['price'],
        ':seen_at' => time()
    ]);
}

// Function to fetch and parse listings
function fetchListings(Client $client, string $url): array {
    try {
        $resp = $client->get($url);
        $html = (string)$resp->getBody();
    } catch (Exception $e) {
        fwrite(STDERR, "[" . date('c') . "] Fetch error: " . $e->getMessage() . PHP_EOL);
        return [];
    }

    $crawler = new Crawler($html);

    $listings = [];

    // Find anchors that contain "/oferta/" in the href
    $crawler->filter('a[href*="/oferta/"]')->each(function (Crawler $node) use (&$listings) {
        $href = $node->attr('href') ?: '';
        // Normalize OLX internal links
        if (strpos($href, 'http') !== 0) {
            $href = 'https://www.olx.pl' . $href;
        }

        // Try to extract an ID from the URL: OLX often has "-<digits>/" or at the end "-1234567890"
        $id = null;
        if (preg_match('/-([0-9]+)(?:[\/?#]|$)/', $href, $m)) {
            $id = $m[1];
        } elseif (preg_match('/oferta\/([^\/?#]+)(?:[\/?#]|$)/', $href, $m2)) {
            $id = $m2[1];
        } else {
            $id = md5($href);
        }

        // Title
        $title = trim($node->text());
        // Fallback: look for headings inside
        if ($title === '') {
            $titleNode = $node->filter('h3, h4, h5, h6')->first();
            $title = $titleNode->count() ? trim($titleNode->text()) : $title;
        }

        // Price: try to find within the anchor or within parent nodes
        $price = '';
        try {
            $priceNode = $node->filter('.price, .offer-price, .css-1oarkqv'); // keep a few common classes; adjust if needed
            if ($priceNode->count()) {
                $price = trim($priceNode->text());
            } else {
                // search parent for price
                $p = $node->ancestors()->filter('.price, .offer-price')->first();
                if ($p->count()) $price = trim($p->text());
            }
        } catch (Exception $e) {
            $price = '';
        }

        // Image (optional)
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

    // Remove duplicates by id, keep order
    $unique = [];
    foreach ($listings as $l) {
        if (!isset($unique[$l['id']])) $unique[$l['id']] = $l;
    }

    return array_values($unique);
}

// Send to Discord webhook
function notifyDiscord(string $webhookUrl, array $listing, Client $client) {
    $content = "**" . addslashes($listing['title']) . "**\nPrice: " . $listing['price'] . "\n" . $listing['url'];
    $payload = [
        'content' => $content
    ];

    // If image available, send as embed (simple)
    if (!empty($listing['img'])) {
        $payload['embeds'] = [[
            'title' => $listing['title'],
            'url' => $listing['url'],
            'image' => ['url' => $listing['img']],
            'fields' => [
                ['name' => 'Price', 'value' => $listing['price'], 'inline' => true]
            ]
        ]];
    }

    try {
        $resp = $client->post($webhookUrl, [
            'json' => $payload,
            'headers' => ['Content-Type' => 'application/json']
        ]);
        return $resp->getStatusCode() >= 200 && $resp->getStatusCode() < 300;
    } catch (Exception $e) {
        fwrite(STDERR, "[" . date('c') . "] Discord send error: " . $e->getMessage() . PHP_EOL);
        return false;
    }
}

// Main loop
fwrite(STDOUT, "[" . date('c') . "] Starting OLX sniper. Polling {$searchUrl} every {$pollInterval}s\n");
while (true) {
    try {
        $listings = fetchListings($client, $searchUrl);
        if (empty($listings)) {
            fwrite(STDOUT, "[" . date('c') . "] No listings parsed or error.\n");
        } else {
            // iterate in reverse order if you want older->newer; here we process in listing order
            foreach ($listings as $l) {
                if (!isSeen($pdo, $l['id'])) {
                    fwrite(STDOUT, "[" . date('c') . "] New listing: {$l['title']} ({$l['id']})\n");
                    $ok = notifyDiscord($webhookUrl, $l, $client);
                    if ($ok) {
                        markSeen($pdo, $l);
                        // brief sleep between posts to avoid webhook rate limits
                        sleep(1);
                    } else {
                        fwrite(STDERR, "[" . date('c') . "] Failed to notify Discord for {$l['id']}\n");
                    }
                }
            }
        }
    } catch (Exception $e) {
        fwrite(STDERR, "[" . date('c') . "] Unexpected error: " . $e->getMessage() . PHP_EOL);
    }

    // sleep poll interval with jitter to avoid perfect periodicity
    $jitter = rand(0, intval(max(1, $pollInterval * 0.2)));
    sleep(max(1, $pollInterval + $jitter - intval($pollInterval*0.1)));
}
