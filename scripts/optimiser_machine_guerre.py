# -*- coding: utf-8 -*-
import os

root = '/Users/denmac/Assistant_IA/jarvis'
files_to_fix = [
    os.path.join(root, 'run_jarvis.py'),
    os.path.join(root, 'tools/gui_control.py'),
    os.path.join(root, 'tools/jarvis_telegram_hub.py'),
    os.path.join(root, 'tools/local_model_manager.py'),
    os.path.join(root, 'tools/deep_research.py'),
    os.path.join(root, 'scripts/installer_tout_propre.py'),
    os.path.join(root, 'bac_a_sable/synthese_gemma_maison_rustique.py')
]

print('=== DÉBUT DE L\'OPTIMISATION MACHINE DE GUERRE ===')
for fp in files_to_fix:
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'time.sleep(' in content:
            new_content = content.replace('time.sleep(', '# [OPTIMISÉ MACHINE DE GUERRE] time.sleep -> asyncio.sleep recommandé\n# time.sleep(')
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'Optimisé avec succès : {fp}')
        else:
            print(f'Déjà propre ou sans time.sleep : {fp}')
    else:
        print(f'Fichier introuvable : {fp}')

print('=== OPTIMISATION TERMINÉE ===')
