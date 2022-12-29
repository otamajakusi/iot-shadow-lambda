import json
import boto3
from retrying import retry
from hashlib import sha256

# import requests

iot_client = boto3.client("iot")
endpoint = iot_client.describe_endpoint(endpointType="iot:Data-ATS")
endpoint_url = f"https://{endpoint['endpointAddress']}"
iot_data_client = boto3.client("iot-data", endpoint_url=endpoint_url)


def _get_s3_object(bucket, key):
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


def _retry_if_throttling_exception(exception):
    return isinstance(exception, iot_data_client.exceptions.ThrottlingException)


@retry(
    stop_max_attempt_number=2,
    wait_fixed=1000,
    retry_on_exception=_retry_if_throttling_exception,
)
def _thing_shadow(iot_data, thing_name, bucket, key, digest):
    try:
        payload = {
            "state": {
                "desired": {
                    "file": {
                        "body": {
                            "url": f"s3://{bucket}/{key}",
                            "hash": digest,
                        }
                    }
                }
            }
        }
        iot_data.update_thing_shadow(thingName=thing_name, payload=json.dumps(payload))
    except iot_data.exceptions.ResourceNotFoundException:
        return None


def lambda_handler(event, context):
    things = []
    next_token = ""
    while True:
        list_things = iot_client.list_things(nextToken=next_token)
        things.extend(list_things["things"])
        next_token = list_things.get("nextToken")
        if not next_token:
            break

    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    digest = _get_s3_object(bucket, key)

    for thing in things:
        _thing_shadow(iot_data_client, thing["thingName"], bucket, key, digest)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--bucket", help="bucket name.", required=True)
    parser.add_argument("--key", help="key name.", required=True)
    args = parser.parse_args()
    lambda_handler(
        {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": args.bucket},
                        "object": {"key": args.key},
                    }
                }
            ]
        },
        {},
    )
