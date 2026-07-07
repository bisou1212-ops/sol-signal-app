# SOL 선물 매매 신호 앱 (Bitget SOLUSDT Perpetual)

## 구조
```
sol_signal_app/
├── app/
│   ├── main.py          # FastAPI 진입점
│   ├── config.py        # 전역 설정
│   ├── core/            # 공통 유틸/타입
│   ├── api/             # 거래소 API 클라이언트 (Bitget)
│   ├── data/            # 캔들/시세 수집
│   ├── indicators/      # 지표 계산 (EMA, RSI, ATR 등)
│   ├── strategy/        # 5개 독립 전략 모듈
│   ├── scoring/         # 전략 점수화/종합 엔진
│   ├── signals/         # 최종 신호 생성 로직
│   ├── backtest/        # 백테스트 엔진
│   └── ui/              # 한국어 UI (신호 화면)
├── requirements.txt
└── .env.example
```

## 개발 단계
1. 프로젝트 구조 ✅ (완료)
2. Bitget API
3. 데이터 수집
4. 지표 엔진
5. 전략 엔진
6. 점수 엔진
7. 신호 생성
8. 백테스트
9. UI
10. 최적화

`진행` 입력 시 다음 단계 코드만 생성됩니다.
