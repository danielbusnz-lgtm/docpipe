"""InkVault AWS infrastructure.

Creates S3 bucket, DynamoDB table, Lambda function (Docker image),
and API Gateway to expose the FastAPI endpoints.
"""

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
)
from constructs import Construct


class InkVaultStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # --- S3: document storage ---
        bucket = s3.Bucket(
            self, "DocumentsBucket",
            bucket_name="inkvault-documents",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # --- DynamoDB: document metadata ---
        table = dynamodb.Table(
            self, "MetadataTable",
            table_name="inkvault-metadata",
            partition_key=dynamodb.Attribute(
                name="document_id", type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )
        table.add_global_secondary_index(
            index_name="status-created_at-index",
            partition_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Lambda: API + processing ---
        api_function = _lambda.DockerImageFunction(
            self, "ApiFunction",
            code=_lambda.DockerImageCode.from_image_asset(".."),  # project root
            timeout=Duration.seconds(300),
            memory_size=1024,
            environment={
                "INKVAULT_S3_BUCKET": bucket.bucket_name,
                "INKVAULT_DYNAMO_TABLE": table.table_name,
                "AWS_REGION": self.region,
                "ANTHROPIC_API_KEY": "{{resolve:ssm:/inkvault/anthropic-api-key}}",
            },
        )

        # permissions
        bucket.grant_read_write(api_function)
        table.grant_read_write_data(api_function)

        # --- S3 trigger: auto-process uploads ---
        processor_function = _lambda.DockerImageFunction(
            self, "ProcessorFunction",
            code=_lambda.DockerImageCode.from_image_asset(".."),
            timeout=Duration.seconds(900),  # 15 min max for processing
            memory_size=2048,
            environment={
                "INKVAULT_S3_BUCKET": bucket.bucket_name,
                "INKVAULT_DYNAMO_TABLE": table.table_name,
                "AWS_REGION": self.region,
                "ANTHROPIC_API_KEY": "{{resolve:ssm:/inkvault/anthropic-api-key}}",
            },
        )
        bucket.grant_read(processor_function)
        table.grant_read_write_data(processor_function)

        # trigger on PDF upload
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(processor_function),
            s3.NotificationKeyFilter(suffix=".pdf"),
        )

        # --- API Gateway ---
        api = apigw.LambdaRestApi(
            self, "InkVaultApi",
            handler=api_function,
            proxy=True,  # forward all requests to FastAPI/Mangum
        )
