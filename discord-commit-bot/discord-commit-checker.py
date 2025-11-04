import json
import boto3
import os
from urllib import request, parse
from datetime import datetime, timezone, timedelta

s3 = boto3.client('s3')
BUCKET = os.environ['S3_BUCKET']
KEY = 'my_key.json'
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK_URL']
GITHUB_USERNAME = os.environ['GITHUB_USERNAME']

def lambda_handler(event, context):
    """
    EventBridge에서 호출됨 (12시, 22시, 23:59)
    """
    # 현재 시간 (한국 시간)
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    current_hour = now.hour
    
    # 오늘 커밋 상태 확인
    status = get_today_status()
    committed = status['users'].get(GITHUB_USERNAME, False)
    
    # 시간대별 메시지 생성
    if current_hour == 12:
        if committed:
            message = f"✅ {GITHUB_USERNAME}님이 이미 커밋을 완료했습니다! 👏"
        else:
            message = f"⏰ {GITHUB_USERNAME}님, 오늘 TIL 커밋 잊지 마세요!"
    
    elif current_hour == 22:
        if committed:
            message = f"✅ {GITHUB_USERNAME}님이 커밋을 완료했습니다. 내일도 스터디를 진행해주세요~ 🔥"
        else:
            message = f"⚠️ {GITHUB_USERNAME}님이 커밋을 아직 하지 않았습니다. 빨리 commit 하세요! ⏳"
    
    else:  # 23:59
        if committed:
            message = f"🎉 {GITHUB_USERNAME}님 오늘도 완료! 내일도 화이팅!"
        else:
            message = f"🚨 {GITHUB_USERNAME}님! 마지막 기회! 자기 전에 커밋하세요! 🏃‍♂️"
    
    # 디스코드로 전송
    send_discord_message(message)
    
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Success'})
    }

def get_today_status():
    """S3에서 오늘 상태 가져오기"""
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=KEY)
        data = json.loads(obj['Body'].read())
        
        # 날짜가 바뀌었으면 초기화
        kst = timezone(timedelta(hours=9))
        today = str(datetime.now(kst).date())
        
        if data.get('date') != today:
            return reset_status()
        return data
    except s3.exceptions.NoSuchKey:
        return reset_status()

def reset_status():
    """상태 초기화"""
    kst = timezone(timedelta(hours=9))
    today = str(datetime.now(kst).date())
    
    data = {
        'date': today,
        'users': {
            GITHUB_USERNAME: False
        }
    }
    s3.put_object(
        Bucket=BUCKET, 
        Key=KEY, 
        Body=json.dumps(data, ensure_ascii=False)
    )
    return data

def send_discord_message(message):
    """디스코드 웹훅으로 메시지 전송"""
    if not DISCORD_WEBHOOK:
        print("Discord webhook URL not set")
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
            print(f"Discord response body: {response.read().decode('utf-8')}")
            return response.status == 204
    except Exception as e:
        print(f"Discord send error: {e}")
        import traceback
        print(traceback.format_exc())
        return False
