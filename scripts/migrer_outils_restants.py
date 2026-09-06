#!/usr/bin/env python3
"""
scripts/migrer_outils_restants.py — migration mécanique des fichiers restants
====================================================================================

Ce script ne réécrit AUCUNE logique métier — il applique uniquement des
correctifs mécaniques, sûrs, et déjà vérifiés ailleurs dans le projet :

  1. Retire le bug heredoc (`cat << 'EOF' > fichier.py` en 1ère ligne, `EOF`
     en dernière ligne) s'il est présent — voir docs/AUDIT_JARVIS.md §2.1.
  2. Rédige le jeton Telegram compromis partout où il apparaît en dur, et le
     remplace par un appel à la config centrale.
  3. Copie chaque fichier vers tools_legacy/ ou scripts_legacy/ (PAS vers
     tools/ directement) : ces fichiers n'ont pas été relus un par un dans
     cette passe (voir docs/MIGRATION.md pour la liste et l'état de chacun),
     ils doivent être relus et rebranchés au registre central
     (core.tools_registry.outil) avant usage réel.

Usage :
    python scripts/migrer_outils_restants.py /chemin/vers/JARVIS_MARDI_extrait
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

JETON_COMPROMIS_RE = re.compile(r'["\']?\d{8,10}:AA[A-Za-z0-9_-]{20,}["\']?')

DOSSIERS_A_MIGRER = {
    "tools": "tools_legacy",
    "scripts": "scripts_legacy",
    "interface": "interface_legacy",
    "automation": "automation_legacy",
}

# Fichiers déjà entièrement réécrits à la main dans la nouvelle base — à ne
# PAS recopier depuis l'ancien projet pour ne pas écraser le travail fait.
DEJA_MIGRES = {
    "tools/herdr_bridge.py", "tools/notebooklm_tool.py", "tools/network_tool.py",
    "tools/jarvis_tools.py",  # remplacé par tools/system_tools.py, nom volontairement différent
    "tools/web_browser_tool.py",  # remplacé par tools/web_tool.py (2 failles corrigées au passage)
    "scripts/consolidation_nocturne.py",
    "scripts/importer_second_cerveau.py",  # remplacé par tools/second_cerveau.py
}


def corriger_heredoc(source: str) -> str:
    lignes = source.splitlines()
    if lignes and re.match(r"^\s*cat\s*<<\s*'?EOF'?\s*>", lignes[0]):
        lignes = lignes[1:]
        if lignes and lignes[-1].strip() == "EOF":
            lignes = lignes[:-1]
        return "\n".join(lignes) + "\n"
    return source


def rediger_secrets(source: str) -> tuple[str, int]:
    """Remplace un jeton en dur par None. Le commentaire d'explication est mis
    SUR SA PROPRE LIGNE APRÈS le remplacement plutôt qu'en fin de ligne
    directement : coller un commentaire sur la même ligne qu'un remplacement
    peut avaler le reste d'une expression multi-lignes (parenthèse fermante
    d'un appel de fonction, etc.) et casser la syntaxe du fichier — bug réel
    trouvé et corrigé après une première migration (voir docs/AUDIT_JARVIS.md
    ou l'historique de la session : tools_legacy/jarvis_startup_notify.py
    avait exactement ce problème)."""
    nb = len(JETON_COMPROMIS_RE.findall(source))
    source = JETON_COMPROMIS_RE.sub("None", source)
    if nb:
        source = f"# JETON(S) RETIRÉ(S) PAR LA MIGRATION ({nb}) — utilise config.TELEGRAM_TOKEN\n" + source
    return source, nb


def renommer_module_config(source: str) -> str:
    """jarvis_config.py est devenu config.py (source unique, voir config.py) —
    renommage mécanique sûr : tous les fichiers de l'ancien projet utilisaient
    l'alias `import jarvis_config as config`, donc tout `config.X` déjà
    présent dans le fichier reste valide sans autre changement."""
    source = re.sub(r"^(\s*)import jarvis_config as config", r"\1import config", source, flags=re.MULTILINE)
    source = re.sub(r"^(\s*)from jarvis_config import", r"\1from config import", source, flags=re.MULTILINE)
    return source


def migrer(racine_source: Path, racine_cible: Path) -> None:
    total_heredoc_corriges = 0
    total_secrets_rediges = 0
    total_fichiers = 0

    for dossier_source, dossier_cible in DOSSIERS_A_MIGRER.items():
        src_dir = racine_source / dossier_source
        if not src_dir.exists():
            continue
        for fichier in src_dir.glob("*.py"):
            rel = f"{dossier_source}/{fichier.name}"
            if rel in DEJA_MIGRES:
                continue

            source = fichier.read_text(encoding="utf-8", errors="replace")
            source_avant = source
            source = corriger_heredoc(source)
            heredoc_corrige = source != source_avant

            source, nb_secrets = rediger_secrets(source)
            source = renommer_module_config(source)

            entete = (
                f'"""\n[MIGRATION AUTOMATIQUE — voir docs/MIGRATION.md]\n'
                f"Ce fichier vient de l'ancien projet ({rel}). Corrections mécaniques "
                f"appliquées automatiquement : "
                f"{'bug heredoc retiré, ' if heredoc_corrige else ''}"
                f"{f'{nb_secrets} secret(s) en dur rédigé(s), ' if nb_secrets else ''}"
                f"aucune autre modification.\n"
                f"PAS ENCORE relu ni rebranché au registre central (core.tools_registry) "
                f"— voir docs/MIGRATION.md avant usage réel.\n\"\"\"\n\n"
            )

            cible_dir = racine_cible / dossier_cible
            cible_dir.mkdir(parents=True, exist_ok=True)
            (cible_dir / fichier.name).write_text(entete + source, encoding="utf-8")

            total_fichiers += 1
            total_heredoc_corriges += int(heredoc_corrige)
            total_secrets_rediges += nb_secrets

            if heredoc_corrige or nb_secrets:
                print(f"  {rel} -> {dossier_cible}/{fichier.name} "
                      f"({'heredoc corrigé' if heredoc_corrige else ''}"
                      f"{', ' if heredoc_corrige and nb_secrets else ''}"
                      f"{f'{nb_secrets} secret(s) rédigé(s)' if nb_secrets else ''})")

    print(f"\n{total_fichiers} fichiers migrés — {total_heredoc_corriges} bug(s) heredoc corrigé(s), "
          f"{total_secrets_rediges} secret(s) en dur rédigé(s).")
    print("Rappel : ces fichiers doivent être relus avant usage (voir docs/MIGRATION.md).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python scripts/migrer_outils_restants.py /chemin/vers/JARVIS_MARDI_extrait")
        sys.exit(1)

    racine_source = Path(sys.argv[1]).expanduser().resolve()
    racine_cible = Path(__file__).resolve().parent.parent
    migrer(racine_source, racine_cible)
