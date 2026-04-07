import qrcode
import cv2
import numpy as np
import time
import random
import string

def generate_long_text(length=2000):
    """
    테스트를 위한 긴 텍스트 생성 (한글/영문 혼합 가능)
    실제 사용 시에는 이 함수 대신 보낼 데이터를 넣으세요.
    """
    letters = string.ascii_letters + string.digits + " "
    # 2000자 생성
    return ''.join(random.choice(letters) for _ in range(length))

def main():
    # 1. 기본 설정
    window_name = "QR Auto Sequence"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    display_size = (800, 800)  # 화면에 표시될 고정 크기 (픽셀)
    
    print(f"시퀀스 시작... 창 크기: {display_size}")
    print("종료하려면 이미지 창을 클릭한 후 'q'를 누르세요.")

    count = 1
    try:
        while True:
            # 2. 데이터 준비 (여기에서 실제 전송할 데이터를 교체하세요)
            raw_data = f"No.{count} | " + generate_long_text(2000)
            
            # 3. QR 코드 객체 생성
            # version=None으로 두면 데이터 양에 따라 QR 크기가 자동 조절됩니다.
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L, # 점 개수 최소화 (인식률 향상)
                box_size=10,
                border=2,
            )
            qr.add_data(raw_data)
            qr.make(fit=True)

            # 4. QR 이미지를 PIL에서 넘파이(OpenCV) 배열로 변환
            img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            frame = cv2.cvtColor(np.array(img_qr), cv2.COLOR_RGB2BGR)

            # 5. 🔥 크기 강제 고정 및 선명도 최적화
            # INTER_NEAREST를 써야 픽셀이 뭉개지지 않아 휴대폰이 잘 읽습니다.
            frame_resized = cv2.resize(frame, display_size, interpolation=cv2.INTER_NEAREST)

            # 6. 화면 출력 및 정보 표시
            # 현재 몇 번째 QR인지 상단에 표시 (선택 사항)
            cv2.putText(frame_resized, f"QR Sequence: {count}", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            cv2.imshow(window_name, frame_resized)

            # 데이터 출력(콘솔)
            print(f"[{count}] 2000자 QR 발행 중...")

            # 7. 대기 시간 조절 (500ms = 0.5초)
            # 사용 중인 앱의 인식 속도에 따라 500~1000 사이로 조절하세요.
            if cv2.waitKey(500) & 0xFF == ord('q'):
                break
            
            count += 1

    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        cv2.destroyAllWindows()
        print("프로그램이 종료되었습니다.")

if __name__ == "__main__":
    main()