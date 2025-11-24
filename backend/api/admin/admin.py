#!/usr/bin/env python3
"""
Admin CLI for managing bike-share-alerts API resources
"""

import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AdminClient:
    """Client for interacting with the admin API"""

    def __init__(self, api_url: str, admin_key: str):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {admin_key}", "Content-Type": "application/json"}

    def _request(self, method: str, endpoint: str, json_data: dict | None = None):
        """Make an HTTP request to the admin API"""
        try:
            response = httpx.request(
                method=method,
                url=f"{self.api_url}{endpoint}",
                json=json_data,
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()

            # Handle 204 No Content responses
            if response.status_code == 204:
                return None

            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"Error: HTTP {e.response.status_code}")
            print(f"Response: {e.response.text}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    # User commands
    def create_user(self, email: str, firstname: str, lastname: str):
        """Create or get a user"""
        data = self._request(
            "POST",
            "/admin/users",
            {"user_email": email, "user_firstname": firstname, "user_lastname": lastname},
        )

        if data.get("existed"):
            print(f"✓ Found existing user: {data['user_email']}")
        else:
            print(f"✓ Created new user: {data['user_email']}")

        return data

    def list_users(self):
        """List all users"""
        data = self._request("GET", "/admin/users")
        users = data.get("users", [])

        if not users:
            print("No users found")
            return

        print(f"\n{'Email':<40} {'First Name':<15} {'Last Name':<15} {'Created':<20}")
        print("-" * 95)
        for user in users:
            print(
                f"{user['user_email']:<40} {user.get('user_firstname', 'N/A'):<15} {user.get('user_lastname', 'N/A'):<15} {user.get('created_at', 'N/A'):<20}"
            )

    def get_user(self, email: str):
        """Get user details by email"""
        data = self._request("GET", f"/admin/users/by-email/{email}")

        print("\nUser Details:")
        print(f"  Email:      {data['user_email']}")
        print(f"  First Name: {data.get('user_firstname', 'N/A')}")
        print(f"  Last Name:  {data.get('user_lastname', 'N/A')}")
        print(f"  Device Token: {data.get('device_token', 'N/A')}")
        print(f"  Created:    {data.get('created_at', 'N/A')}")

    def delete_user(self, email: str):
        """Delete a user and all associated data"""
        self._request("DELETE", f"/admin/users/{email}")
        print(f"✓ Deleted user: {email}")

    # Key commands
    def create_key(self, email: str, label: str):
        """Create or get an API key"""
        data = self._request("POST", "/admin/keys", {"user_email": email, "label": label})

        if data.get("existed"):
            print(f"✓ Key already exists with ID: {data['key_id']}")
            print(f"\n{data.get('message', '')}")
            print("\nTo regenerate the key, use:")
            print(f'  uv run python admin/admin.py keys roll {email} "{label}"')
        else:
            api_key = data["key"]
            print("\n" + "=" * 70)
            print("SUCCESS! API Key Created")
            print("=" * 70)
            print(f"\nUser Email: {email}")
            print(f"Key ID:     {data['key_id']}")
            print("\nAPI Key (save this - it won't be shown again):")
            print(f"  {api_key}")
            print("\n" + "=" * 70)
            print("Test with curl:")
            print("=" * 70)
            print(f"""
curl {self.api_url}/routes \\
  -H "Authorization: Bearer {api_key}"
""")
            print("=" * 70)

        return data

    def list_keys(self):
        """List all API keys"""
        data = self._request("GET", "/admin/keys")
        keys = data.get("keys", [])

        if not keys:
            print("No API keys found")
            return

        print(f"\n{'Key ID':<40} {'User Email':<30} {'Label':<25} {'Last Used':<20}")
        print("-" * 120)
        for key in keys:
            last_used = key.get("last_used_at", "Never")
            print(f"{key['key_id']:<40} {key['user_email']:<30} {key['label']:<25} {last_used:<20}")

    def roll_key(self, email: str, label: str):
        """Regenerate an API key"""
        data = self._request("POST", "/admin/keys/roll", {"user_email": email, "key_label": label})

        api_key = data["key"]
        print("\n" + "=" * 70)
        print("SUCCESS! API Key Rolled")
        print("=" * 70)
        print(f"\nUser Email: {email}")
        print(f"Key ID:     {data['key_id']}")
        print("\nNew API Key (save this - it won't be shown again):")
        print(f"  {api_key}")
        print("\n" + "=" * 70)

    def delete_key(self, key_id: str):
        """Delete an API key"""
        self._request("DELETE", f"/admin/keys/{key_id}")
        print(f"✓ Deleted API key: {key_id}")

    # Route commands (using regular API with user's key)
    def list_routes(self, user_key: str):
        """List routes for a user (requires user's API key)"""
        # Use user's key instead of admin key
        headers = {"Authorization": f"Bearer {user_key}", "Content-Type": "application/json"}

        try:
            response = httpx.get(f"{self.api_url}/routes", headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            print(f"Error: HTTP {e.response.status_code}")
            print(f"Response: {e.response.text}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

        routes = data.get("routes", [])

        if not routes:
            print("No routes found")
            return

        print(f"\n{'ID':<40} {'Name':<25} {'Start→End':<20} {'Active':<8}")
        print("-" * 95)
        for route in routes:
            active = "Yes" if route.get("active") else "No"
            stations = (
                f"{route.get('start_station_id', 'N/A')}→{route.get('end_station_id', 'N/A')}"
            )
            print(f"{route['id']:<40} {route['name']:<25} {stations:<20} {active:<8}")


def main():
    parser = argparse.ArgumentParser(
        description="Admin CLI for bike-share-alerts API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # User commands
    users_parser = subparsers.add_parser("users", help="Manage users")
    users_subparsers = users_parser.add_subparsers(dest="subcommand")

    create_user_parser = users_subparsers.add_parser("create", help="Create a user")
    create_user_parser.add_argument("email", help="User email")
    create_user_parser.add_argument("firstname", help="First name")
    create_user_parser.add_argument("lastname", help="Last name")

    _list_users_parser = users_subparsers.add_parser("list", help="List all users")

    get_user_parser = users_subparsers.add_parser("get", help="Get user details")
    get_user_parser.add_argument("email", help="User email")

    delete_user_parser = users_subparsers.add_parser("delete", help="Delete a user")
    delete_user_parser.add_argument("email", help="User email")

    # Key commands
    keys_parser = subparsers.add_parser("keys", help="Manage API keys")
    keys_subparsers = keys_parser.add_subparsers(dest="subcommand")

    create_key_parser = keys_subparsers.add_parser("create", help="Create an API key")
    create_key_parser.add_argument("email", help="User email")
    create_key_parser.add_argument("label", help="Key label")

    _list_keys_parser = keys_subparsers.add_parser("list", help="List all API keys")

    roll_key_parser = keys_subparsers.add_parser("roll", help="Roll (regenerate) an API key")
    roll_key_parser.add_argument("email", help="User email")
    roll_key_parser.add_argument("label", help="Key label")

    delete_key_parser = keys_subparsers.add_parser("delete", help="Delete an API key")
    delete_key_parser.add_argument("key_id", help="Key ID")

    # Route commands
    routes_parser = subparsers.add_parser("routes", help="Manage routes")
    routes_subparsers = routes_parser.add_subparsers(dest="subcommand")

    list_routes_parser = routes_subparsers.add_parser("list", help="List routes for a user")
    list_routes_parser.add_argument("user_key", help="User's API key")

    # Quick command for creating user + key
    quick_parser = subparsers.add_parser("quick", help="Quickly create user and API key")
    quick_parser.add_argument("email", help="User email")
    quick_parser.add_argument("key_label", help="Key label")
    quick_parser.add_argument("--firstname", default="User", help="First name (default: User)")
    quick_parser.add_argument("--lastname", default="", help="Last name (default: empty)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Get configuration
    api_url = os.getenv("API_URL", "https://bike-share-alerts-api.vercel.app")
    admin_key = os.getenv("ADMIN_API_KEY")

    if not admin_key:
        print("Error: ADMIN_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export ADMIN_API_KEY='your-admin-key-here'")
        print("\nOr create a .env file with:")
        print("  ADMIN_API_KEY=your-admin-key-here")
        sys.exit(1)

    client = AdminClient(api_url, admin_key)

    # Execute commands
    if args.command == "users":
        if args.subcommand == "create":
            client.create_user(args.email, args.firstname, args.lastname)
        elif args.subcommand == "list":
            client.list_users()
        elif args.subcommand == "get":
            client.get_user(args.email)
        elif args.subcommand == "delete":
            client.delete_user(args.email)
        else:
            users_parser.print_help()

    elif args.command == "keys":
        if args.subcommand == "create":
            client.create_key(args.email, args.label)
        elif args.subcommand == "list":
            client.list_keys()
        elif args.subcommand == "roll":
            client.roll_key(args.email, args.label)
        elif args.subcommand == "delete":
            client.delete_key(args.key_id)
        else:
            keys_parser.print_help()

    elif args.command == "routes":
        if args.subcommand == "list":
            client.list_routes(args.user_key)
        else:
            routes_parser.print_help()

    elif args.command == "quick":
        # Quick create user + key
        print(f"Creating user and API key for {args.email}...")
        client.create_user(args.email, args.firstname, args.lastname)
        client.create_key(args.email, args.key_label)


if __name__ == "__main__":
    main()
