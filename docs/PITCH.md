# VORA: l'argumentaire

Ce document sert a deux choses: preparer la presentation, et repondre aux
questions difficiles sans improviser. Tous les chiffres cites ici sont
reproductibles par une commande, indiquee a chaque fois.

---

## 1. En une phrase

**Nous n'avons pas ajoute le partage a une application de taxi. Nous avons
numerise le modele du taxi partage qui existe deja a Yaounde, et ajoute la
course exclusive par-dessus.**

C'est la phrase qui doit passer en premier. Tout le reste en decoule.

---

## 2. Le probleme, tel qu'il se pose ici

Trois faits que toute application de VTC importee ignore:

1. **Personne n'a d'adresse.** On se deplace par carrefours, stations, marches
   et quartiers. Un geocodeur concu pour des noms de rue ne peut pas servir ce
   marche, quelle que soit sa qualite.
2. **Le partage n'est pas une option, c'est la norme.** Le taxi de Yaounde fait
   du ramassage le long d'un corridor a un tarif par place. Une application qui
   traite le partage comme un supplement se bat contre l'usage reel.
3. **Tout se paie en especes.** Il n'existe aucun rail de paiement sur lequel
   prelever automatiquement. Chaque mecanisme de confiance doit fonctionner
   sans qu'un centime bouge.

---

## 3. Les deux paris

### Pari 1: la recherche par reperes

5454 lieux curates. "warda carefour", mal orthographie et dans le desordre,
retrouve Carrefour Warda. Le resultat dit **pourquoi** il a ete trouve, au lieu
de deviner avec assurance.

**90,5 % de reussite dans les trois premiers resultats sur 42 requetes reelles.**
100 % sur les accents et les formes exactes.

```bash
.venv/bin/python scripts/geo_eval.py
```

### Pari 2: le corridor

Deux reservations partagent un vehicule. Chacune paie sa propre portion,
mesuree le long du trajet reellement parcouru avec PostGIS, et non un tarif
coupe en deux.

| | Paie | Aurait paye seul | Economise |
|---|---|---|---|
| Passager A | 1550 | 2300 | 750 |
| Passager B | 900 | 1300 | 400 |
| **Le chauffeur encaisse** | **2450** | 2300 | **+150** |

Les deux passagers paient moins **et** le chauffeur gagne plus, parce que le
vehicule n'est pas vendu a une seule personne. C'est la proposition entiere, et
elle tient en une ligne.

```bash
.venv/bin/python scripts/corridor_flow.py
```

---

## 4. Ce qui est verifie, pas seulement affirme

| | | Commande |
|---|---|---|
| tests unitaires | 173 | `.venv/bin/python -m pytest` |
| suites d'acceptation | 16, toutes passantes | `./scripts/acceptance.sh` |
| fuites IDOR | 0 sur 10 routes | `scripts/idor_sweep.py` |
| acceptations simultanees | 1 gagnant sur 20 | `scripts/race_test.py` |
| matrice d'annulation | 20 cellules sur 20 | `scripts/cancel_matrix.py` |
| degradation | 17 verifications | `scripts/degradation_test.py` |
| secrets dans l'historique | aucun | `./scripts/security_audit.sh` |

---

## 5. Ce que nous ne pretendons pas avoir

A dire avant qu'on nous le demande. Un jury qui decouvre lui-meme une lacune
non annoncee cesse de croire le reste.

- Aucune evaluation du chauffeur. La note est affichee, aucun endpoint ne la
  collecte.
- L'administration se limite a deux endpoints. Les autres ecrans le disent au
  lieu d'inventer des lignes.
- Le paiement est en especes. L'interface de fournisseur existe, aucun
  prestataire reel n'est integre.
- Pas de notification poussee.

Liste complete: `README.md` §17.

---

## 6. La feuille de route: la course programmee avec acompte

**Non construite.** C'est la suite logique des deux paris, et la reponse au
seul probleme que notre registre de dettes ne resout qu'a moitie.

### Le mecanisme

1. **La veille**, le passager reserve: une heure, un point de rendez-vous
   precis (sa porte, ou un carrefour), et le choix de partager ou non.
2. **Un acompte est bloque** par mobile money au moment de la reservation. Il
   n'est ni verse au chauffeur ni encaisse par la plateforme. Il est retenu.
3. **Le chauffeur se presente** au point convenu. Un compteur demarre a
   l'arrivee constatee par le releve GPS du serveur, jamais a la declaration du
   chauffeur.
4. **Le passager arrive:** l'acompte est deduit du tarif, il ne paie que le
   solde en especes a la fin.
5. **Le passager ne vient pas dans le delai:** le chauffeur encaisse l'acompte
   et repart. Rien a reclamer, aucune dette a poursuivre.
6. **En partage:** chaque passager qui accepte une course programmee partagee
   depose son propre acompte, obtient son propre point de rendez-vous et son
   propre delai. Le chauffeur parcourt l'itineraire et attend le temps convenu
   a chaque point.

### Pourquoi cela vaut la peine

**Le passager fantome est le probleme non resolu d'un marche en especes.**
Aujourd'hui nous y repondons apres coup: des frais inscrits a un registre de
dettes qui bloque la reservation suivante. C'est reel, et c'est lent. L'acompte
y repond avant, et il regle le litige sans que personne ait a discuter.

**La planification vaut de l'argent.** Un chauffeur qui connait sa tournee de
6 h la veille ne tourne pas a vide pour la trouver. Le corridor cesse d'etre
une rencontre heureuse entre deux trajets et devient une tournee assemblee a
l'avance, avec un taux de remplissage qu'on peut prevoir au lieu de l'esperer.

**La symetrie rend la regle acceptable.** Le chauffeur n'est pas le seul a
etre protege. S'il ne se presente pas, l'acompte revient integralement au
passager, et c'est le releve GPS qui tranche, pas la parole de l'un contre
celle de l'autre.

### Ce sur quoi cela s'appuie, deja construit

Ce n'est pas un nouveau systeme. Quatre pieces existent et sont testees:

- **Le moteur de corridor:** contenance, plafond de detour, tarification par
  portion. La geometrie est faite.
- **Le releve GPS et son filtre de plausibilite:** c'est ce qui prouve qu'un
  chauffeur etait bien la et a bien attendu.
- **`ride_events`, en ajout seul et impose par un declencheur:** la couche de
  preuve sur laquelle un litige d'acompte repose.
- **`ledger_entries`, deja signe et en ajout seul:** l'acompte y est un
  nouveau `kind`, pas une nouvelle table.

### Pourquoi ce n'est pas livre

C'est la premiere fonctionnalite qui exige que de l'argent bouge reellement.
Conserver les fonds d'un client est une activite reglementee. La retenue doit
donc etre operee par un prestataire mobile money agree (MTN MoMo, Orange
Money), pas par nous. Cela se decide avec un partenaire et un cadre juridique,
pas en 48 heures. Nous preferons le dire que livrer une fausse sequestration.

---

## 7. Les questions difficiles

**Qui detient l'argent de l'acompte ?**
Pas nous. Un prestataire mobile money agree. Conserver les fonds d'un tiers
releve d'un agrement que nous n'avons pas et qu'une equipe de hackathon ne doit
pas pretendre avoir.

**Et si c'est le chauffeur qui ne se presente pas ?**
L'acompte revient integralement au passager et le manquement est inscrit au
dossier du chauffeur. Le releve GPS du serveur tranche, pas la parole de l'un
contre celle de l'autre.

**Combien de temps le chauffeur attend-il ?**
Assez peu pour qu'il ne soit pas immobilise, assez pour que ce soit juste. Le
point important est ailleurs: le compteur demarre a l'arrivee **constatee**,
pas a un bouton presse.

**Qu'est-ce qui empeche un chauffeur de declarer une fausse arrivee ?**
Le meme filtre de plausibilite qui empeche deja de gonfler un tarif. Une
arrivee est une position dans le releve du serveur, pas une declaration.

**Le partage n'est-il pas dangereux ?**
Deux reservations au maximum, et le second passager voyage a l'avant, seul. Le
premier peut monter avec ses proches; un inconnu qui rejoint reste une seule
personne, dans le champ de vision du chauffeur. Personne ne se retrouve assis a
l'arriere a cote d'un inconnu. Et le chauffeur est consulte avant chaque ajout,
jamais force.

**Comment gagnez-vous de l'argent ?**
Une commission sur la course. Elle n'est pas implementee: sans rail de paiement
elle se preleverait a la main, et nous avons prefere livrer l'abstraction de
paiement et dire que l'especes est le defaut honnete.

**Qu'est-ce qui vous protege d'un concurrent international ?**
Le dictionnaire de 5454 lieux est un actif de donnees, pas une ligne de code:
il se construit localement et se verifie sur le terrain. Le modele du corridor
est culturellement natif, pas une fonctionnalite ajoutee. Et notre posture
vis-a-vis de la Loi 2024/017 est dans le schema de la base, pas dans une
politique de confidentialite.

**Et la Loi No. 2024/017 ?**
Aucune donnee de sante, jamais. Les besoins decrivent ce que le chauffeur fait,
jamais qui est le passager: quelqu'un de grand et quelqu'un a mobilite reduite
choisissent la meme option et le systeme est incapable de les distinguer. Le
journal des courses est en ajout seul, impose par un declencheur, parce que la
notification de violation exigee par la loi repose dessus.

**Est-ce que cela passe a l'echelle ?**
La question du corridor ("cette ligne passe-t-elle pres de ces deux points, et
dans cet ordre") est un `ST_DWithin` et un `ST_LineLocatePoint` contre un index
GiST. C'est une recherche dans un index spatial, pas un parcours de toutes les
courses en cours.

---

## 8. La demonstration, dans l'ordre

```bash
./scripts/seed.sh && ./scripts/demo.sh --check
```

1. Taper "warda carefour", mal orthographie. Le lieu est retrouve, avec la
   raison du match.
2. Basculer Prive / Partage. Les deux tarifs, cote a cote, sur un seul ecran.
3. Deuxieme fenetre: le chauffeur passe en service. La demande arrive avec le
   tarif et les deux etapes.
4. Le code PIN: en grand chez le passager, quatre cases vides chez le
   chauffeur.
5. Le choix des besoins, avec la ligne "Nous n'enregistrons aucune information
   de sante" visible a l'ecran.

Comptes de demonstration et pieges a eviter: `README.md` §14 et
`DEMARRAGE.md` §6.
