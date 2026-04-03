# 카카오톡 API 자동 메시지 전송

이 프로젝트는 **Python**을 사용하여 카카오톡의 **나에게 보내기** 기능을 자동화합니다.

## 📦 파일 구성

| 파일 | 설명 |
|------|------|
| `kakao_message.py` | 기본 버전 - 간단한 텍스트 메시지 발송 |
| `kakao_message_advanced.py` | 고급 버전 - 토큰 저장, 피드 메시지, 버튼 포함 |
| `카카오톡_API_사용법.md` | 상세 가이드 및 커스터마이징 방법 |
| `README.md` | 이 파일 |

## 🚀 빠른 시작 (3단계)

### 1️⃣ 라이브러리 설치
```bash
pip install requests
```

### 2️⃣ 코드 실행
```bash
# 기본 버전
python kakao_message.py

# 또는 고급 버전 (토큰 저장 기능 포함)
python kakao_message_advanced.py
```

### 3️⃣ 확인
카카오톡 앱을 열어서 **나에게 보내기** 채팅방에서 메시지를 확인하세요!

---

## 🔑 API 정보

```
📌 REST API 키:
   e9e1ecb6bd42784f1b2b9bf3dcad3dea

📌 클라이언트 시크릿:
   WyLqbd7pmgx1UXpVWiW2tm6iZk7KiXze

📌 리다이렉트 URI:
   https://example.com/oauth
```

---

## 💡 사용 예제

### 기본: 텍스트 메시지
```python
python kakao_message.py
```

### 고급: 다양한 메시지 유형
```bash
python kakao_message_advanced.py
```

### 커스텀 메시지
`kakao_message.py` 파일을 열어서 아래 부분을 수정하세요:

```python
message_template = {
    "object_type": "text",
    "text": "여기에 원하는 메시지를 입력하세요!",  # 👈 수정
    "link": {
        "web_url": "https://example.com"  # 👈 링크 수정
    }
}
```

---

## ⏰ 자동 실행 설정

### Windows - 작업 스케줄러
1. `Win + R` → `taskschd.msc` 실행
2. **기본 작업 만들기**
3. **트리거**: 매일 원하는 시간에 실행
4. **작업**: `python C:\경로\kakao_message.py` 입력
5. **저장**

### Mac/Linux - 크론(Cron)
```bash
# 매일 오전 9시에 실행
0 9 * * * /usr/bin/python3 /path/to/kakao_message.py

# crontab에 추가
crontab -e
```

---

## 📊 메시지 유형

### 1. 텍스트 메시지 (기본)
```python
{
    "object_type": "text",
    "text": "메시지 내용",
    "link": {"web_url": "https://example.com"}
}
```

### 2. 피드 메시지 (이미지 + 설명)
```python
{
    "object_type": "feed",
    "content": {
        "title": "제목",
        "description": "설명",
        "image_url": "https://...",
        "link": {"web_url": "https://example.com"}
    }
}
```

### 3. 버튼 포함 메시지
```python
{
    "object_type": "feed",
    "content": {...},
    "buttons": [
        {"title": "버튼1", "link": {"web_url": "https://..."}},
        {"title": "버튼2", "link": {"web_url": "https://..."}}
    ]
}
```

---

## ❓ FAQ

**Q: 실행 시 오류가 나요**
- `pip install requests` 명령어를 다시 실행해보세요
- Python이 설치되어 있는지 확인하세요 (`python --version`)

**Q: 다른 사람에게도 메시지를 보낼 수 있나요?**
- 네! `친구 메시지 API`를 사용하면 됩니다
- 추가 권한 설정이 필요합니다 (카카오 개발자 콘솔에서)

**Q: 토큰이 만료되면?**
- 고급 버전(`kakao_message_advanced.py`)에서 자동 갱신됩니다
- 기본 버전은 새로운 인증이 필요합니다

**Q: 특정 시간마다 메시지를 보내려면?**
- 위의 **자동 실행 설정** 섹션을 참고하세요
- 또는 Python의 `schedule` 라이브러리를 사용할 수 있습니다

---

## 📚 추가 자료

- 🔗 [카카오 개발자 공식 문서](https://developers.kakao.com/docs)
- 🔗 [메시지 API 레퍼런스](https://developers.kakao.com/docs/latest/ko/message/rest-api)
- 🔗 [내 애플리케이션 관리](https://developers.kakao.com/console/app)

---

## 📝 라이선스

자유롭게 사용하고 수정할 수 있습니다.

---

**🎉 즐겁게 사용하세요!**
