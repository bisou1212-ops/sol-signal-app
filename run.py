"""Pydroid3 등에서 ▶ 버튼으로 바로 실행하기 위한 스크립트
(터미널 명령 없이 이 파일만 실행하면 서버가 켜집니다)
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
