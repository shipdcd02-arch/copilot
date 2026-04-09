# FASOO SDK가 제공된 경우 (예시 구조 — 실제 API는 SDK마다 다름)
import ctypes

fasoo_dll = ctypes.CDLL("FasooSDK.dll")  # Windows 기준

# 파일 암호화
result = fasoo_dll.FasooEncryptFile(
    b"input_file.xlsx",
    b"output_file.xlsx",
    b"policy_id"
)
