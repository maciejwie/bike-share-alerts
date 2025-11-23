# Bike Share Alerts

A real-time bike share monitoring system with iOS app, backend API, and data collector.

## Architecture

- **Backend API** (`backend/api/`): Python serverless functions on Vercel
- **Data Collector** (`backend/collector/`): Go serverless function on Vercel, triggered by Cloudflare Worker
- **Cloudflare Worker** (`cloudflare-worker/`): Cron job that triggers the collector every minute
- **iOS App** (`ios/`): SwiftUI app for bike share alerts
- **Database**: TimescaleDB on Neon (PostgreSQL)
- **Storage**: Cloudflare R2 for raw JSON backups

## Automated Deployment

The project uses GitHub Actions to automatically deploy on push to `main`:
- **Vercel**: Backend API and Collector
- **Cloudflare Worker**: Cron trigger

### Setup GitHub Actions

Add these secrets to your GitHub repository (Settings > Secrets and variables > Actions):

#### Vercel Secrets
1. **VERCEL_TOKEN**: Get from https://vercel.com/account/tokens
2. **VERCEL_ORG_ID**: Run `vercel` locally, then check `.vercel/project.json`
3. **VERCEL_PROJECT_ID**: Same as above

#### Cloudflare Secrets
1. **CLOUDFLARE_API_TOKEN**: 
   - Go to Cloudflare Dashboard > My Profile > API Tokens
   - Create Token > Edit Cloudflare Workers template
   - Grant "Edit" permissions for Workers

### Environment Variables

Configure these in your deployment platforms:

#### Vercel (Dashboard > Settings > Environment Variables)
- `DATABASE_URL`: PostgreSQL connection string from Neon
- `R2_ACCOUNT_ID`: Cloudflare account ID
- `R2_ACCESS_KEY_ID`: R2 access key
- `R2_SECRET_ACCESS_KEY`: R2 secret key
- `R2_BUCKET_NAME`: R2 bucket name
- `CRON_SECRET`: Shared secret for collector authentication

#### Cloudflare Worker (Dashboard > Workers & Pages > collector-cron > Settings > Variables)
- `CRON_SECRET`: Same value as Vercel (encrypted variable)

## Local Development

### Backend API
```bash
cd backend/api
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python routes.py
```

### Collector (Local Testing)
```bash
cd backend/collector
cp ../.env.example ../.env
# Edit ../.env with your credentials
go run main.go
```

### Cloudflare Worker
```bash
cd cloudflare-worker
wrangler dev
```

## Manual Deployment

If you need to deploy manually:

### Vercel
```bash
vercel --prod
```

### Cloudflare Worker
```bash
cd cloudflare-worker
wrangler deploy
```

## Database Setup

Run the schema from `backend/database/schema.sql` on your Neon database:
```bash
psql $DATABASE_URL -f backend/database/schema.sql
```
