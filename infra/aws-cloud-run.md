# AWS cloud run — reference spec

Not wired into `tdmcalib` yet. This is the precise spec to build the EC2 instance,
IAM roles, and Secrets Manager entry against, so that when a `tdmcalib cloud-run`
command is eventually implemented it has a known-working target. Written for a
**manual, on-demand trigger**: you run a command from your own machine when you want
a calibration cycle kicked off; nothing here runs on a schedule.

Routine: start the (stopped) EC2 instance → run `tdmcalib run --run <id>` on it via
SSM → commit + push the curated `runs/<id>/` output straight to `main` → stop the
instance again, whether the run succeeded or failed.

## Assumptions

- Windows Server EC2 instance, Cube Voyager + license already installed on it, this
  repo already cloned on it (with `tdm/` submodule initialized) at a fixed path, e.g.
  `C:\tdmcalib\WF-TDM-Calibration`, with `config\local.yaml` already filled in for
  that machine's `Voyager_EXE` path.
- Instance is normally **stopped** (not just OS-sleeping) between runs — that's what
  actually deallocates EC2 compute billing.
- AMI is recent enough to ship the SSM Agent preinstalled (true for current Windows
  Server AMIs) — no manual agent install needed.

## 1. EC2 instance role (attached instance profile)

Trust policy (who can assume this role):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Attach the AWS-managed policy `AmazonSSMManagedInstanceCore` (lets the instance
register with Systems Manager and receive Run Commands — this is what makes
inbound RDP unnecessary).

Plus one inline policy, scoped to exactly one secret (see §3):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:tdmcalib/github-push-token-??????"
    }
  ]
}
```

(The trailing `-??????` matches Secrets Manager's random 6-character ARN suffix —
`?` is a valid IAM ARN wildcard for exactly one character.)

## 2. Trigger-side IAM policy (attached to your own IAM user/role, used from your laptop)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ec2:StartInstances", "ec2:StopInstances"],
      "Resource": "arn:aws:ec2:<REGION>:<ACCOUNT_ID>:instance/<INSTANCE_ID>"
    },
    {
      "Effect": "Allow",
      "Action": "ec2:DescribeInstances",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["ssm:SendCommand"],
      "Resource": [
        "arn:aws:ssm:<REGION>::document/AWS-RunPowerShellScript",
        "arn:aws:ec2:<REGION>:<ACCOUNT_ID>:instance/<INSTANCE_ID>"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "ssm:DescribeInstanceInformation",
      "Resource": "*"
    }
  ]
}
```

`ec2:DescribeInstances` and `ssm:DescribeInstanceInformation`/`GetCommandInvocation`
don't support resource-level restriction in AWS's IAM model — that's an AWS API
limitation, not a scoping choice; `StartInstances`/`StopInstances`/`SendCommand` are
the ones actually locked to this one instance.

## 3. Secrets Manager

Create one secret:

- **Name**: `tdmcalib/github-push-token`
- **Value**: a fine-grained GitHub PAT scoped to *only* this repository, with
  **Contents: read and write** permission and nothing else (no org-wide scope, no
  other repos).
- Nobody but the EC2 instance role (§1) and whoever administers the secret should
  have read access to it.

## 4. The remote script (sent via SSM `AWS-RunPowerShellScript`)

Runs *on* the instance, as the account SSM executes under (default: `SYSTEM`).

```powershell
$ErrorActionPreference = "Stop"
Set-Location C:\tdmcalib\WF-TDM-Calibration

git pull --ff-only

& ".venv\Scripts\tdmcalib.exe" run --run $env:CALIB_RUN_ID
if ($LASTEXITCODE -ne 0) { throw "tdmcalib run failed with exit code $LASTEXITCODE" }

git add "runs/$env:CALIB_RUN_ID"
git commit -m "Cloud run: $env:CALIB_RUN_ID"

$secret = Get-SECSecretValue -SecretId "tdmcalib/github-push-token"
$token = $secret.SecretString
$pushUrl = "https://x-access-token:$token@github.com/WFRCAnalytics/WF-TDM-Calibration.git"
git push $pushUrl HEAD:main
$token = $null
$pushUrl = $null
```

Notes:
- `git push` targets an inline authenticated URL rather than `origin`, so the token
  is never written to `.git/config` — it only exists in this process's memory for
  the duration of the push, then is cleared.
- `Get-SECSecretValue` is the AWS Tools for PowerShell cmdlet (installed alongside
  the SSM Agent's AWS PowerShell module on most Windows AMIs — confirm it's present,
  or call the Secrets Manager HTTPS API directly if not); it uses the instance role
  automatically, no credentials needed in-script.
- If `tdmcalib run` fails, the script throws before ever reaching the commit/push —
  nothing gets pushed for a failed run. Commit happens only after a clean run.
- `$env:CALIB_RUN_ID` is passed in as an SSM command parameter (§5), not hardcoded,
  so the same document works for any calibration run id.

## 5. Trigger-side boto3 sequence (reference, not yet wired to a CLI command)

```python
import time
import boto3

REGION = "<REGION>"
INSTANCE_ID = "<INSTANCE_ID>"
POWERSHELL_SCRIPT = "..."  # §4, as a single string

ec2 = boto3.client("ec2", region_name=REGION)
ssm = boto3.client("ssm", region_name=REGION)

def run(calib_run_id: str) -> None:
    ec2.start_instances(InstanceIds=[INSTANCE_ID])
    ec2.get_waiter("instance_running").wait(InstanceIds=[INSTANCE_ID])

    # instance_running only means EC2 booted -- SSM Agent registration lags behind.
    while True:
        resp = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [INSTANCE_ID]}]
        )
        infos = resp["InstanceInformationList"]
        if infos and infos[0]["PingStatus"] == "Online":
            break
        time.sleep(10)

    try:
        send = ssm.send_command(
            InstanceIds=[INSTANCE_ID],
            DocumentName="AWS-RunPowerShellScript",
            Parameters={
                "commands": [POWERSHELL_SCRIPT],
                # or pass calib_run_id via a preceding
                # `$env:CALIB_RUN_ID = "..."` line built into the script string
            },
            TimeoutSeconds=90000,  # exceeds framework.yaml's 86400s model timeout
            CloudWatchOutputConfig={
                "CloudWatchLogGroupName": "/tdmcalib/cloud-run",
                "CloudWatchOutputEnabled": True,
            },
        )
        command_id = send["Command"]["CommandId"]

        while True:
            inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=INSTANCE_ID)
            if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
                break
            time.sleep(15)

        print(inv["StandardOutputContent"])
        if inv["Status"] != "Success":
            print(inv["StandardErrorContent"])
            raise RuntimeError(f"Cloud run {calib_run_id} failed: {inv['Status']}")
    finally:
        ec2.stop_instances(InstanceIds=[INSTANCE_ID])
```

`StandardOutputContent`/`StandardErrorContent` from `GetCommandInvocation` truncate
at 2500 characters — `CloudWatchOutputConfig` above captures the full log in
CloudWatch Logs for anything longer (relevant here: a 24-hour model run's full
output). The instance role needs `logs:CreateLogStream`/`PutLogEvents` on that log
group added to §1 if you want this.

The `finally: stop_instances` is the load-bearing part — it fires whether the run
threw, timed out, or SSM itself errored, so a bad run costs one instance-hour, not
a forgotten-on overnight bill.

## Open items to fill in once the instance exists

- `<REGION>`, `<ACCOUNT_ID>`, `<INSTANCE_ID>` throughout.
- Confirm `Get-SECSecretValue` / AWS Tools for PowerShell is present on the AMI, or
  swap in a direct HTTPS call to Secrets Manager.
- Decide the CloudWatch log group name and add its IAM permissions if you want full
  output capture rather than the 2500-char truncated inline output.
- When ready to wire this into `tdmcalib` itself: new optional dependency group
  `cloud = ["boto3>=1.34"]` in `pyproject.toml`, a `src/tdmcalib/cloud_aws.py`
  module, a `cloud-run` CLI verb in `src/tdmcalib/cli.py`, and an `aws:` block
  (`instance_id`, `region`) added to `config/local.yaml`/`local.example.yaml`.
