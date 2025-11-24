# API Admin README

Helper app for managing the bike-share-alerts API.

## admin.py

Comprehensive admin CLI for managing users, API keys, and routes.

### Prerequisites

1. Set the `ADMIN_API_KEY` environment variable:
   ```bash
   export ADMIN_API_KEY='your-admin-key-here'
   ```

2. (Optional) Set a custom API URL:
   ```bash
   export API_URL='http://localhost:8000'  # defaults to production
   ```

### Usage

```bash
cd backend/api

# Quick create user + API key (most common use case)
uv run python admin/admin.py quick <email> <key_label> [--firstname NAME] [--lastname NAME]

# User management
uv run python admin/admin.py users create <email> <firstname> <lastname>
uv run python admin/admin.py users list
uv run python admin/admin.py users get <email>
uv run python admin/admin.py users delete <email>

# API key management
uv run python admin/admin.py keys create <email> <label>
uv run python admin/admin.py keys list
uv run python admin/admin.py keys roll <email> <label>
uv run python admin/admin.py keys delete <key_id>

# Route management (requires user's API key, not admin key)
uv run python admin/admin.py routes list <user_api_key>
```

### Examples

#### Quick setup (create user + key)
```bash
uv run python admin/admin.py quick "steve@apple.com" "iOS App" --firstname Steve --lastname Jobs
```

#### Create a user
```bash
uv run python admin/admin.py users create "steve@apple.com" Steve Jobs
```

#### List all users
```bash
uv run python admin/admin.py users list
```

#### Create an API key for a user
```bash
uv run python admin/admin.py keys create "steve@apple.com" "Production iOS App"
```

#### Roll (regenerate) an API key
```bash
uv run python admin/admin.py keys roll "steve@apple.com" "Production iOS App"
```

#### List all API keys
```bash
uv run python admin/admin.py keys list
```

#### Delete a user (cascades to keys and routes)
```bash
uv run python admin/admin.py users delete "steve@apple.com"
```

#### List routes for a user
```bash
uv run python admin/admin.py routes list "sk_live_508a598b-e933-4040-85e0-d771420f16d5"
```

### Example output

```
$ uv run python admin/admin.py quick "steve@apple.com" "iOS App" --firstname Steve --lastname Jobs

Creating user and API key for steve@apple.com...
✓ Created new user: steve@apple.com

======================================================================
SUCCESS! API Key Created
======================================================================

User Email: steve@apple.com
Key ID:     123e4567-e89b-12d3-a456-426614174000

API Key (save this - it won't be shown again):
  sk_live_508a598b-e933-4040-85e0-d771420f16d5

======================================================================
Test with curl:
======================================================================

curl https://bike-share-alerts-api.vercel.app/routes \
  -H "Authorization: Bearer sk_live_508a598b-e933-4040-85e0-d771420f16d5"

======================================================================
```
