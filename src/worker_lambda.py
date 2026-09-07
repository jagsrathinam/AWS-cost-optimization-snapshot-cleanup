import os
import time
import random
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta

# Boto3 Adaptive Retry Mode automatically backs off on API throttling headers
BOTO_CONFIG = Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'
    }
)

DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'
DAYS_THRESHOLD = int(os.environ.get('DAYS_THRESHOLD', '30'))


def call_with_jitter(client_method, **kwargs):
    """
    Executes an EC2 API call with exponential backoff and full jitter.
    """
    max_retries = 6
    for attempt in range(max_retries):
        try:
            return client_method(**kwargs)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['RequestLimitExceeded', 'ThrottlingException', 'Client.RequestLimitExceeded']:
                if attempt == max_retries - 1:
                    raise e
                # Exponential backoff with full jitter
                sleep_time = random.uniform(0, min(16, (2 ** attempt)))
                time.sleep(sleep_time)
            else:
                raise e


def lambda_handler(event, context):
    """
    Scans and deletes old EBS snapshots for a given region.
    """
    region = event.get('region', 'us-east-1')
    print(f"Processing region: {region} | Dry-Run: {DRY_RUN} | Threshold: {DAYS_THRESHOLD} days")
    
    ec2_client = boto3.client('ec2', region_name=region, config=BOTO_CONFIG)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_THRESHOLD)
    
    scanned_count = 0
    deleted_count = 0
    skipped_count = 0

    # Paginate requests to handle thousands of snapshots safely
    paginator = ec2_client.get_paginator('describe_snapshots')
    page_iterator = paginator.paginate(
        OwnerIds=['self'],
        PaginationConfig={'PageSize': 500}
    )

    for page in page_iterator:
        snapshots = page.get('Snapshots', [])
        scanned_count += len(snapshots)

        for snap in snapshots:
            snap_id = snap['SnapshotId']
            start_time = snap['StartTime']

            if start_time < cutoff_date:
                if DRY_RUN:
                    print(f"[DRY-RUN] Would delete snapshot {snap_id} in {region} (Created: {start_time})")
                    deleted_count += 1
                    continue

                try:
                    # Wrapped API call with jitter retry protection
                    call_with_jitter(ec2_client.delete_snapshot, SnapshotId=snap_id)
                    print(f"Successfully deleted snapshot {snap_id} in {region}")
                    deleted_count += 1
                    
                    # 50ms pacing delay to smooth out API request rate
                    time.sleep(0.05)

                except ClientError as e:
                    # Catches snapshots locked by active AMIs or volume restores
                    skipped_count += 1
                    print(f"Skipped snapshot {snap_id} in {region}: {e.response['Error']['Message']}")

    summary = {
        "region": region,
        "scanned": scanned_count,
        "deleted": deleted_count,
        "skipped": skipped_count,
        "dry_run": DRY_RUN
    }
    
    print(f"Completed region {region}: {summary}")
    return summary
