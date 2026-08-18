# Copied from AWS Lambda's inline editor on 2025-08-13, 
# 
# function ARN: arn:aws:lambda:us-east-1:619903709069:function:ec2MakeTerminate
# function URL: https://bye3zzfifkcgbq5ycurv6xc5ne0vnfwu.lambda-url.us-east-1.on.aws/
#
# Note that at time of writing, this is not deployed at all automatically, and is only
# deployed by copy-pasting into the lambda interface; we can improve that. 

import boto3
import json

aws_region = 'us-east-1'

def lambda_handler(event, context):
    # Create an EC2 client
    ec2_client = boto3.client('ec2', region_name=aws_region)
    print('simmer',event)
    print('simmer2',context)
    instance_id = event['body']['instance_id']

    # Terminate the EC2 instance
    ec2_client.terminate_instances(InstanceIds=[instance_id])

    return {
        'statusCode': 200,
        'body': 'works'
    }
