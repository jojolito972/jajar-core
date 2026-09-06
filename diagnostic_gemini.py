"""
diagnostic_gemini.py — isole un appel Gemini réel, hors de la boucle de retry
silencieuse de core/engine.py, pour voir exactement ce qui casse.

Usage : depuis le dossier jarvis, venv activé :
    python diagnostic_gemini.py

Colle-moi les DEUX blocs de sortie (TEST 1 et TEST 2) tels quels.
"""

import json
import sys

sys.path.insert(0, ".")

import config
from google import genai
from google.genai import types

try:
    from core.schemas import Decision
except Exception as e:
    Decision = None
    print(f"(info : import de Decision impossible, {e} — les tests continuent quand même)\n")

SYSTEM_PROMPT_MINIMAL = """\
Tu es un assistant qui répond STRICTEMENT en JSON, sans aucun texte autour, sans balises markdown.
Format obligatoire :
{
  "thinking": "raisonnement court",
  "action": "final_answer",
  "tool_name": null,
  "tool_args": {},
  "answer": "ta réponse",
  "confidence": "haute",
  "self_critique": "ce que tu as vérifié",
  "statut_epistemique": "fait_verifie",
  "sources": [],
  "contradiction_memoire": null,
  "meilleur_contre_argument": "objection réaliste à ta propre réponse"
}
"""
USER_PROMPT = "Tâche : Combien font 12 x 8 ?\n\nHistorique :\n(aucun)"

client = genai.Client(api_key=config.GEMINI_API_KEY)


def tester_pydantic(brut: str) -> None:
    if Decision is None:
        return
    try:
        d = Decision(**json.loads(brut))
        d.validate_coherence("jarvis") if hasattr(d, "validate_coherence") else None
        print("-> Pydantic + validate_coherence : OK")
    except Exception as e:
        print(f"-> ÉCHEC Pydantic/JSON : {type(e).__name__}: {e}")


print("=" * 70)
print("TEST 1 — approche actuelle (response_mime_type seul, comme core/llm_router.py)")
print("=" * 70)
try:
    res = client.models.generate_content(
        model=config.MODELE_TEXTE_GEMINI,
        contents=USER_PROMPT,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT_MINIMAL,
            temperature=0.3,
            response_mime_type="application/json",
        ),
    )
    print("--- texte brut (res.text) ---")
    print(repr(res.text))
    if res.text:
        tester_pydantic(res.text)
except Exception as e:
    print(f"EXCEPTION SDK : {type(e).__name__}: {e}")

print()
print("=" * 70)
print("TEST 2 — avec response_schema=Decision (structured output imposé par l'API)")
print("=" * 70)
print(
    "NOTE : cet essai est INFORMATIF, pas un test de non-régression. Decision.tool_args "
    "est un dict libre -> Pydantic génère 'additionalProperties: true' dans le schéma, "
    "et l'API Gemini Developer (clé AI Studio) refuse ce mot-clé (seul Vertex/Enterprise "
    "le supporte). Un échec ici est ATTENDU et sans conséquence : core/llm_router.py "
    "n'utilise jamais response_schema (voir _appeler_gemini), donc ce comportement ne "
    "touche pas le bot en production.\n"
)
if Decision is None:
    print("(ignoré : Decision non importable)")
else:
    try:
        res2 = client.models.generate_content(
            model=config.MODELE_TEXTE_GEMINI,
            contents=USER_PROMPT,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT_MINIMAL,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=Decision,
            ),
        )
        print("--- texte brut (res2.text) ---")
        print(repr(res2.text))
        print("--- res2.parsed ---")
        print(res2.parsed)
    except Exception as e:
        print(f"ÉCHEC ATTENDU (additionalProperties, tier Developer API) : {type(e).__name__}: {e}")
