# 배포 가이드 (Railway)

## 1. GitHub 저장소 생성 및 업로드
```bash
cd sol_signal_app
git init
git add .
git commit -m "SOL 선물 신호 앱 초기 배포"
```
GitHub에서 새 저장소(예: `sol-signal-app`) 생성 후:
```bash
git remote add origin https://github.com/<본인계정>/sol-signal-app.git
git branch -M main
git push -u origin main
```

## 2. Railway 배포
1. https://railway.app 접속 → GitHub으로 로그인
2. "New Project" → "Deploy from GitHub repo" → 방금 만든 저장소 선택
3. Settings → Variables 에서 필요 시 환경변수 추가 (선택, 공개 데이터만 쓰면 불필요):
   - BITGET_API_KEY
   - BITGET_API_SECRET
   - BITGET_PASSPHRASE
4. Deploy 완료 후 "Generate Domain" 클릭 → `xxxx.up.railway.app` 형태 URL 생성
5. 해당 URL을 휴대폰 브라우저에서 접속 → 대시보드 확인

## 3. 확인용 엔드포인트
- `/` : 신호 대시보드 (모바일 화면)
- `/health` : 서버 상태 확인
- `/signal` : 신호 JSON
- `/backtest` : 백테스트 결과 JSON

Procfile이 이미 포함되어 있어 Railway가 자동으로 `uvicorn app.main:app --host 0.0.0.0 --port $PORT` 로 실행합니다.
