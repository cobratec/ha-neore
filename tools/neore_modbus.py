#!/usr/bin/env python3
"""
neore_modbus.py - pruzkum Modbus registru tepelneho cerpadla (POUZE CTENI).

Prikazy:
  scan      najde citelne rozsahy holding registru a ulozi je do ranges.json
  snapshot  jednorazove precte vsechny registry do JSON (hledani nastaveni)
  diff      porovna dva snapshoty a ukaze zmenene registry
  log       periodicky loguje vsechny registry (+ volitelne prikon z Home Assistanta) do CSV
  analyze   v CSV logu hleda registr tepelneho vykonu a citac dodaneho tepla

Skript do cerpadla NIKDY nezapisuje.

Instalace:  pip install pymodbus numpy
"""
import argparse
import csv
import datetime as dt
import json
import sys
import time
import urllib.request

DEFAULT_PORT = 502
PERF_ADDR = 1108          # pozadovany vykon %, float32, swap word
BLOCK = 100               # max registru na jeden dotaz


# --------------------------------------------------------------------------- Modbus

def connect(host, port):
    from pymodbus.client import ModbusTcpClient
    client = ModbusTcpClient(host, port=port, timeout=2)
    if not client.connect():
        sys.exit(f"Nelze se pripojit k {host}:{port}")
    return client


def read_block(client, addr, count, unit):
    """Precte holding registry, pri chybe vrati None. Funguje s pymodbus 2.x i 3.x."""
    if not client.connected:
        client.connect()
    for kw in ("device_id", "slave", "unit"):
        try:
            rr = client.read_holding_registers(addr, count=count, **{kw: unit})
        except TypeError:
            continue
        except Exception:
            return None
        if rr is None or rr.isError():
            return None
        return list(rr.registers)
    raise RuntimeError("Nepodporovana verze pymodbus")


def detect_unit(client, wanted):
    candidates = [wanted] if wanted is not None else [1, 0, 255]
    for unit in candidates:
        if read_block(client, PERF_ADDR, 2, unit) is not None:
            print(f"Unit ID: {unit}")
            return unit
    sys.exit("Cerpadlo neodpovida na zadne unit ID (zkuste --unit).")


def add_range(ranges, start, count):
    if ranges and ranges[-1][0] + ranges[-1][1] == start:
        ranges[-1][1] += count
    else:
        ranges.append([start, count])


def read_all(client, unit, ranges, pause):
    values = {}
    for start, count in ranges:
        for s in range(start, start + count, BLOCK):
            n = min(BLOCK, start + count - s)
            regs = read_block(client, s, n, unit)
            for i in range(n):
                values[s + i] = regs[i] if regs is not None else None
            time.sleep(pause)
    return values


def load_ranges(path):
    with open(path) as f:
        cfg = json.load(f)
    return cfg["unit"], cfg["ranges"]


# --------------------------------------------------------------------------- prikazy

def cmd_scan(a):
    client = connect(a.host, a.port)
    unit = detect_unit(client, a.unit)
    ranges = []
    for start in range(a.start, a.end, BLOCK):
        count = min(BLOCK, a.end - start)
        if read_block(client, start, count, unit) is not None:
            add_range(ranges, start, count)
        else:
            for s in range(start, start + count, 10):
                n = min(10, start + count - s)
                if read_block(client, s, n, unit) is not None:
                    add_range(ranges, s, n)
                elif a.fine:
                    for x in range(s, s + n):
                        if read_block(client, x, 1, unit) is not None:
                            add_range(ranges, x, 1)
                time.sleep(a.pause)
        time.sleep(a.pause)
        print(f"\r  {start + count}/{a.end}", end="", flush=True)
    print()
    total = sum(c for _, c in ranges)
    with open(a.out, "w") as f:
        json.dump({"host": a.host, "unit": unit, "ranges": ranges}, f, indent=1)
    print(f"Citelnych registru: {total} v {len(ranges)} rozsazich -> {a.out}")
    client.close()


def cmd_snapshot(a):
    unit, ranges = load_ranges(a.ranges)
    client = connect(a.host, a.port)
    values = read_all(client, unit, ranges, a.pause)
    client.close()
    with open(a.out, "w") as f:
        json.dump({"time": dt.datetime.now().isoformat(timespec="seconds"),
                   "values": {str(k): v for k, v in values.items()}}, f)
    print(f"Ulozeno {len(values)} registru -> {a.out}")


def _interp_pair(vals, a):
    """Mozne vyklady dvojice registru a, a+1 jako 32bit hodnoty."""
    import struct
    x, y = vals.get(a), vals.get(a + 1)
    if x is None or y is None:
        return {}
    out = {}
    for name, hi, lo in (("BE", x, y), ("WS", y, x)):
        raw = struct.pack(">HH", hi, lo)
        out[f"f32-{name}"] = struct.unpack(">f", raw)[0]
        out[f"u32-{name}"] = struct.unpack(">I", raw)[0]
    return out


def cmd_diff(a):
    with open(a.old) as f:
        old = {int(k): v for k, v in json.load(f)["values"].items()}
    with open(a.new) as f:
        new = {int(k): v for k, v in json.load(f)["values"].items()}
    changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    if not changed:
        print("Zadny registr se nezmenil.")
        return
    print(f"Zmenenych registru: {len(changed)}\n")
    for k in changed:
        o, n = old.get(k), new.get(k)
        line = f"{k:6d}: {o} -> {n}"
        if o is not None and n is not None:
            si = lambda v: v - 65536 if v >= 32768 else v
            if o >= 32768 or n >= 32768:
                line += f"   (i16: {si(o)} -> {si(n)})"
        print(line)
        for base in (k - 1, k):
            po, pn = _interp_pair(old, base), _interp_pair(new, base)
            if not po or not pn:
                continue
            for key in ("f32-WS", "f32-BE"):
                vo, vn = po[key], pn[key]
                if all(abs(v) < 1e6 and (v == 0 or abs(v) > 1e-3) for v in (vo, vn)):
                    print(f"          jako {key} od {base}: {vo:.3f} -> {vn:.3f}")


def ha_power(url, token, entity):
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/states/{entity}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=3) as r:
        data = json.load(r)
    value = float(data["state"])
    if data.get("attributes", {}).get("unit_of_measurement", "").lower() == "kw":
        value *= 1000
    return value


def cmd_log(a):
    unit, ranges = load_ranges(a.ranges)
    addrs = [s + i for s, c in ranges for i in range(c)]
    use_ha = bool(a.ha_url and a.ha_token and a.power_entity)
    client = connect(a.host, a.port)
    with open(a.out, "a", newline="") as f:
        w = csv.writer(f)
        if f.tell() == 0:
            w.writerow(["time"] + (["power_w"] if use_ha else []) + [f"r{x}" for x in addrs])
        print(f"Loguji {len(addrs)} registru kazdych {a.interval} s do {a.out} (Ctrl+C = konec)")
        n = 0
        try:
            while True:
                t0 = time.time()
                values = read_all(client, unit, ranges, a.pause)
                row = [dt.datetime.now().isoformat(timespec="seconds")]
                if use_ha:
                    try:
                        row.append(ha_power(a.ha_url, a.ha_token, a.power_entity))
                    except Exception:
                        row.append("")
                row += ["" if values.get(x) is None else values[x] for x in addrs]
                w.writerow(row)
                f.flush()
                n += 1
                print(f"\r  zaznamu: {n}", end="", flush=True)
                time.sleep(max(0, a.interval - (time.time() - t0)))
        except KeyboardInterrupt:
            print("\nKonec.")
    client.close()


# --------------------------------------------------------------------------- analyza

def cmd_analyze(a):
    import numpy as np

    with open(a.csv) as f:
        rd = csv.reader(f)
        header = next(rd)
        rows = [r for r in rd if len(r) == len(header)]
    if len(rows) < 30:
        sys.exit("Malo dat - logujte aspon par hodin vcetne nekolika behu kompresoru.")

    t = np.array([dt.datetime.fromisoformat(r[0]).timestamp() for r in rows])

    def col(i):
        return np.array([float(r[i]) if r[i] != "" else np.nan for r in rows])

    power = col(header.index("power_w")) if "power_w" in header else None
    regs = {int(h[1:]): col(i) for i, h in enumerate(header) if h[:1] == "r" and h[1:].isdigit()}

    # vsechny mozne vyklady registru
    cands = {}
    for addr, v in regs.items():
        cands[f"{addr} u16"] = v
        i16 = np.where(v >= 32768, v - 65536, v)
        if not np.array_equal(i16, v, equal_nan=True):
            cands[f"{addr} i16"] = i16
        b = regs.get(addr + 1)
        if b is None:
            continue
        ok = ~(np.isnan(v) | np.isnan(b))
        vi = np.nan_to_num(v).astype(np.uint32)
        bi = np.nan_to_num(b).astype(np.uint32)
        for name, hi, lo in (("BE", vi, bi), ("WS", bi, vi)):
            u = ((hi << 16) | lo).astype(np.uint32)
            for suffix, arr in (("f32", u.view(np.float32).astype(float)),
                                ("u32", u.astype(float)),
                                ("i32", u.view(np.int32).astype(float))):
                arr = arr.copy()
                arr[~ok] = np.nan
                cands[f"{addr} {suffix}-{name}"] = arr

    def plausible(x):
        fin = np.isfinite(x)
        if fin.mean() < 0.9:
            return False
        xs = x[fin]
        if xs.std() == 0 or np.abs(xs).max() > 1e7:
            return False
        nz = xs[xs != 0]
        return not (len(nz) and np.abs(nz).min() < 1e-6)

    cands = {k: v for k, v in cands.items() if plausible(v)}

    perf = cands.get(f"{PERF_ADDR} f32-WS")
    if perf is not None:
        run = np.nan_to_num(perf) > 1
    elif power is not None:
        run = np.nan_to_num(power) > 150
    else:
        sys.exit("Nenasel jsem performance ani prikon - nelze urcit, kdy kompresor bezi.")
    if run.all() or not run.any():
        sys.exit("V logu chybi useky behu i klidu kompresoru - logujte dele.")
    ref = power if power is not None else perf
    print(f"Zaznamu: {len(rows)}, kompresor bezel v {run.mean() * 100:.0f} % casu, "
          f"zmenovych kandidatu: {len(cands)}")
    print(f"Referencni signal: {'prikon ze Shelly' if power is not None else 'performance %'}\n")

    scales = (1, 10, 100, 1000, 0.1, 0.01)

    # --- okamzity vykon
    inst = []
    for name, x in cands.items():
        fin = np.isfinite(x)
        on, off = x[run & fin], x[~run & fin]
        if len(on) < 5 or len(off) < 5:
            continue
        on_m, off_m = np.median(on), np.median(np.abs(off))
        if on_m <= 0 or off_m > 0.2 * on_m:
            continue
        m = fin & np.isfinite(ref)
        if x[m].std() == 0 or ref[m].std() == 0:
            continue
        r = np.corrcoef(x[m], ref[m])[0, 1]
        if not np.isfinite(r) or r < 0.5:
            continue
        note = ""
        if power is not None:
            mm = run & fin & (np.nan_to_num(power) > 200)
            if mm.sum() >= 5:
                ratio = np.median(x[mm] / power[mm])
                fits = [s for s in scales if 1.5 <= ratio * s <= 7]
                note = f"pomer k prikonu {ratio:.4g}"
                if fits:
                    note += f"  -> COP {ratio * fits[0]:.2f} pri meritku x{fits[0]}"
        inst.append((r, name, on_m, note))
    inst.sort(reverse=True)

    print("=== Kandidati na OKAMZITY tepelny vykon (0 v klidu, roste s behem) ===")
    if not inst:
        print("  nic nenalezeno")
    for r, name, on_m, note in inst[:a.top]:
        print(f"  {name:16s} korelace {r:.2f}  median za behu {on_m:.4g}  {note}")

    # --- citac tepla
    energy_kwh = None
    if power is not None:
        p = np.nan_to_num(power)
        energy_kwh = float(np.sum((p[1:] + p[:-1]) / 2 * np.diff(t)) / 3.6e6)
    cum = []
    for name, x in cands.items():
        idx = np.where(np.isfinite(x))[0]
        if len(idx) < 10:
            continue
        xs = x[idx]
        d = np.diff(xs)
        if (d < 0).mean() > 0.01 or xs[-1] - xs[0] <= 0:
            continue
        pos = d > 0
        run_pair = run[idx[1:]] | run[idx[:-1]]
        share = d[run_pair & pos].sum() / d[pos].sum()
        if share < 0.8:
            continue
        total = xs[-1] - xs[0]
        note = ""
        if energy_kwh:
            ratio = total / energy_kwh
            fits = [s for s in scales if 1.5 <= ratio * s <= 7]
            note = f"prirustek/kWh ze Shelly {ratio:.4g}"
            if fits:
                note += f"  -> COP {ratio * fits[0]:.2f} pri meritku x{fits[0]}"
        cum.append((share, name, total, note))
    cum.sort(reverse=True)

    print("\n=== Kandidati na CITAC dodaneho tepla (roste jen za behu) ===")
    if energy_kwh is not None:
        print(f"  (elektricka energie za obdobi logu: {energy_kwh:.2f} kWh)")
    if not cum:
        print("  nic nenalezeno")
    for share, name, total, note in cum[:a.top]:
        print(f"  {name:16s} prirustek {total:.4g}  ({share * 100:.0f} % za behu)  {note}")

    print("\nTip: skutecny registr tepla ma realny COP (2-5) a sedi u topeni i TUV.")


# --------------------------------------------------------------------------- CLI

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", required=True, help="IP adresa tepelného čerpadla")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--pause", type=float, default=0.05, help="pauza mezi dotazy [s]")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="najit citelne rozsahy registru")
    s.add_argument("--unit", type=int, default=None, help="unit ID (jinak autodetekce 1/0/255)")
    s.add_argument("--start", type=int, default=0)
    s.add_argument("--end", type=int, default=10000)
    s.add_argument("--fine", action="store_true", help="dohledat i jednotlive registry v chybnych blocich")
    s.add_argument("--out", default="ranges.json")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("snapshot", help="jednorazove precist vse do JSON")
    s.add_argument("out")
    s.add_argument("--ranges", default="ranges.json")
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("diff", help="porovnat dva snapshoty")
    s.add_argument("old")
    s.add_argument("new")
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("log", help="periodicke logovani do CSV")
    s.add_argument("--ranges", default="ranges.json")
    s.add_argument("--out", default="log.csv")
    s.add_argument("--interval", type=float, default=10)
    s.add_argument("--ha-url", help="napr. http://homeassistant.local:8123")
    s.add_argument("--ha-token", help="long-lived access token z profilu v HA")
    s.add_argument("--power-entity", help="entita prikonu cerpadla, napr. sensor.shelly_tc_power")
    s.set_defaults(func=cmd_log)

    s = sub.add_parser("analyze", help="najit registr tepelneho vykonu / citac tepla")
    s.add_argument("csv", nargs="?", default="log.csv")
    s.add_argument("--top", type=int, default=15)
    s.set_defaults(func=cmd_analyze)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
