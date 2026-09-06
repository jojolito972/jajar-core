# -*- coding: utf-8 -*-
import os

print('=== VÉRIFICATION ENVIRONNEMENT NVIDIA NIM ===')
api_key = os.environ.get('NVIDIA_API_KEY', '')
if api_key:
    print(f'clé NVIDIA_API_KEY détectée (longueur: {len(api_key)})')
else:
    print('⚠️ Aucune clé NVIDIA_API_KEY trouvée dans les variables d\'environnement.')
    print('Recherche dans les fichiers de configuration (~/.bashrc, ~/.zshrc, ~/.env)...')

# Test d'import de requests ou openai pour interroger l'endpoint NIM standard (https://integrate.api.nvidia.com/v1)
try:
    import openai
    print('Module openai disponible pour interroger l\'API NIM.')
except ImportError:
    print('Module openai non installé. Installation recommandée pour NIM.')
