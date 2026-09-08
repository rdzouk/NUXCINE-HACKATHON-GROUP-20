# Manuel de demarrage

"Je viens de cloner votre depot. Que dois-je faire pour lancer le projet ?"

Reponse courte, sur une machine qui a deja Docker:

```bash
git clone git@github.com:rdzouk/NUXCINE-HACKATHON-GROUP-20.git
cd NUXCINE-HACKATHON-GROUP-20
cp .env.example .env
./scripts/gen_secrets.sh
docker compose up -d
./scripts/seed.sh
```

L'application est ensuite sur **http://localhost:8090**.

Le reste de ce document explique chaque etape, ce qui peut echouer, et
comment le verifier.

Pour voir a quoi ressemble le resultat avant de lancer quoi que ce soit:
[docs/screenshots/](docs/screenshots/), 21 captures de l'application en
marche.

---

## 1. Ce qu'il faut avoir

**Docker Desktop avec Compose v2, et rien d'autre.**

C'est volontaire: tout tourne dans des conteneurs, y compris les migrations et
les scripts de chargement des donnees. Une personne qui clone le depot une
heure avant la demonstration ne doit pas avoir a construire un environnement
Python en plus.

Verification:

```bash
docker --version
docker compose version
```

Prevoir environ 4 Go de memoire pour Docker. Le service de routage OSRM en
consomme a lui seul environ 1 Go.

**Sur Windows**, tout ce qui suit se lance depuis un terminal **WSL** (Ubuntu),
pas depuis `cmd.exe` ni PowerShell. Docker Desktop doit avoir l'integration WSL
activee. Le depot doit vivre dans le systeme de fichiers Linux
(`/home/vous/...`) et non dans `/mnt/c/...`: sur un montage Windows, les droits
d'execution des scripts sont perdus et les liaisons de volumes Docker sont
traduites de travers.

## 2. Cloner et configurer

```bash
git clone git@github.com:rdzouk/NUXCINE-HACKATHON-GROUP-20.git
cd NUXCINE-HACKATHON-GROUP-20
cp .env.example .env
```

`.env.example` est le modele documente. `.env` contient les vraies valeurs, il
est ignore par git, et il ne doit jamais etre commite.

### Generer les secrets

```bash
./scripts/gen_secrets.sh
```

Le script remplit `JWT_SECRET`, `QUOTE_HMAC_SECRET`, `SHARE_TOKEN_SECRET` et
`KYC_ENCRYPTION_KEY` avec 32 octets aleatoires chacun. Une cle distincte par
usage: compromettre l'une ne doit pas donner les autres.

Pour le faire a la main:

```bash
openssl rand -hex 32
```

### La seule cle a fournir soi-meme

Ouvrez `.env` et renseignez le jeton Mapbox:

```
VITE_MAPBOX_TOKEN=pk.votre_jeton_public
```

Pour l'obtenir: creez un compte sur [mapbox.com](https://account.mapbox.com),
ouvrez la page "Access tokens", et copiez le jeton public par defaut. Il
commence par `pk.`.

**Un jeton `sk.` est un secret serveur et l'application le refuse
explicitement**, plutot que de le livrer au navigateur.

Sans jeton, tout le reste fonctionne. La carte affiche a la place un espace
annonce comme tel, ce qui vaut mieux qu'un ecran blanc sans explication.

## 3. Demarrer la pile

```bash
docker compose up -d
```

Six services demarrent:

| Service | Role | Port sur l'hote |
|---|---|---|
| `postgres` | PostgreSQL 16 + PostGIS 3.4 | aucun |
| `redis` | Limitation de debit, presence | aucun |
| `osrm` | Calcul d'itineraires | aucun |
| `api` | FastAPI | 127.0.0.1:8080 |
| `caddy` | Sert l'application et relaie l'API | 8090 |
| `cloudflared` | Adresse publique HTTPS | aucun |

Seuls Caddy et l'API sont accessibles depuis l'hote, et l'API uniquement en
boucle locale. Tout le reste ne communique que sur le reseau interne.

Verifier que tout est en bonne sante:

```bash
docker compose ps
```

Si le port 8090 ou 8080 est deja pris sur votre machine, changez
`WEB_HOST_PORT` ou `API_HOST_PORT` dans `.env` et relancez.

## 4. Base de donnees et donnees de demonstration

```bash
./scripts/seed.sh
```

Le script attend que Postgres et Redis soient prets, applique les migrations
Alembic, puis charge:

```
  landmarks        5454
  drivers online     12
  vehicles           12
  with a ramp         3
  passengers          5
  admins              1
  completed rides    20
```

Il est idempotent: le relancer laisse le meme systeme, pas un systeme double.
Chaque semeur possede un bloc de numeros reserve et converge au lieu de
recreer.

Pour appliquer seulement les migrations, sans donnees:

```bash
docker compose exec -T api alembic upgrade head
```

## 5. Ouvrir l'application

**http://localhost:8090**

Pour y acceder depuis un telephone sur le meme reseau, utilisez l'adresse IP de
la machine, par exemple `http://192.168.1.20:8090`.

Pour une adresse publique en HTTPS, sans configuration:

```bash
docker compose logs cloudflared | grep trycloudflare.com
```

Un nom d'hote est genere a chaque demarrage. Pour un nom stable, creez un
tunnel dans le tableau de bord Cloudflare Zero Trust, collez son jeton dans
`CLOUDFLARE_TUNNEL_TOKEN` et mettez `CLOUDFLARE_TUNNEL_ARGS="tunnel run"`.

### Installer comme application

L'application est une PWA. Sur Android, ouvrez l'adresse dans Chrome, puis le
menu, puis "Ajouter a l'ecran d'accueil". Elle s'ouvre ensuite en plein ecran,
sans barre d'adresse.

## 6. Se connecter

Il n'y a pas de mot de passe. On saisit un numero, on recoit un code a quatre
chiffres.

Ces numeros sont dans la plage de test, donc **le code s'affiche directement a
l'ecran** au lieu d'etre envoye par SMS:

| Role | Numero |
|---|---|
| Passager | `+237600000008000` |
| Chauffeur | `+237600000009000` |
| Administrateur | `+237600000007000` |

Pour montrer les deux cotes en meme temps, ouvrez le passager dans une fenetre
normale et le chauffeur dans une fenetre de navigation privee. Sans cela, les
deux partagent le meme stockage local et se deconnectent mutuellement.

### Le parcours complet

1. **Passager**: se connecter, taper "warda" dans la destination, choisir un
   resultat, comparer les deux tarifs, confirmer.
2. **Chauffeur** (autre fenetre): se connecter, passer en service. La demande
   apparait dans les cinq secondes.
3. **Chauffeur**: accepter, puis demander son code au passager et le saisir.
4. **Passager**: suivre la course, partager le trajet, terminer.

Le chauffeur doit passer en service **avant** que le passager ne reserve. La
premiere vague de mise en relation part au moment de la creation de la course:
un chauffeur qui arrive apres n'est pas dans l'ensemble des candidats.

## 7. Verifier que cela fonctionne vraiment

### Avant une demonstration

```bash
./scripts/demo.sh --check
```

Repond en quelques secondes: la sante des composants, le nombre de lieux
charges, de chauffeurs en ligne et de courses dans l'historique. S'il manque
quelque chose, il le dit et donne la commande a lancer.

### La suite complete

```bash
./scripts/acceptance.sh
```

Seize suites, dans l'ordre des phases, jusqu'a l'audit de securite et
l'epreuve de degradation. Cette derniere arrete des conteneurs volontairement,
donc elle passe en dernier et seulement contre la pile locale.

Sur une machine avec peu de memoire, les suites peuvent se gener entre elles:
chaque connexion coute deux hachages argon2 a 32 Mio, deliberement. Augmentez
`ACCEPTANCE_SETTLE_S` pour espacer les suites. La bonne reponse est d'espacer
la charge, jamais d'affaiblir le hachage.

### Les tests unitaires

Ceux-la ont besoin d'un environnement Python, mais ni de Postgres ni de Redis:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

173 tests.

### L'audit de securite

```bash
./scripts/security_audit.sh
```

Vulnerabilites des dependances, secrets dans l'historique git, secrets sur le
disque, et huit garde-fous de production lus dans le code plutot qu'affirmes
dans un document.

### Explorer l'API a la main

`bruno/` est une collection [Bruno](https://usebruno.com) de la demonstration,
dans l'ordre ou l'on declencherait reellement les requetes, avec le jeton,
l'identifiant d'estimation et l'identifiant de course chaines automatiquement.
Ouvrez-la, choisissez l'environnement `local`, commencez a `02 auth`.

La documentation interactive est sur `/docs` en developpement, et desactivee en
production.

## 8. Quand quelque chose ne va pas

**La page est blanche ou toutes les pages renvoient 404**

Le paquet du client est copie dans l'image de Caddy au moment de la
construction. Apres un `npm run build`, il faut reconstruire l'image:

```bash
npm run build && docker compose up -d --build caddy
```

**Le code OTP n'arrive pas**

Verifiez que le numero commence par `+23760000000`. En dehors de cette plage,
l'application tente un envoi SMS reel, qui echoue si `HTTPSMS_API_KEY` est
vide. C'est delibere: mieux vaut echouer que d'annoncer un code qui n'arrivera
jamais.

**"Trop de tentatives"**

La limitation de debit fait son travail. Attendez, ou videz les seaux:

```bash
docker compose exec -T redis redis-cli --scan --pattern 'rl:*' | xargs -r docker compose exec -T redis redis-cli DEL
```

**Aucun chauffeur ne recoit la demande**

Le chauffeur doit etre passe en service avant la reservation, et sa position
doit dater de moins de deux minutes. Rechargez la flotte:

```bash
docker compose exec -T api python scripts/seed_drivers.py --count 12
```

**"Vous avez deja une course en cours"**

Une seule course active par passager, impose par un index unique partiel.
Annulez la precedente depuis l'ecran de suivi, ou changez de compte passager.

**Une modification du code Python ne change rien**

L'image de l'API contient les sources. `docker compose restart` ne suffit pas:

```bash
docker compose up -d --build api
```

**OSRM signale `not_configured`**

Le graphe de routage n'a pas ete construit. L'estimation continue de
fonctionner avec un repli haversine, **annonce comme tel** dans la reponse.
Pour construire le graphe:

```bash
./docker/osrm/prepare.sh
```

Comptez plusieurs minutes et environ 223 Mo de telechargement.

**Docker consomme toute la machine**

```bash
docker compose stop osrm cloudflared
```

L'application continue de fonctionner: le routage bascule sur le repli, et
l'acces public disparait mais pas l'acces local.

## 9. Tout arreter

```bash
docker compose down
```

Pour effacer aussi les donnees et repartir de zero:

```bash
docker compose down -v && docker compose up -d && ./scripts/seed.sh
```
