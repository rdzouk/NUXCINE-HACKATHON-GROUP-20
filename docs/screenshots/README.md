# Captures d'ecran

Produites par `node scripts/screenshots.mjs` contre la pile en marche et
la base de donnees chargee. Rien ici n'est une maquette: une course est
creee par l'API entre deux captures pour que les ecrans de course
existent vraiment.

| Fichier | Ce que cela montre |
|---|---|
| `01-splash.png` | L'ecran d'ouverture: les deux paris du produit et le code PIN. |
| `02-login.png` | Connexion par numero de telephone. Aucun mot de passe nulle part. |
| `03-otp.png` | Quatre cases, et le code affiche a l'ecran pour les numeros de test. |
| `04-home.png` | Destinations recentes, tirees des courses reelles du passager. |
| `05-landmark-search.png` | Pari 1: un carrefour mal orthographie et dans le desordre, retrouve, avec la raison du match. |
| `06-quote.png` | Les deux tarifs cote a cote: prive et partage, calcules par le serveur. |
| `07-corridor-mode.png` | Pari 2: payez votre place, avec le selecteur de places. |
| `08-ride-needs.png` | Sept besoins. Chacun decrit ce que le chauffeur fait, aucun n'enregistre quoi que ce soit sur la personne. |
| `09-history.png` | Les trajets du passager, servis par GET /rides. |
| `10-profile.png` | Profil et bascule de langue. |
| `11-notifications.png` | Construites a partir des courses reelles, et l'ecran le dit. |
| `12-privacy.png` | Ce qui est collecte, et ce qui est refuse. |
| `13-driver-offduty.png` | Hors service, avec la raison pour laquelle rien n'arrive. |
| `14-driver-offer.png` | En service: la demande arrive avec le tarif et les deux etapes. |
| `15-driver-request.png` | La demande en detail, avec ce que le passager a demande, avant d'accepter. |
| `16-driver-earnings.png` | Gains, sommes sur les courses terminees, honnete sur sa propre portee. |
| `17-driver-safety.png` | Ecran de securite du chauffeur. |
| `18-pickup-pin.png` | Le code de prise en charge, chez le passager uniquement. Le chauffeur ne le recoit jamais. |
| `19-admin-overview.png` | Chiffres reels, derives de la liste des chauffeurs. Rien de fabrique. |
| `20-admin-kyc.png` | La file KYC, avec la decision reellement branchee. |
| `21-admin-notbuilt.png` | Un ecran non construit le dit, au lieu d'afficher des lignes inventees. |

## Regenerer

```bash
docker compose up -d && ./scripts/seed.sh
npm i --no-save puppeteer@22.15.0
node scripts/screenshots.mjs
```

Sur une machine sans les bibliotheques systeme que Chromium exige et sans
droits root, elles peuvent etre depaquetees a cote:

```bash
mkdir -p /tmp/chromedeps && cd /tmp/chromedeps
apt-get download libnss3 libnspr4 libasound2t64
for d in *.deb; do dpkg -x "$d" root; done
export LD_LIBRARY_PATH=/tmp/chromedeps/root/usr/lib/x86_64-linux-gnu
```
