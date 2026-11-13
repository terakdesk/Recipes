# Fix for Login Redirect Issue

## Problem
After logging in with correct credentials, the user sees a blank page with 2 small boxes instead of being redirected to the intended page. However, if you navigate to other pages, you're already logged in.

## Root Cause
When Flask generates a redirect response after login (e.g., `Location: /recipe/1608/edit`), the PHP proxy wrapper is not rewriting the `Location` header to include the `/food55` prefix. So the browser redirects to `/recipe/1608/edit` instead of `/food55/recipe/1608/edit`, which results in a 404 or malformed response.

## Solution
Update `index.php` to rewrite the `Location` header in redirect responses to include the `/food55` prefix.

## How to Deploy

### Option 1: Via SCP (Recommended)
```bash
scp C:\Users\miket\Recipes_remote\index.php f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/42wide.com/food55/index.php
```

### Option 2: Via SSH Direct Edit
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
```

Then run (use your favorite text editor):
```bash
nano /home/f42widec/42wide.com/food55/index.php
```

Find the section that starts with `// Forward response headers (skip some)` and replace it with the code below.

### Option 3: Via SSH with sed (Advanced)
The updated code is embedded in this file below.

## Updated index.php Section

Replace this section (around line 68):
```php
// Forward response headers (skip some)
$header_lines = explode("\r\n", $headers);
foreach ($header_lines as $header) {
    if (!empty($header) && !preg_match('#^HTTP|^Content-Encoding|^Transfer-Encoding|^Connection#', $header)) {
        header($header);
    }
}
```

With this:
```php
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
```

## Testing After Fix

1. Go to: http://www.42wide.com/food55/recipe/1608
2. Click "Login to edit"
3. Enter credentials
4. Should now redirect to: http://www.42wide.com/food55/recipe/1608/edit
5. NOT a blank page with 2 small boxes

If it still doesn't work:
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "tail -50 /var/log/apache2/error.log"
```

Check the Apache error log for any PHP errors.
