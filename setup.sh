#!/usr/bin/env bash
# Provision what each module's demos need in the Pluralsight Azure sandbox.
#
#   bash setup.sh m1        Cosmos DB (vector search on at creation), empty containers
#   bash setup.sh m2        Cosmos DB with 500 tickets, storage, Linux Consumption function app
#   bash setup.sh m3        PostgreSQL General Purpose D2ds_v5; VECTOR not yet allowed
#   bash setup.sh m4        PostgreSQL with VECTOR allowed and the knowledge base loaded
#   bash setup.sh m5        Azure Managed Redis Balanced_B0 with RediSearch, plus the m4 state
#   bash setup.sh all       everything (about 15 to 20 minutes)
#
# Run it before you start a module. Running it again reuses what already exists.
# Endpoints and keys go to .env; the demos read them and never print them.
set +H                      # a ! in a generated password would break bash history expansion
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n== %s\n' "$*"; }
envset() {                  # envset NAME VALUE: write or replace one line in .env
  touch .env; chmod 600 .env
  grep -v "^$1=" .env > .env.tmp || true; mv .env.tmp .env
  printf '%s=%s\n' "$1" "$2" >> .env
}

# ---------------------------------------------------------------- sandbox basics
RG=$(az group list --query "[0].name" -o tsv)
LOC=$(az group show -n "$RG" --query location -o tsv)    # the region changes between sandboxes
SUFFIX=$(echo -n "$RG" | md5sum | cut -c1-6)
SHELL_LOC=$(echo "${ACC_LOCATION:-}" | tr "A-Z" "a-z" | tr -d " ")   # the Cloud Shell region, when known
COSMOS="ai200cosmos$SUFFIX"; PG="ai200pg$SUFFIX"; REDIS="ai200redis$SUFFIX"
ST="ai200st$SUFFIX"; FUNC="ai200func$SUFFIX"
envset RESOURCE_GROUP "$RG"; envset LOCATION "$LOC"
say "Resource group $RG in $LOC"

venv() {
  if [ ! -d .venv ]; then
    say "Python virtual environment"
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
  say "Prewarming the embedding model (first download only)"
  python -m common.embed
  if ! python -c "import json;assert 'embedding' in json.load(open('data/tickets.json'))[0]" 2>/dev/null; then
    say "Computing seed embeddings (about 1 minute)"
    python tools/make_seed.py --embed
  fi
}

cosmos() {
  if ! az cosmosdb show -n "$COSMOS" -g "$RG" -o none 2>/dev/null; then
    say "Cosmos DB account $COSMOS (serverless, vector search enabled at creation, about 5 minutes)"
    # Vector search has to be on at creation. Turning it on later never took effect for me.
    az cosmosdb create -n "$COSMOS" -g "$RG" --locations regionName="$LOC" \
      --capabilities EnableServerless EnableNoSQLVectorSearch \
      --default-consistency-level Session --only-show-errors -o none
  fi
  envset COSMOS_ENDPOINT "$(az cosmosdb show -n "$COSMOS" -g "$RG" --query documentEndpoint -o tsv)"
  envset COSMOS_KEY "$(az cosmosdb keys list -n "$COSMOS" -g "$RG" --query primaryMasterKey -o tsv --only-show-errors)"
}

functions() {
  say "Storage account and Linux Consumption function app (Python 3.11)"
  az storage account show -n "$ST" -g "$RG" -o none 2>/dev/null || \
    az storage account create -n "$ST" -g "$RG" -l "$LOC" --sku Standard_LRS --only-show-errors -o none
  # Flex Consumption is blocked by sandbox policy; Application Insights creation failed alongside it.
  az functionapp show -n "$FUNC" -g "$RG" -o none 2>/dev/null || \
    az functionapp create -n "$FUNC" -g "$RG" --storage-account "$ST" --consumption-plan-location "$LOC" \
      --os-type Linux --runtime python --runtime-version 3.11 --functions-version 4 \
      --disable-app-insights true --only-show-errors -o none
  CONN=$(az cosmosdb keys list -n "$COSMOS" -g "$RG" --type connection-strings \
    --query "connectionStrings[0].connectionString" -o tsv --only-show-errors)
  az functionapp config appsettings set -n "$FUNC" -g "$RG" --settings "COSMOS=$CONN" --only-show-errors -o none
  envset FUNC_APP "$FUNC"
}

postgres() {
  local allow_vector=$1
  # Prefer a server in the same region as this Cloud Shell: across regions every connection pays
  # tens of milliseconds of network time, and the module 4 timings stop making sense.
  local found
  found=$(az postgres flexible-server list -g "$RG" --query "[].[name,location]" -o tsv 2>/dev/null | \
    python3 -c 'import sys; L, P = sys.argv[1], sys.argv[2]; rows = [r.rstrip("\n").split("\t") for r in sys.stdin if r.strip()]; rows = [r for r in rows if r[0].startswith("ai200pg")]; m = [n for n, l in rows if L and l.lower().replace(" ", "") == L] or [n for n, l in rows if n == P]; print(m[0] if m else "")' \
    "$SHELL_LOC" "$PG" || true)
  [ -n "$found" ] && PG="$found"
  if ! az postgres flexible-server show -n "$PG" -g "$RG" -o none 2>/dev/null; then
    PGPASS="Ai200-$(openssl rand -hex 12)"
    say "PostgreSQL $PG: General Purpose Standard_D2ds_v5, 32 GiB, auto-grow (about 6 minutes)"
    # Created at General Purpose: Burstable has no built-in PgBouncer, and scaling up later took 10 minutes.
    # Some sandbox regions refuse PostgreSQL ("The location is restricted"); try the next region.
    for PGLOC in ${PG_LOC:-${SHELL_LOC:-$LOC}} $LOC eastus2 centralus westus2 westus3; do
      say "Trying $PGLOC"
      if az postgres flexible-server create -n "$PG" -g "$RG" -l "$PGLOC" --tier GeneralPurpose \
        --sku-name Standard_D2ds_v5 --storage-size 32 --storage-auto-grow Enabled --version 16 \
        --admin-user ai200admin --admin-password "$PGPASS" --public-access All --yes --only-show-errors -o none; then
        break
      fi
    done
    envset PG_PASSWORD "$PGPASS"
  fi
  if ! grep -q '^PG_PASSWORD=' .env; then
    # Server made from another Cloud Shell: this one has no password yet, so set a new one.
    PGPASS="Ai200-$(openssl rand -hex 12)"
    say "Setting a new admin password for this Cloud Shell (about 1 minute)"
    az postgres flexible-server update -n "$PG" -g "$RG" --admin-password "$PGPASS" --only-show-errors -o none
    envset PG_PASSWORD "$PGPASS"
  fi
  envset PG_HOST "$PG.postgres.database.azure.com"; envset PG_USER ai200admin
  envset PG_DB postgres; envset PG_PORT 5432; envset PG_BOUNCER_PORT 6432
  if [ "$allow_vector" = yes ]; then
    say "Allowing VECTOR and PG_DISKANN in azure.extensions"
    az postgres flexible-server parameter set -g "$RG" -s "$PG" -n azure.extensions \
      -v VECTOR,PG_DISKANN --only-show-errors -o none
  else
    say "Leaving VECTOR out of azure.extensions (module 3 adds it)"
  fi
}

redis_cache() {
  az extension add -n redisenterprise --only-show-errors 2>/dev/null || true
  # Reuse a cache that finished; Balanced_B0 capacity varies by region, so fall back across regions.
  NAME=$(az redisenterprise list -g "$RG" --query "[?provisioningState=='Succeeded'].name | [0]" -o tsv 2>/dev/null || true)
  if [ -z "$NAME" ]; then
    for RLOC in ${REDIS_LOC:-${SHELL_LOC:-$LOC}} $LOC westus2 eastus2 centralus westus3; do
      NAME="$REDIS-$RLOC"
      say "Azure Managed Redis $NAME in $RLOC: Balanced_B0, RediSearch, Enterprise clustering (about 8 minutes)"
      # No --no-wait: the database must finish. Access keys are explicit because the CLI default changes.
      if az redisenterprise create -n "$NAME" -g "$RG" -l "$RLOC" --sku Balanced_B0 \
        --modules name=RediSearch --clustering-policy EnterpriseCluster --eviction-policy NoEviction \
        --public-network-access Enabled --access-keys-auth Enabled --only-show-errors -o none; then
        break
      fi
      NAME=""
    done
    [ -n "$NAME" ] || { echo "Azure Managed Redis could not be created in any region"; exit 1; }
  fi
  envset REDIS_HOST "$(az redisenterprise show -n "$NAME" -g "$RG" --query hostName -o tsv)"
  envset REDIS_PORT 10000; envset REDIS_SSL true
  envset REDIS_KEY "$(az redisenterprise database list-keys --cluster-name "$NAME" -g "$RG" \
    --query primaryKey -o tsv)"
}

case "${1:-}" in
  m1) cosmos; venv; python tools/setup_cosmos.py --empty ;;
  m2) cosmos; venv; python tools/setup_cosmos.py; functions ;;
  m3) postgres no; venv; python tools/setup_pg.py m3 ;;
  m4) postgres yes; venv; python tools/setup_pg.py m4 ;;
  m5) postgres yes; redis_cache; venv; python tools/setup_pg.py m4 ;;
  all) cosmos; postgres yes; redis_cache; venv; python tools/setup_cosmos.py; functions; python tools/setup_pg.py m4 ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
say "Done. Activate the environment with: source .venv/bin/activate"
