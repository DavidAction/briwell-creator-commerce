from typing import Any


PRODUCT_LABELS = {
    "sunscreen": "protector solar coreano",
    "calming_serum": "serum calmante coreano",
    "cleanser": "limpiador coreano",
    "sheet_mask": "mascarilla coreana",
    "cushion_foundation": "cushion foundation coreana",
}


def build_dm_drafts(
    creator: dict[str, Any],
    product_category: str,
    product_name: str | None = None,
) -> list[dict[str, Any]]:
    display_name = creator.get("display_name") or creator.get("username") or "hola"
    product_label = product_name or PRODUCT_LABELS.get(product_category, "producto K-beauty")
    evidence = _personalization_evidence(creator)

    return [
        {
            "variant": "soft_intro",
            "message": (
                f"Hola {display_name}, soy del equipo de Briwell. Nos gusto tu contenido de "
                f"belleza y estamos preparando una colaboracion de K-beauty con {product_label}. "
                "Si te interesa, puedo compartirte los detalles."
            ),
            "personalization_evidence": evidence,
            "product_angle": PRODUCT_LABELS.get(product_category, "K-beauty"),
            "claims_check_status": "needs_review",
        },
        {
            "variant": "product_review",
            "message": (
                f"Hola {display_name}, en Briwell estamos buscando creadoras en LatAm para probar "
                f"{product_label} y compartir una resena honesta si encaja con su estilo. "
                "La colaboracion seria clara, sencilla y con aprobacion previa de los detalles."
            ),
            "personalization_evidence": evidence,
            "product_angle": "resena honesta de producto",
            "claims_check_status": "needs_review",
        },
        {
            "variant": "ugc_collaboration",
            "message": (
                f"Hola {display_name}, nos encanto tu estilo y nos gustaria invitarte a crear contenido "
                f"UGC con {product_label} para las campanas de Briwell en LatAm. Tu defines el formato; "
                "nosotros coordinamos producto, brief y aprobacion previa de los detalles."
            ),
            "personalization_evidence": evidence,
            "product_angle": "contenido UGC de marca",
            "claims_check_status": "needs_review",
        },
        {
            "variant": "commerce_collaboration",
            "message": (
                f"Hola {display_name}, en Briwell preparamos una colaboracion de comercio con {product_label}: "
                "codigo de descuento y link de compra para tu comunidad, con condiciones claras y aprobacion "
                "previa. Si te interesa, te comparto los detalles de la comision."
            ),
            "personalization_evidence": evidence,
            "product_angle": "colaboracion de comercio con link",
            "claims_check_status": "needs_review",
        },
    ]


def _personalization_evidence(creator: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    if creator.get("country"):
        evidence.append(f"creator_country:{creator['country']}")
    if creator.get("bio"):
        evidence.append("profile_bio_provided")
    if creator.get("follower_count") is not None:
        evidence.append("follower_count_provided")
    if not evidence:
        evidence.append("minimal_profile_context")
    return evidence[:3]
