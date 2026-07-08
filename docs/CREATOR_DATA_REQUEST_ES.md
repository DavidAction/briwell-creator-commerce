# Creator Data Request Templates (creator_provided lane)

Outreach copy for asking a creator to share their own stats and recent posts —
the legal, consent-based inflow lane (`creator_provided`, source risk `low`).
Pairs with the two CSV templates in
`work/briwell_dashboard_app/templates/creator_provided_{profile,posts}_template.csv`
and the 후보 인테이크 → 크리에이터 제공 데이터 panel in the dashboard.

**운영 원칙 (비협상 제약과 동일):** 이 메시지는 운영자가 **수동으로** 보낸다
(자동 발송 금지). 크리에이터가 회신으로 보낸 데이터만 `creator_provided`로
등록하며, 업로드 전에 운영자가 `consent_ref`(동의가 담긴 메시지의 참조 —
DM 링크·이메일 제목·날짜 등)와 `provided_at`(수신 시각, ISO 8601)을 채운다.
이 두 컬럼이 비어 있으면 대시보드가 정규화를 거부한다(fail-closed).

## DM version (short — Instagram/TikTok)

> Hola {nombre} 👋 Somos el equipo de Creator Partnerships de **Briwell**
> (K-Beauty coreana para Latinoamérica). Nos encantó tu contenido y queremos
> evaluar una colaboración pagada contigo.
>
> Para hacerlo con datos reales — y solo con tu permiso — ¿podrías
> compartirnos tus estadísticas (seguidores, vistas promedio, engagement) y
> tus últimas 20 publicaciones? Te podemos enviar dos plantillas sencillas
> para llenar, o si ya tienes un media kit o un export de analytics, también
> nos sirve tal cual.
>
> Al enviarnos esta información nos autorizas a usarla **únicamente para
> evaluar esta colaboración**. No la compartimos con terceros y la eliminamos
> si nos lo pides. ¡Gracias! ✨

## Email version (with templates attached)

Asunto: Colaboración K-Beauty con Briwell — solicitud de media kit

> Hola {nombre},
>
> Somos el equipo de Creator Partnerships de Briwell, una marca de cosmética
> coreana (K-Beauty) que está lanzando en México, Perú y Ecuador. Seguimos tu
> contenido de skincare y creemos que encaja muy bien con nuestra línea de
> {categoría — p. ej. protector solar}.
>
> Para evaluar una colaboración pagada trabajamos solo con datos que cada
> creador nos comparte directamente. ¿Podrías enviarnos:
>
> 1. **Tu perfil** — completa `creator_provided_profile_template.csv`
>    (país, usuario, seguidores, vistas promedio, engagement).
> 2. **Tus últimas 20 publicaciones** — completa
>    `creator_provided_posts_template.csv` (URL, vistas, likes, comentarios;
>    las columnas que no tengas pueden quedar vacías).
>
> Si ya tienes un media kit o un export de analytics (TikTok/Instagram),
> puedes enviarlo tal cual y nosotros lo pasamos al formato.
>
> **Sobre tus datos:** al enviarlos nos autorizas a usarlos únicamente para
> evaluar esta colaboración. No los compartimos con terceros y los eliminamos
> si nos lo solicitas.
>
> Un saludo,
> {운영자 이름} — Briwell Creator Partnerships

## Operator checklist (업로드 전)

1. 크리에이터의 회신(데이터 첨부)이 있는 메시지를 확인하고 그 참조를
   `consent_ref`에 기입 — 예: `ig-dm-2026-07-08-@handle`, `email-2026-07-08-@handle`.
2. 수신 시각을 `provided_at`에 ISO 8601로 기입 — 예: `2026-07-08T15:00:00Z`.
3. 대시보드 → 후보 인테이크 → **크리에이터 제공 데이터** 패널에서 두 CSV 업로드
   → 미리보기(동의 검증) → 정규화 실행 → 기존 크리에이터/영상 등록 버튼으로 DB 반영.
4. 크리에이터가 미디어킷/스크린샷으로 보낸 경우: 운영자가 템플릿에 옮겨 적고
   원본 파일 참조를 `consent_ref`에 남긴다.
