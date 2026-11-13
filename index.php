<?php
// Build the target URL
$path = isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '/';
// Remove /food55 prefix if present
$path = preg_replace('#^/food55#', '', $path);
if (empty($path)) $path = '/';

$target_url = 'http://127.0.0.1:8055' . $path;

// Debug: log the request
error_log("PHP Proxy: REQUEST_URI=" . $_SERVER['REQUEST_URI'] . " -> target_url=" . $target_url);

// Add query string if present
if (!empty($_SERVER['QUERY_STRING'])) {
    $target_url .= '?' . $_SERVER['QUERY_STRING'];
}

// Initialize cURL
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $target_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);
curl_setopt($ch, CURLOPT_HEADER, true);
curl_setopt($ch, CURLOPT_BINARYTRANSFER, true);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
curl_setopt($ch, CURLOPT_TIMEOUT, 30);

// Forward request method
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $_SERVER['REQUEST_METHOD']);

// Forward headers
$headers = [];
foreach (getallheaders() as $name => $value) {
    if (!in_array(strtolower($name), ['host', 'connection'])) {
        $headers[] = $name . ': ' . $value;
    }
}
// Add X-Script-Name header so Flask knows about /food55 prefix
$headers[] = 'X-Script-Name: /food55';
if (!empty($headers)) {
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
}

// Forward body for POST/PUT
if (in_array($_SERVER['REQUEST_METHOD'], ['POST', 'PUT', 'PATCH'])) {
    curl_setopt($ch, CURLOPT_POSTFIELDS, file_get_contents('php://input'));
}

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$header_size = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
$content_type = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
curl_close($ch);

// Split headers and body
$headers = substr($response, 0, $header_size);
$body = substr($response, $header_size);

// Forward response headers (skip some)
$header_lines = explode("\r\n", $headers);
foreach ($header_lines as $header) {
    if (!empty($header) && !preg_match('#^HTTP|^Content-Encoding|^Transfer-Encoding|^Connection#', $header)) {
        // Rewrite Location header for redirects to include /food55 prefix
        if (preg_match('#^Location:\s*(.*)$#i', $header, $matches)) {
            $location = trim($matches[1]);
            // Only rewrite if it's a relative path that doesn't already have /food55
            if (strpos($location, '/') === 0 && strpos($location, '/food55/') !== 0 && strpos($location, '//') !== 0) {
                $header = 'Location: /food55' . $location;
            }
        }
        header($header);
    }
}

// Set status code
http_response_code($http_code);

// Rewrite paths in HTML responses to include /food55 prefix
if (preg_match('#text/html#', $content_type)) {
    // Simple string replacement for common patterns
    $body = str_replace('href="/', 'href="/food55/', $body);
    $body = str_replace("href='/", "href='/food55/", $body);
    $body = str_replace('src="/', 'src="/food55/', $body);
    $body = str_replace("src='/", "src='/food55/", $body);
    $body = str_replace('action="/', 'action="/food55/', $body);
    $body = str_replace("action='/", "action='/food55/", $body);
    
    // Fix double /food55/food55 if any
    $body = str_replace('="/food55/food55/', '="/food55/', $body);
}

// Output body
echo $body;
?>
