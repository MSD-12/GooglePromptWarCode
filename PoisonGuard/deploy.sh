#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Poison Guard — MCP Server  |  Cloud Run Deployment Script
# ─────────────────────────────────────────────────────────────────────────────
# Usage:  bash deploy.sh
# Prerequisites:
#   - gcloud CLI installed and authenticated  (gcloud auth login)
#   - gcloud project set                      (gcloud config set project PROJECT_ID)
#   - Artifact Registry API enabled
#   - Cloud Run API enabled
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID="$(gcloud config get-value project 2>/dev/null)"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-poison-guard-mcp}"
REPO_NAME="${REPO_NAME:-poison-guard}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌  No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME:$IMAGE_TAG"

echo "════════════════════════════════════════════════════════════"
echo "  Poison Guard MCP — Cloud Run Deployment"
echo "  Project : $PROJECT_ID"
echo "  Region  : $REGION"
echo "  Image   : $IMAGE"
echo "════════════════════════════════════════════════════════════"

# ── Step 1: Read Gemini API Key ───────────────────────────────────────────────
if [[ -f ".env" ]]; then
  GEMINI_API_KEY="$(grep -E '^GEMINI_API_KEY=' .env | cut -d= -f2 | tr -d '"' | tr -d "'")"
fi

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo ""
  read -rsp "🔑  Enter your Gemini API Key: " GEMINI_API_KEY
  echo ""
fi

if [[ -z "$GEMINI_API_KEY" ]]; then
  echo "❌  Gemini API Key is required."
  exit 1
fi

# ── Step 2: Enable required APIs ─────────────────────────────────────────────
echo ""
echo "🔧  Enabling required Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project="$PROJECT_ID" \
  --quiet

# ── Step 3: Create Artifact Registry repo (idempotent) ───────────────────────
echo ""
echo "📦  Ensuring Artifact Registry repository exists..."
gcloud artifacts repositories describe "$REPO_NAME" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --quiet 2>/dev/null || \
gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --description="Poison Guard MCP container images" \
  --quiet

# ── Step 4: Configure Docker to use gcloud credentials ───────────────────────
echo ""
echo "🔐  Configuring Docker authentication for Artifact Registry..."
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

# ── Step 5: Build and push the container image ────────────────────────────────
echo ""
echo "🏗️   Building container image with Cloud Build..."
gcloud builds submit . \
  --tag="$IMAGE" \
  --project="$PROJECT_ID" \
  --quiet

# ── Step 6: Store Gemini Key in Secret Manager ───────────────────────────────
echo ""
echo "🔑  Storing Gemini API Key in Secret Manager..."
gcloud services enable secretmanager.googleapis.com \
  --project="$PROJECT_ID" --quiet

SECRET_NAME="gemini-api-key"
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" --quiet 2>/dev/null; then
  echo "$GEMINI_API_KEY" | \
    gcloud secrets versions add "$SECRET_NAME" \
      --data-file=- \
      --project="$PROJECT_ID" \
      --quiet
else
  echo "$GEMINI_API_KEY" | \
    gcloud secrets create "$SECRET_NAME" \
      --replication-policy="automatic" \
      --data-file=- \
      --project="$PROJECT_ID" \
      --quiet
fi

# Grant the default Cloud Run SA access to the secret
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
SA_EMAIL="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  --quiet

# ── Step 7: Deploy to Cloud Run ──────────────────────────────────────────────
echo ""
echo "🚀  Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE" \
  --platform=managed \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --allow-unauthenticated \
  --port=8080 \
  --cpu=1 \
  --memory=512Mi \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=300 \
  --set-secrets="GEMINI_API_KEY=$SECRET_NAME:latest" \
  --quiet

# ── Done ─────────────────────────────────────────────────────────────────────
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --platform=managed \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅  Deployment Complete!"
echo ""
echo "  Service URL   : $SERVICE_URL"
echo "  MCP SSE URL   : $SERVICE_URL/sse"
echo "  Health Check  : $SERVICE_URL/health"
echo ""
echo "  Add to your MCP client config:"
echo "  {"
echo "    \"mcpServers\": {"
echo "      \"poison-guard\": {"
echo "        \"url\": \"$SERVICE_URL/sse\""
echo "      }"
echo "    }"
echo "  }"
echo "════════════════════════════════════════════════════════════"
