# NeoRé Heat Pump – integrace pro Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/cobratec/ha-neore/actions/workflows/validate.yml/badge.svg)](https://github.com/cobratec/ha-neore/actions/workflows/validate.yml)

> **English:** Unofficial Home Assistant integration for NeoRé heat pumps (Czech manufacturer NEOTA)
> with a controller reachable over Modbus TCP. Reads temperatures, heat meter, states and faults
> and lets you set the hot water and room setpoints and the heating curve. Uses Home Assistant's
> shared Modbus connection (HA 2026.10+). Install via HACS as a custom repository
> `https://github.com/cobratec/ha-neore`. The UI is translated to English and Czech;
> the documentation below is in Czech.

Neoficiální integrace pro tepelná čerpadla **NeoRé** s regulací přístupnou přes **Modbus TCP**.
Čte teploty, výkon a stav čerpadla a umožňuje měnit požadovanou teplotu teplé vody (TUV),
třeba pro ukládání přebytků z fotovoltaiky do bojleru.

> ⚠️ Integrace vznikla zpětnou analýzou registrů na čerpadle NeoRé 8 a výrobce ji nepodporuje.
> Zápis mění nastavení řídicí jednotky – používáte ji na vlastní riziko.

## Co integrace umí

| Entita | Typ | Popis |
|---|---|---|
| Teplá voda | `water_heater` | aktuální a požadovaná teplota TUV, nastavení teploty |
| Požadovaná teplota TUV | `number` | totéž jako číslo – pohodlné v automatizacích |
| Požadovaná teplota objektu | `number` | cílová teplota v místnosti (krok 0,1 °C) |
| Ekvitermní křivka −20 / −7 / +6 / +19 °C | `number` (konfigurace) | teploty topné vody hlavního okruhu |
| Venkovní / vnitřní teplota | `sensor` | °C |
| Teplota výstupu / zpátečky | `sensor` | °C |
| Teplota TUV | `sensor` | °C |
| Požadovaná teplota topné vody | `sensor` | aktuální hodnota z ekvitermní křivky, °C |
| IQ korekce | `sensor` | °C |
| Oběhové čerpadlo | `sensor` | % |
| Průtok vody | `sensor` | m³/h |
| Tlak vody | `sensor` | bar |
| Tepelný výkon | `sensor` | kW (kalorimetr) |
| Dodané teplo | `sensor` | kWh, rostoucí – lze použít v Energy dashboardu a pro výpočet COP |
| Motohodiny | `sensor` (diagnostika) | h |
| Výkon kompresoru | `sensor` | % (požadovaný výkon) |
| Hystereze TUV, teplota dezinfekce, zpoždění el. dohřevu | `sensor` (diagnostika) | aktuální nastavení |
| Stavový kód, Popis stavu | `sensor` (diagnostika) | kód a texty jako na displeji, např. `0073` |
| Porucha | `binary_sensor` | zapnuto, když čerpadlo hlásí poruchu |
| Chod, Ohřev TUV, El. dohřev TUV, Bivalence, Oběhové čerpadlo | `binary_sensor` | stav provozu |
| Vysoký tarif, Útlum, Odtávání, Dezinfekce | `binary_sensor` | stav provozu |
| Další stavy | `binary_sensor` (diagnostika) | topení/TUV zapnuto, stupně bivalence, zahřívání, protizámrazová ochrana, odvzdušnění |

Komunikace běží přes sdílené Modbus spojení vestavěné integrace `modbus` (knihovna `modbus-connection`). Čerpadlo se proto zobrazí v panelu **Nastavení → Konektivita → Modbus** a s ostatními integracemi se stejnými parametry sdílí jedno spojení. Logika zařízení je v `device.py` bez závislosti na Home Assistantu.

## Požadavky

- Home Assistant 2026.10 nebo novější (sdílené Modbus spojení)
- Tepelné čerpadlo NeoRé s Modbus TCP (port 502) dostupné v síti
- IP adresa čerpadla (doporučeno nastavit pevnou v routeru)

## Instalace

### Varianta A: HACS (doporučeno)

1. HACS → ⋮ → **Vlastní repozitáře** (Custom repositories).
2. Vložte `https://github.com/cobratec/ha-neore`, kategorie **Integration**.
3. Vyhledejte **NeoRé Heat Pump** a nainstalujte.
4. Restartujte Home Assistant.

### Varianta B: ručně

1. Zkopírujte složku `custom_components/neore` do složky `config/custom_components/`
   ve vašem Home Assistantu (přes Samba share, File editor nebo Studio Code Server).
   Výsledná cesta musí být `config/custom_components/neore/manifest.json`.
2. Restartujte Home Assistant.

### Přidání čerpadla

1. **Nastavení → Zařízení a služby → Přidat integraci → NeoRé Heat Pump.**
2. Vyplňte IP adresu, port (502) a unit ID (1).
3. Po úspěšném připojení se vytvoří zařízení se všemi entitami.

### Volby

V **Nastavení → Zařízení a služby → NeoRé Heat Pump → Konfigurovat** lze změnit:

- interval čtení (výchozí 30 s),
- povolený rozsah požadované teploty TUV (výchozí 40–55 °C, technicky max. 63,5 °C).

## Přechod z ruční Modbus konfigurace v YAML

Pokud čerpadlo už čtete přes integraci `modbus:` v `configuration.yaml`:

1. Nainstalujte a přidejte tuto integraci a ověřte, že entity ukazují správné hodnoty.
2. Upravte automatizace a dashboardy na nové entity. Přesná entity ID najdete v
   **Nastavení → Zařízení a služby → NeoRé Heat Pump → zařízení**.
3. Z `configuration.yaml` odstraňte hub `Heatpump` z `modbus:`, template `number`
   pro teplotu TUV a template senzory, které na hub odkazovaly.
4. Restartujte Home Assistant.

Souběh obou nevadí: pokud má YAML hub stejnou adresu a port, sdílí s integrací jedno spojení.

## Příklad: ukládání přebytků FVE do bojleru

Entity ID upravte podle své instalace (střídač Solax, název zařízení).

```yaml
alias: Hot water – PV surplus storage
mode: single
triggers:
  - trigger: numeric_state
    entity_id: sensor.solax_grid_export
    above: 3500
    for: "00:10:00"
    id: start
  - trigger: numeric_state
    entity_id: sensor.solax_battery_capacity
    above: 95
    id: start
  - trigger: numeric_state
    entity_id: sensor.solax_battery_capacity
    below: 80
    id: stop
  - trigger: time
    at: "16:30:00"
    id: stop
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: start
          - condition: time
            after: "10:00:00"
            before: "16:00:00"
          - condition: numeric_state
            entity_id: sensor.solax_battery_capacity
            above: 95
          - condition: numeric_state
            entity_id: sensor.solax_grid_export
            above: 3500
        sequence:
          - action: number.set_value
            target:
              entity_id: number.neore_heat_pump_hot_water_setpoint
            data:
              value: 52
      - conditions:
          - condition: trigger
            id: stop
        sequence:
          - action: number.set_value
            target:
              entity_id: number.neore_heat_pump_hot_water_setpoint
            data:
              value: 48
```

### Výpočet COP

Pokud měříte příkon čerpadla (např. Shelly), lze z denních přírůstků **Dodaného tepla**
a odebrané elektřiny spočítat skutečný COP, třeba přes dva `utility_meter` a template senzor.

Integrace zapisuje jen při skutečné změně hodnoty, takže opakované volání se stejnou
teplotou paměť řídicí jednotky nezatěžuje. Po zápisu hodnotu ověří zpětným čtením
a při nesouhlasu vrátí chybu.

## Řešení problémů

- **Diagnostika:** Nastavení → Zařízení a služby → NeoRé Heat Pump → ⋮ → Stáhnout diagnostiku. Obsahuje dekódované hodnoty i surové registry (bez IP adresy) – přiložte ji k hlášení chyby.

- **„Cannot read data“ při přidání:** ověřte IP a port (např. `Test-NetConnection <IP> -Port 502`
  ve Windows) a unit ID (obvykle 1).
- **Entity jsou nedostupné:** čerpadlo neodpovídá; v logu hledejte `custom_components.neore`.
- **Ladicí log:**
  ```yaml
  logger:
    logs:
      custom_components.neore: debug
      modbus_connection: debug
  ```

## Technické detaily

Mapa registrů a kódování je v [docs/registers.md](docs/registers.md).

## Nástroje

Ve složce [`tools/`](tools/) je skript `neore_modbus.py`, kterým byla mapa registrů zjištěna
(vyčtení všech registrů, porovnání snímků, logování a hledání hodnot). Hodí se při rozšiřování
integrace nebo u jiných modelů NeoRé. Webový server řídicí jednotky navíc ve stránkách `PAGExx.XML`
uvádí přesné adresy proměnných – viz [docs/registers.md](docs/registers.md).

## Licence

[MIT](LICENSE). Integrace není spojena s výrobcem NeoRé ani jím podporována; název a logo NeoRé
patří jejich vlastníkovi a jsou použity pouze pro identifikaci zařízení.
