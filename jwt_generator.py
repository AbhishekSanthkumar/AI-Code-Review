#!/usr/bin/env python3
import time
import jwt
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get values from .env
app_id = os.getenv("GITHUB_APP_ID")
pem_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")

if not app_id or not pem_path:
    raise Exception("Missing GITHUB_APP_ID or GITHUB_PRIVATE_KEY_PATH in .env")

# Read private key
with open(pem_path, "r") as pem_file:
    signing_key = pem_file.read()

payload = {
    "iat": int(time.time()),          # issued at
    "exp": int(time.time()) + 600,    # expires in 10 min
    "iss": app_id                     # GitHub App ID
}

# Generate JWT
encoded_jwt = jwt.encode(payload, signing_key, algorithm="RS256")

print(encoded_jwt)