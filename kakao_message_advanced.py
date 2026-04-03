import requests
import json
import os
from datetime import datetime

# ============ 설정 정보 ============
REST_API_KEY = "e9e1ecb6bd42784f1b2b9bf3dcad3dea"
REDIRECT_URI = "https://example.com/oauth"
AUTH_CODE = "2FWsFNPGXS835gPvD1kJ-EnJN17LylHEUZejLJxwKKh09j3zvHRhtgAAAAQKFxDvAAABnU4AtmK37mS5Kc-sjw"
CLIENT_SECRET = "WyLqbd7pmgx1UXpVWiW2tm6iZk7KiXze"

TOKEN_FILE = "kakao_token.json"

def save_token(token_data):
    """토큰을 파일에 저장"""
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f, indent=2, ensure_ascii=False)
    print(f"✅ 토큰이 {TOKEN_FILE}에 저장되었습니다")

def load_token():
    """파일에서 토큰 불러오기"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return None

def get_access_token(refresh=False):
    """액세스 토큰 발급 또는 갱신"""
    token_data = load_token()

    # 저장된 토큰이 있고, 갱신 요청이 아니면 재사용
    if token_data and not refresh:
        print("✅ 저장된 토큰을 사용합니다")
        return token_data['access_token']

    print("🔑 새로운 액세스 토큰을 발급받는 중...")

    token_url = "https://kauth.kakao.com/oauth/token"

    if token_data and refresh:
        # 리프레시 토큰으로 갱신
        params = {
            "grant_type": "refresh_token",
            "client_id": REST_API_KEY,
            "refresh_token": token_data['refresh_token']
        }
    else:
        # 인증 코드로 새로 발급
        params = {
            "grant_type": "authorization_code",
            "client_id": REST_API_KEY,
            "redirect_uri": REDIRECT_URI,
            "code": AUTH_CODE,
            "client_secret": CLIENT_SECRET
        }

    try:
        response = requests.post(token_url, data=params)
        response.raise_for_status()

        token_data = response.json()
        token_data['issued_at'] = datetime.now().isoformat()

        save_token(token_data)
        print(f"✅ 토큰 발급 성공!")
        return token_data['access_token']

    except requests.exceptions.RequestException as e:
        print(f"❌ 토큰 발급 실패: {e}")
        return None

def send_message(message_text, message_type="text", extra_data=None):
    """카카오톡 나에게 보내기 메시지 발송"""
    access_token = get_access_token()
    if not access_token:
        return False

    print(f"\n💬 메시지를 보내는 중...")

    message_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    # 메시지 템플릿 구성
    if message_type == "text":
        message_template = {
            "object_type": "text",
            "text": message_text,
            "link": {
                "web_url": "https://example.com"
            }
        }
    elif message_type == "feed":
        message_template = extra_data or {
            "object_type": "feed",
            "content": {
                "title": "제목",
                "description": message_text,
                "image_url": "https://example.com/image.jpg",
                "image_width": 800,
                "image_height": 800,
                "link": {
                    "web_url": "https://example.com"
                }
            }
        }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "template_object": json.dumps(message_template)
    }

    try:
        response = requests.post(message_url, headers=headers, data=data)
        response.raise_for_status()

        print(f"✅ 메시지 발송 성공!")
        print(f"   응답: {response.json()}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ 메시지 발송 실패: {e}")
        return False

# ============ 메인 함수 ============
def main():
    print("=" * 50)
    print("카카오톡 나에게 보내기 - 자동화 도구")
    print("=" * 50)

    # 예제 1: 간단한 텍스트 메시지
    send_message("🎉 카카오톡 API 테스트입니다!\n\n이 메시지는 Python으로 자동 발송되었습니다.")

    # 예제 2: 시간이 포함된 메시지
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_message(f"⏰ 현재 시간: {current_time}\n\n자동 알림 테스트입니다.")

    # 예제 3: 피드 메시지 (이미지와 버튼 포함)
    feed_data = {
        "object_type": "feed",
        "content": {
            "title": "카카오 개발자 가이드",
            "description": "Python으로 카카오톡 메시지를 자동으로 보내보세요!",
            "image_url": "https://www.kakaocorp.com/page/favicon/kakao_256x256.png",
            "image_width": 256,
            "image_height": 256,
            "link": {
                "web_url": "https://developers.kakao.com"
            }
        },
        "buttons": [
            {
                "title": "카카오 개발자 문서",
                "link": {
                    "web_url": "https://developers.kakao.com/docs"
                }
            },
            {
                "title": "내 애플리케이션",
                "link": {
                    "web_url": "https://developers.kakao.com/console/app"
                }
            }
        ]
    }
    send_message("카카오톡 메시지 API 안내", message_type="feed", extra_data=feed_data)

    print("\n" + "=" * 50)
    print("🎯 모든 메시지가 '나에게 보내기'에서 확인됩니다!")
    print("=" * 50)

if __name__ == "__main__":
    main()
