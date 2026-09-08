# Checklist de soumission

La checklist du §28 du manuel, verifiee point par point contre ce depot, avec
la commande qui le prouve quand il y en a une.

Ce qui reste a faire par l'equipe est en tete, parce que c'est la seule partie
qui bloque.

---

## Ce qui manque encore

| Ce qu'il faut | Ou | Pourquoi cela bloque |
|---|---|---|
| **Le lien Figma** | `README.md` §19 | Livrable obligatoire (§24.5). La section porte un marqueur explicite |
| **Confirmer les roles de l'equipe** | `README.md` §18 | Les noms viennent de l'historique git, les roles sont une supposition |
| **Commiter et pousser** | tout le depot | Rien n'est commite. Voir la fin de ce document |

---

## Produit

| Point | Etat | Preuve |
|---|---|---|
| Le parcours principal fonctionne | oui | `./scripts/demo.sh` |
| Le passager peut demander une course | oui | `scripts/ride_flow.py` |
| Le chauffeur peut gerer une course | oui | `scripts/ride_flow.py` |
| La carte fonctionne | oui, avec un jeton Mapbox | sinon un espace annonce comme tel |
| L'itineraire fonctionne | oui | OSRM, avec repli haversine annonce |
| Le prix est estime | oui | `scripts/quote_smoke.py` |
| Le suivi est fonctionnel | oui | `scripts/tracking_demo.py`, WebSocket |

## Design

| Point | Etat | Note |
|---|---|---|
| Interfaces concues sur Figma | a confirmer | La maquette est dans `design-prototype/`, le lien manque |
| Le parcours utilisateur est clair | oui | `DEMARRAGE.md` §6 |
| L'interface est coherente | oui | Un seul fond, un seul accent, memes primitives partout |
| L'experience est intuitive | oui | Recherche en action principale, un seul appui par etape |

## Securite

| Point | Etat | Preuve |
|---|---|---|
| Authentification securisee | oui | OTP argon2 32 Mio, jetons rotatifs |
| Gestion des roles | oui | passager, chauffeur, admin, separes au niveau des dependances |
| Validation des donnees | oui | Pydantic v2 sur chaque entree, `additionalProperties: false` |
| Pas de secrets dans GitHub | oui | `./scripts/security_audit.sh`, gitleaks sur 25 commits |
| Fonctionnalites de securite | oui | PIN, partage, SOS, signalement, filtre GPS |
| Gestion des erreurs | oui | Une seule enveloppe d'erreur, jamais de texte d'exception |

## Technique

| Point | Etat | Note |
|---|---|---|
| Code present dans GitHub | **non, pas encore commite** | voir plus bas |
| Projet organise | oui | `README.md` §15 |
| Commits comprehensibles | oui | prefixes `feat:`, `sec:`, `docs:` |
| Variables d'environnement documentees | oui | `.env.example`, commente ligne par ligne |
| Base de donnees documentee | oui | `README.md` §12, `DEMARRAGE.md` §4 |

## Documentation

| Point | Etat | Fichier |
|---|---|---|
| README termine | oui | `README.md`, les 20 sections du §19 |
| Manuel de demarrage | oui | `DEMARRAGE.md` |
| Installation expliquee | oui | `README.md` §9, `DEMARRAGE.md` §2 |
| Configuration expliquee | oui | `README.md` §10, `DEMARRAGE.md` §2 |
| Comptes de demonstration | oui | `README.md` §14, verifies par `scripts/check_admin_login.py` |
| Figma indique dans le README | **marqueur en place, lien manquant** | `README.md` §19 |
| Captures d'ecran | oui, 21, produites par script | `docs/screenshots/` |

## Presentation

| Point | Etat | Ou |
|---|---|---|
| Demonstration preparee | oui | `./scripts/demo.sh`, chronometree |
| Innovation expliquee | oui | `README.md` §5 |
| Architecture expliquee | oui | `README.md` §7, `ARCHITECTURE.md` |
| Securite expliquee | oui | `README.md` §6, `THREAT_MODEL.md` |
| Repartition des roles expliquee | a confirmer | `README.md` §18 |

---

## Ce qui a ete verifie, et comment

| | | Commande |
|---|---|---|
| tests unitaires | 173 | `.venv/bin/python -m pytest` |
| suites d'acceptation | 16 | `./scripts/acceptance.sh` |
| audit de securite | 14 verifications | `./scripts/security_audit.sh` |
| economie du corridor | 46 verifications | `scripts/corridor_flow.py` |
| chaine des besoins | 9 verifications | `scripts/needs_flow.py` |
| degradation | 17 verifications | `scripts/degradation_test.py` |
| dictionnaire de lieux | 90,5 % top-3 sur 42 requetes | `scripts/geo_eval.py` |
| annulations | 20 cellules sur 20 | `scripts/cancel_matrix.py` |
| concurrence | 1 gagnant sur 20 | `scripts/race_test.py` |
| balayage IDOR | 0 fuite sur 10 routes | `scripts/idor_sweep.py` |
| compte administrateur | connexion complete | `scripts/check_admin_login.py` |

---

## Ce que le depot ne pretend pas avoir

Liste complete dans `README.md` §17. Les points qu'un jury remarquera:

- Aucune evaluation du chauffeur. La note est affichee, aucun endpoint ne la
  collecte.
- L'administration se limite a deux endpoints. Les quatre autres ecrans le
  disent au lieu d'inventer des lignes.
- Le paiement est en especes. L'interface de fournisseur existe, aucun
  prestataire reel n'est integre.
- Pas de notification poussee.
- L'ecran de signature des engagements chauffeur n'existe pas, alors que
  l'endpoint et la contrainte en base existent.

C'est delibere de les ecrire. Le §23 du manuel interdit de presenter de
fausses donnees comme reelles, et un jury qui decouvre une seule invention
cesse de croire le reste.

---

## Deux decisions prises pendant cette passe

**Le tarif corridor est passe de 0,62 a 0,68.** La limite de partage avait ete
ramenee a deux reservations pour une raison de securite. A 0,62, deux portions
rapportaient 2250 XAF contre 2300 pour une seule course exclusive: on demandait
au chauffeur de prendre un inconnu et de gagner moins. A 0,68, il encaisse 2450
et les deux passagers paient toujours environ un tiers de moins. Le raisonnement
complet est dans la docstring de `app/services/fare.py`.

**Les ecrans admin non construits le disent au lieu d'inventer.** Utilisateurs,
courses, statistiques et signalements affichaient des lignes fabriquees, dont
une alerte SOS "examinee par le support". Le §23 du manuel l'interdit, et
inventer une reponse d'urgence traitee est la pire chose a inventer dans cette
application. Ces ecrans nomment maintenant l'endpoint manquant.

---

## Avant de commiter

Rien n'est commite. L'etat courant contient:

**Le bit d'execution des scripts, deja mis dans l'index.** Tous les `.sh` du
depot etaient enregistres en mode `100644`, donc un juge qui clone sur Linux ou
macOS recevait "Permission denied" sur la premiere commande du README. Le mode
a ete corrige avec `git update-index --chmod=+x`; c'est une modification
indexee, elle doit entrer dans le commit.

**Des fichiers non suivis a ajouter.** Notamment `DEMARRAGE.md`,
`README.en.md`, les nouveaux composants sous `features/shared/`,
`features/admin/components/NotBuilt.jsx`, les migrations `0007` et `0008`, les
scripts `seed_admin.py`, `needs_flow.py`, `check_admin_login.py`, et les
fichiers PWA sous `public/`.

Verifier avant de commiter:

```bash
git status
git diff --cached --stat
```

Verifier qu'aucun secret ne part avec:

```bash
./scripts/security_audit.sh
```

Et confirmer que `.env` n'est pas dans la liste:

```bash
git status --porcelain | grep -E '(^|/)\.env$' || echo "aucun .env suivi"
```
