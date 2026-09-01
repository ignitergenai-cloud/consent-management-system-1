$ErrorActionPreference = "Stop"

$AWS_CMD = "aws"
$AWS_ARGS = @("--endpoint-url=http://localhost:4566", "--region", "us-east-1", "--no-cli-pager")
$REGION = "us-east-1"
$ACCOUNT = "000000000000"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  CMS AWS Resource Bootstrap" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# DynamoDB
Write-Host ""
Write-Host "Creating DynamoDB table..."
$tableExists = $false
try {
    & $AWS_CMD @AWS_ARGS dynamodb describe-table --table-name cms-consents 2>$null | Out-Null
    $tableExists = $true
} catch {}

if ($tableExists) {
    Write-Host "  Table 'cms-consents' already exists, skipping." -ForegroundColor Yellow
} else {
    $gsiJson = @'
[
    {
        "IndexName": "GSI1",
        "KeySchema": [
            {"AttributeName": "GSI1PK", "KeyType": "HASH"},
            {"AttributeName": "GSI1SK", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"}
    },
    {
        "IndexName": "GSI2",
        "KeySchema": [
            {"AttributeName": "GSI2PK", "KeyType": "HASH"},
            {"AttributeName": "GSI2SK", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"}
    },
    {
        "IndexName": "GSI3",
        "KeySchema": [
            {"AttributeName": "GSI3PK", "KeyType": "HASH"},
            {"AttributeName": "GSI3SK", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"}
    }
]
'@
    & $AWS_CMD @AWS_ARGS dynamodb create-table `
        --table-name cms-consents `
        --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE `
        --attribute-definitions `
            AttributeName=PK,AttributeType=S `
            AttributeName=SK,AttributeType=S `
            AttributeName=GSI1PK,AttributeType=S `
            AttributeName=GSI1SK,AttributeType=S `
            AttributeName=GSI2PK,AttributeType=S `
            AttributeName=GSI2SK,AttributeType=S `
            AttributeName=GSI3PK,AttributeType=S `
            AttributeName=GSI3SK,AttributeType=S `
        --global-secondary-indexes $gsiJson `
        --billing-mode PAY_PER_REQUEST | Out-Null
    Write-Host "  Table 'cms-consents' created." -ForegroundColor Green
}

# SNS Topics
Write-Host ""
Write-Host "Creating SNS topics..."
$topics = @(
    "cms-consent-events",
    "cms-notification-commands",
    "cms-notification-events",
    "cms-incident-events",
    "cms-internal-commands",
    "mims-inbound-incidents",
    "cms-incident-commands"
)

foreach ($topic in $topics) {
    Write-Host "  Creating topic: $topic"
    & $AWS_CMD @AWS_ARGS sns create-topic --name $topic | Out-Null
}

# SQS Queues with DLQs
Write-Host ""
Write-Host "Creating SQS queues..."
$queues = @(
    "cms-consent-processing-queue",
    "cms-notification-queue",
    "cms-notification-status-queue",
    "cms-incident-detection-queue",
    "cms-incident-bridge-queue",
    "cms-incident-commands-queue",
    "cms-internal-commands-queue"
)

foreach ($queue in $queues) {
    $dlqName = "$queue-dlq"

    Write-Host "  Creating DLQ: $dlqName"
    & $AWS_CMD @AWS_ARGS sqs create-queue --queue-name $dlqName | Out-Null

    $dlqArn = & $AWS_CMD @AWS_ARGS sqs get-queue-attributes `
        --queue-url "http://localhost:4566/000000000000/$dlqName" `
        --attribute-names QueueArn `
        --query 'Attributes.QueueArn' `
        --output text

    $redrivePolicy = "{""RedrivePolicy"":""{\\""deadLetterTargetArn\\"":\\""$dlqArn\\"",\\""maxReceiveCount\\"":\\""3\\""}""}";

    Write-Host "  Creating queue: $queue"
    & $AWS_CMD @AWS_ARGS sqs create-queue --queue-name $queue --attributes $redrivePolicy | Out-Null
}

# SNS Subscriptions
Write-Host ""
Write-Host "Creating SNS -> SQS subscriptions..."

function Subscribe-SqsToSns {
    param($TopicName, $QueueName)
    $topicArn = "arn:aws:sns:${REGION}:${ACCOUNT}:${TopicName}"
    $queueArn = "arn:aws:sqs:${REGION}:${ACCOUNT}:${QueueName}"
    Write-Host "  Subscribing $QueueName to $TopicName"
    & $AWS_CMD @AWS_ARGS sns subscribe --topic-arn $topicArn --protocol sqs --notification-endpoint $queueArn | Out-Null
}

Subscribe-SqsToSns "cms-consent-events" "cms-consent-processing-queue"
Subscribe-SqsToSns "cms-consent-events" "cms-incident-detection-queue"
Subscribe-SqsToSns "cms-notification-commands" "cms-notification-queue"
Subscribe-SqsToSns "cms-notification-events" "cms-notification-status-queue"
Subscribe-SqsToSns "cms-incident-events" "cms-incident-bridge-queue"
Subscribe-SqsToSns "cms-internal-commands" "cms-internal-commands-queue"
Subscribe-SqsToSns "cms-incident-commands" "cms-incident-commands-queue"

# S3
Write-Host ""
Write-Host "Creating S3 buckets..."
try {
    & $AWS_CMD @AWS_ARGS s3api head-bucket --bucket cms-consent-documents 2>$null
    Write-Host "  Bucket 'cms-consent-documents' already exists, skipping." -ForegroundColor Yellow
} catch {
    & $AWS_CMD @AWS_ARGS s3 mb s3://cms-consent-documents | Out-Null
    Write-Host "  Bucket 'cms-consent-documents' created." -ForegroundColor Green
}

# SES
Write-Host ""
Write-Host "Verifying SES identities..."
& $AWS_CMD @AWS_ARGS ses verify-email-identity --email-address no-reply@cms.example.com
Write-Host "  Verified: no-reply@cms.example.com" -ForegroundColor Green

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  All AWS resources created successfully!" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
