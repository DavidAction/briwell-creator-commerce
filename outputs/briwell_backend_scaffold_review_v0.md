# Briwell Backend Scaffold Review v0

작성일: 2026-06-17  
상태: PRD/설계 산출물 재검토 후 FastAPI backend scaffold 생성 완료

## 1. Review Summary

기존 산출물을 다시 검토했고, 기능상 큰 구조 문제는 없었다. 다만 일부 문구가 High Risk 데이터를 화면/프롬프트/API에서 다룰 수 있는 것처럼 오해될 여지가 있어 명확히 수정했다.

수정 내용:

1. Dashboard wireframe에서 High Risk는 legacy import quarantine/admin view에만 표시된다고 명확화
2. AI prompt에서 High Risk/not_allowed는 outreach recommendation이 아니라 rejected status를 반환하도록 명확화
3. API spec에서 High Risk/Not Allowed creator는 outreach record 자체를 생성하지 않도록 명확화

## 2. Next Step Completed

다음 단계로 FastAPI backend scaffold를 생성했다.

생성 위치:

```text
work/briwell_mvp_app
```

전달용 zip:

```text
outputs/briwell_mvp_app_scaffold_v0.zip
```

## 3. Scaffold Contents

```text
app/
  main.py
  core/
    config.py
    policy.py
  routers/
    health.py
    creators.py
    keywords.py
    products.py
db/
  migrations/
    001_initial_schema.sql
  seeds/
    001_seed_data.sql
    keyword_seed_v0.csv
scripts/
  validate_csv_imports.py
tests/
  test_policy.py
  test_csv_validation.py
```

## 4. Implemented Guardrails

1. Allowed source risks: `low`, `low_medium`, `medium`
2. Blocked source risks: `high`, `not_allowed`
3. `low_medium` and `medium` require admin approval
4. do-not-contact creators cannot receive DM generation
5. removal-request creators cannot receive outreach
6. DM sent status requires claims check and do-not-contact check
7. CSV templates reject High Risk source risk values

## 5. Verification

Executed checks:

```text
python -m unittest discover -s tests -v
python scripts/validate_csv_imports.py
python -m compileall .
```

Results:

1. Unit tests: 11 passed
2. CSV validation: passed
3. Python syntax compilation: passed

Environment note:

FastAPI, Pydantic, and Pytest are not installed in the current local Python environment. The scaffold includes `requirements.txt`, but runtime API testing should be done after installing dependencies.

## 6. Files Updated

Updated output documents:

1. `briwell_dashboard_wireframes_v0.md`
2. `briwell_ai_prompts_v0.md`
3. `briwell_api_spec_v0.md`

Created scaffold package:

1. `briwell_mvp_app_scaffold_v0.zip`

## 7. Recommended Next Build Task

Next implementation step:

1. Install backend dependencies from `requirements.txt`
2. Run `uvicorn app.main:app --reload`
3. Add DB connection layer
4. Implement persistent `/products`, `/keywords`, `/creators/import`, `/creators`
5. Add migration runner or Alembic
6. Add integration tests for PostgreSQL constraints
