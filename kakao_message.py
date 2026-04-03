import requests
import json

# ============ 설정 정보 ============
REST_API_KEY = "e9e1ecb6bd42784f1b2b9bf3dcad3dea"
REDIRECT_URI = "https://example.com/oauth"
AUTH_CODE = "2FWsFNPGXS835gPvD1kJ-EnJN17LylHEUZejLJxwKKh09j3zvHRhtgAAAAQKFxDvAAABnU4AtmK37mS5Kc-sjw"
CLIENT_SECRET = "WyLqbd7pmgx1UXpVWiW2tm6iZk7KiXze"

# ============ Step 1: 액세스 토큰 발급 받기 ============
print("🔑 액세스 토큰을 발급받는 중...")

token_url = "https://kauth.kakao.com/oauth/token"
token_params = {
    "grant_type": "authorization_code",
    "client_id": REST_API_KEY,
    "redirect_uri": REDIRECT_URI,
    "code": AUTH_CODE,
    "client_secret": CLIENT_SECRET
}

token_response = requests.post(token_url, data=token_params)

if token_response.status_code == 200:
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    print(f"✅ 토큰 발급 성공!")
    print(f"   Access Token: {access_token[:50]}...")
    print(f"   Refresh Token: {refresh_token[:50]}...")
else:
    print(f"❌ 토큰 발급 실패: {token_response.text}")
    exit(1)

# ============ Step 2: 나에게 메시지 보내기 ============
print("\n💬 나에게 메시지를 보내는 중...")

message_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

message_template = {
    "object_type": "text",
    "text": "🎉 카카오톡 API 테스트입니다!\n\n이 메시지는 Python으로 자동 발송되었습니다.",
    "link": {
        "web_url": "https://example.com"
    }
}

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/x-www-form-urlencoded"
}

message_data = {
    "template_object": json.dumps(message_template)
}

message_response = requests.post(message_url, headers=headers, data=message_data)

if message_response.status_code == 200:
    result = message_response.json()
    print(f"✅ 메시지 발송 성공!")
    print(f"   Response: {result}")
else:
    print(f"❌ 메시지 발송 실패: {message_response.text}")
    exit(1)

print("\n🎯 완료! 카카오톡 '나에게 보내기'에서 메시지를 확인해보세요.")
