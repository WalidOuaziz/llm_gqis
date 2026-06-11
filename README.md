# QGIS LLM Agent

Un plugin QGIS 3.34+ qui utilise un LLM (Grand Modèle de Langage) pour convertir des instructions en langage naturel en opérations SIG exécutables.

## Architecture

- **Planner LLM** — traduit la requête utilisateur en plan JSON `{"steps": [...]}`
- **Fixer LLM** — corrige automatiquement les étapes en erreur (max 3 tentatives)
- **Re-plan contextuel** — après ouverture de projet, met à jour le plan avec les vrais noms de couches
- **28 outils** — projet, couches, traitement, canevas, export, système

## Technologies

- QGIS 3.34+ (PyQGIS)
- OpenAI-compatible API (défaut: Ollama avec `qwen2.5:3b`)
- Modèle local gratuit, aucune clé API requise

## Installation

1. Copier le dossier `qgis_llm_agent` dans :
   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
   ```
2. Activer le plugin dans QGIS : **Extensions → Gérer les extensions → QGIS LLM Agent**
3. Lancer via le bouton dans la barre d'outils ou **Extensions → QGIS LLM Agent**

## Utilisation

```
"Ouvre projet.qgz, calcule la surface en hectares dans un champ surface_ha,
exporte en GeoJSON, crée un buffer de 100m, et sauvegarde"
```

Le plugin génère et exécute automatiquement un plan multi-étapes.

## Licence

MIT
