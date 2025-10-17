<?php
$webhook = "https://discord.com/api/webhooks/1428608006811029504/Jjgdw6tDxuU2x0d2Ra72-s6pPwl6oOXEfSvusSFJkXCZQP_D1os7bsj5sUYOF8S2vVgP"; // replace with yours

$data = [
    "content" => "🚀 New iPhone found on OLX!",
    "username" => "OLX Sniper",
    "embeds" => [[
        "title" => "iPhone 15 Pro - 4500 PLN",
        "url" => "https://www.olx.pl/d/oferta/iphone-15-pro-4500zl",
        "description" => "Brand new condition, Warsaw",
        "color" => 5814783
    ]]
];

$options = [
    "http" => [
        "header"  => "Content-Type: application/json",
        "method"  => "POST",
        "content" => json_encode($data),
    ],
];
$context  = stream_context_create($options);
$result = file_get_contents($webhook, false, $context);

if ($result === FALSE) {
    echo "Error sending webhook\n";
} else {
    echo "✅ Message sent to Discord!\n";
}
?>