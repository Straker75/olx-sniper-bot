#!/usr/bin/env php
<?php
/**
 * olx_sniperbot.php
 * - Polls OLX search results for new iPhone listings (API-first placeholder; fallback to scraping)
 * - Stores seen listing IDs in SQLite (seen.sqlite)
 * - Posts new listings to a Discord webhook
 *
 * Requirements: PHP 8+, SQLite PDO extension enabled, CLI environment.
 *
 * Usage:
 *   php olx_sniperbot.php
 *
 * Notes:
 *  - Respect OLX terms and robots.txt.
 *  - Keep poll interval reasonable (30-120s).
 */

/* ----------------- CONFIG ----------------- */
const CONFIG = [
    // Preferred: OLX API base and token (if you have developer access). Leave empty to use scraping.
    'OLX_API_BASE' => '',   
    'OLX_API_TOKEN' => '',

    // Scrape fallback search URL. Adjust to city/filters: e.g. "https://www.olx.pl/d/oferty/q-iphone/warszawa/"
    'SCRAPE_SEARCH_URL' => 'https://www.olx.pl/oferty/q-iphone/',

    // Discord webhook to post messages to
    'DISCORD_WEBHOOK' => 'https://discord.com/api/webhooks/1428608006811029504/Jjgdw6tDxuU2x0d2Ra72-s6pPwl6oOXEfSvusSFJkXCZQP_D1os7bsj5sUYOF8S2vVgP',

    // How often to poll (seconds)
    'POLL_INTERVAL' => 15,

    // Filtering keywords to match title (case-insensitive)
    'KEYWORDS' => ['iphone', 'iPhone 15', 'iPhone 14', 'iPhone 13', 'iPhone 12', 'iPhone 11'],

    // Max results to parse per poll
    'MAX_RESULTS' => 50,
];
/* ------------------------------------------ */

function log_msg(string $s) {
    echo "[" . date('Y-m-d H:i:s') . "] " . $s . PHP_EOL;
}

/* ---------- Database (SQLite) ---------- */
function get_db(): PDO {
    $dbfile = __DIR__ . '/seen.sqlite';
    $dsn = "sqlite:$dbfile";
    $pdo = new PDO($dsn);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->exec("CREATE TABLE IF NOT EXISTS seen (
        id TEXT PRIMARY KEY,
        url TEXT,
        title TEXT,
        price TEXT,
        seen_at INTEGER
    )");
    return $pdo;
}

function is_seen(PDO $pdo, string $id): bool {
    $stmt = $pdo->prepare("SELECT 1 FROM seen WHERE id = :id LIMIT 1");
    $stmt->execute([':id' => $id]);
    return (bool)$stmt->fetchColumn();
}

function mark_seen(PDO $pdo, array $listing) {
    $stmt = $pdo->prepare("INSERT OR IGNORE INTO seen (id, url, title, price, seen_at) VALUES (:id, :url, :title, :price, :seen_at)");
    $stmt->execute([
        ':id' => $listing['id'],
        ':url' => $listing['url'],
        ':title' => $listing['title'],
        ':price' => $listing['price'] ?? null,
        ':seen_at' => time()
    ]);
}

/* ---------- Discord webhook ---------- */
function post_to_discord(string $webhook, array $listing): bool {
    $payload = [
        'embeds' => [[
            'title' => $listing['title'] ?? 'New listing',
            'url' => $listing['url'] ?? null,
            'description' => isset($listing['price']) ? "Price: {$listing['price']}" : '',
            'fields' => [
                ['name' => 'ID', 'value' => $listing['id'], 'inline' => true],
            ],
        ]]
    ];
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE);
    $ch = curl_init($webhook);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $json);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
    $resp = curl_exec($ch);
    $err = curl_error($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($err) {
        log_msg("Discord post error: $err");
        return false;
    }
    if ($code < 200 || $code >= 300) {
        log_msg("Discord returned HTTP $code. Resp: $resp");
        return false;
    }
    return true;
}

/* ---------- OLX API placeholder (adapt to real API if you get credentials) ---------- */
function fetch_from_api(string $base, string $token, array $keywords, ?string $location=null, $max_price=null): array {
    // This is a placeholder skeleton. Fill with real OLX API endpoints/params when you have them.
    if (empty($base) || empty($token)) return [];
    $url = rtrim($base, '/') . '/offers/?q=' . urlencode(implode(' ', $keywords)) . '&limit=20';
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "Authorization: Bearer $token",
        "Accept: application/json",
        "User-Agent: OLXSniperBot/1.0"
    ]);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $resp = curl_exec($ch);
    if ($resp === false) {
        log_msg("API fetch failed: " . curl_error($ch));
        curl_close($ch);
        return [];
    }
    curl_close($ch);
    $data = json_decode($resp, true);
    if (!is_array($data)) return [];
    $listings = [];
    // Adapt parsing to the API's JSON schema
    foreach ($data['data'] ?? [] as $item) {
        $listings[] = [
            'id' => (string)($item['id'] ?? $item['offerId'] ?? null),
            'title' => $item['title'] ?? null,
            'url' => $item['url'] ?? null,
            'price' => $item['price']['value'] ?? ($item['price'] ?? null),
            'location' => $item['location']['label'] ?? null,
        ];
    }
    return $listings;
}

/* ---------- Scraping fallback (polite) ---------- */
function fetch_by_scraping(string $search_url, array $keywords, int $max_results = 50): array {
    // Use a polite UA and timeout
    $opts = [
        "http" => [
            "method" => "GET",
            "header" => "User-Agent: Mozilla/5.0 (compatible; OLXSniperBot/1.0; +https://example.com/bot)\r\n",
            "timeout" => 15
        ]
    ];
    $context = stream_context_create($opts);

    $html = @file_get_contents($search_url, false, $context);
    if ($html === false) {
        log_msg("Failed to fetch $search_url");
        return [];
    }

    libxml_use_internal_errors(true);
    $dom = new DOMDocument();
    $dom->loadHTML($html);
    $xpath = new DOMXPath($dom);

    // Look for anchors that include '/oferta/' — common OLX pattern
    $anchors = $xpath->query("//a[contains(@href, '/oferta/')]");
    $results = [];
    foreach ($anchors as $a) {
        if (!($a instanceof DOMElement)) continue;
        $href = $a->getAttribute('href');
        // Normalize relative URLs
        if (strpos($href, 'http') !== 0) {
            $href = rtrim($search_url, '/') . '/' . ltrim($href, '/');
        }

        $title = trim($a->textContent);
        if ($title === '') {
            // sometimes the title is inside child elements; try parent
            $title = trim($a->getAttribute('title') ?: '');
        }
        $title = mb_substr($title, 0, 200);

        // Extract ID from URL if present (OLX often has last token as ID)
        $id = null;
        if (preg_match('~/oferta/[^/]+-([A-Za-z0-9]+)(?:\.html)?~', $href, $m)) {
            $id = $m[1];
        } else {
            // fallback to using URL as ID
            $id = md5($href);
        }

        // Price: try to find nearest text node with "zł"
        $price = null;
        $maybe = $xpath->query("(.//text())[contains(., 'zł')]", $a);
        if ($maybe->length > 0) {
            $price = trim($maybe->item(0)->nodeValue);
        } else {
            // look sibling nodes
            $sibling = $a->nextSibling;
            if ($sibling && $sibling->nodeType === XML_ELEMENT_NODE) {
                $text = $sibling->textContent;
                if (strpos($text, 'zł') !== false) $price = trim($text);
            }
        }

        // Keyword filtering (case-insensitive)
        $lower = mb_strtolower($title . ' ' . $price);
        $keep = false;
        foreach ($keywords as $k) {
            if (mb_stripos($lower, mb_strtolower($k)) !== false) {
                $keep = true;
                break;
            }
        }
        if (!$keep) continue;

        $results[$id] = [
            'id' => $id,
            'url' => $href,
            'title' => $title ?: 'No title',
            'price' => $price ?: null,
        ];
        if (count($results) >= $max_results) break;
    }
    return array_values($results);
}

/* ---------- Main loop ---------- */
function main() {
    $cfg = CONFIG;
    $pdo = get_db();
    log_msg("Starting OLX sniper bot (PHP). Press Ctrl-C to stop.");

    while (true) {
        try {
            $listings = [];

            if (!empty($cfg['OLX_API_BASE']) && !empty($cfg['OLX_API_TOKEN'])) {
                log_msg("Trying OLX API...");
                $listings = fetch_from_api($cfg['OLX_API_BASE'], $cfg['OLX_API_TOKEN'], $cfg['KEYWORDS']);
            } else {
                log_msg("Using scraper fallback...");
                $listings = fetch_by_scraping($cfg['SCRAPE_SEARCH_URL'], $cfg['KEYWORDS'], $cfg['MAX_RESULTS']);
            }

            if (empty($listings)) {
                log_msg("No listings fetched this cycle.");
            }

            foreach ($listings as $l) {
                if (empty($l['id'])) continue;
                if (!is_seen($pdo, $l['id'])) {
                    log_msg("New: " . ($l['title'] ?? 'No title') . " | " . ($l['url'] ?? 'no-url'));
                    mark_seen($pdo, $l);
                    $ok = post_to_discord($cfg['DISCORD_WEBHOOK'], $l);
                    if ($ok) {
                        log_msg("Posted to Discord: {$l['id']}");
                    } else {
                        log_msg("Failed to post to Discord for {$l['id']}");
                    }
                } else {
                    // already seen
                }
            }

            // Respectful sleep
            sleep((int)$cfg['POLL_INTERVAL']);
        } catch (Exception $e) {
            log_msg("Unexpected error: " . $e->getMessage());
            sleep(30);
        }
    }
}

main();
