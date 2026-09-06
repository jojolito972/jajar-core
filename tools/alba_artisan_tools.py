"""
tools/alba_artisan_tools.py — Outils de calcul technique et de gestion d'atelier
pour Madame Laura Puntillo (Signature de prompt corrigée).
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Final

import config
from config import SecurityTier
from core.tools_registry import outil

logger: Final[logging.Logger] = logging.getLogger("jajar.alba_tools")

DOSSIER_CLIENTS: Final[Path] = config.PUNTILLO_DIR / "Fiches_Clients_Bespoke"
DOSSIER_CATALOGUE: Final[Path] = config.PUNTILLO_DIR / "Catalogue_Cuirs"
DOSSIER_INSTAGRAM: Final[Path] = config.PUNTILLO_DIR / "Publications_Instagram"
DOSSIER_ATELIER: Final[Path] = config.PUNTILLO_DIR / "Journal_Atelier"

for p in (DOSSIER_CLIENTS, DOSSIER_CATALOGUE, DOSSIER_INSTAGRAM, DOSSIER_ATELIER):
    p.mkdir(parents=True, exist_ok=True)


@outil(tier=SecurityTier.AUTO, personas=["alba", "jarvis", "cleo"])
def calculer_metrage_et_cout_cuir(
    type_modele: str,
    pointure: float,
    type_cuir: str,
    prix_dm2_ht: float,
    hauteur_tige_cm: float = 0.0,
    coefficient_perte: float = 0.30,
) -> str:
    """Calcule le métrage de cuir nécessaire (en dm² et pieds carrés), les pertes de coupe et le coût de revient matière."""
    modele_clean = type_modele.strip().lower()

    if any(k in modele_clean for k in ("botte", "cavaliere", "cuissarde")):
        surface_base_dm2 = 55.0 + (hauteur_tige_cm * 0.8)
    elif any(k in modele_clean for k in ("bottine", "chelsea", "derby montant", "chukka")):
        surface_base_dm2 = 32.0
    elif any(k in modele_clean for k in ("richelieu", "derby", "oxford", "monk", "boucle")):
        surface_base_dm2 = 22.0
    elif any(k in modele_clean for k in ("mocassin", "loafer", "escarpin")):
        surface_base_dm2 = 18.0
    else:
        surface_base_dm2 = 24.0

    facteur_pointure = 1.0 + ((pointure - 41.0) * 0.02)
    surface_ajustee = surface_base_dm2 * facteur_pointure
    surface_brute_requise_dm2 = surface_ajustee * (1.0 + coefficient_perte)
    surface_sqft = surface_brute_requise_dm2 / 9.2903

    cout_tige_ht = surface_brute_requise_dm2 * prix_dm2_ht
    cout_doublure_veau_ht = 18.0 * 0.45
    cout_bloc_semelle_trépointe_ht = 42.00
    cout_fournitures_ht = 15.00

    cout_total_matiere_ht = cout_tige_ht + cout_doublure_veau_ht + cout_bloc_semelle_trépointe_ht + cout_fournitures_ht

    return (
        f"📊 **Calcul de Métrage & Coût de Revient Matière — Atelier Laura Puntillo**\n\n"
        f"• **Modèle :** {type_modele.capitalize()} (Pointure {pointure})\n"
        f"• **Cuir Tige Sélectionné :** {type_cuir} ({prix_dm2_ht:.2f} € HT / dm²)\n"
        f"• **Surface Brute à Commander :** **`{surface_brute_requise_dm2:.1f} dm²`** (`{surface_sqft:.2f} sq ft`)\n"
        f"• **Coût Matière Total HT par Paire :** **`{cout_total_matiere_ht:.2f} € HT`**"
    )


@outil(tier=SecurityTier.AUTO, personas=["alba", "jarvis", "alfred"])
def creer_fiche_client_mesures_bespoke(
    nom_client: str,
    pointure_estimee: float,
    type_modele: str,
    longueur_pied_gauche_mm: float,
    longueur_pied_droit_mm: float,
    tour_joint_metatarse_mm: float,
    tour_cou_de_pied_mm: float,
    particularites_morphologie: str = "Pied standard, cambrure normale",
    choix_cuir_finition: str = "Box-Calf Noir Tannage Végétal",
) -> str:
    """Enregistre une fiche client complète de prise de mesures et de commande dans Obsidian (en français)."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d")
    slug_nom = nom_client.strip().replace(" ", "_").lower()
    fichier_cible = DOSSIER_CLIENTS / f"Client_{slug_nom}.md"

    difference_longueur = abs(longueur_pied_gauche_mm - longueur_pied_droit_mm)

    contenu = f"""---
title: "Fiche Client Bespoke — {nom_client}"
date: {ts}
atelier: "Laura Puntillo"
client: "{nom_client}"
pointure_base: {pointure_estimee}
modele: "{type_modele}"
cuir: "{choix_cuir_finition}"
statut_commande: "Prise de mesures effectuée"
tags: ["bespoke", "mesures", "client", "bottier"]
---

# 👢 Fiche Client Bespoke : {nom_client}

**Date de Prise de Mesures :** {ts}  
**Modèle Commandé :** {type_modele}  
**Cuir & Finitions :** {choix_cuir_finition}  

---

## 📏 Relevé Morphologique & Mesures d'Atelier

| Paramètre Anatomique | Pied Gauche | Pied Droit | Tolérance / Remarques |
| :--- | :---: | :---: | :--- |
| **Longueur Totale** | `{longueur_pied_gauche_mm} mm` | `{longueur_pied_droit_mm} mm` | Écart : `{difference_longueur:.1f} mm` |
| **Périmètre Métatarso-Phalangien (Joint)** | `{tour_joint_metatarse_mm} mm` | `{tour_joint_metatarse_mm} mm` | Largeur d'appui |
| **Tour de Cou-de-Pied (Instep)** | `{tour_cou_de_pied_mm} mm` | `{tour_cou_de_pied_mm} mm` | Volume d'entrée |

**Spécificités :** > {particularites_morphologie}

---
*Fiche générée par Alba pour l'atelier Laura Puntillo.*
"""
    fichier_cible.write_text(contenu, encoding="utf-8")

    try:
        from tools.graph_memory import enregistrer_relation_graphe
        enregistrer_relation_graphe(nom_client, "commande_bespoke", type_modele, f"{choix_cuir_finition} ({ts})")
    except Exception:
        pass

    return f"✅ **Fiche Client Bespoke créée pour [[{fichier_cible.stem}]] !**"


@outil(tier=SecurityTier.AUTO, personas=["alba", "jarvis", "leo", "franklin"])
def generer_post_instagram_artisan(
    sujet_creation: str,
    angle_editorial: str = "coulisses_savoir_faire",
    langue_principale: str = "fr",
) -> str:
    """Rédige une publication Instagram valorisant l'artisanat d'art avec correction des arguments d'appel."""
    from core.llm_router import router

    prompt_systeme = (
        "Tu es Alba, la voix éditoriale et la directrice de communication de Madame Laura Puntillo.\n"
        "Rédige une publication Instagram haut de gamme valorisant le savoir-faire bottier bespoke.\n"
        "Format : Titre poétique, corps en Français, traduction élégante en Italien, 15 hashtags spécialisés."
    )

    try:
        # Correction P1 : Appel par mot-clé explicite pour éviter l'inversion d'arguments
        texte_post, _ = router.generer(
            system_prompt=prompt_systeme,
            user_prompt=f"Sujet de la création : '{sujet_creation}' (Angle : {angle_editorial})",
            temperature=0.3,
        )
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        fichier_post = DOSSIER_INSTAGRAM / f"Post_Instagram_{ts}.md"

        frontmatter = f"---\ndate: {datetime.datetime.now().isoformat()}\nsujet: \"{sujet_creation}\"\n---\n\n"
        fichier_post.write_text(frontmatter + texte_post, encoding="utf-8")

        return f"📸 **Publication Instagram Prête :**\n\n{texte_post}\n\n📂 *Archivée dans :* `[[{fichier_post.stem}]]`"
    except Exception as e:
        return f"Erreur génération Instagram : {e}"
