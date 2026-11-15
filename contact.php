<?php
http_response_code(410);
header('X-Robots-Tag: noindex');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
echo json_encode(['ok' => false, 'channel' => 'https://t.me/saitvdelo'], JSON_UNESCAPED_SLASHES);
