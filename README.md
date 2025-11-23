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

#### Database Secrets
1. **DATABASE_URL**: Connection string for your production database (e.g., from Neon)

### Environment Variables

Configure these in your deployment platforms:

#### Vercel (Dashboard > Settings > Environment Variables)
 **Note**: Make sure that these are configured as secrets, not as plain variables.
- `DATABASE_URL`: PostgreSQL connection string from Neon
- `R2_ACCOUNT_ID`: Cloudflare account ID
- `R2_ACCESS_KEY_ID`: R2 access key
- `R2_SECRET_ACCESS_KEY`: R2 secret key
- `R2_BUCKET_NAME`: R2 bucket name
- `CRON_SECRET`: Shared secret for collector authentication
- `ADMIN_API_KEY`: Shared secret for admin API authentication

#### Cloudflare Worker (Dashboard > Workers & Pages > collector-cron > Settings > Variables)
- `CRON_SECRET`: Same value as Vercel (encrypted variable)

## Local Development

### Environment Variables
```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials
```

### Install Dependencies
```bash
make install
```

### Backend API
```bash
# Run locally
make dev-api
```

### Collector (Local Testing)
```bash
make dev-collector
```

### Cloudflare Worker
```bash
make dev-worker
wrangler dev
```

## Manual Deployment

If you need to deploy manually:

### Vercel
```bash
make deploy-api
```

### Cloudflare Worker
```bash
make deploy-worker
```

## Database Management

### Migrations
Database changes are managed via versioned SQL files in `backend/database/migrations/`.

**To apply migrations locally:**
```bash
make migrate
```

**To create a new migration:**
1. Create a new SQL file in `backend/database/migrations/` (e.g., `003_add_feature.sql`).
2. Commit and push to `main`.
3. The deployment pipeline will automatically apply pending migrations.

**Initial Setup:**
If setting up a fresh database, the migration tool will automatically apply the schema from scratch (starting with `001_init.sql`).
