#!/usr/bin/env bash
# Run a shell script on an EC2 instance through SSM and print its output.
# Usage: ssm-run.sh <instance-id> <script-file> [timeout-seconds]
# Env: AWS_PROFILE / AWS_REGION select the account. Bounded wait, no retry.
set -euo pipefail
instance="$1"; script="$2"; limit="${3:-900}"
params="$(jq -Rs '{commands: ["bash <<'"'"'__SSM_EOF__'"'"'\n" + . + "\n__SSM_EOF__"]}' < "$script")"
cmd_id="$(aws ssm send-command --instance-ids "$instance" \
  --document-name AWS-RunShellScript --timeout-seconds "$limit" \
  --parameters "$params" --query Command.CommandId --output text)"
deadline=$((SECONDS + limit + 60))
while :; do
  status="$(aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$instance" \
    --query Status --output text 2>/dev/null || echo Pending)"
  case "$status" in
    Pending|InProgress|Delayed) ;;
    *) break ;;
  esac
  [ "$SECONDS" -lt "$deadline" ] || { echo "timed out waiting for $cmd_id" >&2; exit 124; }
  sleep 5
done
aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$instance" \
  --query '[StandardOutputContent,StandardErrorContent]' --output text
echo "status=$status command=$cmd_id"
[ "$status" = Success ]
