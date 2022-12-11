import json
import boto3
from retrying import retry
from hashlib import sha256

# import requests

endpoint = "https://a15ks10d68w3hk-ats.iot.us-east-1.amazonaws.com"


def get_s3_object(bucket, key):
    s3 = boto3.client("s3")
    m = sha256()

    with open("/tmp/s3obj", "wb") as f:
        s3.download_file(bucket, key, "/tmp/s3obj")

    with open("/tmp/s3obj", "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if len(chunk) == 0:
                break
            m.update(chunk)
        return m.hexdigest()


@retry(stop_max_attempt_number=2, wait_fixed=1000)
def _thing_shadow(iot_data, thing_name):
    try:
        return iot_data.get_thing_shadow(thingName=thing_name)
    except iot_data.exceptions.ResourceNotFoundException:
        return None


def lambda_handler(event, context):
    iot_data = boto3.client("iot-data", endpoint_url=endpoint)
    iot = boto3.client("iot")
    things = []
    next_token = ""
    while True:
        # list_things = iot.list_things(nextToken=next_token, maxResults=1) # for debug
        list_things = iot.list_things(nextToken=next_token)
        things.extend(list_things["things"])
        next_token = list_things.get("nextToken")
        if not next_token:
            break
    print(things)
    for thing in things:
        shadow = _thing_shadow(iot_data, thing["thingName"])
        if shadow:
            payload = shadow["payload"].read().decode("utf-8")
            print(f'{thing["thingName"]}, {json.loads(payload)}')

    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    digest = get_s3_object(bucket, key)
    print(digest)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "hello world",
                # "location": ip.text.replace("\n", "")
            }
        ),
    }


if __name__ == "__main__":
    print(lambda_handler({}, {}))
