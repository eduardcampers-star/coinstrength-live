# Willy Wortel Research Checkpoint — EMA / 60m Deceleration
Datum: 2026-10-06

## Status
OBSERVER-ONDERZOEK.

Geen productiestrategie, shadowregels, thresholds of live tradingregels gewijzigd.
Principe blijft: meten -> verzamelen -> pas daarna beslissen.

---

## 1. Historische dataset

Gereconstrueerde v0.4-marktevents uit Git-history van film60_summary.json.

- Marktevents: 179
- Bruikbare coin-cases: 4833
- Follow-through dekking: ongeveer 99%
- Metingen per case:
  - vooraf: -60 / -40 / -20 / event
  - vervolg: +5 / +15 / +30 / +45 / +60 minuten

Richting is genormaliseerd:
positief vervolg = beweging in de onderzochte tegenbewegingsrichting.

---

## 2. Hoofdbevinding: afremming na forse beweging

Positieve voorafgaande 60m-beweging:

- mediaan: +0.593%
- P75: +1.132%

Afremmers werden vergeleken met doorstampers.

### Sterkste 25% voorafgaande beweging (>= +1.132%)

AFREMMERS:
- N = 223
- +5:  +0.061% / 57.8% hit
- +15: +0.229% / 59.6% hit
- +30: +0.213% / 59.2% hit
- +45: +0.195% / 60.5% hit
- +60: +0.399% / 61.0% hit

DOORSTAMPERS:
- N = 138
- +5:  +0.005% / 55.8%
- +15: +0.097% / 57.2%
- +30: +0.251% / 63.0%
- +45: +0.147% / 55.1%
- +60: +0.220% / 61.6%

Voorlopige conclusie:
afremming bevat vooral informatie nadat eerst een behoorlijke beweging heeft plaatsgevonden.

---

## 3. Signaalsterkte per voorafgaande 60m-beweging

Kwartielen:

- Q25 = +0.285%
- Q50 = +0.593%
- Q75 = +1.132%

AFREMMERS:

Q1 laag:
- N 185
- +5  -0.031% / 43.2%
- +15 -0.011% / 48.1%
- +30 -0.027% / 49.2%
- +45 -0.007% / 54.1%
- +60 -0.037% / 56.2%

Q2:
- N 243
- +5  +0.021% / 51.4%
- +15 +0.022% / 58.4%
- +30 +0.111% / 61.7%
- +45 +0.103% / 57.2%
- +60 +0.105% / 56.4%

Q3:
- N 272
- +5  +0.048% / 58.8%
- +15 +0.085% / 56.6%
- +30 +0.193% / 60.7%
- +45 +0.178% / 58.8%
- +60 +0.217% / 57.6%

Q4 sterkste:
- N 223
- +5  +0.061% / 57.8%
- +15 +0.229% / 59.6%
- +30 +0.213% / 59.2%
- +45 +0.195% / 60.5%
- +60 +0.399% / 61.0%

Belangrijk:
de gemiddelde follow-through neemt duidelijk toe naarmate de voorafgaande beweging groter is.
Afvlakking zonder betekenisvolle voorafgaande beweging lijkt weinig bruikbaar.

---

## 4. Mate van vertraging binnen Q4

Q4 = voorafgaande 60m-beweging >= +1.132%.

Aantal Q4-afremmers: 223.

Restsnelheid t.o.v. eerste 20m-blok:

block2 / block1:
- P10 +0.15
- P25 +0.26
- mediaan +0.47
- P75 +0.70
- P90 +0.86

block3 / block1:
- P10 -0.45
- P25 -0.28
- mediaan -0.09
- P75 +0.14
- P90 +0.31

Typisch beeld:
forse beweging -> tweede blok duidelijk trager -> laatste blok vrijwel vlak of lichte omslag.

---

## 5. Follow-through per mate van laatste afremming

Kwartielen op block3/block1:

- Q25 = -0.28
- Q50 = -0.09
- Q75 = +0.14

D1 VERST GEDRAAID (< -0.28), N=55:
- +5  -0.028% / 45.5%
- +15 +0.192% / 56.4%
- +30 +0.120% / 47.3%
- +45 +0.150% / 60.0%
- +60 +0.393% / 60.0%

D2 (-0.28 tot -0.09), N=56:
- +5  +0.029% / 57.1%
- +15 +0.083% / 50.0%
- +30 +0.082% / 58.9%
- +45 +0.027% / 53.6%
- +60 +0.182% / 58.9%

D3 (-0.09 tot +0.14), N=56:
- +5  +0.098% / 62.5%
- +15 +0.249% / 66.1%
- +30 +0.338% / 71.4%
- +45 +0.301% / 64.3%
- +60 +0.404% / 58.9%

D4 MINST GEREMD (>= +0.14), N=56:
- +5  +0.143% / 66.1%
- +15 +0.393% / 66.1%
- +30 +0.310% / 58.9%
- +45 +0.303% / 64.3%
- +60 +0.619% / 66.1%

Voorlopige interpretatie:
volledig omgedraaid zijn vóór het event lijkt NIET noodzakelijk.
De interessantste zone lijkt te zijn:

forse voorafgaande beweging
-> duidelijke snelheidsafname
-> vlak / kleine resterende beweging
-> daarna tegenbeweging.

Niet als productieregel gebruiken zonder verdere validatie.

---

## 6. EMA20 zijonderzoek

Eerder observeronderzoek naar EMA20-reclaim:

Reclaim binnen 3 minuten:
- recovered N=33
- +30 gemiddeld ongeveer 0.000%, 16/33 positief
- +60 gemiddeld +0.213%, 21/33 positief

Niet recovered binnen 3 minuten:
- N=30
- +30 gemiddeld -0.115%, 9/30 positief
- +60 gemiddeld -0.228%, 9/30 positief

Interessant observerkenmerk, maar nog geen handelsregel.

---

## 7. Historische B-v2 8h reconstructie

Historische latest.json snapshots zijn via Git-history gereconstrueerd.

Proefmoment:
T en T-8h konden beide binnen ongeveer 2 minuten worden gevonden.

Historische 8h-rank dekking in kruistest:
- 4725 / 4833 cases
- 97.8%

B-v2 ranking gebruikt absolute rolling-8h beweging.

Eerste kruising met Q4-afremmers gaf geen bewijs dat hoogste absolute 8h-rank automatisch beter is.
Deze onderzoekstak is daarom voorlopig geparkeerd; niet verwarren met bewijs tegen v0.4B als strategie.

---

## 8. Belangrijkste onderzoeksvraag voor vervolg

Niet direct nieuwe filters toevoegen.

Eerst verder onderzoeken:

"Geeft een forse 30-60m beweging die daarna duidelijk snelheid verliest of vlakloopt een reproduceerbaar vroeg signaal voor een tegenbeweging in het volgende uur?"

Daarbij vooral:
- robuustheid over meer dagen / marktregimes;
- LONG en SHORT afzonderlijk;
- exacte timing binnen de afvlakking;
- MFE / MAE en pad na signaal;
- pas daarna eventueel EMA, 1m taker/volume en orderbook als timinglaag.

---

## 9. Bestanden in deze checkpointmap

- ema_reclaim_followthrough.py
- trend_deceleration_60m.py
- trend_deceleration_cross.py
- historical_8h_check.py
- trend_deceleration_8h_rank.py
- deceleration_signal_strength.py
- deceleration_degree.py

Dit checkpoint bewaart onderzoekslogica en conclusies van 6 oktober 2026.
