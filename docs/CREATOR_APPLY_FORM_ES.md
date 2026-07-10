# Formulario de aplicación — Programa de Creadores (ES)

랜딩(work/briwell_landing_page/index.html)의 CTA "Aplicar al programa"에 연결할 지원 폼 스펙.
Tally 또는 Google Forms에 아래 문항을 그대로 붙여 넣으면 됩니다 (제작 ~10분).
응답은 기존 creator_provided 인테이크 CSV로 그대로 매핑되도록 설계했습니다
(work/briwell_dashboard_app/templates/creator_provided_profile_template.csv).

## 폼 헤더 (ES)

> **Programa de Creadores Briwell**
> Cuéntanos quién eres. Toma 3 minutos y no te compromete a nada.
> Revisamos cada aplicación de forma personal — nada de respuestas automáticas.

## 문항 (순서대로)

| # | 질문 (ES) | 타입 | 필수 | → CSV 컬럼 |
|---|---|---|---|---|
| 1 | ¿Cómo te llamas (o tu nombre de creadora/creador)? | 짧은 텍스트 | ✔ | display_name |
| 2 | ¿Desde qué país creas? | 선택: México / Perú / Ecuador / Otro país | ✔ | country (MX/PE/EC) |
| 3 | ¿Cuál es tu plataforma principal? | 선택: TikTok / Instagram / YouTube / Otra | ✔ | (profile_url 판별용) |
| 4 | Tu usuario en esa plataforma (ej. @tu.usuario) | 짧은 텍스트 | ✔ | username |
| 5 | Enlace a tu perfil | URL | ✔ | profile_url |
| 6 | ¿Sobre qué creas contenido? | 체크박스: Skincare / Maquillaje / Bienestar / Moda / Otro | ✔ | product_category, signals |
| 7 | ¿Cuántos seguidores tienes aprox.? | 선택: <10 mil / 10–50 mil / 50–200 mil / +200 mil / Prefiero no decir | — | follower_count(근사) |
| 8 | ¿Cómo prefieres que te contactemos? (correo o WhatsApp) | 짧은 텍스트 | ✔ | (아웃리치 연락처; CSV 외 보관) |
| 9 | ¿Por qué te interesa la K-beauty? (opcional) | 긴 텍스트 | — | bio |

## 동의 문항 (필수 체크박스 2개 — 이 문구 그대로)

- [ ] **Autorizo a Briwell a revisar mi contenido público y a guardar los datos de este
  formulario para evaluar una posible colaboración.** (필수)
- [ ] **Acepto que Briwell me contacte por el medio que indiqué.** (필수)

마지막에 안내문 한 줄:

> Tus datos se usan solo para evaluar la colaboración. Puedes pedir que los borremos
> cuando quieras escribiéndonos.

## 운영 흐름 (KO — 응답 → 인테이크)

1. 폼 응답을 CSV로 내보내 `creator_provided_profile_template.csv` 컬럼으로 옮긴다.
2. `consent_ref` = `apply-form-<응답ID 또는 타임스탬프>-<username>` — 폼 응답 자체가 동의 증빙.
   동의 체크 2개가 모두 없으면 인테이크가 fail-closed로 거부하므로 그대로 두면 된다.
3. `provided_at` = 폼 제출 시각(ISO 8601).
4. 대시보드 Talent Intake → creator_provided 업로드 → 기존 품질 게이트/스크리닝을 그대로 탄다.

## 남은 결정 (David)

- Tally vs Google Forms (추천: **Tally** — 무료 티어에서 로고/스페인어 UI가 더 깔끔, 응답 CSV 내보내기 지원).
- 폼 생성 후 URL을 `work/briwell_landing_page/index.html`의 `href="#aplicar"` 두 곳에 연결.
