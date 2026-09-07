# The gazetteer

A dataset of **5454 landmarks** across Yaounde and Douala, built to answer the
question people here actually ask a mobility app: not "what is the street
address" but "which carrefour".

This is a deliverable in its own right, not a lookup table that fell out of the
build. It is the thing that makes Bet 1 work.

## What is in it

| Category | Count | Why it matters |
|---|---|---|
| business | 1738 | Shops and fuel stations used as reference points |
| school | 1227 | Schools name whole neighbourhoods here |
| quartier | 994 | The unit people give a driver |
| admin | 848 | Post offices, police, ministries |
| hospital | 412 | Hospitals are primary landmarks |
| station | 208 | Fuel stations, bus and taxi stands |
| market | 24 | Marches, the busiest destinations in the city |
| carrefour | 3 | See below |

Yaounde 4003, Douala 1451.

## How it was built

```bash
python scripts/build_gazetteer.py    # parse the Geofabrik Cameroon extract
python scripts/curate_gazetteer.py   # add the vocabulary OSM does not carry
python scripts/seed_landmarks.py     # load into Postgres
```

The output, `data/landmarks.seed.json`, is committed. A teammate seeds a fresh
database without a 223 MB download or a twelve-minute parse.

## The carrefour problem, and how it was solved honestly

The extract yielded **three** landmarks tagged as carrefours. Carrefours are the
single most important category for how people name places in Yaounde. OSM
simply does not tag them, and that gap is exactly what the build plan
anticipated when it said to hand-add what OSM misses.

The tempting fix is to type out a list of fifty carrefours with hand-placed
coordinates. **That would be fabricating survey data**, and a wrong coordinate
is worse than a missing one: it sends a driver confidently to the wrong place.

So `curate_gazetteer.py` adds **no new locations**. For each well-known place
name it finds the OSM node that already exists there and attaches the name-forms
people actually say:

```
OSM has:     "Marche Obili"        (a real, surveyed coordinate)
we add:      "Obili"
             "Carrefour Obili"
             "Rond-point Obili"
             "Obili carrefour"
```

The coordinate stays OSM's. Only the vocabulary is ours. That is what lets the
exact-alias layer hit on "carrefour obili", a query OSM alone answers with
nothing.

Of 63 curated names, **44 matched a real node and 19 did not**. The 19 have no
alias and no invented position. They stay missing until somebody surveys them
or adds them to OpenStreetMap, and `curate_gazetteer.py` prints them by name on
every run so the gap stays visible.

## Why aliases are generated, not typed

One OSM row becomes the several things a person might say. Each rule exists
because it is how names are actually shortened in speech:

| Written | Also said |
|---|---|
| Carrefour Warda | Warda, Warda carrefour |
| Rond-point Nlongkak | Nlongkak |
| Total Nsimeyong | Nsimeyong |
| Ngoa-Ekelle | Ngoa Ekelle |
| Marche Central | Marché Central, Central |

## Measured performance

`scripts/geo_eval.py` runs 42 realistic queries and reports a top-3 hit rate.

```
top-3 hit rate: 39/42  92.9%

  accents      6/6   100.0%     written with and without accents
  exact       10/10  100.0%     the name as written
  reordered    3/3   100.0%     words in a different order
  misspelled   7/8    87.5%     realistic typos
  quartier     7/8    87.5%     a neighbourhood, not a landmark
  shortened    6/7    85.7%     how people actually shorten it
```

The three misses are informative rather than embarrassing:

- **`total nsimeyong`** returns three stations literally named "Total". A
  ranking problem: a bare brand name outranks the branch someone meant.
- **`bieym assi`** transposes two letters and falls below the trigram
  threshold.
- **`emana`** has no node in the extract at all. It is one of the 19, and
  returning nothing is the correct answer to a place we do not know.

### On the honesty of that number

The fixtures were written from how places are named here, not by reading the
seed file. Matching is by expected substring rather than by landmark id, because
a fixture keyed to an id only ever confirms that the row it was written from
still exists.

That still leaves one bias worth stating: the same person wrote the extractor
and the fixtures, so this measures the cascade rather than independently
auditing coverage. Having a teammate who has not seen the seed data write a
second fixture file is the honest next step, and it costs twenty minutes.
