import os
import sys
import json
from decimal import Decimal
from dotenv import load_dotenv

# Allow importing from the parent directory (for db_handler.py)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_handler import DynamoDBHandler, convert_floats_to_decimal

# Load .env file (from this script’s directory)
load_dotenv()

# Configuration 
USER_DIRS = ["users_and_artists/combined"]  # Folders containing user JSONs
MAX_USERS = 25 # None # Set to None for unlimited uploads

# --- Upload function ---
def upload_users(folders, max_users=None):
    # Load AWS credentials from environment
    aws_access_key = os.getenv("AWS_ACCESS_KEY")
    aws_secret_key = os.getenv("AWS_SECRET_KEY")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    # Verify credentials are present
    if not aws_access_key or not aws_secret_key:
        print("AWS credentials are missing Check .env file.")
        return

    # Initialize the DynamoDB handler
    db_handler = DynamoDBHandler(
        region_name=aws_region,
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key
    )

    uploaded = 0
    skipped = 0
    errors = 0
    seen_ids = set()

    print(f"Starting batch upload with max_users={max_users}")

    with db_handler.users_table.batch_writer(overwrite_by_pkeys=['user_id']) as batch:
        for folder in folders:
            for filename in os.listdir(folder):
                if not filename.endswith(".json"):
                    continue

                if max_users is not None and uploaded >= max_users:
                    print(f"Reached max upload limit: {max_users}")
                    print_summary(uploaded, skipped, errors)
                    return

                path = os.path.join(folder, filename)

                try:
                    with open(path, "r") as f:
                        user_data = json.load(f)

                    user_id = user_data.get("user_id")
                    cluster_id = user_data.get("cluster_id")

                    if not user_id or cluster_id is None:
                        print(f"Skipping {filename}: missing user_id or cluster_id")
                        skipped += 1
                        continue

                    if user_id in seen_ids:
                        print(f"Skipping duplicate user_id: {user_id}")
                        skipped += 1
                        continue

                    item = convert_floats_to_decimal(user_data)
                    batch.put_item(Item=item)
                    seen_ids.add(user_id)
                    uploaded += 1
                    print(f"Uploaded {user_id} → cluster {cluster_id}")

                except Exception as e:
                    print(f"Error uploading {filename}: {e}")
                    errors += 1

    print_summary(uploaded, skipped, errors)

# --- Summary Printer ---
def print_summary(uploaded, skipped, errors):
    print("\nUpload Summary:")
    print(f"Uploaded: {uploaded}")
    print(f"Skipped:  {skipped}")
    print(f"Errors:   {errors}")

# --- Main entry point ---
if __name__ == "__main__":
    upload_users(USER_DIRS, max_users=MAX_USERS)
