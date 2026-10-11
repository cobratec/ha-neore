"""NeoRé heat pump device library (no Home Assistant imports).

The controller exposes its RAM as holding registers. Each register carries two
bytes of little-endian memory (low byte first), so the whole register space is
one little-endian byte image: memory byte offset = 2 * register (+1 for the high
byte). The offsets below are the ones the controller's built-in web server uses
(``__R<offset>_<type>``). Values are packed structs; floats are often not
register-aligned.

Communication goes through ``modbus_connection.ModbusUnit``.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit


# --------------------------------------------------------------------------- memory map


@dataclass(frozen=True)
class Value:
    """A value in the controller memory image (offsets as used by the built-in web server)."""

    offset: int          # memory byte offset (= 2 * register, +1 for the high byte)
    kind: str = "f32"    # "f32", "u16", "u32", "bit", "str"
    bit: int = 0         # bit number for kind "bit"
    length: int = 0      # byte length for kind "str"
    invert: bool = False  # for kind "bit"

    @property
    def size(self) -> int:
        return {"f32": 4, "u16": 2, "u32": 4, "bit": 1}.get(self.kind, self.length)

    @property
    def registers(self) -> range:
        return range(self.offset // 2, (self.offset + self.size - 1) // 2 + 1)


def _bit(offset: int, bit: int, invert: bool = False) -> Value:
    return Value(offset, "bit", bit=bit, invert=invert)


VALUES: dict[str, Value] = {
    # parameters (writable)
    "hot_water_target": Value(1),            # Požadovaná T TUV
    "room_target": Value(413),               # Požadovaná T objektu
    "curve_m20": Value(47),                  # Ekv. T pro -20 °C (hlavní okruh)
    "curve_m7": Value(51),                   # Ekv. T pro -7 °C
    "curve_p6": Value(55),                   # Ekv. T pro +6 °C
    "curve_p19": Value(59),                  # Ekv. T pro +19 °C
    # parameters (read only here)
    "hot_water_hysteresis": Value(391),      # Požadovaná hystereze TUV
    "disinfection_temperature": Value(400),  # Požadovaná T dezinfekce TUV
    "heater_delay": Value(396, "u32"),       # Zpoždění el. dohřevu TUV (ms)
    # live values
    "heating_water_target": Value(2062),     # Ekviterm – požadovaná teplota topné vody
    "compressor_output": Value(2066),        # výkon kompresoru % (velké číslo u ventilátoru)
    "flow": Value(2079),                     # Průtok vody m3/h
    "thermal_power": Value(2083),            # Aktuální výkon kW (kalorimetr)
    "heat_energy": Value(2087),              # Dodaný výkon (kalorimetr) kWh
    "kalorimeter_return": Value(2092),       # Vrat (kalorimetr)
    "indoor_temperature": Value(2191),       # Objekt
    "iq_correction": Value(2276),            # IQ korekce °C
    "water_pressure": Value(2295),           # Tlak vody bar
    "outdoor_temperature": Value(2550),
    "output_temperature": Value(2554),
    "hot_water_temperature": Value(2558),
    "return_temperature": Value(2574),
    "circulation_pump": Value(2591),         # Výkon oběhového čerpadla %
    "operating_hours": Value(2605, "u32"),   # Motohodiny
    # states (bits); invert=True where the panel shows the label when the bit is 0
    "heating_enabled": _bit(0, 0),           # tlačítko Chod (topení)
    "hot_water_enabled": _bit(0, 1),         # tlačítko TUV
    "error": _bit(2061, 0),                  # „Porucha:“ v záhlaví
    "bivalence": _bit(2188, 3),              # Bival.
    "hot_water_heating": _bit(2225, 1),      # TUV ohřev
    "hot_water_electric": _bit(2225, 2),     # TUV el. dohřev
    "setback": _bit(2252, 2, invert=True),   # Útlum
    "high_tariff": _bit(2252, 5, invert=True),  # Vys. sazba! (topení)
    "warm_up": _bit(2261, 0),                # Zahřívání
    "outdoor_too_cold": _bit(2230, 1),       # ikona: příliš nízká venkovní teplota, topí jen bivalence
    "secondary_source": _bit(2294, 0),       # ikona: provoz sekundárního zdroje
    "floor_drying": _bit(805, 0),            # Vysoušení
    "hot_water_high_tariff": _bit(9039, 0, invert=True),  # Vys. sazba ! (TUV)
    "hot_water_time_blocked": _bit(9041, 0, invert=True),  # ikona: ohřev TV blokován časovým programem
    "economy": _bit(18961, 0),               # ikona „e“: ekonomický provoz
    "circulation_pump_running": _bit(2603, 0),
    "bivalence_stage_1": _bit(2603, 6),      # 1st.
    "bivalence_stage_2": _bit(2603, 7),      # 2st.
    "disinfection_running": _bit(8768, 0),   # ikona legionely
    "frost_protection": _bit(10302, 0),      # Zámraz. ochr.
    "venting": _bit(18440, 0),               # Odvzdušnění
    "defrost": _bit(18440, 2),               # ikona odtávání
    # texts
    "status_code": Value(18880, "str", length=8),     # Kód stavů a poruch
    "status_text_1": Value(18982, "str", length=48),  # Popis aktuálního stavu / poruchy
    "status_text_2": Value(19063, "str", length=48),
    "status_text_3": Value(19144, "str", length=48),
    "status_text_4": Value(19225, "str", length=48),
}

RUNNING_THRESHOLD_KW = 0.5  # thermal power from the heat meter

WRITABLE = {
    "hot_water_target",
    "room_target",
    "curve_m20",
    "curve_m7",
    "curve_p6",
    "curve_p19",
}


@dataclass(frozen=True)
class Block:
    """Contiguous range of holding registers read in one request."""

    start: int
    count: int


def _build_blocks(max_gap: int = 8, max_count: int = 120) -> tuple[Block, ...]:
    regs = sorted({r for v in VALUES.values() for r in v.registers})
    blocks: list[list[int]] = [[regs[0], regs[0]]]
    for r in regs[1:]:
        start, end = blocks[-1]
        if r - end <= max_gap and r - start < max_count:
            blocks[-1][1] = r
        else:
            blocks.append([r, r])
    return tuple(Block(s, e - s + 1) for s, e in blocks)


READ_BLOCKS: tuple[Block, ...] = _build_blocks()


def _mem(regs: dict[int, int], value: Value) -> bytes | None:
    out = bytearray()
    for r in value.registers:
        if (raw := regs.get(r)) is None:
            return None
        out += struct.pack("<H", raw)
    start = value.offset - 2 * value.registers.start
    return bytes(out[start : start + value.size])


def decode_value(regs: dict[int, int], value: Value) -> float | int | bool | str | None:
    data = _mem(regs, value)
    if data is None:
        return None
    if value.kind == "bit":
        return bool((data[0] >> value.bit) & 1) != value.invert
    if value.kind == "str":
        return data.split(b"\0", 1)[0].decode("cp1250", errors="replace").strip()
    if value.kind == "u16":
        return struct.unpack("<H", data)[0]
    if value.kind == "u32":
        return struct.unpack("<I", data)[0]
    result = struct.unpack("<f", data)[0]
    if not math.isfinite(result) or abs(result) > 1e7:
        return None
    return round(result, 3)


def decode_registers(regs: dict[int, int]) -> dict[str, float | int | bool | str | None]:
    data = {key: decode_value(regs, value) for key, value in VALUES.items()}
    texts = [data.pop(f"status_text_{i}") for i in range(1, 5)]
    data["status_texts"] = [t for t in texts if t]
    # "chod" on the panel belongs to a cascade slave unit; derive running from the heat meter
    power = data.get("thermal_power")
    data["running"] = None if power is None else power >= RUNNING_THRESHOLD_KW
    if data.get("heater_delay") is not None:
        data["heater_delay"] = round(data["heater_delay"] / 60000)  # ms -> minutes
    return data


def plan_float_write(current: list[int], value: Value, new: float) -> list[tuple[int, int]]:
    """Return [(register, raw)] needed to store `new` at `value`, given current registers.

    Only registers whose content changes are returned, least significant first,
    so intermediate states stay close to the old/new value.
    """
    if value.kind != "f32":
        raise ValueError("Only float parameters are writable")
    regs = list(value.registers)
    mem = bytearray(b"".join(struct.pack("<H", r) for r in current))
    start = value.offset - 2 * regs[0]
    mem[start : start + 4] = struct.pack("<f", float(new))
    updated = [struct.unpack("<H", mem[i : i + 2])[0] for i in range(0, len(mem), 2)]
    return [(reg, raw) for reg, old, raw in zip(regs, current, updated) if old != raw]


class NeoreDevice:
    """NeoRé heat pump on a backend-neutral ``modbus_connection.ModbusUnit``.

    Has no Home Assistant dependency: the unit can come from Home Assistant's
    shared Modbus connection or from a standalone ``ModbusConnection``.
    """

    def __init__(self, unit: ModbusUnit) -> None:
        self.unit = unit

    async def async_read_raw(self) -> dict[int, int]:
        """Read every register the integration uses, keyed by address."""
        regs: dict[int, int] = {}
        for block in READ_BLOCKS:
            values = await self.unit.read_holding_registers(block.start, block.count)
            regs.update({block.start + i: v for i, v in enumerate(values)})
        return regs

    async def async_update(self) -> dict[str, Any]:
        """Read and decode all values."""
        return decode_registers(await self.async_read_raw())

    async def async_validate(self) -> None:
        """Probe the device; raise ``ValueError`` if it does not look like a NeoRé."""
        data = await self.async_update()
        if data.get("hot_water_temperature") is None or data.get("status_code") is None:
            raise ValueError("Device did not return NeoRé data")

    async def async_write_float(self, key: str, new: float) -> float | None:
        """Read-modify-write a float parameter and return the value read back."""
        if key not in WRITABLE:
            raise ValueError(f"{key} is not writable")
        value = VALUES[key]
        regs = list(value.registers)
        current = await self.unit.read_holding_registers(regs[0], len(regs))
        for reg, raw in plan_float_write(current, value, new):
            await self.unit.write_register(reg, raw)
        after = await self.unit.read_holding_registers(regs[0], len(regs))
        return decode_value(dict(zip(regs, after)), value)
