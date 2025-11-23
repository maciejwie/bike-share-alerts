# Backend API

This is a FastAPI application deployed as a serverless function on Vercel.

## Authentication

All endpoints require an API Key passed in the `Authorization` header:

```
Authorization: Bearer <YOUR_API_KEY>
```

API Keys are managed in the `api_keys` database table.

## Admin API

To manage API keys, you must set the `ADMIN_API_KEY` environment variable.

Authenticate admin requests with:
```
Authorization: Bearer <ADMIN_API_KEY>
```

### Endpoints

- `POST /admin/keys`: Create a new API key.
  - Body: `{"user_id": "string", "label": "string"}`
  - Returns: `{"key": "sk_live_...", "key_id": "..."}`
  - **Note**: The returned `key` is the **only** time you will see the raw key. Store it safely.
- `DELETE /admin/keys/{key_id}`: Revoke an API key.
- `GET /admin/keys`: List all API keys.

## Endpoints

### Routes

- `GET /routes`: List all routes for the authenticated user.
- `POST /routes`: Create a new route.

### Stations

- `GET /stations`: Get the latest status of all stations.

### Monitor

- `POST /monitor`: Check the status of a specific route (bikes at start, docks at end).
  - Body: `{"route_id": 123}`

## Local Development

Run with `uv`:

```bash
uv run uvicorn index:app --reload
```
