# Mapa Modbus registrů NeoRé

Hodnoty byly zjištěny měřením na čerpadle **NeoRé 8** (split Fujitsu, regulace s dotykovým
panelem, Modbus TCP na portu 502, unit ID 1) a porovnáním s displejem. Výrobce mapu
registrů nezveřejňuje, u jiných modelů nebo verzí firmwaru se adresy mohou lišit.

## Model paměti

Řídicí jednotka zpřístupňuje svou paměť jako **holding registers** (funkce 3, adresy 0–9999).
Každý registr nese dva bajty paměti v pořadí **little-endian** (nižší bajt první):

```
bajt paměti 2·r     = registr r & 0xFF
bajt paměti 2·r + 1 = registr r >> 8
```

Řídicí jednotka má vestavěný webový server. Jeho stránky (`PAGExx.XML`) uvádějí proměnné
ve tvaru `__R<offset>_<typ>`, kde offset je přímo bajtový offset v této paměti
(např. `__R2079_REAL` = float na bajtu 2079, `__R2603.6_BOOL` = bajt 2603, bit 6).
Z XML a XSL stránek webu tak lze přesně určit adresy, typy i význam hodnot.

Hodnoty jsou uložené jako zabalené struktury: float32 little-endian, často **nezarovnané**
na hranici registru (začínají v horním bajtu registru). Float zarovnaný na registr
odpovídá v HA nastavení `data_type: float32`, `swap: word`.

## Hodnoty

Offset = bajtový offset v paměti, registry = které registry hodnota zabírá.

| Offset | Registry | Typ | Význam (displej) |
|---|---|---|---|
| 1 | 0–2 | float | **Požadovaná T TUV** °C (parametr, zapisovatelný) |
| 5–17 | 2–8 | float ×4 | Pravděpodobně ekvitermní křivka 2. okruhu (42 / 32 / 26 / 22 °C), neověřeno |
| 47, 51, 55, 59 | 23–31 | float ×4 | **Ekvitermní křivka hlavního okruhu** – teplota vody pro −20 / −7 / +6 / +19 °C (zapisovatelné) |
| 63–75 | 31–37 | float ×4 | Venkovní body křivky −20 / −7 / +6 / +19 °C |
| 413 | 206–208 | float | **Požadovaná T objektu** °C (parametr, zapisovatelný) |
| 2062 | 1031–1032 | float | Ekviterm – aktuální požadovaná teplota topné vody °C |
| 2079 | 1039–1041 | float | Průtok vody m³/h |
| 2083 | 1041–1043 | float | Aktuální výkon (kalorimetr) kW |
| 2087 | 1043–1045 | float | Dodaný výkon (kalorimetr) kWh – čítač, při záporném výkonu (odtávání) klesá |
| 2216 | 1108–1109 | float | Požadovaný výkon % – kopie hodnoty 2066 (integrace používá 2066) |
| 2226 | 1113–1114 | float | Požadovaná T TUV (kopie parametru) |
| 2295 | 1147–1149 | float | Tlak vody bar |
| 2550 | 1275–1276 | float | Venkovní teplota °C |
| 2554 | 1277–1278 | float | Teplota výstupu °C |
| 2558 | 1279–1280 | float | Teplota TUV °C |
| 2574 | 1287–1288 | float | Teplota zpátečky °C |
| 2591 | 1295–1297 | float | Výkon oběhového čerpadla % |
| 4244 | 2122–2123 | float | Teplota objektu (čidlo) °C, nepoužito |
| 2066 | 1033–1035 | float | Požadovaný výkon % (velké číslo u ventilátoru, používá web) – požadavek regulace, ne skutečný výkon kompresoru |
| 2092 | 1046–1047 | float | Vrat (kalorimetr) °C |
| 2191 | 1095–1097 | float | Objekt °C (hodnota zobrazená na panelu) |
| 2276 | 1138–1139 | float | IQ korekce °C (zobrazená) |
| 2361 | 1180–1182 | float | Otáčky kompresoru rps (u split jednotky Fujitsu trvale 0) |
| 2365 | 1182–1184 | float | Otáčky ventilátoru rpm (u split jednotky Fujitsu trvale 0) |
| 2253 | 1126–1128 | float | Ekviterm 2. okruhu °C |
| 2566 / 2570 / 2578 | | float | Aku / Bazén / 2. okruh °C (155 = čidlo nepřipojeno) |
| 2605 | 1302–1304 | uint32 | Motohodiny h |
| 387 | 193–195 | float | Požadovaná T chladící vody °C |
| 391 | 195–197 | float | Hystereze TUV °C |
| 396 | 198–199 | TIME (uint32 ms) | Zpoždění el. dohřevu TUV |
| 400 | 200–201 | float | Teplota dezinfekce TUV °C |
| 593 | 296–298 | float | Korekce výstupní vody °C |
| 607 | 303–305 | float | Velikost IQ korekce |
| 2243–2245 | | uint8 ×3 | Hodiny řídicí jednotky (h, min, s) |

### Stavové bity

Popisy podle panelu. „Inverzní“ znamená, že panel zobrazuje popisek, když je bit 0.

| Bit | Význam |
|---|---|
| 0.0 | Topení zapnuto (tlačítko Chod) |
| 0.1 | TUV zapnuto (tlačítko TUV) |
| 2061.0 | Porucha (v záhlaví „Porucha:“ + kód) |
| 2188.3 | Bivalence |
| 2225.0 | Režim topení (červený pruh; 0 = modrý) |
| 2225.1 | Ohřev TUV |
| 2225.2 | El. dohřev TUV |
| 2252.2 | Útlum (inverzní; ověřeno – při útlumu klesne ekvitermní teplota o hodnotu útlumu) |
| 2252.5 | Vysoký tarif – topení (inverzní, ověřeno proti HDO) |
| 9039.0 | Vysoký tarif – TUV (inverzní, ověřeno proti HDO) |
| 2261.0 | Zahřívání |
| 2266.1 | „chod“ u tlačítka Chod – stav podřízené jednotky v kaskádě (Slave), u samostatného čerpadla stále 0; integrace odvozuje chod z tepelného výkonu ≥ 0,5 kW |
| 4192.1 | Chyba (u tlačítka Chod) |
| 601.1 | Slave |
| 2294.2 | Bazén ohřev |
| 2603.0 | Oběhové čerpadlo topení |
| 2603.5 | Oběhové čerpadlo / ventil TUV (ikona) |
| 2603.6 / 2603.7 | Bivalence 1. / 2. stupeň |
| 805.0 | Vysoušení podlah |
| 2230.1 | Příliš nízká venkovní teplota – topí jen bivalentní zdroj (ikona) |
| 2294.0 | Provoz sekundárního zdroje (ikona; 0 = ikona venkovní jednotky) |
| 9041.0 | Ohřev TV blokován časovým programem (inverzní, ikona měsíce) |
| 18961.0 | Ekonomický provoz (ikona „e“: výstup ≤ 45 °C a výkon < 50 %) |
| 8768.0 | Antilegionella – el. ohřev zásobníku (ikona legionely; podle manuálu sobota 1:00–10:00) |
| 10302.0 | Protizámrazová ochrana |
| 18440.0 | Odvzdušnění |
| 18440.2 | Odtávání (ikona) – jen s komunikačním modulem MX; u splitu Fujitsu bez modulu stále 0 |

### Texty a poruchy

| Offset | Typ | Význam |
|---|---|---|
| 18880 | STRING | Kód stavů a poruch, např. `0073` |
| 18982, 19063, 19144, 19225 | STRING[80] | Popis aktuálního stavu / poruchy (4 řádky) |
| 18962–18980 | UINT ×10 | Historie poruch – kódy |
| 137, 146, … 218 (krok 9) | DT | Historie poruch – datum a čas |

Registry 63–64 obsahují kopii kódu stavů (každý bajt jedna číslice).

Význam číslic podle manuálu výrobce k podobnému modelu (pořadí číslic se u tohoto modelu
může lišit – např. kód `0073` zde znamená vadné čidlo aku nádoby a 2. okruhu):

| Číslice | Hodnota | Význam |
|---|---|---|
| 1. | 1 / 2 / 3 / 4 | Zámrazová ochrana / Nedostatečný průtok / Porucha venkovní jednotky / Nízký tlak vody |
| 2. | 1,2 / 3,4 | Vadné čidlo teploty výstupní / vratné vody |
| 3. | 1,2 / 3,4 | Vadné čidlo teploty bazénu / 2. okruhu |
| 4. | 1,2 / 3,4 / 5,6 / 7,8 | Vadné čidlo venkovní / objektu / TV / akumulační nádoby |

První dvě číslice signalizují kritickou poruchu, při které je provoz omezen nebo zastaven.
Nepřipojená čidla (aku, 2. okruh, bazén) se hlásí trvale a provoz neomezují.

## Poznámky z manuálu výrobce

- **Útlumová tabulka:** dvě časová pásma pro každý den. *Uvnitř* pásma pracuje čerpadlo normálně,
  *mimo* něj je v útlumu (pásma jsou tedy časy komfortu). Útlum snižuje teplotu výstupní vody
  o nastavenou hodnotu; při útlumu 0 °C se časy neprojeví.
- **Doporučená křivka pro podlahové topení:** −20 °C → 38, −7 °C → 33, +6 °C → 28, +19 °C → 22 °C.
  Pro podlahové topení se doporučuje regulace jen podle křivky (bez IQ ekvitermu).
- **Bivalentní zdroj:** 1. stupeň 2 kW, 2. stupeň 4 kW.
- **Zpoždění el. dohřevu TV** doporučené výrobcem: 200 l – 40 min, 300 l – 60 min, 400 l – 90 min.
- **Doporučená teplota TV:** 44–48 °C.

## Zápis

Parametry se mění funkcí 6 (zápis jednoho registru) metodou read-modify-write: přečtou se
registry, které float zabírá, v paměťovém obrazu se přepíšou 4 bajty a zapíšou se jen
registry, které se změnily (od méně významného). Sousední bajty jiných parametrů zůstanou
zachované.

- **Požadovaná T TUV** (offset 1): panel umožňuje jen celé stupně (integrace také); mění se jen registr 1,
  hodnota `(T − 32) × 1024` (32–64 °C). Ověřeno – změna se ihned projeví na displeji
  a přežije restart.
- **Požadovaná T objektu** (offset 413): mění se registry 206 a 207. Ověřeno.
- **Ekvitermní křivka** (offsety 47–59): pro celé stupně se mění jeden registr. Ověřeno.

| T TUV °C | registr 1 |
|---|---|
| 45 | 13312 |
| 48 | 16384 |
| 50 | 18432 |
| 52 | 20480 |
| 55 | 23552 |

Zápis do kopií (např. 1113) se neprojeví, řídicí program je přepisuje. Parametry se ukládají
do paměti s omezeným počtem zápisů – nezapisujte periodicky, jen při změně.

## Pozorování

- Kompresor se při ohřevu TUV vypíná na ochranu při výstupní teplotě ~55–56 °C, v bojleru
  (250 l, výměník 3 m²) to odpovídá maximu ~50 °C. Vyšší teplotu dohřívá elektrická patrona
  po uplynutí „Zpoždění el. dohřevu TUV“.
- Příkon při ohřevu TUV (80 %) je ~3,4–3,5 kW.
- Při ohřevu TUV se požadavek (2066) drží na hodnotě „Výkon dobíjení TUV“ (servisní menu,
  u testovaného čerpadla 80 %), i když kompresor stojí po dosažení ochranné teploty výstupu. Ventil zůstává
  v poloze TUV a oběhové čerpadlo vede vodu přes výměník v bojleru – bojler tak ztrácí
  ~0,7 kW tepla, dokud požadavek neskončí (setpoint, vysoký tarif nebo el. dohřev).
- Ohřev TUV začíná při poklesu pod *setpoint − hystereze*.
- Servisní obrazovka „Data venkovní jednotky“ (teploty, otáčky, BDEF odtávání) je bez
  komunikačního modulu MX prázdná – regulace s jednotkou Fujitsu komunikuje jen přes
  požadavek výkonu.
