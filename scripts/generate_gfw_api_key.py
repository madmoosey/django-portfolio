#!/usr/bin/env python3
"""
Global Forest Watch Data API Key Generator
Based on: https://data-api.globalforestwatch.org/#tag/Authentication/operation/create_api_key_auth_apikey_post

Usage:
  python3 scripts/generate_gfw_api_key.py --email "your@email.com" --org "ArborWatch" --alias "arborwatch-dev"
"""

import argparse
import sys
import json
import requests

GFW_API_URL = "https://data-api.globalforestwatch.org/auth/apikey"

def generate_api_key(alias, organization, email, domains=None, token=None, never_expires=True):
    """
    Sends a POST request to the GFW Data API to generate a new API key.
    """
    payload = {
        "alias": alias,
        "organization": organization,
        "email": email,
        "domains": domains or ["localhost", "127.0.0.1"]
    }

    headers = {
        "Content-Type": "application/json"
    }
    
    # If the API requires authentication to create a key, we pass the Bearer token
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"[*] Requesting new API Key from {GFW_API_URL}")
    print(f"[*] Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(GFW_API_URL, json=payload, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            api_key = data.get("data", {}).get("api_key", "UNKNOWN")
            print("\n[+] SUCCESS! API Key generated successfully.")
            print("="*50)
            print(f"API_KEY: {api_key}")
            print("="*50)
            print("Please add this key to your .env file as GFW_API_KEY.\n")
            return api_key
        else:
            print(f"\n[-] FAILED. HTTP {response.status_code}")
            print("Response:", response.text)
            
            if response.status_code == 401:
                print("\n[!] The API requires a Bearer token (OAuth2). You must login to the GFW website, extract your Bearer token from the Network tab, and pass it using --token.")
                
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"\n[-] ERROR: Failed to connect to API. {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a GFW Data API Key")
    parser.add_argument("--alias", required=True, help="Nickname for API Key")
    parser.add_argument("--org", required=True, help="Name of organization or website")
    parser.add_argument("--email", required=True, help="Email address of POC")
    parser.add_argument("--domains", nargs="*", help="List of domains to allow (e.g. localhost arborwatch.net)")
    parser.add_argument("--token", help="Bearer token if authentication is required by GFW")
    parser.add_argument("--never_expires", action="store_true", default=True, help="Does the key expire (defaults to True)")


    args = parser.parse_args()

    generate_api_key(
        alias=args.alias,
        organization=args.org,
        email=args.email,
        domains=args.domains,
        token=args.token,
        never_expires=args.never_expires,
    )
