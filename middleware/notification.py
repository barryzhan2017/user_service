import boto3

# Create an SNS client
sns = boto3.client('sns')

filter = {
    "/api/registration": {
        "method": 
    }
}

def register():
    boto3.session