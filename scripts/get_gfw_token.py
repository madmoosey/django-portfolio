#!/usr/bin/env python3
"""
Global Forest Watch Data API Token Generator
Based on: https://data-api.globalforestwatch.org/#tag/Authentication/operation/get_token_auth_token_post

Usage:
  python3 scripts/get_gfw_token.py --username "your_email" --password "your_password"
"""

import argparse
import sys

import requests

GFW_TOKEN_URL = "https://data-api.globalforestwatch.org/auth/token"


def get_token(username, password):
    """
    Sends a POST request to the GFW Data API to get an OAuth2 Bearer token.
    """
    payload = {"grant_type": "password", "username": username, "password": password}

    # The API expects form data (application/x-www-form-urlencoded)
    print(f"[*] Requesting Token from {GFW_TOKEN_URL}")
    print(f"[*] Username: {username}")

    try:
        response = requests.post(GFW_TOKEN_URL, data=payload)

        if response.status_code == 200:
            data = response.json()
            data = data.get("data", {})
            # FastAPI's OAuth2PasswordRequestForm usually returns access_token
            access_token = data.get("access_token", "UNKNOWN")
            token_type = data.get("token_type", "bearer")

            print("\n[+] SUCCESS! Token retrieved successfully.")
            print("=" * 50)
            print(f"TOKEN ({token_type}): {access_token}")
            print("=" * 50)
            print(
                "You can use this token with the generate_gfw_api_key.py script using the --token flag.\n"
            )
            return access_token
        else:
            print(f"\n[-] FAILED. HTTP {response.status_code}")
            print("Response:", response.text)
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"\n[-] ERROR: Failed to connect to API. {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get a GFW Data API Bearer Token")
    parser.add_argument("--username", required=True, help="Your GFW Username/Email")
    parser.add_argument("--password", required=True, help="Your GFW Password")

    args = parser.parse_args()

    get_token(username=args.username, password=args.password)
