# domhunter

Pipeline pour:
- Vérifier la disponibilité d’un domaine (InternetBS)
- Vérifier l’indexation Google (Programmable Search Engine / Custom Search API)
- Récupérer des screenshots Wayback Machine (WebArchive)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
# édite .env et ajoute tes clés
```

## Utilisation

```bash
domhunter --domains examples/input_domains.txt --out output --max-screenshots 5 --concurrency 5
```

Résultats:
- output/results.json
- output/results.csv
- output/screenshots/<domaine>/<timestamp>.png

## Variables d’environnement

Voir `.env.example`:
- INTERNETBS_API_KEY, INTERNETBS_PASSWORD
- GOOGLE_API_KEY, GOOGLE_CX

## Notes

- Google: utilise l’API Custom Search (CSE). Évite le scraping direct des SERP.
- Wayback: certains snapshots n’ont pas de screenshot disponible.

## Étapes SEO avancées (optionnel)

Intégrables plus tard via des providers dédiés (Ahrefs, Majestic, Moz, SEMrush) pour:
- domaines référents
- trafic récent
- mots-clés indexés
- qualité des backlinks