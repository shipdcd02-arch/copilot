import requests
import json
import os

REST_API_KEY = "e9e1ecb6bd42784f1b2b9bf3dcad3dea"
CLIENT_SECRET = "WyLqbd7pmgx1UXpVWiW2tm6iZk7KiXze"
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "kakao_token.json")

# ✅ 보낼 메시지를 여기서 수정하세요!
MESSAGE = "안녕! Python으로 보낸 카카오톡 메시지야2 🎉"


def get_access_token():
    with open(TOKEN_FILE) as f:
        saved = json.load(f)

    res = requests.post("https://kauth.kakao.com/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "client_secret": CLIENT_SECRET,
        "refresh_token": saved["refresh_token"],
    })

    if res.status_code != 200:
        print("❌ 토큰 갱신 실패:", res.text)
        return None

    data = res.json()
    saved["access_token"] = data["access_token"]
    if "refresh_token" in data:
        saved["refresh_token"] = data["refresh_token"]

    with open(TOKEN_FILE, "w") as f:
        json.dump(saved, f)

    return data["access_token"]


def send_message(message):
    access_token = get_access_token()
    if not access_token:
        return

    res = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps({
            "object_type": "text",
            "text": message,
            "link": {"web_url": "https://kakao.com"}
        })}
    )

    if res.status_code == 200:
        print("✅ 메시지 전송 성공! 카카오톡 '나에게 보내기'를 확인하세요.")
    else:
        print("❌ 메시지 전송 실패:", res.text)


send_message(MESSAGE)
