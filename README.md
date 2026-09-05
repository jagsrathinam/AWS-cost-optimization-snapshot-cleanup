# AWS Multi-Region Resilient EBS Snapshot Cleanup


An enterprise-ready, serverless FinOps solution designed to safely scan, identify, and delete orphaned EBS snapshots older than 30 days across multiple AWS regions without hitting AWS API throttling limits (`RequestLimitExceeded`).

---

## Key Features

* **Resilient API Handling:** Built with Boto3 `adaptive` retry mode, exponential backoff, and full jitter to prevent AWS API rate-limiting.
* **Controlled Parallelization:** Uses AWS Step Functions Distributed Map to process global regions in parallel while enforcing `MaxConcurrency` controls.
* **Memory & Execution Efficient:** Leverages AWS S3/EC2 paginated requests (`PageSize: 500`) to handle thousands of snapshots smoothly.
* **AMI Dependency Protection:** Catches and logs locked snapshot exceptions (e.g., snapshots attached to active AMIs) without breaking execution loops.
* **Dry-Run Mode:** Supports a risk-free simulation mode to preview candidate snapshots before performing actual deletions.

---

## Architecture Overview

1. **Amazon EventBridge:** Fires a cron event (e.g., weekly) to trigger the cleanup workflow.
2. **Region Discoverer Lambda:** Queries EC2 to retrieve all active, enabled AWS regions in the account.
3. **AWS Step Functions (Distributed Map):** Distributes region-specific tasks to worker Lambdas in parallel with concurrency controls.
4. **Parallel Worker Lambdas:** Fetches regional snapshots via paginated requests, checks age thresholds (>30 days), and deletes expired snapshots using adaptive retries and pacing delays.
5. **Amazon CloudWatch:** Collects detailed logs and metric summaries for auditing and compliance tracking.

---

## IAM Permissions & Policy

Create an IAM Role for the Lambda functions (e.g., `SnapshotCleanupLambdaRole`) with the following minimal privilege policy attached:

### `iam_policy.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EC2SnapshotReadDeletePermissions",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeRegions",
        "ec2:DescribeSnapshots",
        "ec2:DeleteSnapshot"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLoggingPermissions",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}

---

## Project Structure

```text

├── README.md
├── architecture.dot            # Graphviz source for architecture diagram
├── aws_architecture_diagram.png # Rendered architecture diagram
├── iam_policy.json             # Minimal IAM policy for Lambda Execution Role
├── src/
│   ├── discoverer_lambda.py    # Fetches active AWS regions
│   └── worker_lambda.py        # Scans and deletes stale snapshots per region
└── step_function_definition.json # Step Functions State Machine definition