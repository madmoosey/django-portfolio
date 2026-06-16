#!/usr/bin/env python3
"""
Global Forest Watch Data API Key Management
Based on:
- https://data-api.globalforestwatch.org/#tag/Authentication/operation/get_api_keys_auth_apikeys_get
- https://data-api.globalforestwatch.org/#tag/Authentication/operation/validate_api_key_auth_apikey__api_key__validate_get

Usage:
  # List all API keys
  python3 scripts/manage_gfw_api_keys.py list --token "YOUR_BEARER_TOKEN"
  
  # Validate a specific API key
  python3 scripts/manage_gfw_api_keys.py validate --api-key "YOUR_API_KEY"
"""

import argparse
import json
import sys

import requests

GFW_API_BASE_URL = "https://data-api.globalforestwatch.org/auth"


def list_api_keys(token):
    """
    GET /auth/apikeys
    Retrieves all API keys associated with the authenticated user.
    """
    url = f"{GFW_API_BASE_URL}/apikeys"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"[*] Fetching API keys from {url}")
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            keys = data.get("data", [])
            print("\n[+] SUCCESS! Retrieved API Keys:")
            print("=" * 50)
            if not keys:
                print("No API keys found for this account.")
            else:
                for idx, key_info in enumerate(keys, 1):
                    print(f"Key #{idx}")
                    print(f"  Alias:        {key_info.get('alias')}")
                    print(f"  API Key:      {key_info.get('api_key')}")
                    print(f"  Organization: {key_info.get('organization')}")
                    print(f"  Domains:      {', '.join(key_info.get('domains', []))}")
                    print("-" * 30)
            print("=" * 50)
        else:
            print(f"\n[-] FAILED to list API keys. HTTP {response.status_code}")
            print("Response:", response.text)
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"\n[-] ERROR: Failed to connect to API. {e}")
        sys.exit(1)


def validate_api_key(api_key, token):
    """
    GET /auth/apikey/{api_key}/validate
    Validates the provided API key.
    """
    url = f"{GFW_API_BASE_URL}/apikey/{api_key}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"[*] Validating API Key: {api_key}")
    print(f"[*] Endpoint: {url}")
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            is_valid = data.get("status") == "success"
            print("\n[+] SUCCESS! Validation check complete.")
            print("=" * 50)
            if is_valid:
                print("Status: VALID")
                print("The API key exists and is correctly formatted.")
            else:
                print("Status: INVALID")
                print("The API key might be revoked or incorrect.")
            print("=" * 50)
        elif response.status_code == 404:
            print("\n[-] FAILED. API Key not found (HTTP 404).")
        else:
            print(f"\n[-] FAILED to validate API key. HTTP {response.status_code}")
            print("Response:", response.text)
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"\n[-] ERROR: Failed to connect to API. {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage GFW Data API Keys")
    subparsers = parser.add_subparsers(dest="action", required=True, help="Action to perform")

    # Subparser for 'list'
    list_parser = subparsers.add_parser("list", help="List all API keys for your account")
    list_parser.add_argument(
        "--token", required=True, help="Your OAuth2 Bearer token (generated via get_gfw_token.py)"
    )

    # Subparser for 'validate'
    validate_parser = subparsers.add_parser("validate", help="Validate an existing API key")
    validate_parser.add_argument("--api-key", required=True, help="The API Key to validate")
    validate_parser.add_argument("--token", required=True, help="Your OAuth2 Bearer token")

    args = parser.parse_args()

    if args.action == "list":
        list_api_keys(token=args.token)
    elif args.action == "validate":
        validate_api_key(api_key=args.api_key, token=args.token)
