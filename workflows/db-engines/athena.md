# db-engine: athena

Receives pre-resolved variables from the /db router:
- $ATHENA_REGION — AWS region (e.g. us-east-1)
- $ATHENA_DATABASE — Glue database name
- $ATHENA_WORKGROUP — Athena workgroup (default: primary)
- $ATHENA_S3_OUTPUT — S3 URI for query results (e.g. s3://my-bucket/athena-results/)
- $AWS_PROFILE — AWS CLI profile name (optional, uses default if unset)
- $SQL — query to execute

---

## Step 1 — Validate prerequisites

```bash
python3 -c "import boto3" 2>/dev/null \
  || { echo "ERROR: boto3 not found. Install: pip install boto3"; exit 1; }

python3 -c "
import boto3, os
session = boto3.Session(profile_name=os.environ.get('AWS_PROFILE','default'))
session.client('sts').get_caller_identity()
print('AWS credentials valid ✓')
" AWS_PROFILE="${AWS_PROFILE:-default}" || { echo "ERROR: Invalid AWS credentials. Run: aws configure"; exit 1; }
```

## Step 2 — Execute query and poll for results

```bash
ATHENA_REGION="$ATHENA_REGION" ATHENA_DATABASE="$ATHENA_DATABASE" \
ATHENA_WORKGROUP="${ATHENA_WORKGROUP:-primary}" ATHENA_S3_OUTPUT="$ATHENA_S3_OUTPUT" \
AWS_PROFILE="${AWS_PROFILE:-default}" SQL="$SQL" \
python3 << 'PYEOF'
import os, time, boto3

try:
    from tabulate import tabulate
    use_tabulate = True
except ImportError:
    use_tabulate = False

session = boto3.Session(
    profile_name=os.environ.get('AWS_PROFILE', 'default'),
    region_name=os.environ['ATHENA_REGION'],
)
client = session.client('athena')

response = client.start_query_execution(
    QueryString=os.environ['SQL'],
    QueryExecutionContext={'Database': os.environ['ATHENA_DATABASE']},
    WorkGroup=os.environ.get('ATHENA_WORKGROUP', 'primary'),
    ResultConfiguration={'OutputLocation': os.environ['ATHENA_S3_OUTPUT']},
)
query_id = response['QueryExecutionId']
print(f"Query submitted: {query_id}")

while True:
    status = client.get_query_execution(QueryExecutionId=query_id)
    state = status['QueryExecution']['Status']['State']
    if state == 'SUCCEEDED':
        break
    elif state in ('FAILED', 'CANCELLED'):
        reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"ERROR: Query {state}: {reason}")
        exit(1)
    print(f"  Status: {state} — waiting 2s...")
    time.sleep(2)

results = client.get_query_results(QueryExecutionId=query_id)
columns = [col['Label'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
rows = [[field.get('VarCharValue', '') for field in row['Data']] for row in results['ResultSet']['Rows'][1:]]
if use_tabulate:
    print(tabulate(rows, headers=columns, tablefmt='psql'))
else:
    print('\t'.join(columns))
    for row in rows:
        print('\t'.join(row))
PYEOF
```

## Safety rules
- S3 output bucket must exist and IAM role must have s3:PutObject access
- Athena charges per data scanned — use LIMIT and partition filters
- Results are also saved to $ATHENA_S3_OUTPUT for later reference
- tabulate is optional — falls back to tab-separated output
