# POLARIS — assistant vocal pour Windows 11  (v2)

Assistant personnel inspiré de JARVIS : veille vocale « Hey Polaris » (locale), Gemini pour l'intelligence,
contrôle d'applications, recherche et gestion de fichiers, interface sombre bleu/cyan.
Application **portable** : un seul `Polaris.exe`, pas de Python à installer, pas de registre, pas de démarrage automatique.

## 1. Obtenir Polaris.exe (compilation sur GitHub, pas sur ton PC)

1. Crée un dépôt GitHub (privé conseillé) et envoie-y **tout le contenu** de ce dossier (le fichier `.github/workflows/build.yml` doit rester à cet endroit).
2. Onglet **Actions** → workflow **Build Polaris** → il démarre tout seul (ou **Run workflow**). Durée : environ 5 à 10 minutes.
3. Quand il est vert, ouvre l'exécution → **Artifacts** → télécharge **Polaris-Windows11** → décompresse → double-clic sur `Polaris.exe`.
4. Si le workflow échoue, ouvre l'étape rouge, copie le message d'erreur et donne-le moi : je corrige.

Le workflow installe les dépendances, télécharge le modèle vocal français Vosk (~40 Mo, embarqué dans l'EXE), lance les tests,
compile avec PyInstaller, vérifie `dist/Polaris.exe` puis publie l'artifact.

## 2. Premier lancement

- Windows SmartScreen / Defender peut avertir pour un EXE non signé (« Informations complémentaires » → « Exécuter quand même »).
  Ne désactive jamais Defender : Polaris n'en a pas besoin.
- Windows 11 → Paramètres → Confidentialité et sécurité → Microphone : autorise les applications de bureau.
- **Paramètres** (dans Polaris) → colle ta clé API Gemini (gratuite sur aistudio.google.com) → **Enregistrer** → **Tester**.
  La clé est chiffrée avec DPAPI (liée à ta session Windows) dans `Polaris_data/settings.json`. Elle n'est jamais dans le dépôt.
- Clique **Activer le micro**, puis dis : « Hey Polaris » (bip) puis ta demande. Tu peux aussi enchaîner : « Hey Polaris, ouvre le Bloc-notes ».
- Pour une voix française : Paramètres Windows → Heure et langue → Voix (ajoute le français si besoin).

## 3. Ce que Polaris sait faire

| Demande | Fonctionne sans Internet ? |
|---|---|
| « Ouvre / ferme le Bloc-notes, la calculatrice, Chrome, Spotify… » | oui |
| « Ouvre les paramètres Wi-Fi », « affiche le bureau », « minimise la fenêtre » | oui |
| « Quelle heure est-il ? », « Arrête d'écouter », « Stop » | oui |
| « Trouve mon fichier PDF sur Apollo 11 », « Cherche une image dans mes téléchargements », « Trouve tous mes fichiers Python », « Cherche un fichier qui contient le mot facture » | oui |
| « Ouvre le premier résultat » | oui |
| Renommer, déplacer, classer, mettre à la corbeille (confirmation à chaque fois) | oui |
| Questions, explications, rédaction, code, recherche web, résumé de document | non (Gemini) |

Les recherches de fichiers couvrent Bureau, Documents, Téléchargements, Images, Vidéos, Musique (et OneDrive) + les dossiers ajoutés dans Paramètres.
Le contenu est lu pour : texte/code, PDF (avec texte) et Word `.docx`.

## 4. Vie privée et sécurité

- Le micro n'est actif que si Polaris est ouvert **et** que tu as activé le micro. **STOP ÉCOUTE** le coupe et libère la carte son.
- Aucun son n'est enregistré ni envoyé : la détection de « Polaris » ET la transcription de ta demande se font en local (Vosk).
  Seul le **texte** de ta demande est envoyé à Gemini, et seulement si elle n'est pas une commande locale.
- Un fichier n'est envoyé à Gemini (résumé) qu'après une confirmation explicite.
- Gemini ne peut déclencher que les outils de la liste blanche (`core/tools.py`) : aucune commande libre, aucun shell.
- Confirmation obligatoire avant : fermeture d'appli, ouverture d'un exécutable/script, renommer, déplacer, classer, supprimer (corbeille uniquement, jamais d'écrasement).
- Les accès sont limités aux dossiers autorisés. Chaque catégorie d'action peut être désactivée dans Paramètres.
- Journal des actions : `Polaris_data/actions.log`. L'historique texte n'est conservé que si tu l'actives.
- Pour supprimer Polaris : supprime `Polaris.exe` et le dossier `Polaris_data`.

## 5. Performance

- Aucun gros modèle local : Vosk « small » (~40 Mo) n'est chargé que pendant que le micro est actif, puis libéré.
- Un seul processus, une seule instance. Interface animée à ~20 images/s (5 en mode économie, quasi à l'arrêt si la fenêtre est réduite).
- Gemini n'est appelé que si la commande locale ne suffit pas ; pause automatique 60 s après une erreur de quota ; compteur de requêtes dans Paramètres.
- RAM/CPU de Polaris affichés en bas à gauche : **mesure-les sur ton PC**, je ne promets pas de chiffres.
- Le démarrage de l'EXE (mode « un fichier ») prend quelques secondes : il se décompresse en mémoire temporaire à chaque lancement.

## 6. Limites connues (honnêteté)

- **Je n'ai pas pu tester l'interface, le micro ni Windows** : seuls la logique (mot de réveil, commandes, recherche de fichiers, plan Gemini, clé chiffrée) est couverte par des tests automatiques (`tests/`, exécutés aussi dans le workflow).
  Les premiers lancements peuvent révéler des bugs : envoie-moi `Polaris_data/polaris.log`.
- Le mot de réveil utilise le modèle français : « polaris » n'est pas un mot français, il est reconnu par approximation.
  Si Polaris se réveille trop peu ou trop, change la **sensibilité** dans Paramètres.
- Pas d'annulation du bruit : une TV allumée peut déclencher des commandes. Polaris ignore le micro pendant qu'il parle.
- Fermer une appli envoie une demande de fermeture polie (elle propose d'enregistrer) ; elle ne force jamais l'arrêt.
- Les apps installées sont trouvées via le Menu Démarrer (raccourcis + `Get-StartApps` pour les apps du Store).
- Non fait : lecture de PDF scannés (OCR), Excel/PowerPoint en contenu, contrôle du volume, démarrage automatique (exclu volontairement).

## 7. Structure

```
main.py  build.py  requirements.txt
config/     paramètres (JSON portable) et chemins
core/       assistant (orchestrateur), router (commandes locales), tools + executor (actions autorisées), logger
voice/      listener (Vosk + micro), wakeword, tts (SAPI5)
ai/         gemini_client (plan JSON, recherche web, résumé)
windows/    apps, winctl (fenêtres), web, system
files/      search, manager
interface/  app (fenêtre principale), settings_window
security/   permissions, secrets (DPAPI)
assets/     logo.png, polaris.ico
tests/      tests unitaires
.github/workflows/build.yml
```


## Nouveautés v2

- **Gemini corrigé** : `gemini-2.5-flash` a été arrêté par Google le 16 octobre 2026. Polaris choisit maintenant tout seul le meilleur modèle Flash disponible (réglage « auto », bouton « Détecter le meilleur modèle » dans Paramètres) et en change si un modèle disparaît.
- **Endormi jusqu'à « Hey Polaris »** : Polaris démarre réduit, n'analyse rien tant qu'il n'y a pas de son, se réveille avec « Hey Polaris » (bip + fenêtre), puis se réduit après 25 s d'inactivité.
- **Contrôle de l'écran** (« va sur Wikipédia et cherche… ») : Polaris regarde l'écran, clique et tape. Accord demandé une fois par session ; **accord obligatoire avant tout téléchargement, suppression ou paiement** ; Échap ou STOP arrête tout. Il ne saisit jamais de mot de passe et ne tape jamais dans un terminal.
- **Nouvelle interface** avec ton logo : Accueil (orbe animé), Conversation, Profil (prénom, âge, surnom, tutoiement, style de réponse), Activité (journal), Paramètres, Aide.
