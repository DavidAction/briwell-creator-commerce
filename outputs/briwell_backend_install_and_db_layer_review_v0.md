# Briwell Backend Install and DB Layer Review v0

작성일: 2026-06-17  
상태: FastAPI/Pydantic/Pytest 설치, API smoke test, DB connection layer, repository scaffold 완료

## 1. Install Result

가상환경 생성 위치:

```text
work/briwell_mvp_app/.venv
```

설치 완료 패키지:

1. fastapi 0.137.1
2. pydantic 2.13.4
3. pytest 9.1.0
4. uvicorn 0.49.0
5. psycopg 3.3.4
6. httpx 0.28.1
7. python-dotenv 1.2.2

초기 설치는 sandbox 네트워크 제한으로 실패했지만, 승인된 PyPI 접근으로 재시도하여 성공했다.

## 2. Review Fixes

기존 산출물 재검토 후 보완한 점:

1. Dashboard wireframe의 High Risk 표시 문구를 legacy quarantine/admin view로 한정
2. AI prompt에서 High Risk/not_allowed는 outreach recommendation이 아니라 rejected status로 처리하도록 명확화
3. API spec에서 High Risk/Not Allowed는 outreach record를 생성하지 않는다고 명시
4. keyword seed 재실행 import를 위해 `idx_keyword_seed_unique` unique index 추가

## 3. Implemented Next Step

새로 구현한 backend pieces:

1. `app/core/db.py`
   - PostgreSQL connection helper
   - `USE_DATABASE=false` 기본값
   - DB 비활성 시 안전한 placeholder mode

2. `app/repositories/products.py`
   - product list/create repository

3. `app/repositories/keywords.py`
   - keyword list repository

4. `app/repositories/creators.py`
   - creator list/import repository
   - eligible source risk only

5. Router DB integration
   - `/products`
   - `/keywords`
   - `/creators`
   - `/creators/import`

6. DB utility scripts
   - `scripts/apply_sql.py`
   - `scripts/import_keyword_seed.py`

7. API smoke tests
   - `/health`
   - `/products`
   - `/products` create validation
   - `/creators/import` High Risk rejection
   - `/creators/import` Medium Risk validation

## 4. Verification

Commands run:

```text
.venv\\Scripts\\python.exe -m pytest -v
.venv\\Scripts\\python.exe scripts\\validate_csv_imports.py
.venv\\Scripts\\python.exe -m compileall app scripts tests
uvicorn app.main:app --host 127.0.0.1 --port 8765
GET http://127.0.0.1:8765/health
```

Results:

1. Pytest: 16 passed
2. CSV validation: passed
3. Python compile: passed
4. Uvicorn smoke test: `/health` returned `status=ok`

## 5. Current Limitations

1. PostgreSQL server was not available in this environment, so DB-backed integration tests were not executed.
2. Routers use placeholder mode unless `USE_DATABASE=true`.
3. API auth/role middleware is still a next implementation step.
4. AI provider adapters are not implemented yet.

## 6. Recommended Next Step

Next build step:

1. Start local PostgreSQL
2. Set `USE_DATABASE=true`
3. Run `python scripts/apply_sql.py --with-seeds`
4. Run `python scripts/import_keyword_seed.py`
5. Add DB integration tests
6. Add auth/role middleware
7. Implement AnalysisJob worker and AI adapter interfaces
