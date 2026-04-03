# 카카오톡 나에게 보내기 Python 자동화 가이드

## 📋 발급받은 API 정보

```
REST API 키: e9e1ecb6bd42784f1b2b9bf3dcad3dea
Redirect URI: https://example.com/oauth
클라이언트 시크릿: WyLqbd7pmgx1UXpVWiW2tm6iZk7KiXze
인증 코드: 2FWsFNPGXS835gPvD1kJ-EnJN17LylHEUZejLJxwKKh09j3zvHRhtgAAAAQKFxDvAAABnU4AtmK37mS5Kc-sjw
```

## 🚀 실행 방법

### 1단계: 필수 라이브러리 설치
```bash
pip install requests
```

### 2단계: Python 스크립트 실행
```bash
python kakao_message.py
```

### 3단계: 결과 확인
- 카카오톡 앱의 **나에게 보내기** 채팅방을 확인하세요
- 메시지가 자동으로 발송됩니다

---

## 📝 코드 커스터마이징 방법

### 메시지 내용 변경하기

`kakao_message.py` 파일에서 아래 부분을 수정하세요:

```python
message_template = {
    "object_type": "text",
    "text": "여기에 보내고 싶은 메시지를 쓰세요!",  # 👈 이 부분을 수정
    "link": {
        "web_url": "https://example.com"  # 👈 링크도 수정 가능
    }
}
```

### 버튼이 있는 메시지 보내기

```python
message_template = {
    "object_type": "feed",
    "content": {
        "title": "제목입니다",
        "description": "설명입니다",
        "image_url": "https://example.com/image.jpg",
        "image_width": 800,
        "image_height": 800,
        "link": {
            "web_url": "https://example.com"
        }
    },
    "buttons": [
        {
            "title": "버튼1",
            "link": {
                "web_url": "https://example.com/1"
            }
        },
        {
            "title": "버튼2",
            "link": {
                "web_url": "https://example.com/2"
            }
        }
    ]
}
```

---

## ⚙️ 자동 실행 설정 (Windows 작업 스케줄러)

매일 특정 시간에 자동으로 메시지를 보내고 싶으면:

1. **Windows 작업 스케줄러** 열기
2. **기본 작업 만들기** 클릭
3. **트리거** 설정: 매일 특정 시간
4. **작업** 설정: `python C:\경로\kakao_message.py` 실행

---

## 🔄 토큰 갱신하기

액세스 토큰은 시간이 지나면 만료됩니다. 다음과 같이 갱신할 수 있습니다:

```python
import requests

REST_API_KEY = "e9e1ecb6bd42784f1b2b9bf3dcad3dea"
REFRESH_TOKEN = "발급받은 리프레시 토큰"

token_url = "https://kauth.kakao.com/oauth/token"
token_params = {
    "grant_type": "refresh_token",
    "client_id": REST_API_KEY,
    "refresh_token": REFRESH_TOKEN
}

response = requests.post(token_url, data=token_params)
new_access_token = response.json().get("access_token")
```

---

## ❓ 자주 묻는 질문

**Q: 메시지가 안 보내져요**
- REST API 키와 토큰이 정확한지 확인하세요
- 카카오톡 앱이 설치되어 있는지 확인하세요
- 나에게 보내기 채팅방을 먼저 만들어야 합니다

**Q: 다른 사람에게도 메시지를 보낼 수 있나요?**
- 네! `https://kapi.kakao.com/v2/api/talk/friends/message/default/send` 엔드포인트를 사용하면 됩니다
- 대신 친구 목록 조회 권한이 필요합니다

**Q: 사진이나 동영상도 보낼 수 있나요?**
- 네! 위의 "버튼이 있는 메시지" 예제를 참고하세요
- `image_url`에 이미지 링크를 넣으면 됩니다

---

## 📚 참고 자료

- [카카오 개발자 문서](https://developers.kakao.com/docs)
- [메시지 API](https://developers.kakao.com/docs/latest/ko/message/rest-api)
- [나의 애플리케이션](https://developers.kakao.com/console/app)
