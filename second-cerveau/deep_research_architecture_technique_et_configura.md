# Deep Research : Architecture technique et configuration du système vocal mains-libres par mot-clé 'Alba' avec validation vocale pour Laura Puntillo (botterie bespoke)
*Date : 2026-08-25 02:31*

# RAPPORT D'INVESTIGATION TECHNIQUE ET CONFIGURATION SYSTÈME
**Sujet :** Architecture technique et configuration du système vocal mains-libres par mot-clé 'Alba' avec validation vocale pour Laura Puntillo (botterie bespoke)  
**Destinataire :** Denis  
**Analyste :** JAJAR (Deep Research Analyst)  

---

## 1. Introduction & Contexte du Projet

Dans le cadre de l'activité d'artisanat d'art haut de gamme menée par **Laura Puntillo**, bottière spécialisée dans la création de souliers sur-mesure pour femmes installée au Viaduc des Arts à Paris (67 Avenue Daumesnil, 75012) [Home - Laura Puntillo], l'atelier fait face à des contraintes opérationnelles inhérentes au travail manuel du cuir. L'assemblage, la découpe des peaux et le montage sur forme nécessitent l'utilisation constante des mains et requièrent un haut niveau de précision stérile ou exempte de manipulations tactiles d'interfaces numériques.

Pour répondre à cette problématique, ce rapport détaille l'architecture technique d'un **système vocal mains-libres déclenché par le mot-clé « Alba »**, couplé à une **validation vocale** sécurisée. Ce dispositif permet de piloter l'environnement numérique de l'atelier (gestion des commandes, prises de notes de mesures, consultation des fiches techniques de fabrication) sans compromettre la concentration ni l'intégrité manuelle de l'artisane.

---

## 2. Analyse de l'Écosystème Métier (Laura Puntillo - Bespoke Shoemaking)

L'investigation de l'activité de Laura Puntillo met en lumière les paramètres contextuels de l'atelier devant être pris en compte par l'architecture vocale :

*   **Nature de l'activité :** Bottière bespoke (sur-mesure intégral). Chaque paire est une « mini-architecture au service du corps », nécessitant un dialogue approfondi, des prises de cotes, le patronnage, l'apprêt, le piquage et le montage manuel [Home - Laura Puntillo].
*   **Environnement acoustique et physique :** 
    *   Présence d'outils de coupe, de marteaux, de machines à coudre et de solvants/colles dans l'atelier.
    *   Niveau de bruit ambiant variable (machine à parer, bruits de frottement du cuir, passages rue Daumesnil).
    *   Nécessité absolue de robustesse contre les faux positifs (un ordre non validé ne doit pas modifier par erreur une spécification de forme ou une commande).

---

## 3. Architecture Technique du Système Vocal « Alba »

Pour garantir une faible latence, une confidentialité locale et une fiabilité à toute épreuve dans un environnement artisanal, l'architecture repose sur une topologie **Edge-Cloud Hybride** (privilégiant le traitement local pour le mot-clé et la validation).

```
[ Capteur Audio / Microphone directionnel ]
                   │
                   ▼
         [ Module Wake-Word 'Alba' ] (Traitement Edge / Local - Porcupine/Snowboy)
                   │
         (Détection validée)
                   │
                   ▼
       [ Moteur STT (Speech-to-Text) ] (Whisper Local / VOSK)
                   │
                   ▼
       [ Analyseur Intent & NLP ] (Rasa / LLM embarqué léger)
                   │
                   ▼
     [ Étape de Validation Vocale ] ("Confirmez-vous ? [Oui/Non]")
                   │
                   ▼
     [ Exécution API / ERP Atelier Bespoke ]
```

### 3.1. Couche d'Acquisition Audio et Réduction de Bruit
*   **Matériel :** Réseau de microphones (Microphone Array) à formation de faisceau (Beamforming) pour isoler la voix de Laura Puntillo par rapport aux bruits parasites de l'établi.
*   **Prétraitement :** Suppression de l'écho acoustique (AEC), suppression du bruit stationnaire (NS) et contrôle automatique du gain (AGC) via des filtres DSP ou des bibliothèques logicielles open-source (WebRTC Audio Processing).

### 3.2. Moteur de Détection du Mot-Clé (« Wake-Word ») : *Alba*
*   **Technologie :** Modèle de détection de mot-clé basé sur les réseaux de neurones profonds (DNN) entraîné spécifiquement sur le phonème « Alba ».
*   **Implantation :** Exécution locale sur un micro-ordinateur de type Raspberry Pi 4/5 ou un mini-PC fanless situé dans l'atelier (garantissant la souveraineté des données et une absence de dépendance réseau critique).
*   **Paramétrage de sensibilité :** Seuil de déclenchement (*Sensitivity Threshold*) configuré à `0.75` pour minimiser les faux négatifs tout en éliminant les déclenchements fortuits liés aux conversations.

### 3.3. Reconnaissance Vocale (STT - Speech-to-Text)
*   Une fois « Alba » détecté, le système s'active pour une fenêtre d'écoute de 10 secondes.
*   **Moteur STT :** Utilisation de **VOSK** (pour un fonctionnement 100% hors-ligne, ultra-rapide et adapté au vocabulaire technique de la botterie) ou d'une instance locale de **OpenAI Whisper (Tiny/Base)** optimisée en CTranslate2.
*   **Lexique personnalisé (Custom Vocabulary / Biasing) :** Intégration d'un dictionnaire phonétique spécifique au métier de Laura Puntillo incluant :
    *   Termes anatomiques du pied et mesures (tour de cou-de-pied, petit tour, longueur, largeur Ball/Heel).
    *   Noms de matières et cuirs (agneau, chevreau, box-calf, daim, crêpe de Chine, semelle, trépointe).
    *   Noms de modèles de référence (ex: *Mimi*, *Salomé*, *Sakura*) [Home - Laura Puntillo].

---

## 4. Protocole de Validation Vocale (Double-Check Sécurisé)

Étant donné la criticité des données dans la botterie sur-mesure (une erreur de pointure ou de spécification de patronage entraîne des semaines de retravail sur un travail de 2 à 3 mois [«Des chaussures sur-mesure, c'est 2 à 3 mois de travail», Laura Puntillo, bottière]), une commande vocale directe ne peut être exécutée sans **validation explicite**.

### 4.1. Séquence de Validation en 3 Étapes

1.  **Activation :** Laura prononce *"Alba, enregistrer la mesure du cou-de-pied à 24 centimètres."*
2.  **Rétroaction Audio (TTS - Text-to-Speech) :** Le système répète l'action comprise via un retour vocal synthétique discret :  
    > *"Mesure du cou-de-pied : 24 centimètres. Confirmez-vous ?"*
3.  **Validation Vocale :** Laura valide par un mot-clé court ("*Oui*", "*Valider*", "*C'est bon*") ou invalide par ("*Annuler*", "*Non*").
    *   *Alternative de sécurité renforcée :* Possibilité d'exiger un code PIN vocal à 2 chiffres pour les modifications majeures de fiches clientes.

---

## 5. Synthèse de la Configuration Technique

| Composant | Technologie Recommandée | Rôle / Spécification |
| :--- | :--- | :--- |
| **Wake-Word** | Picovoice Porcupine / Custom DNN | Détection locale et instantanée du mot « Alba » |
| **Audio Processing** | WebRTC / PortAudio | Réduction du bruit d'atelier (marteaux, machines) |
| **STT (Transcription)** | VOSK Engine (Modèle Français + Lexique Métier) | Transcription hors-ligne du langage naturel orienté botterie |
| **NLU / Intent Parser** | Rasa Open Source / Regex contextuel | Extraction des entités (mesures, clients, types de peaux) |
| **Validation** | Double-opt-in vocal (TTS + Commande de confirmation) | Prévention stricte des erreurs de saisie sur-mesure |
| **Hardware Cible** | Mini-PC Fanless (ex: Intel NUC / SBC ARM) + Micro USB directionnel | Implantation discrète dans l'atelier du Viaduc des Arts |

---

## 6. Conclusion & Recommandations pour Denis

L'architecture présentée offre à Laura Puntillo un assistant vocal sur-mesure (« Alba ») parfaitement adapté aux exigences physiques et qualitatives de son atelier de botterie bespoke. 

**Prochaines étapes recommandées :**
1.  Réaliser une phase de test d'enregistrement des bruits de l'atelier du Viaduc des Arts pour calibrer finement le filtre de réduction de bruit ambiant.
2.  Alimenter le lexique du moteur STT avec la nomenclature exacte des cuirs et des clients de Laura Puntillo pour atteindre un taux de reconnaissance supérieur à 98%.
3.  Procéder à un prototypage rapide (PoC) sur Raspberry Pi 5 avec le déclencheur « Alba ».