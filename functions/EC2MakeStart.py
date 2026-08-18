# Copied from AWS Lambda's inline editor on 2025-08-13, 
# 
# function ARN: arn:aws:lambda:us-east-1:619903709069:function:EC2MakeStart
# function URL: https://ihwpbnjt2syrzqtvlgrndo5qpi0sxeqa.lambda-url.us-east-1.on.aws/
#
# Note that at time of writing, this is not deployed at all automatically, and is only
# deployed by copy-pasting into the lambda interface; we can improve that. 

import boto3
import json
from datetime import datetime, timedelta

aws_region = 'us-east-1'

# EC2 launch template ID
launch_template_id = 'launchOptimizeContainerREAL'

def lambda_handler(event, context):
    response = {
    "isBase64Encoded": False,
    "headers": {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Allow-Methods": "OPTIONS,POST,GET,PUT,DELETE"
    },
    "statusCode": 200,
    "body": ''
    };
    print('hello',event)
    if False and event["requestContext"]["http"]["method"] == 'OPTIONS':
        return response;
    else:
        # Create an EC2 client
        print('seeker')
        ec2_client = boto3.client('ec2', region_name=aws_region)
    
        # Launch an EC2 instance using the launch template
        response = ec2_client.run_instances(
            LaunchTemplate={
                'LaunchTemplateName': launch_template_id,
                'Version': '21'  # Specify the version of the launch template
            },
            MinCount=1,
            MaxCount=1
        )
    
        # Get the instance ID
        instance_id = response['Instances'][0]['InstanceId']
        
        # Create a CloudWatch Events client
        client = boto3.client('events', region_name=aws_region)  # Replace 'us-east-1' with your desired region
        
        # Define the event rule details
        rule_name = f'{instance_id}-event'
        description = "-"
        state = "ENABLED"
        
        # Define the execution role (IAM role) ARN
        role_arn = "arn:aws:iam::619903709069:role/cloudwatchevents"  # Replace with your IAM role ARN
        #arn:aws:iam::619903709069:role/service-role/EventBridgeThingRole
        
        # Define the Lambda function ARN and payload
        lambda_arn = "arn:aws:lambda:us-east-1:619903709069:function:ec2MakeTerminate"
        payload = f'{{ "body": {{"instance_id": "{instance_id}"}} }}'
        
        
        # Calculate the time 15 minutes from now in UTC
        scheduled_time = datetime.utcnow() + timedelta(minutes=15)
        schedule_expression = f"cron({scheduled_time.minute} {scheduled_time.hour} {scheduled_time.day} {scheduled_time.month} ? {scheduled_time.year})"
        
        # Create the rule
        response = client.put_rule(
           Name=rule_name,
           Description=description,
           ScheduleExpression=schedule_expression,
           State=state,
           RoleArn=role_arn
        )
        
        # Add a target to the rule
        client.put_targets(
           Rule=rule_name,
           Targets=[
               {
                   'Id': '1',
                   'Arn': lambda_arn,
                   'Input': payload
               }
           ]
        )
        
        # Enable the rule
        client.enable_rule(Name=rule_name)
        
        print(f"Event rule '{rule_name}' created and enabled to trigger in 15 minutes.")
        
        # Wait for the instance to become running
        ec2_client.get_waiter('instance_running').wait(InstanceIds=[instance_id])
        response2 = ec2_client.describe_instances(InstanceIds=[instance_id])
        print('vooby2',response2['Reservations'][0]['Instances'][0]['State'])
        print('dooby2',response2['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['Association']['PublicIp'])
        public_ip = response2['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['Association']['PublicIp']
            
        
        print('foog',public_ip)
        return {
            'statusCode': 200,
            'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'
                },
            'body': json.dumps({'public_ip':public_ip,'instance_id':instance_id})
        }
