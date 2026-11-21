"""
Deploy KarmaForge to Hugging Face Space:
1. Injects all secrets from .env into the Space
2. Pushes git repo to the Space
"""

import os
import subprocess
from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv(".env")
HF_TOKEN = os.getenv("HF_TOKEN", "")
REPO_ID = os.getenv("HF_SPACE_ID", "Shlokok/KarmaForge")

api = HfApi(token=HF_TOKEN)

print(f"Connecting to Hugging Face Space: {REPO_ID}...")

# 1. Inject Secrets
secrets_to_upload = [
    "GEMINI_API_KEYS",
    "GROQ_API_KEY",
    "REDDIT_ACCOUNT_1_ENABLED",
    "REDDIT_ACCOUNT_1_USERNAME",
    "REDDIT_ACCOUNT_1_SESSION",
    "REDDIT_ACCOUNT_2_ENABLED",
    "REDDIT_ACCOUNT_2_USERNAME",
    "REDDIT_ACCOUNT_2_SESSION",
    "DISCORD_BOT_TOKEN",
    "DISCORD_CLIENT_ID"
]

print("\nUploading environment secrets to Space...")
for key in secrets_to_upload:
    val = os.getenv(key, "").strip()
    if val:
        try:
            api.add_space_secret(repo_id=REPO_ID, key=key, value=val)
            print(f"  Secret set: {key}")
        except Exception as e:
            print(f"  Error setting secret {key}: {e}")

# 2. Configure Git Remote and Push
print("\nPushing code to Hugging Face Space...")
remote_url = f"https://Shlokok:{HF_TOKEN}@huggingface.co/spaces/{REPO_ID}"

# Check if remote 'hf' already exists
res = subprocess.run(["git", "remote"], capture_output=True, text=True)
if "hf" in res.stdout:
    subprocess.run(["git", "remote", "set-url", "hf", remote_url])
else:
    subprocess.run(["git", "remote", "add", "hf", remote_url])

# Push to Hugging Face Space
push_res = subprocess.run(["git", "push", "hf", "main", "--force"], capture_output=True, text=True)
print("Git Push stdout:\n", push_res.stdout)
if push_res.stderr:
    print("Git Push stderr:\n", push_res.stderr)

if push_res.returncode == 0:
    print("\nDeployment successfully pushed to Hugging Face!")
else:
    print(f"\nGit push failed with returncode {push_res.returncode}")
