import json
import boto3
import os
from urllib import request
from datetime import datetime, timezone, timedelta

s3 = boto3.client('s3')
BUCKET = os.environ.get('S3_BUCKET', '')
KEY = 'my-key.json'
DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_URL', '')
GITHUB_USERNAME = os.environ.get('GITHUB_USERNAME', '')

def lambda_handler(event, context):
    print("=== Lambda function started ===")
    print(f"Full event: {json.dumps(event)}")
    print(f"Environment - Username: {GITHUB_USERNAME}")
    print(f"Environment - Webhook exists: {bool(DISCORD_WEBHOOK)}")
    
    try:
        if 'body' in event:
            print("Body found in event")
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            print("No body, using event directly")
            body = event
        
        print(f"Parsed body: {json.dumps(body)}")
        
        user = body.get('user')
        repo = body.get('repo', '')
        commit_sha = body.get('commit_sha', '')[:7]
        
        print(f"Extracted - User: {user}, Repo: {repo}, SHA: {commit_sha}")
        
        if user != GITHUB_USERNAME:
            print(f"User mismatch: {user} != {GITHUB_USERNAME}")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Not target user'})
            }
        
        print("User matched! Processing commit...")
        
        status = get_today_status()
        print(f"Current status: {status}")
        
        if status['users'].get(user, False):
            print("Already committed today")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Already committed today'})
            }
        
        status['users'][user] = True
        status['commit_time'] = datetime.now(timezone(timedelta(hours=9))).isoformat()
        
        try:
            s3.put_object(
                Bucket=BUCKET, 
                Key=KEY, 
                Body=json.dumps(status, ensure_ascii=False)
            )
            print(f"S3 updated successfully: {status}")
        except Exception as e:
            print(f"S3 write error: {e}")
        
        message = f"🎯 {user}님 커밋 완료! (`{commit_sha}`) 오늘도 수고하셨습니다! 💪"
        print(f"Sending message: {message}")
        
        result = send_discord_message(message)
        print(f"Discord send result: {result}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Commit recorded', 'discord_sent': result})
        }
        
    except Exception as e:
        print(f"ERROR occurred: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_today_status():
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=KEY)
        data = json.loads(obj['Body'].read())
        
        kst = timezone(timedelta(hours=9))
        today = str(datetime.now(kst).date())
        
        if data.get('date') != today:
            print("Date changed, resetting")
            return reset_status()
        return data
    except Exception as e:
        print(f"S3 read error: {e}")
        return reset_status()

def reset_status():
    kst = timezone(timedelta(hours=9))
    today = str(datetime.now(kst).date())
    
    data = {
        'date': today,
        'users': {
            GITHUB_USERNAME: False
        }
    }
    print(f"Status reset to: {data}")
    return data

def send_discord_message(message):
    if not DISCORD_WEBHOOK:
        print("ERROR: Discord webhook URL not set")
        return False
    
    payload = {
        "content": message,
        "username": "TIL Commit Bot"
    }
    
    data = json.dumps(payload).encode('utf-8')
    
    req = request.Request(
        DISCORD_WEBHOOK,
        data=data,
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'DiscordBot (TIL-Commit-Bot, 1.0)'
        }
    )
    
    try:
        with request.urlopen(req, timeout=10) as response:
            print(f"Discord response status: {response.status}")
            return response.status == 204 or response.status == 200
    except Exception as e:
        print(f"Discord send error: {e}")
        import traceback
        print(traceback.format_exc())
        return False
