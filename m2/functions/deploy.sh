#!/usr/bin/env bash
# Module 2: deploy the change feed processor and wake it.
#   bash m2/functions/deploy.sh
# Uses FUNC_APP and RESOURCE_GROUP from .env (written by setup.sh).
set -euo pipefail
cd "$(dirname "$0")"
set -a; source ../../.env; set +a

rm -f /tmp/cfp.zip
zip -q -r /tmp/cfp.zip function_app.py host.json requirements.txt
echo "Deploying to $FUNC_APP (remote build, about 1 to 2 minutes)..."
az functionapp deployment source config-zip -g "$RESOURCE_GROUP" -n "$FUNC_APP" \
  --src /tmp/cfp.zip --build-remote true --only-show-errors -o none

echo "Syncing triggers..."
az resource invoke-action --action syncfunctiontriggers -g "$RESOURCE_GROUP" \
  -n "$FUNC_APP" --resource-type Microsoft.Web/sites --only-show-errors -o none

echo "Waking the host..."
for i in 1 2 3 4 5 6; do
  if curl -fsS "https://$FUNC_APP.azurewebsites.net/api/ping"; then echo; break; fi
  sleep 10
done
echo "Ready. Leases appear in the leases container once the trigger starts."
