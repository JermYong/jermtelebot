import boto3
import json
import os
from datetime import datetime

# S3 client
def get_secret(path):
    with open(path, "r") as f:
        return f.read().strip()

aws_access_key_id = get_secret("/etc/secrets/AWS_ACCESS_KEY_ID")
aws_secret_access_key = get_secret("/etc/secrets/AWS_SECRET_ACCESS_KEY")
aws_region = get_secret("/etc/secrets/AWS_DEFAULT_REGION")
BUCKET = get_secret("/etc/secrets/S3_BUCKET_NAME")

s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)


def log_action(user_id: int, action: str, details: dict = None):
    """
    Logs an action and uploads to S3 as JSON.
    
    Args:
        user_id: Telegram user ID
        action: string describing the action ("submission", "approved", "rejected", etc.)
        details: extra info dictionary (caption, reason, schedule_time, etc.)
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details or {}
    }

    # Filename per day
    filename = f"logs/{datetime.utcnow().date()}.json"

    try:
        # Try to fetch existing log file
        obj = s3.get_object(Bucket=BUCKET, Key=filename)
        existing_logs = json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        existing_logs = []

    # Append new log
    existing_logs.append(log_entry)

    # Upload back to S3
    s3.put_object(
        Bucket=BUCKET,
        Key=filename,
        Body=json.dumps(existing_logs, indent=2),
        ContentType="application/json"
    )
    print(f"[S3 LOG] Logged {action} for user {user_id}")
    print(f"{action}: {details}")