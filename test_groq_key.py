#!/usr/bin/env python3
"""
Check the configured Groq API key by requesting a short LLM response.

The script loads GROQ_API_KEY, GROQ_MODEL, and GROQ_BASE_URL from the project's
.env file when present, then calls the OpenAI-compatible chat completions API.

Usage:
    python test_groq_key.py
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv


def main():
    load_dotenv()

    token = os.environ.get("GROQ_API_KEY", "").strip()
    if not token:
        print("Error: GROQ_API_KEY not set in environment.")
        sys.exit(2)

    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()
    base_url = os.environ.get(
        "GROQ_BASE_URL", "https://api.groq.com/openai/v1"
    ).rstrip("/")
    ca_bundle = (
        os.environ.get("REQUESTS_CA_BUNDLE")
        or os.environ.get("CURL_CA_BUNDLE")
        or os.environ.get("GROQ_CA_CERT")
    )
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Reply with exactly: Groq API key works."}
        ],
        "temperature": 0,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
            verify=ca_bundle or True,
        )
        response.raise_for_status()
        result = response.json()
        message = result["choices"][0]["message"]["content"]
        print(f"API key works. Model: {model}")
        print(f"LLM response: {message}")
    except requests.HTTPError:
        print(f"API request failed (HTTP {response.status_code}).")
        try:
            error = response.json()
            print(json.dumps(error, indent=2))
        except ValueError:
            print(response.text)
        sys.exit(1)
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as e:
        print(f"Request failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
