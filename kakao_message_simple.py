import requests
import json

# ============ API 정보 (카카오 개발자 콘솔에서 복사) ============
# 아래의 ACCESS_TOKEN은 나중에 카카오톡에서 받은 새로운 토큰으로 교체하세요

REST_API_KEY = "e9e1ecb6bd42784f1b2b9bf3dcad3dea"
REDIRECT_URI = "https://example.com/oauth"

def get_new_token():
    """새로운 액세스 토큰을 받기 위한 URL 생성"""
    auth_url = f"https://kauth.kakao.com/oauth/authorize?client_id={REST_API_KEY}&redirect_uri={REDIRECT_URI}&response_type=code&scope=talk_message"

    print("=" * 60)
    print("🔐 새로운 토큰을 받아야 합니다!")
    print("=" * 60)
    print("\n아래 URL을 브라우저에 복사해서 열어주세요:")
    print(f"\n{auth_url}\n")
    print("=" * 60)
    print("1. 카카오 로그인 후 허가 버튼을 클릭하세요")
    print("2. 리다이렉트된 주소에서 'code=' 뒤의 코드를 복사하세요")
    print("3. 아래에서 코드를 입력하세요")
    print("=" * 60)

    auth_code = input("\n인증 코드를 입력하세요: ").strip()

    return get_access_token_from_code(auth_code)

def get_access_token_from_code(auth_code):
    """인증 코드로 액세스 토큰 발급"""
    token_url = "https://kauth.kakao.com/oauth/token"

    params = {
        "grant_type": "authorization_code",
        "client_id": REST_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": auth_code,
    }

    try:
        response = requests.post(token_url, data=params)
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data.get("access_token")

        print(f"\n✅ 토큰 발급 성공!")
        print(f"ACCESS_TOKEN = '{access_token}'")
        print(f"\n위의 토큰을 이 파일의 ACCESS_TOKEN 변수에 복사 & 붙여넣기 하세요!")

        return access_token

    except requests.exceptions.RequestException as e:
        print(f"❌ 토큰 발급 실패: {e}")
        return None

def send_message_to_me(access_token, message_text):
    """나에게 메시지 보내기"""

    if not access_token:
        print("❌ 액세스 토큰이 없습니다!")
        return False

    print("\n" + "=" * 60)
    print("💬 나에게 메시지를 보내는 중...")
    print("=" * 60)

    # 나에게 보내기 API
    message_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    # 간단한 텍스트 메시지
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": message_text,
            "link": {
                "web_url": "https://www.kakao.com"
            }
        })
    }

    try:
        response = requests.post(message_url, headers=headers, data=data)

        if response.status_code == 200:
            print(f"✅ 메시지 발송 성공!")
            print(f"응답: {response.json()}")
            return True
        else:
            print(f"❌ 메시지 발송 실패!")
            print(f"상태 코드: {response.status_code}")
            print(f"응답: {response.text}")

            # 403 에러이면 토큰이 talk_message 권한을 가지고 있지 않다는 뜻
            if response.status_code == 403:
                print("\n💡 해결 방법:")
                print("   토큰을 다시 받을 때 다음 URL을 사용하세요:")
                auth_url = f"https://kauth.kakao.com/oauth/authorize?client_id={REST_API_KEY}&redirect_uri={REDIRECT_URI}&response_type=code&scope=talk_message"
                print(f"   {auth_url}")

            return False

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

# ============ 메인 실행 ============
if __name__ == "__main__":
    print("\n")
    print("█" * 60)
    print("█" + " " * 58 + "█")
    print("█" + "  카카오톡 나에게 보내기 - 자동화 도구".center(58) + "█")
    print("█" + " " * 58 + "█")
    print("█" * 60)

    # ===== 여기에 토큰을 붙여넣으세요! =====
    ACCESS_TOKEN = ""  # 👈 여기에 토큰을 붙여넣기
    # =====================================

    if not ACCESS_TOKEN:
        print("\n⚠️  아직 토큰을 설정하지 않았습니다.")
        ACCESS_TOKEN = get_new_token()

        if not ACCESS_TOKEN:
            print("❌ 토큰을 받지 못했습니다. 다시 시도해주세요.")
            exit(1)

    # 메시지 발송
    test_messages = [
        "🎉 카카오톡 API 테스트입니다!\n\n이 메시지는 Python으로 자동 발송되었습니다.",
        f"⏰ 현재 시간: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n자동 알림 테스트입니다.",
        "✅ 나에게 보내기가 정상 작동합니다!\n\n🎊 축하합니다! 카카오톡 API를 성공적으로 설정했습니다.",
    ]

    for i, message in enumerate(test_messages, 1):
        print(f"\n[메시지 {i}]")
        send_message_to_me(ACCESS_TOKEN, message)

        if i < len(test_messages):
            input("\nEnter를 눌러 다음 메시지를 보내세요...")

    print("\n" + "=" * 60)
    print("🎯 완료! 카카오톡 '나에게 보내기'에서 메시지를 확인해보세요!")
    print("=" * 60)
