# AWS Multi-Region Resilient EBS Snapshot Cleanup

```dot
digraph AWS_Scale_Snapshot_Cleanup {
    compound=true;
    rankdir=LR;
    bgcolor="white";
    fontname="Helvetica";
    fontsize=12;

    node [shape=none, fontname="Helvetica", fontsize=10, fontcolor="#232F3E"];
    edge [fontname="Helvetica", fontsize=9, color="#545B64", fontcolor="#545B64"];

    EventBridge [label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
        <TR><TD><FONT COLOR="#FF4F00" POINT-SIZE="24">⏰</FONT></TD></TR>
        <TR><TD><B>Amazon EventBridge</B></TD></TR>
        <TR><TD><FONT COLOR="#545B64" POINT-SIZE="8">(Cron Schedule)</FONT></TD></TR>
    </TABLE>>];

    subgraph cluster_aws_cloud {
        label = <<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
            <TR>
                <TD ALIGN="LEFT"><B><FONT COLOR="#232F3E" POINT-SIZE="14">aws</FONT>   AWS Cloud</B></TD>
                <TD ALIGN="RIGHT"><B><FONT COLOR="#232F3E" POINT-SIZE="11">Steps</FONT></B><BR/>
                    <FONT COLOR="#545B64" POINT-SIZE="9">1. EventBridge triggers Region Discoverer</FONT><BR/>
                    <FONT COLOR="#545B64" POINT-SIZE="9">2. Step Functions Map State fans out execution</FONT><BR/>
                    <FONT COLOR="#545B64" POINT-SIZE="9">3. Workers delete stale snapshots safely</FONT>
                </TD>
            </TR>
        </TABLE>>;
        style = "rect";
        color = "#232F3E";
        penwidth = 2.0;
        margin = 30;

        DiscovererLambda [label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
            <TR><TD><FONT COLOR="#ED7100" POINT-SIZE="28">ƛ</FONT></TD></TR>
            <TR><TD><B>AWS Lambda</B></TD></TR>
            <TR><TD><FONT COLOR="#545B64" POINT-SIZE="8">(Region Discoverer)</FONT></TD></TR>
        </TABLE>>];

        StepFunctions [label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
            <TR><TD><FONT COLOR="#D05C17" POINT-SIZE="24">⚙️</FONT></TD></TR>
            <TR><TD><B>AWS Step Functions</B></TD></TR>
            <TR><TD><FONT COLOR="#545B64" POINT-SIZE="8">(Distributed Map)</FONT></TD></TR>
        </TABLE>>];

        WorkerLambda [label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
            <TR><TD><FONT COLOR="#ED7100" POINT-SIZE="28">ƛ</FONT></TD></TR>
            <TR><TD><B>AWS Lambda</B></TD></TR>
            <TR><TD><FONT COLOR="#545B64" POINT-SIZE="8">(Parallel Worker)</FONT></TD></TR>
        </TABLE>>];

        EC2Snapshots [label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
            <TR><TD><FONT COLOR="#7AA116" POINT-SIZE="24">📦</FONT></TD></TR>
            <TR><TD><B>Amazon EC2</B></TD></TR>
            <TR><TD><FONT COLOR="#545B64" POINT-SIZE="8">(EBS Snapshots)</FONT></TD></TR>
        </TABLE>>];

        CloudWatch [label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
            <TR><TD><FONT COLOR="#E7157B" POINT-SIZE="24">📊</FONT></TD></TR>
            <TR><TD><B>Amazon CloudWatch</B></TD></TR>
            <TR><TD><FONT COLOR="#545B64" POINT-SIZE="8">(Logs & Metrics)</FONT></TD></TR>
        </TABLE>>];
    }

    EventBridge -> DiscovererLambda [label=" Trigger Run  "];
    DiscovererLambda -> StepFunctions [label=" Pass Region Array  "];
    StepFunctions -> WorkerLambda [label=" Controlled\n MaxConcurrency  "];
    WorkerLambda -> EC2Snapshots [label=" Adaptive Retries\n & 50ms Pacing  "];
    WorkerLambda -> CloudWatch [label=" Stream Logs  "];
}


An enterprise-ready, serverless FinOps solution designed to safely scan, identify, and delete orphaned EBS snapshots older than 30 days across multiple AWS regions without hitting AWS API throttling limits (RequestLimitExceeded).
Key Features
Resilient API Handling: Built with Boto3 adaptive retry mode, exponential backoff, and full jitter to prevent AWS API rate-limiting.
Controlled Parallelization: Uses AWS Step Functions Distributed Map to process global regions in parallel while enforcing MaxConcurrency controls.
Memory & Execution Efficient: Leverages AWS EC2 paginated requests (PageSize: 500) to handle thousands of snapshots smoothly.
AMI Dependency Protection: Catches and logs locked snapshot exceptions (e.g., snapshots attached to active AMIs) without breaking execution loops.
Dry-Run Mode: Supports a risk-free simulation mode to preview candidate snapshots before performing actual deletions.
Project Structure



Plaintext
.
├── README.md
├── iam_policy.json               # Minimal IAM policy for Lambda Execution Role
├── step_function_definition.json # Step Functions State Machine definition
└── src/
    ├── discoverer_lambda.py      # Fetches active AWS regions
    └── worker_lambda.py          # Scans and deletes stale snapshots per region


IAM Policy Configuration
Create an IAM Role for the Lambda functions (SnapshotCleanupLambdaRole) with the following minimal privilege policy attached:
iam_policy.json



JSON
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


Step Functions State Machine Definition
Import this JSON into the AWS Step Functions Console to orchestrate region discovery and worker fan-out.
step_function_definition.json



JSON
{
  "Comment": "Orchestrates multi-region EBS snapshot cleanup with concurrency limits",
  "StartAt": "DiscoverRegions",
  "States": {
    "DiscoverRegions": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:snapshot-cleanup-discoverer",
      "ResultPath": "$.discovery",
      "Next": "ProcessRegionsDistributedMap"
    },
    "ProcessRegionsDistributedMap": {
      "Type": "Map",
      "ItemProcessor": {
        "ProcessorConfig": {
          "Mode": "DISTRIBUTED",
          "ExecutionType": "STANDARD"
        },
        "StartAt": "DeleteStaleSnapshots",
        "States": {
          "DeleteStaleSnapshots": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:us-east-1:123456789012:function:snapshot-cleanup-worker",
            "Parameters": {
              "region.$": "$"
            },
            "End": true
          }
        }
      },
      "ItemsPath": "$.discovery.regions",
      "MaxConcurrency": 5,
      "End": true
    }
  }
}


Deployment Steps
Step 1: Deploy the Discoverer Lambda Function
Open the AWS Lambda Console and click Create function.
Name the function snapshot-cleanup-discoverer.
Choose runtime Python 3.11 (or higher).
Assign the SnapshotCleanupLambdaRole.
Paste the code from src/discoverer_lambda.py.
Step 2: Deploy the Worker Lambda Function
Create a second Lambda function named snapshot-cleanup-worker.
Choose runtime Python 3.11 (or higher).
Assign the SnapshotCleanupLambdaRole.
Paste the code from src/worker_lambda.py.
Configure Environment Variables under Configuration -> Environment variables:
DRY_RUN: true (set to false when ready for actual deletions)
DAYS_THRESHOLD: 30
Adjust the function timeout to 5 minutes under General configuration.
Step 3: Configure AWS Step Functions
Open the AWS Step Functions Console and click Create state machine.
Choose the Code editor.
Import step_function_definition.json and replace the placeholder ARNs with your deployed Lambda ARNs.
Save the State Machine as SnapshotCleanupOrchestrator.
Step 4: Schedule via Amazon EventBridge
Open the Amazon EventBridge Console and select Rules -> Create rule.
Name the rule weekly-snapshot-cleanup-schedule.
Set Rule Type to Schedule.
Define a Cron Expression (e.g., run every Sunday at midnight UTC):
Plaintext
cron(0 0 ? * SUN *)


Set the Target to Step Functions State Machine and select SnapshotCleanupOrchestrator.
Save and enable the rule.
Verification & Testing
Run a manual execution of SnapshotCleanupOrchestrator with DRY_RUN = true.
Review Amazon CloudWatch Logs for snapshot-cleanup-worker to inspect candidate snapshots:
Plaintext
[DRY-RUN] Would delete snapshot snap-0123456789abcdef0 in us-east-1 (Created: 2026-07-01 10:00:00+00:00)


Once verified, change the DRY_RUN environment variable to false to enable automated production cleanup.

