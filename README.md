# YouTube Auto Publisher

Chaîne YouTube 100% automatisée propulsée par l'IA. Génère et publie 5 vidéos Short par jour sur la finance, le business et la tech, sans aucune intervention manuelle.

## Comment ça marche

1. **Mistral AI** choisit le meilleur sujet trending du jour
2. **Mistral AI** génère le script (~90 secondes)
3. **ElevenLabs / gTTS** crée la voix off en anglais
4. **Picsum / Unsplash** fournit les images liées au sujet
5. **MoviePy** assemble la vidéo verticale (1080x1920) avec sous-titres
6. **YouTube API** publie automatiquement la vidéo en Short

## Horaires de publication

| Heure (France) | Cron UTC |
|---|---|
| 07h00 | `0 5 * * *` |
| 12h00 | `0 10 * * *` |
| 17h30 | `30 15 * * *` |
| 20h00 | `0 18 * * *` |
| 22h30 | `30 20 * * *` |

## Stack technique (100% gratuit)

| Rôle | Outil |
|---|---|
| Génération texte | Mistral AI (free tier) |
| Voix off | ElevenLabs (free) / gTTS (fallback) |
| Images | Unsplash / Picsum |
| Montage | MoviePy 1.0.3 |
| Serveur | GitHub Actions |
| Upload | YouTube Data API v3 |

## Configuration

### Secrets GitHub requis

Aller dans `Settings → Secrets and variables → Actions` et ajouter :

| Secret | Description |
|---|---|
| `MISTRAL_KEY` | Clé API Mistral AI |
| `ELEVEN_KEY` | Clé API ElevenLabs |
| `YT_CLIENT_ID` | Google Cloud OAuth Client ID |
| `YT_CLIENT_SECRET_STR` | Google Cloud OAuth Client Secret |
| `YT_REFRESH_TOKEN` | Token OAuth YouTube généré une fois |

### Structure du repo

```
Auto-Upload-Video/
├── main.py                          # Script principal
├── README.md                        # Ce fichier
└── .github/
    └── workflows/
        └── publish.yml              # Configuration GitHub Actions
```

## Lancer manuellement

Dans GitHub : `Actions → YouTube Auto Publisher → Run workflow`

## Niche

Finance · Business · AI & Tech — contenu en anglais pour maximiser le CPM publicitaire.
