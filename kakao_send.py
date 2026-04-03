import requests


KAKAO_ACCESS_TOKEN = "여기에_액세스_토큰_입력"

# 친구에게 보낼 경우: 카카오 친구 UUID (아래 get_friends()로 조회 가능)
RECEIVER_UUID = "여기에_수신자_UUID_입력"


def send_to_me(text: str) -> bool:
    """나에게 카카오톡 메시지 보내기"""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {KAKAO_ACCESS_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "template_object": f'{{"object_type":"text","text":"{text}","link":{{"web_url":"","mobile_web_url":""}}}}'
    }

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200 and response.json().get("result_code") == 0:
        print("✓ 나에게 보내기 성공")
        return True
    else:
        print(f"✗ 실패: {response.status_code} - {response.text}")
        return False


def send_to_friend(text: str, receiver_uuid: str = RECEIVER_UUID) -> bool:
    """특정 친구에게 카카오톡 메시지 보내기"""
    import json

    url = "https://kapi.kakao.com/v1/api/talk/friends/message/default/send"
    headers = {
        "Authorization": f"Bearer {KAKAO_ACCESS_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    template = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": "", "mobile_web_url": ""},
    }
    payload = {
        "receiver_uuids": json.dumps([receiver_uuid]),
        "template_object": json.dumps(template),
    }

    response = requests.post(url, headers=headers, data=payload)
    data = response.json()
    if response.status_code == 200 and data.get("successful_receiver_uuids"):
        print(f"✓ 전송 성공: {data['successful_receiver_uuids']}")
        return True
    else:
        print(f"✗ 실패: {response.status_code} - {response.text}")
        return False


def get_friends() -> list:
    """카카오 친구 목록 조회 (UUID 확인용)"""
    url = "https://kapi.kakao.com/v1/api/talk/friends"
    headers = {"Authorization": f"Bearer {KAKAO_ACCESS_TOKEN}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        friends = response.json().get("elements", [])
        for f in friends:
            print(f"이름: {f['profile_nickname']}, UUID: {f['uuid']}")
        return friends
    else:
        print(f"친구 목록 조회 실패: {response.status_code} - {response.text}")
        return []


if __name__ == "__main__":
    # 사용 예시
    send_to_me("테스트 메시지입니다.")
    # send_to_friend("테스트 메시지입니다.")
