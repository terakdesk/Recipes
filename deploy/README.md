Secure runtime-socket deployment

This folder contains helper deploy artifacts to run the Recipes Flask app under systemd
and have nginx proxy to a unix socket created under /run/recipes.

Steps to apply on the server (run from the user's home directory where the repo was copied):

1. Copy the unit into place and restart the service:

   sudo cp ~/recipes_remote/deploy/recipes.service /etc/systemd/system/recipes.service
   sudo systemctl daemon-reload
   sudo systemctl restart recipes.service

   The systemd unit uses `RuntimeDirectory=recipes` and `User=me` `Group=www-data`, so
   systemd will create `/run/recipes` at service start with ownership `me:www-data` and
   mode `0750`. The gunicorn socket will be created as `/run/recipes/recipes.sock`.

2. Update nginx site and reload nginx:

   sudo cp ~/recipes_remote/deploy/recipes_nginx /etc/nginx/sites-available/recipes
   sudo ln -sf /etc/nginx/sites-available/recipes /etc/nginx/sites-enabled/recipes
   sudo nginx -t && sudo systemctl reload nginx

3. Validate:

   # Check socket and permissions
   ls -ld /run/recipes
   ls -l /run/recipes/recipes.sock

   # Quick curl checks
   curl --unix-socket /run/recipes/recipes.sock http://localhost/
   curl -I http://127.0.0.1/

If anything goes wrong, view the logs:

   sudo journalctl -u recipes.service -n 200
   sudo tail -n 200 /var/log/nginx/error.log

Notes:
- This approach avoids making parent home directories world-traversable. The runtime directory
  under /run is created by systemd with the configured user/group and permissions.
- Ensure nginx worker runs as `www-data` (default) so it can enter `/run/recipes` group and
  access the socket.
