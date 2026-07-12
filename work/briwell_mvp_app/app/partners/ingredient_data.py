"""Code-seeded INCI dictionary and regulatory rule set (Phase 1).

Kept in code rather than tables so the pipeline and its tests work without a
database and the seed cannot drift from the matcher. Sources:

* Dictionary: hand-curated subset of the EU CosIng inventory (public open
  data, ec.europa.eu/growth/tools-databases/cosing) covering the ingredients
  that dominate K-beauty INCI lists. Extend freely; the matcher treats this
  as the canonical spelling. Since P3 the full CosIng inventory (~28,700
  names, data/cosing_ingredients.csv via app/partners/cosing_data.py) sits
  underneath as a fallback layer — this curated seed always wins.
* Regulatory rules: conservative starter set of substances that are
  prohibited or restricted in cosmetics across our launch markets (MX/PE/EC),
  anchored to Andean Decision 833 (which adopts EU Annex II/III-style lists,
  recognized in PE and EC) and Mexico's COFEPRIS acuerdos. Only clear-cut,
  widely documented entries are seeded; everything else stays unflagged.

IMPORTANT: screening output is an informational signal for operators — it is
NOT legal advice and never blocks anything by itself (non-negotiable
constraint 6). Every rule carries source_ref so an operator can verify.
"""

SEED_VERSION = "v0-2026-07-12"

REGULATORY_DISCLAIMER = (
    "규제 신호는 참고용 사전 스크리닝이며 법률 자문이 아닙니다. "
    "수입·판매 전 반드시 각국 인허가 전문가 검토가 필요합니다."
)

# INCI name -> {aliases: [...], functions: [...]}
# Canonical spelling is title-case INCI as published in CosIng.
INGREDIENT_DICTIONARY: dict[str, dict[str, list[str]]] = {
    "Water": {"aliases": ["Aqua", "Eau", "정제수"], "functions": ["solvent"]},
    "Glycerin": {"aliases": ["Glycerine", "글리세린"], "functions": ["humectant"]},
    "Butylene Glycol": {"aliases": ["1,3-Butylene Glycol", "부틸렌글라이콜"], "functions": ["humectant", "solvent"]},
    "Propanediol": {"aliases": ["프로판다이올"], "functions": ["humectant", "solvent"]},
    "Dipropylene Glycol": {"aliases": ["다이프로필렌글라이콜"], "functions": ["solvent"]},
    "Niacinamide": {"aliases": ["Nicotinamide", "나이아신아마이드"], "functions": ["brightening", "conditioning"]},
    "Adenosine": {"aliases": ["아데노신"], "functions": ["conditioning"]},
    "Sodium Hyaluronate": {"aliases": ["소듐하이알루로네이트"], "functions": ["humectant"]},
    "Hyaluronic Acid": {"aliases": ["하이알루로닉애씨드"], "functions": ["humectant"]},
    "Hydrolyzed Hyaluronic Acid": {"aliases": ["가수분해하이알루로닉애씨드"], "functions": ["humectant"]},
    "Panthenol": {"aliases": ["D-Panthenol", "판테놀"], "functions": ["soothing", "humectant"]},
    "Allantoin": {"aliases": ["알란토인"], "functions": ["soothing"]},
    "Centella Asiatica Extract": {"aliases": ["병풀추출물", "Centella Extract"], "functions": ["soothing"]},
    "Madecassoside": {"aliases": ["마데카소사이드"], "functions": ["soothing"]},
    "Asiaticoside": {"aliases": ["아시아티코사이드"], "functions": ["soothing"]},
    "Asiatic Acid": {"aliases": ["아시아틱애씨드"], "functions": ["soothing"]},
    "Madecassic Acid": {"aliases": ["마데카식애씨드"], "functions": ["soothing"]},
    "Ceramide NP": {"aliases": ["Ceramide 3", "세라마이드엔피"], "functions": ["emollient", "barrier"]},
    "Squalane": {"aliases": ["스쿠알란"], "functions": ["emollient"]},
    "Tocopherol": {"aliases": ["Vitamin E", "토코페롤"], "functions": ["antioxidant"]},
    "Tocopheryl Acetate": {"aliases": ["토코페릴아세테이트"], "functions": ["antioxidant"]},
    "Ascorbic Acid": {"aliases": ["Vitamin C", "아스코빅애씨드"], "functions": ["antioxidant", "brightening"]},
    "3-O-Ethyl Ascorbic Acid": {"aliases": ["에틸아스코빅애씨드"], "functions": ["brightening"]},
    "Arbutin": {"aliases": ["알부틴"], "functions": ["brightening"]},
    "Alpha-Arbutin": {"aliases": ["알파-알부틴"], "functions": ["brightening"]},
    "Titanium Dioxide": {"aliases": ["티타늄디옥사이드", "CI 77891"], "functions": ["uv_filter", "colorant"]},
    "Zinc Oxide": {"aliases": ["징크옥사이드"], "functions": ["uv_filter"]},
    "Ethylhexyl Methoxycinnamate": {"aliases": ["Octinoxate", "에틸헥실메톡시신나메이트"], "functions": ["uv_filter"]},
    "Ethylhexyl Salicylate": {"aliases": ["Octisalate", "에틸헥실살리실레이트"], "functions": ["uv_filter"]},
    "Homosalate": {"aliases": ["호모살레이트"], "functions": ["uv_filter"]},
    "Butyl Methoxydibenzoylmethane": {"aliases": ["Avobenzone", "부틸메톡시디벤조일메탄"], "functions": ["uv_filter"]},
    "Bis-Ethylhexyloxyphenol Methoxyphenyl Triazine": {"aliases": ["Bemotrizinol", "Tinosorb S"], "functions": ["uv_filter"]},
    "Diethylamino Hydroxybenzoyl Hexyl Benzoate": {"aliases": ["Uvinul A Plus"], "functions": ["uv_filter"]},
    "Snail Secretion Filtrate": {"aliases": ["달팽이점액여과물"], "functions": ["conditioning"]},
    "Propolis Extract": {"aliases": ["프로폴리스추출물"], "functions": ["soothing", "antioxidant"]},
    "Honey Extract": {"aliases": ["꿀추출물", "Mel Extract"], "functions": ["humectant"]},
    "Houttuynia Cordata Extract": {"aliases": ["어성초추출물"], "functions": ["soothing"]},
    "Artemisia Princeps Leaf Extract": {"aliases": ["쑥잎추출물", "Mugwort Extract"], "functions": ["soothing"]},
    "Camellia Sinensis Leaf Extract": {"aliases": ["녹차추출물", "Green Tea Extract"], "functions": ["antioxidant"]},
    "Aloe Barbadensis Leaf Extract": {"aliases": ["알로에베라잎추출물"], "functions": ["soothing", "humectant"]},
    "Betaine": {"aliases": ["베타인"], "functions": ["humectant"]},
    "Trehalose": {"aliases": ["트레할로스"], "functions": ["humectant"]},
    "Beta-Glucan": {"aliases": ["베타글루칸"], "functions": ["soothing", "humectant"]},
    "Salicylic Acid": {"aliases": ["살리실릭애씨드", "BHA"], "functions": ["exfoliant", "preservative"]},
    "Glycolic Acid": {"aliases": ["글라이콜릭애씨드", "AHA"], "functions": ["exfoliant"]},
    "Lactic Acid": {"aliases": ["락틱애씨드"], "functions": ["exfoliant", "ph_adjuster"]},
    "Gluconolactone": {"aliases": ["글루코노락톤", "PHA"], "functions": ["exfoliant"]},
    "Citric Acid": {"aliases": ["시트릭애씨드"], "functions": ["ph_adjuster"]},
    "Sodium Hydroxide": {"aliases": ["소듐하이드록사이드"], "functions": ["ph_adjuster"]},
    "Tromethamine": {"aliases": ["트로메타민"], "functions": ["ph_adjuster"]},
    "Carbomer": {"aliases": ["카보머"], "functions": ["thickener"]},
    "Xanthan Gum": {"aliases": ["잔탄검"], "functions": ["thickener"]},
    "Hydroxyethylcellulose": {"aliases": ["하이드록시에틸셀룰로오스"], "functions": ["thickener"]},
    "Polyglyceryl-3 Methylglucose Distearate": {"aliases": [], "functions": ["emulsifier"]},
    "Glyceryl Stearate": {"aliases": ["글리세릴스테아레이트"], "functions": ["emulsifier"]},
    "Cetearyl Alcohol": {"aliases": ["세테아릴알코올"], "functions": ["emollient", "emulsifier"]},
    "Caprylic/Capric Triglyceride": {"aliases": ["카프릴릭/카프릭트라이글리세라이드"], "functions": ["emollient"]},
    "Shea Butter": {"aliases": ["Butyrospermum Parkii Butter", "시어버터"], "functions": ["emollient"]},
    "Macadamia Ternifolia Seed Oil": {"aliases": ["마카다미아씨오일"], "functions": ["emollient"]},
    "Helianthus Annuus Seed Oil": {"aliases": ["해바라기씨오일", "Sunflower Seed Oil"], "functions": ["emollient"]},
    "Rosmarinus Officinalis Leaf Extract": {"aliases": ["로즈마리잎추출물", "Rosemary Leaf Extract"], "functions": ["antioxidant"]},
    "Melaleuca Alternifolia Leaf Oil": {"aliases": ["티트리잎오일", "Tea Tree Leaf Oil"], "functions": ["conditioning"]},
    "Phenoxyethanol": {"aliases": ["페녹시에탄올"], "functions": ["preservative"]},
    "Ethylhexylglycerin": {"aliases": ["에틸헥실글리세린"], "functions": ["preservative", "conditioning"]},
    "1,2-Hexanediol": {"aliases": ["헥산다이올", "1,2 Hexanediol"], "functions": ["solvent", "preservative"]},
    "Chlorphenesin": {"aliases": ["클로페네신"], "functions": ["preservative"]},
    "Benzyl Glycol": {"aliases": ["벤질글라이콜"], "functions": ["solvent"]},
    "Disodium EDTA": {"aliases": ["다이소듐이디티에이"], "functions": ["chelating"]},
    "Fragrance": {"aliases": ["Parfum", "향료"], "functions": ["fragrance"]},
    "Limonene": {"aliases": ["리모넨"], "functions": ["fragrance"]},
    "Linalool": {"aliases": ["리날룰"], "functions": ["fragrance"]},
    "Citronellol": {"aliases": ["시트로넬올"], "functions": ["fragrance"]},
    "Retinol": {"aliases": ["레티놀"], "functions": ["conditioning"]},
    "Retinal": {"aliases": ["Retinaldehyde", "레티날"], "functions": ["conditioning"]},
    "Bakuchiol": {"aliases": ["바쿠치올"], "functions": ["conditioning"]},
    "Peptide Complex": {"aliases": ["펩타이드콤플렉스"], "functions": ["conditioning"]},
    "Copper Tripeptide-1": {"aliases": ["구리트라이펩타이드-1"], "functions": ["conditioning"]},
    "Palmitoyl Pentapeptide-4": {"aliases": ["팔미토일펜타펩타이드-4", "Matrixyl"], "functions": ["conditioning"]},
    "Galactomyces Ferment Filtrate": {"aliases": ["갈락토미세스발효여과물"], "functions": ["conditioning"]},
    "Bifida Ferment Lysate": {"aliases": ["비피다발효용해물"], "functions": ["conditioning"]},
    "Saccharomyces Ferment Filtrate": {"aliases": ["효모발효여과물"], "functions": ["conditioning"]},
}

# Conservative starter rules. rule_type: "banned" (prohibited in cosmetics)
# or "restricted" (allowed only under conditions — concentration, rinse-off,
# professional use, mandatory warnings). detail is operator-facing Korean.
REGULATORY_RULES: list[dict[str, str]] = [
    # Mercury and compounds — prohibited in cosmetics; Minamata Convention
    # bans skin-lightening cosmetics >1ppm mercury (MX/PE/EC are parties).
    {"country": "MX", "inci_name": "Mercury", "rule_type": "banned",
     "detail": "수은 및 수은 화합물은 화장품 사용 금지 (미나마타 협약·COFEPRIS)",
     "source_ref": "Minamata Convention Annex A; COFEPRIS prohibited list"},
    {"country": "PE", "inci_name": "Mercury", "rule_type": "banned",
     "detail": "수은 및 수은 화합물은 화장품 사용 금지 (미나마타 협약·Decision 833)",
     "source_ref": "Minamata Convention Annex A; Andean Decision 833"},
    {"country": "EC", "inci_name": "Mercury", "rule_type": "banned",
     "detail": "수은 및 수은 화합물은 화장품 사용 금지 (미나마타 협약·Decision 833)",
     "source_ref": "Minamata Convention Annex A; Andean Decision 833"},
    # Tretinoin (retinoic acid) — drug active, prohibited in cosmetics.
    {"country": "MX", "inci_name": "Tretinoin", "rule_type": "banned",
     "detail": "레티노산(트레티노인)은 의약품 성분 — 화장품 사용 금지",
     "source_ref": "COFEPRIS; EU Annex II ref (Decision 833 준용 계열)"},
    {"country": "PE", "inci_name": "Tretinoin", "rule_type": "banned",
     "detail": "레티노산(트레티노인)은 의약품 성분 — 화장품 사용 금지",
     "source_ref": "Andean Decision 833 (EU Annex II 준용)"},
    {"country": "EC", "inci_name": "Tretinoin", "rule_type": "banned",
     "detail": "레티노산(트레티노인)은 의약품 성분 — 화장품 사용 금지",
     "source_ref": "Andean Decision 833 (EU Annex II 준용)"},
    # Corticosteroids — drug actives, prohibited in cosmetics.
    {"country": "MX", "inci_name": "Clobetasol Propionate", "rule_type": "banned",
     "detail": "스테로이드(클로베타솔)는 화장품 사용 금지",
     "source_ref": "COFEPRIS prohibited list"},
    {"country": "PE", "inci_name": "Clobetasol Propionate", "rule_type": "banned",
     "detail": "스테로이드(클로베타솔)는 화장품 사용 금지",
     "source_ref": "Andean Decision 833 (EU Annex II 준용)"},
    {"country": "EC", "inci_name": "Clobetasol Propionate", "rule_type": "banned",
     "detail": "스테로이드(클로베타솔)는 화장품 사용 금지",
     "source_ref": "Andean Decision 833 (EU Annex II 준용)"},
    # Hydroquinone — restricted/prohibited for OTC skin lightening.
    {"country": "MX", "inci_name": "Hydroquinone", "rule_type": "restricted",
     "detail": "하이드로퀴논 미백 용도는 일반 화장품에서 제한 — 전문 검토 필요",
     "source_ref": "COFEPRIS 규제 계열; 미백 크림 단속 사례 다수"},
    {"country": "PE", "inci_name": "Hydroquinone", "rule_type": "restricted",
     "detail": "하이드로퀴논 미백 용도는 일반 화장품에서 제한 — 전문 검토 필요",
     "source_ref": "Andean Decision 833 (EU Annex 준용)"},
    {"country": "EC", "inci_name": "Hydroquinone", "rule_type": "restricted",
     "detail": "하이드로퀴논 미백 용도는 일반 화장품에서 제한 — 전문 검토 필요",
     "source_ref": "Andean Decision 833 (EU Annex 준용)"},
    # Lead acetate — prohibited.
    {"country": "MX", "inci_name": "Lead Acetate", "rule_type": "banned",
     "detail": "납 화합물은 화장품 사용 금지",
     "source_ref": "COFEPRIS prohibited list"},
    {"country": "PE", "inci_name": "Lead Acetate", "rule_type": "banned",
     "detail": "납 화합물은 화장품 사용 금지",
     "source_ref": "Andean Decision 833 (EU Annex II 준용)"},
    {"country": "EC", "inci_name": "Lead Acetate", "rule_type": "banned",
     "detail": "납 화합물은 화장품 사용 금지",
     "source_ref": "Andean Decision 833 (EU Annex II 준용)"},
    # Formaldehyde — banned as such in EU-style lists; legacy releasers restricted.
    {"country": "MX", "inci_name": "Formaldehyde", "rule_type": "restricted",
     "detail": "포름알데하이드는 엄격 제한(농도·경고 문구) — 전문 검토 필요",
     "source_ref": "COFEPRIS; NOM 라벨 경고 계열"},
    {"country": "PE", "inci_name": "Formaldehyde", "rule_type": "restricted",
     "detail": "포름알데하이드는 엄격 제한(농도·경고 문구) — 전문 검토 필요",
     "source_ref": "Andean Decision 833 (EU Annex 준용)"},
    {"country": "EC", "inci_name": "Formaldehyde", "rule_type": "restricted",
     "detail": "포름알데하이드는 엄격 제한(농도·경고 문구) — 전문 검토 필요",
     "source_ref": "Andean Decision 833 (EU Annex 준용)"},
    # Methylchloroisothiazolinone (MCI/MI) — rinse-off only.
    {"country": "MX", "inci_name": "Methylchloroisothiazolinone", "rule_type": "restricted",
     "detail": "MCI/MI 보존제는 워시오프 제품 한정 — 리브온 사용 불가 계열",
     "source_ref": "EU Annex V 계열 (LATAM 준용 확인 필요)"},
    {"country": "PE", "inci_name": "Methylchloroisothiazolinone", "rule_type": "restricted",
     "detail": "MCI/MI 보존제는 워시오프 제품 한정 — 리브온 사용 불가 계열",
     "source_ref": "Andean Decision 833 (EU Annex V 준용)"},
    {"country": "EC", "inci_name": "Methylchloroisothiazolinone", "rule_type": "restricted",
     "detail": "MCI/MI 보존제는 워시오프 제품 한정 — 리브온 사용 불가 계열",
     "source_ref": "Andean Decision 833 (EU Annex V 준용)"},
]
