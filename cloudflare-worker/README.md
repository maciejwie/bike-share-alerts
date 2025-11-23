# Cloudflare Worker Cron

This worker triggers the Vercel collector endpoint every minute.

## Automated Deployment (Recommended)

The worker is automatically deployed via GitHub Actions when you push to the `main` branch. See the main project README for setup instructions.

## Manual Deployment

If you need to deploy manually:

1. **Install Wrangler** (if not already installed):
   ```bash
   npm install -g wrangler
   ```

2. **Login to Cloudflare**:
   ```bash
   wrangler login
   ```

3. **Deploy the Worker**:
   ```bash
   cd cloudflare-worker
   wrangler deploy
   ```

## Secret Configuration

The `CRON_SECRET` should be configured in the worker's environment variables in the Cloudflare dashboard.

## Verify

Check the Cloudflare Dashboard > Workers & Pages > collector-cron > Logs to see the cron executions.
