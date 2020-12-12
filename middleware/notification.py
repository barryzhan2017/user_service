import boto3
import os
import json

# Create an SNS client
sns = boto3.client('sns')

filters = {
    "/api/registration": {
        "method": ["POST"],
        "status": 201,
        "topic": os.environ['SNS_ARN']
    }
}


# Notify the sns client if it can pass the filter
def notify(inputs, response):
    filter = filters.get(inputs["path"], None)
    print(response.status_code)
    user = json.loads(response.data.decode("utf-8"))["data"][0]
    # Successful request will notify vai sns
    if filter is not None and response.status_code == filter["status"]:
        if inputs["method"] in filter["method"]:
            event = {
                "resource": inputs["path"],
                "method": inputs["method"],
                "data": {"user_id": user["user_id"], "username": user["username"], "email": user["email"]}
            }
            print(event)
            message = json.dumps(event, default=str)
            response = sns.publish(
                TopicArn=filter["topic"],
                Message=message,
            )
            print(response)
