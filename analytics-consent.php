<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Robots-Tag: noindex');
header('X-Content-Type-Options: nosniff');
function fail(int $status): never {
    http_response_code($status);
    echo json_encode(['ok' => false, 'message' => 'Согласие не сохранено; аналитика не включена.'], JSON_UNESCAPED_UNICODE);
    exit;
}
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST'); fail(405);
}
// Exact same-origin requests only; consent is never inferred from a visit.
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
$host = $_SERVER['HTTP_HOST'] ?? '';
$scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
if ($origin !== $scheme . '://' . $host) fail(403);
if (stripos($_SERVER['CONTENT_TYPE'] ?? '', 'application/json') !== 0) fail(415);
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 1024) fail(413);
$raw = file_get_contents('php://input', false, null, 0, 1025);
if ($raw === false || strlen($raw) > 1024) fail(413);
$body = json_decode($raw, true);
if (!is_array($body) || ($body['version'] ?? '') !== '2026-11-07-v2' || !in_array($body['action'] ?? '', ['granted', 'withdrawn'], true)) fail(400);
// Keep the grant endpoint closed while the public counter is disabled.
if ($body['action'] === 'granted') {
    $config = @file_get_contents(__DIR__ . '/analytics-config.js');
    if (!is_string($config) || !preg_match('/^window\.SVD_ANALYTICS = \{ metrikaId: \d+, enabled: true \};$/m', $config)) fail(503);
}
$receipt = $body['receipt'] ?? null;
if ($receipt !== null && (!is_string($receipt) || !preg_match('/^[a-f0-9]{64}$/D', $receipt))) fail(400);
if ($body['action'] === 'withdrawn' && $receipt === null) fail(400);
try {
    // Outside the document root. If hosting disallows this, fail closed.
    $docroot = realpath(__DIR__);
    $private = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'svd-private-consents';
    if (!is_dir($private) && !@mkdir($private, 0700, false) && !is_dir($private)) fail(503);
    $resolved = realpath($private);
    $webroot = realpath($_SERVER['DOCUMENT_ROOT'] ?? __DIR__) ?: $docroot;
    $normal = static fn(string $path): string => str_replace('\\', '/', strtolower($path));
    if (!$resolved || $normal($resolved) === $normal($webroot) || str_starts_with($normal($resolved) . '/', rtrim($normal($webroot), '/') . '/')) fail(503);
    $receipt = $receipt ?? bin2hex(random_bytes(32));
    $path = $resolved . DIRECTORY_SEPARATOR . $receipt . '.jsonl';
    if ($body['action'] === 'withdrawn' && !is_file($path)) fail(404);
    $record = ['receipt' => $receipt, 'action' => $body['action'], 'version' => $body['version'], 'text_sha256' => hash_file('sha256', __DIR__ . '/analytics-consent/index.html'), 'scope' => 'yandex-metrica-no-webvisor', 'time_utc' => gmdate('c')];
    // No IP, User-Agent, name, email or project text is stored in this application log.
    $file = @fopen($path, 'ab');
    if (!$file) fail(503);
    @chmod($path, 0600);
    if (!flock($file, LOCK_EX)) { fclose($file); fail(503); }
    $ok = fwrite($file, json_encode($record, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");
    fflush($file); flock($file, LOCK_UN); fclose($file);
    if ($ok === false) fail(503);
    // Delete expired evidence when the endpoint is used; monthly maintenance is also required.
    $cutoff = time() - 365 * 86400;
    $checked = 0;
    foreach (new DirectoryIterator($resolved) as $entry) {
        if (++$checked > 500) break;
        if ($entry->isFile() && preg_match('/^[a-f0-9]{64}\.jsonl$/D', $entry->getFilename()) && $entry->getMTime() < $cutoff) @unlink($entry->getPathname());
    }
    echo json_encode(['ok' => true, 'receipt' => $receipt, 'version' => '2026-11-07-v2']);
} catch (Throwable $e) { fail(503); }
