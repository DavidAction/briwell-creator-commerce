# Briwell Landing (ES creator page + KO company page)

Concept C ("editorial hybrid") was approved by David on 2026-07-10 after a strategy
session and a 3-concept comparison. On 2026-07-11 David revealed the brand identity —
**Briwell = Bridge + Well** (Isaiah 12:3 "wells of salvation", Isaac's wells, living
water; one deep well filling other wells, Korea ↔ LATAM) — and both pages were rebuilt
in the identity-driven design system **"The Well"**: deep-well teal ink `#0C2E2F`,
living-water aqua (`#0E7C71` text / `#2FD0BC` decorative), sunlight gold `#D9A441`
(decorative only), stone paper `#F5F2EA`; circular "well-mouth" photo frames; concentric
ripple motifs; deep-ink sections; double-circle logo mark. Copy axis: ES "Que tu
contenido rebose." / "Sin tu permiso, ni una gota." · KO "깊은 우물 하나가 다른 우물들을
채웁니다." / "동의 없이는, 한 방울도." Scripture appears only in the KO brand-story
section; the ES page uses universal water language.

## Files

- `index.html` — **the ES creator landing, "The Well" design** (self-contained: inline CSS, Google Fonts, no JS needed).
- `concepts/` — the A/B/C concept archive from the 2026-07-10 pick (A = dark "system/operator",
  B = clean K-beauty, C = winner). `concepts/index.html` is a side-by-side viewer.
- `_superseded_index_2026-07-09.html` — the pre-strategy-session WIP, kept for reference only.
- `ko/index.html` — Korean company page in "The Well" design (self-contained; targets
  brand partners / grant reviewers; verifiable facts only; brand-story section with the
  Isaiah 12:3 founding verse and a concentric-ripple vision diagram). Old design preserved
  as `ko/_superseded_ko_2026-07-09.html`. `assets/landing.css` + `assets/landing.js` are
  now used only by the superseded archives.
- `assets/img/products/` — official brand product photos + `SOURCES.md` (provenance; confirm
  usage rights with the brands before public launch).
- `assets/img/*.png` — dashboard screenshots used as "sistema real" proof.
- `vercel.json` — leftover from before hosting was decided; hosting is still undecided
  (Render static proposed, matches the API stack).

## Decisions on record (2026-07-10 strategy session)

1. Primary audience: LATAM skincare creators (ES) — supports pilot outreach (roadmap priority 2).
2. CTA: application form only (no WhatsApp, no mailto). Links are `#aplicar` placeholders
   until the form exists — see `docs/CREATOR_APPLY_FORM_ES.md` for the form spec.
3. Cosmetics only: Parnell (Eleven Corp), Essenherb/BRTC (AMI Cosmetic), Dermal masks.
   한글안경 (eyewear) explicitly excluded.
4. No operational promises in copy (no response-time or product-shipping claims).
5. Compliance: no Shopify-store claims, no invented metrics, no commission percentages;
   consent-first copy mirrors the platform's fail-closed consent validation.

## Local preview

```powershell
cd work\briwell_landing_page
python -m http.server 8071
```

Note for screenshots: headless Edge/Chrome clamps windows below ~500px width, so 375px
mobile captures silently render at ~492px and look clipped. Wrap the page in a 375px
iframe inside a ≥520px window instead.

## Before public launch (open items)

- [ ] Create the application form (Tally/Google Form, spec in `docs/CREATOR_APPLY_FORM_ES.md`)
      and wire the ES CTA links (`#aplicar`, 2 places).
- [ ] Domain + hosting + receiving email (all undecided as of 2026-07-10) — then wire the
      KO partner-contact CTA (`#contacto`, 2 places).
- [ ] Brand-side confirmation for product photo usage.
