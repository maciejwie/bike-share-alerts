"""
APNs (Apple Push Notification service) integration for sending push notifications to iOS devices.

Requires environment variables:
- APNS_KEY_ID: The 10-character Key ID from Apple Developer Portal
- APNS_TEAM_ID: Your 10-character Team ID
- APNS_KEY_PATH: Path to the .p8 private key file OR content of the key
- APNS_BUNDLE_ID: Your app's bundle identifier (e.g., com.example.bikesharealerts)
- APNS_USE_SANDBOX: Set to "true" for development, "false" for production
"""

import os
import time

import httpx
import jwt

# Global HTTPX client for connection pooling
_client = None


def _get_apns_config():
    """Get APNs configuration from environment variables."""
    return {
        "key_id": os.environ.get("APNS_KEY_ID"),
        "team_id": os.environ.get("APNS_TEAM_ID"),
        "key_path": os.environ.get("APNS_KEY_PATH"),
        "bundle_id": os.environ.get("APNS_BUNDLE_ID"),
        "use_sandbox": os.environ.get("APNS_USE_SANDBOX", "true").lower() == "true",
    }


def _is_apns_configured() -> bool:
    """Check if APNs is properly configured."""
    config = _get_apns_config()
    return all([config["key_id"], config["team_id"], config["key_path"], config["bundle_id"]])


def _get_client() -> httpx.AsyncClient:
    """Get or create the global HTTPX client with HTTP/2 support."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(http2=True)
    return _client


def _generate_jwt(config: dict) -> str:
    """Generate JWT token for APNs authentication."""
    key_path = config["key_path"]

    # Check if key_path is actually the key content (starts with -----BEGIN PRIVATE KEY-----)
    if "-----BEGIN PRIVATE KEY-----" in key_path:
        secret = key_path
    else:
        # Read from file
        try:
            with open(key_path) as f:
                secret = f.read()
        except Exception as e:
            print(f"Failed to read APNs key file: {e}")
            return None

    algorithm = "ES256"
    headers = {
        "alg": algorithm,
        "kid": config["key_id"],
    }
    payload = {
        "iss": config["team_id"],
        "iat": int(time.time()),
    }

    token = jwt.encode(payload, secret, algorithm=algorithm, headers=headers)
    return token


async def send_push_notification(
    device_token: str,
    title: str,
    body: str,
    data: dict | None = None,
    badge: int | None = None,
) -> bool:
    """
    Send a push notification to an iOS device via APNs.

    Args:
        device_token: The APNs device token (hex string)
        title: Notification title
        body: Notification body text
        data: Optional custom data to include in the notification
        badge: Optional badge count to display on app icon

    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not _is_apns_configured():
        print(f"APNs not configured. Would send: {title} - {body}")
        return False

    config = _get_apns_config()
    token = _generate_jwt(config)
    if not token:
        print("Failed to generate APNs JWT")
        return False

    # Determine endpoint
    endpoint = (
        "https://api.sandbox.push.apple.com"
        if config["use_sandbox"]
        else "https://api.push.apple.com"
    )
    url = f"{endpoint}/3/device/{device_token}"

    headers = {
        "authorization": f"bearer {token}",
        "apns-topic": config["bundle_id"],
        "apns-push-type": "alert",
        "apns-priority": "10",  # Send immediately
    }

    # Build the notification payload
    payload = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": "default",
        }
    }

    if badge is not None:
        payload["aps"]["badge"] = badge

    if data:
        # Merge custom data at root level
        payload.update(data)

    try:
        client = _get_client()
        response = await client.post(url, headers=headers, json=payload, timeout=10.0)

        if response.status_code == 200:
            print(f"APNs notification sent to {device_token[:8]}...")
            return True
        else:
            print(f"APNs failed: {response.status_code} - {response.text}")
            # Handle 410 Gone (Unregistered) -> In a real app, we should remove the token from DB
            return False

    except Exception as e:
        print(f"Failed to send APNs notification: {e}")
        return False


async def send_bike_alert(
    device_token: str,
    station_name: str,
    bike_count: int,
    station_id: int,
) -> bool:
    """
    Send a bike availability alert to the user.
    """
    title = "Bike Availability Update"
    body = f"{bike_count} bike{'s' if bike_count != 1 else ''} at {station_name}"

    data = {
        "type": "bike_alert",
        "station_id": station_id,
        "bike_count": bike_count,
    }

    return await send_push_notification(device_token, title, body, data)


async def send_dock_alert(
    device_token: str,
    station_name: str,
    dock_count: int,
    station_id: int,
    alert_level: int = 0,
) -> bool:
    """
    Send a dock availability alert to the user.
    """
    title = "Dock Availability Update"
    body = f"{dock_count} dock{'s' if dock_count != 1 else ''} at {station_name}"

    if alert_level > 0:
        body += f" ({_ordinal(alert_level + 1)} choice)"

    data = {
        "type": "dock_alert",
        "station_id": station_id,
        "dock_count": dock_count,
        "alert_level": alert_level,
    }

    return await send_push_notification(device_token, title, body, data)


def _ordinal(n: int) -> str:
    """Convert number to ordinal string (1 -> 1st, 2 -> 2nd, etc.)."""
    suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    return f"{n}{suffix}"
