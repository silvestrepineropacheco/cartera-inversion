#!/usr/bin/env python3
"""Seguimiento de una cartera personal: posiciones, valuación, aportes, rebalanceo,
chequeo antes de comprar, diario de decisiones, revisión periódica y resultados.

Solo usa la biblioteca estándar. No hay API de precios: los carga el usuario.
Los datos se guardan en ~/cartera-inversion/cartera.json (o en CARTERA_ARCHIVO,
o en la ruta que se pase con --archivo).

Ejemplos:
  cartera.py init --perfil moderado --moneda-base USD --tipo-cambio 1200 \
      --objetivo "Liquidez=10" "Renta fija dolares=40" "Acciones internacionales=50"
  cartera.py chequear SPY --monto 350000 --moneda ARS --categoria "Acciones internacionales" --tipo etf
  cartera.py compra SPY --categoria "Acciones internacionales" --tipo etf --cantidad 10 --precio 35000 \
      --moneda ARS --motivo "Base de la cartera: 500 empresas de EE. UU."
  cartera.py venta SPY --cantidad 2 --precio 36000
  cartera.py precio SPY=36500 GD30=68.5
  cartera.py editar SPY --tipo etf --motivo "..."
  cartera.py tipo-cambio 1250
  cartera.py estado
  cartera.py aporte 200000 --moneda ARS
  cartera.py rebalanceo
  cartera.py revision            # ¿toca revisar algo?
  cartera.py revision --hecha --nota "Todo en orden"
  cartera.py diario
  cartera.py evolucion
  cartera.py resultados --anio 2026
  cartera.py limites --max-accion 10 --max-activo 25 --banda 5 --minimo 20
"""
import argparse
import calendar
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MONEDAS = ("ARS", "USD")
TIPOS = ("accion", "etf", "fci", "bono", "liquidez", "otro")
# Tipos que ya son una canasta diversificada: no se les aplica el tope por activo.
TIPOS_DIVERSIFICADOS = ("etf", "fci", "liquidez")
DIAS_PRECIO_VIEJO = 7
DIAS_IMPULSO = 30
LIMITES_DEFAULT = {
    "max_accion_individual": 10.0,  # % máximo en una sola acción
    "max_por_activo": 25.0,         # % máximo en un solo bono u otro activo no diversificado
    "banda": 5.0,                   # puntos de desvío tolerados por categoría
    "minimo_operacion": 0.0,        # monto mínimo por compra, en moneda base
    "meses_revision": 6,
}
ARCHIVO_DEFAULT = Path(
    os.environ.get("CARTERA_ARCHIVO", Path.home() / "cartera-inversion" / "cartera.json")
)


# ---------- utilidades ----------

def salir(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def num(x, dec=2):
    """Formato argentino: 1.234.567,89"""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def cant(x):
    """Cantidad sin ceros decimales sobrantes: 10 / 10,5 / 100.000"""
    return num(x, 4).rstrip("0").rstrip(",")


def hoy():
    return date.today().isoformat()


def dias_desde(fecha_iso):
    try:
        return (date.today() - date.fromisoformat(fecha_iso)).days
    except (TypeError, ValueError):
        return None


def sumar_meses(d, meses):
    y, m = divmod(d.month - 1 + meses, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def parsear_pares(pares, que):
    out = {}
    for p in pares:
        if "=" not in p:
            salir(f"'{p}' no tiene el formato NOMBRE=VALOR ({que})")
        k, v = p.rsplit("=", 1)
        try:
            out[k.strip()] = float(v.replace(",", "."))
        except ValueError:
            salir(f"valor inválido en '{p}'")
    return out


def validar_objetivo(obj):
    total = sum(obj.values())
    if abs(total - 100) > 0.01:
        salir(f"los porcentajes del objetivo suman {num(total)} %, tienen que sumar 100 %")
    if any(v < 0 for v in obj.values()):
        salir("hay porcentajes negativos en el objetivo")


# ---------- datos ----------

def cargar(path):
    if not path.exists():
        salir(f"no existe la cartera en {path}. Creala con: cartera.py init ...")
    return migrar(json.loads(path.read_text(encoding="utf-8")))


def guardar(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def migrar(data):
    """Completa campos que no existían en versiones anteriores del archivo."""
    data.setdefault("limites", {})
    for k, v in LIMITES_DEFAULT.items():
        data["limites"].setdefault(k, v)
    data.setdefault("revision", {})
    data["revision"].setdefault(
        "proxima", sumar_meses(date.today(), data["limites"]["meses_revision"]).isoformat())
    data["revision"].setdefault("historial", [])
    data.setdefault("historial", [])
    data.setdefault("chequeos", [])
    tc = data.get("tipo_cambio", {}).get("valor")
    for m in data.get("movimientos", []):
        m.setdefault("tc", tc)
    for t, a in data.get("activos", {}).items():
        a.setdefault("tipo", "otro")
        a.setdefault("motivo", "")
        if "lotes" not in a:
            primera = next((m["fecha"] for m in data["movimientos"]
                            if m["activo"] == t and m["tipo"] == "compra"), hoy())
            precio = a.get("costo_total", 0.0) / a["cantidad"] if a["cantidad"] > 0 else 0.0
            a["lotes"] = [{"fecha": primera, "cantidad": a["cantidad"], "precio": precio}] if a["cantidad"] > 0 else []
        a.pop("costo_total", None)
    data["version"] = 2
    return data


def convertir(valor, de, a, tc):
    if de == a:
        return valor
    if not tc:
        salir("hay montos en otra moneda y no hay tipo de cambio. Cargalo con: cartera.py tipo-cambio N")
    return valor / tc if a == "USD" else valor * tc


def a_base(valor, moneda, data):
    return convertir(valor, moneda, data["moneda_base"], data.get("tipo_cambio", {}).get("valor"))


def desde_base(valor, moneda, data):
    return convertir(valor, data["moneda_base"], moneda, data.get("tipo_cambio", {}).get("valor"))


def costo(a):
    return sum(l["cantidad"] * l["precio"] for l in a["lotes"])


def valuar(data):
    """Devuelve (valor por activo en base, valor por categoría en base, total)."""
    por_activo, por_cat = {}, {c: 0.0 for c in data["objetivo"]}
    for t, a in data["activos"].items():
        if a["cantidad"] <= 0:
            continue
        v = a_base(a["cantidad"] * a["precio"], a["moneda"], data)
        por_activo[t] = v
        por_cat[a["categoria"]] = por_cat.get(a["categoria"], 0.0) + v
    return por_activo, por_cat, sum(por_activo.values())


def aportado_neto(data):
    """Plata puesta menos plata retirada, en moneda base, al tipo de cambio de cada día."""
    base, total = data["moneda_base"], 0.0
    for m in data["movimientos"]:
        v = convertir(m["cantidad"] * m["precio"], m["moneda"], base, m.get("tc"))
        total += v if m["tipo"] == "compra" else -v
    return total


def limite_activo(data, a):
    """Tope en % para un activo, o None si es diversificado."""
    if a["tipo"] == "accion":
        return data["limites"]["max_accion_individual"]
    if a["tipo"] in TIPOS_DIVERSIFICADOS:
        return None
    return data["limites"]["max_por_activo"]


def alertas_concentracion(data, por_activo, total):
    out = []
    for t, v in por_activo.items():
        lim = limite_activo(data, data["activos"][t])
        pct = 100 * v / total
        if lim is not None and pct > lim:
            out.append(f"{t} es el {num(pct, 1)} % de la cartera (tope para tipo '{data['activos'][t]['tipo']}': {num(lim, 0)} %)")
    return out


def precios_viejos(data):
    out = []
    for t, a in data["activos"].items():
        d = dias_desde(a.get("precio_fecha"))
        if a["cantidad"] > 0 and d is not None and d > DIAS_PRECIO_VIEJO:
            out.append(f"{t} ({d} días)")
    return out


def venta_con_perdida_reciente(data, ticker):
    for m in reversed(data["movimientos"]):
        d = dias_desde(m["fecha"])
        if d is not None and d > DIAS_IMPULSO:
            break
        if m["activo"] == ticker and m["tipo"] == "venta" and m.get("resultado", 0) < 0:
            return m
    return None


# ---------- comandos ----------

def cmd_init(args, path):
    if path.exists() and not args.forzar:
        salir(f"ya existe una cartera en {path}. Usá --forzar para reemplazarla")
    obj = parsear_pares(args.objetivo, "objetivo")
    validar_objetivo(obj)
    data = migrar({
        "perfil": args.perfil,
        "moneda_base": args.moneda_base,
        "tipo_cambio": {"valor": args.tipo_cambio, "fecha": hoy()} if args.tipo_cambio else {},
        "objetivo": obj,
        "activos": {},
        "movimientos": [],
    })
    guardar(path, data)
    print(f"Cartera creada en {path}")
    print(f"Perfil: {args.perfil or '-'} | Moneda base: {args.moneda_base}")
    for c, p in obj.items():
        print(f"  {c}: {num(p, 1)} %")
    lim = data["limites"]
    print(f"Límites: acción individual ≤ {num(lim['max_accion_individual'], 0)} %, "
          f"bono u otro activo suelto ≤ {num(lim['max_por_activo'], 0)} %, banda ±{num(lim['banda'], 0)} puntos")
    print(f"Primera revisión: {data['revision']['proxima']}")


def cmd_limites(args, path):
    data = cargar(path)
    lim = data["limites"]
    for campo, valor in (("max_accion_individual", args.max_accion), ("max_por_activo", args.max_activo),
                         ("banda", args.banda), ("minimo_operacion", args.minimo),
                         ("meses_revision", args.meses_revision)):
        if valor is not None:
            lim[campo] = valor
    guardar(path, data)
    print(f"Acción individual ≤ {num(lim['max_accion_individual'], 1)} % | "
          f"Bono u otro activo suelto ≤ {num(lim['max_por_activo'], 1)} % (ETFs, FCI y liquidez no tienen tope)")
    print(f"Banda de rebalanceo ±{num(lim['banda'], 1)} puntos | "
          f"Compra mínima {num(lim['minimo_operacion'])} {data['moneda_base']} | "
          f"Revisión cada {lim['meses_revision']} meses")


def cmd_objetivo(args, path):
    data = cargar(path)
    obj = parsear_pares(args.pares, "objetivo")
    validar_objetivo(obj)
    data["objetivo"] = obj
    huerfanas = {a["categoria"] for a in data["activos"].values() if a["cantidad"] > 0} - set(obj)
    guardar(path, data)
    print("Objetivo actualizado.")
    if huerfanas:
        print(f"Aviso: hay activos en categorías sin objetivo (se toman como 0 %): {', '.join(sorted(huerfanas))}")


def cmd_tipo_cambio(args, path):
    data = cargar(path)
    data["tipo_cambio"] = {"valor": args.valor, "fecha": hoy()}
    guardar(path, data)
    print(f"Tipo de cambio: {num(args.valor)} ARS por USD")


def cmd_compra(args, path):
    data = cargar(path)
    t = args.activo.upper()
    a = data["activos"].get(t)
    fecha = args.fecha or hoy()
    if a is None:
        if not args.categoria or not args.tipo:
            salir(f"{t} es nuevo: indicá --categoria (una de: {', '.join(data['objetivo'])}) "
                  f"y --tipo ({', '.join(TIPOS)})")
        if args.categoria not in data["objetivo"]:
            print(f"Aviso: la categoría '{args.categoria}' no está en el objetivo (se toma como 0 %)")
        a = {"categoria": args.categoria, "tipo": args.tipo, "cantidad": 0.0, "moneda": args.moneda,
             "precio": args.precio, "precio_fecha": fecha, "lotes": [], "motivo": ""}
        data["activos"][t] = a
    elif args.moneda != a["moneda"]:
        salir(f"{t} está registrado en {a['moneda']}; cargá la compra en esa moneda")
    if args.motivo:
        a["motivo"] = args.motivo
    a["cantidad"] += args.cantidad
    a["lotes"].append({"fecha": fecha, "cantidad": args.cantidad, "precio": args.precio})
    a["lotes"].sort(key=lambda l: l["fecha"])  # una compra con fecha pasada no debe romper el FIFO
    if not a.get("precio_fecha") or fecha >= a["precio_fecha"]:
        a["precio"], a["precio_fecha"] = args.precio, fecha
    data["movimientos"].append({
        "fecha": fecha, "tipo": "compra", "activo": t, "cantidad": args.cantidad, "precio": args.precio,
        "moneda": a["moneda"], "tc": data.get("tipo_cambio", {}).get("valor"), "motivo": args.motivo or "",
    })
    data["movimientos"].sort(key=lambda m: m["fecha"])
    guardar(path, data)
    print(f"Compra registrada: {cant(args.cantidad)} {t} a {num(args.precio)} {a['moneda']}. "
          f"Tenencia: {cant(a['cantidad'])}")
    if not a["motivo"]:
        print("Sugerencia: anotá por qué lo compraste (--motivo). Te va a servir cuando el precio baje.")


def cmd_venta(args, path):
    data = cargar(path)
    t = args.activo.upper()
    a = data["activos"].get(t)
    if a is None or a["cantidad"] <= 0:
        salir(f"no tenés {t} registrado")
    if args.cantidad > a["cantidad"] + 1e-9:
        salir(f"querés vender {cant(args.cantidad)} pero tenés {cant(a['cantidad'])}")
    fecha = args.fecha or hoy()
    # Lotes FIFO: se venden primero los más viejos.
    restante, costo_vendido = args.cantidad, 0.0
    while restante > 1e-9 and a["lotes"]:
        lote = a["lotes"][0]
        usa = min(restante, lote["cantidad"])
        costo_vendido += usa * lote["precio"]
        lote["cantidad"] -= usa
        restante -= usa
        if lote["cantidad"] <= 1e-9:
            a["lotes"].pop(0)
    resultado = args.cantidad * args.precio - costo_vendido
    a["cantidad"] -= args.cantidad
    a["precio"], a["precio_fecha"] = args.precio, fecha
    data["movimientos"].append({
        "fecha": fecha, "tipo": "venta", "activo": t, "cantidad": args.cantidad, "precio": args.precio,
        "moneda": a["moneda"], "tc": data.get("tipo_cambio", {}).get("valor"), "motivo": args.motivo or "",
        "resultado": resultado,
    })
    data["movimientos"].sort(key=lambda m: m["fecha"])
    guardar(path, data)
    print(f"Venta registrada: {cant(args.cantidad)} {t} a {num(args.precio)} {a['moneda']}. "
          f"Resultado (FIFO, sin comisiones): {num(resultado)} {a['moneda']}")


def cmd_editar(args, path):
    data = cargar(path)
    t = args.activo.upper()
    a = data["activos"].get(t)
    if a is None:
        salir(f"{t} no está en la cartera")
    for campo in ("categoria", "tipo", "motivo"):
        if getattr(args, campo) is not None:
            a[campo] = getattr(args, campo)
    guardar(path, data)
    print(f"{t}: categoría '{a['categoria']}', tipo '{a['tipo']}', motivo: {a['motivo'] or '-'}")


def cmd_precio(args, path):
    data = cargar(path)
    for t, v in parsear_pares(args.pares, "precio").items():
        t = t.upper()
        if t not in data["activos"]:
            print(f"Aviso: {t} no está en la cartera, se ignora")
            continue
        data["activos"][t]["precio"], data["activos"][t]["precio_fecha"] = v, hoy()
        print(f"{t}: {num(v)} {data['activos'][t]['moneda']}")
    guardar(path, data)


def cmd_estado(args, path):
    data = cargar(path)
    base = data["moneda_base"]
    por_activo, por_cat, total = valuar(data)
    obj = data["objetivo"]
    tc = data.get("tipo_cambio", {})

    print(f"Perfil: {data.get('perfil') or '-'} | Moneda base: {base}", end="")
    print(f" | Tipo de cambio: {num(tc['valor'])} ARS/USD ({tc.get('fecha')})" if tc.get("valor") else "")

    if total == 0:
        print("\nTodavía no hay activos cargados. Objetivo:")
        for c, p in obj.items():
            print(f"  {c}: {num(p, 1)} %")
        return

    puesto = aportado_neto(data)
    ganancia = total - puesto
    print(f"\nValor total:   {num(total)} {base}", end="")
    otra = "ARS" if base == "USD" else "USD"
    print(f"  ({num(desde_base(total, otra, data))} {otra})" if tc.get("valor") else "")
    print(f"Plata puesta:  {num(puesto)} {base}")
    if puesto > 0:
        print(f"Ganancia:      {num(ganancia)} {base} ({num(100 * ganancia / puesto, 1)} %)")

    print("\nPor categoría:")
    print(f"  {'Categoría':<28}{'Valor':>16}{'Actual':>9}{'Objetivo':>10}{'Desvío':>9}")
    for c in sorted(set(obj) | set(por_cat), key=lambda c: -obj.get(c, 0)):
        v = por_cat.get(c, 0.0)
        act, o = 100 * v / total, obj.get(c, 0.0)
        marca = " <" if abs(act - o) > data["limites"]["banda"] else ""
        print(f"  {c:<28}{num(v):>16}{num(act, 1) + ' %':>9}{num(o, 1) + ' %':>10}{num(act - o, 1):>9}{marca}")

    print("\nPor activo:")
    print(f"  {'Activo':<9}{'Tipo':<9}{'Categoría':<26}{'Cantidad':>12}{'Precio':>13}{'Mon':>5}"
          f"{'Valor ' + base:>14}{'Peso':>8}{'Resultado':>11}")
    for t, a in sorted(data["activos"].items(), key=lambda x: -por_activo.get(x[0], 0)):
        if a["cantidad"] <= 0:
            continue
        c = costo(a)
        res = f"{num(100 * (a['cantidad'] * a['precio'] / c - 1), 1)} %" if c > 0 else "-"
        print(f"  {t:<9}{a['tipo']:<9}{a['categoria'][:25]:<26}{num(a['cantidad'], 2):>12}{num(a['precio']):>13}"
              f"{a['moneda']:>5}{num(por_activo[t]):>14}{num(100 * por_activo[t] / total, 1) + ' %':>8}{res:>11}")
    print("  (Resultado = precio actual vs. costo de compra, en la moneda del activo; sin dividendos ni comisiones)")
    print("  (< = categoría fuera de la banda de rebalanceo)")

    avisos = [f"Concentración: {x}" for x in alertas_concentracion(data, por_activo, total)]
    viejos = precios_viejos(data)
    if viejos:
        avisos.append(f"Precios con más de {DIAS_PRECIO_VIEJO} días: {', '.join(viejos)}. Actualizalos con: cartera.py precio TICKER=VALOR")
    d = dias_desde(tc.get("fecha"))
    if d is not None and d > DIAS_PRECIO_VIEJO and any(a["moneda"] != base for a in data["activos"].values()):
        avisos.append(f"El tipo de cambio tiene {d} días. Actualizalo con: cartera.py tipo-cambio N")
    if data["revision"]["proxima"] <= hoy():
        avisos.append(f"Toca la revisión periódica (prevista para {data['revision']['proxima']}): cartera.py revision")
    if avisos:
        print("\nAvisos:")
        for x in avisos:
            print(f"  - {x}")

    # Foto del día para ver la evolución (una por día).
    foto = {"fecha": hoy(), "total": round(total, 2), "aportado": round(puesto, 2), "moneda": base,
            "por_categoria": {c: round(v, 2) for c, v in por_cat.items()}}
    if data["historial"] and data["historial"][-1]["fecha"] == foto["fecha"]:
        data["historial"][-1] = foto
    else:
        data["historial"].append(foto)
    guardar(path, data)


def cmd_evolucion(args, path):
    data = cargar(path)
    h = data["historial"]
    if not h:
        salir("todavía no hay historial. Se guarda una foto cada vez que corrés: cartera.py estado")
    print(f"Evolución de la cartera (cada fila es un día en que corriste 'estado')\n")
    print(f"  {'Fecha':<12}{'Valor':>16}{'Plata puesta':>16}{'Ganancia':>16}{'%':>9}")
    for f in h[-args.ultimas:]:
        g = f["total"] - f["aportado"]
        pct = f"{num(100 * g / f['aportado'], 1)} %" if f["aportado"] > 0 else "-"
        print(f"  {f['fecha']:<12}{num(f['total']):>16}{num(f['aportado']):>16}{num(g):>16}{pct:>9}  {f['moneda']}")
    print("\n'Plata puesta' descuenta lo que retiraste. La ganancia es lo que rindió la cartera, no lo que aportaste.")


def repartir(monto_base, deficit, minimo_base):
    """Reparte proporcional a lo que falta en cada categoría; descarta las porciones menores al mínimo."""
    activas = {c: d for c, d in deficit.items() if d > 0}
    while True:
        suma = sum(activas.values())
        asign = {c: monto_base * d / suma for c, d in activas.items()}
        chicas = [c for c, v in asign.items() if v < minimo_base]
        if not chicas or len(activas) == 1:
            return asign
        del activas[min(chicas, key=asign.get)]


def cmd_aporte(args, path):
    data = cargar(path)
    moneda = args.moneda or data["moneda_base"]
    monto_base = a_base(args.monto, moneda, data)
    minimo = data["limites"]["minimo_operacion"] if args.minimo is None else a_base(args.minimo, moneda, data)
    _, por_cat, total = valuar(data)
    obj = data["objetivo"]
    nuevo_total = total + monto_base
    deficit = {c: max(0.0, obj[c] / 100 * nuevo_total - por_cat.get(c, 0.0)) for c in obj}
    if sum(deficit.values()) <= 0:
        salir("no hay categorías por debajo del objetivo")
    asign = repartir(monto_base, deficit, minimo)

    print(f"Aporte de {num(args.monto)} {moneda}: cómo repartirlo para acercarte al objetivo\n")
    print(f"  {'Categoría':<28}{'Monto ' + moneda:>18}{'Antes':>9}{'Después':>9}{'Objetivo':>10}")
    for c in sorted(obj, key=lambda c: -asign.get(c, 0)):
        a = asign.get(c, 0.0)
        antes = 100 * por_cat.get(c, 0.0) / total if total else 0.0
        despues = 100 * (por_cat.get(c, 0.0) + a) / nuevo_total
        print(f"  {c:<28}{num(desde_base(a, moneda, data)):>18}{num(antes, 1) + ' %':>9}"
              f"{num(despues, 1) + ' %':>9}{num(obj[c], 1) + ' %':>10}")
    print("\nNo hace falta vender nada: la plata nueva va a lo que quedó atrasado.")
    if minimo > 0:
        print(f"Se evitaron compras menores a {num(desde_base(minimo, moneda, data))} {moneda} (comisiones mínimas).")


def cmd_rebalanceo(args, path):
    data = cargar(path)
    base = data["moneda_base"]
    banda = data["limites"]["banda"] if args.banda is None else args.banda
    minimo = data["limites"]["minimo_operacion"]
    por_activo, por_cat, total = valuar(data)
    if total == 0:
        salir("no hay activos cargados")
    obj = data["objetivo"]
    filas = []
    for c in set(obj) | set(por_cat):
        v = por_cat.get(c, 0.0)
        act, o = 100 * v / total, obj.get(c, 0.0)
        ajuste = o / 100 * total - v
        fuera = abs(act - o) > banda and abs(ajuste) >= minimo
        filas.append((c, act, o, ajuste, fuera))
    # Primero las ventas (liberan plata), después las compras.
    filas.sort(key=lambda f: (not f[4], f[3]))

    print(f"Rebalanceo con banda de ±{num(banda, 1)} puntos (valor total {num(total)} {base})\n")
    print(f"  {'Categoría':<28}{'Actual':>9}{'Objetivo':>10}{'Desvío':>9}{'Ajuste ' + base:>18}")
    for c, act, o, ajuste, fuera in filas:
        signo = "+" if ajuste >= 0 else ""
        print(f"  {c:<28}{num(act, 1) + ' %':>9}{num(o, 1) + ' %':>10}{num(act - o, 1):>9}"
              f"{signo + num(ajuste):>18}{' <' if fuera else ''}")
    print("\n  (+ = comprar, - = vender; < = fuera de banda, conviene corregir)")

    fuera = [f for f in filas if f[4]]
    if not fuera:
        print("\nTodo dentro de la banda: no hace falta rebalancear.")
        return
    print(f"\nFuera de banda: {', '.join(f[0] for f in fuera)}.")
    ventas = [f for f in fuera if f[3] < 0]
    if ventas:
        print("\nSi decidís vender, mirá antes la ganancia de cada activo (vender con ganancia puede pagar impuestos):")
        for c, *_ in ventas:
            for t, a in data["activos"].items():
                if a["categoria"] == c and a["cantidad"] > 0:
                    cs = costo(a)
                    g = a["cantidad"] * a["precio"] - cs
                    print(f"  {t}: ganancia sin realizar {num(g)} {a['moneda']}"
                          f"{f' ({num(100 * g / cs, 1)} %)' if cs > 0 else ''}")
    print("\nAntes de vender, considerá corregir con los próximos aportes (cartera.py aporte): "
          "evita comisiones e impuestos. Nada de esto se ejecuta solo: la decisión es tuya.")


def cmd_chequear(args, path):
    data = cargar(path)
    t = args.activo.upper()
    a = data["activos"].get(t)
    moneda = args.moneda or (a["moneda"] if a else data["moneda_base"])
    monto_base = a_base(args.monto, moneda, data)
    categoria = a["categoria"] if a else args.categoria
    tipo = a["tipo"] if a else args.tipo
    if not categoria or not tipo:
        salir(f"{t} es nuevo: indicá --categoria y --tipo ({', '.join(TIPOS)})")
    por_activo, por_cat, total = valuar(data)
    nuevo_total = total + monto_base
    obj, lim = data["objetivo"], data["limites"]
    no, revisar, ok = [], [], []

    # 1. ¿Está en el plan?
    if categoria not in obj or obj[categoria] == 0:
        no.append(f"La categoría '{categoria}' no está en tu plan (objetivo 0 %).")
    else:
        ok.append(f"La categoría '{categoria}' está en tu plan ({num(obj[categoria], 1)} %).")
        act_cat = 100 * por_cat.get(categoria, 0.0) / total if total else 0.0
        desp_cat = 100 * (por_cat.get(categoria, 0.0) + monto_base) / nuevo_total
        if total == 0:
            ok.append("Es tu primera compra: las demás categorías se completan con los próximos aportes.")
        elif act_cat > obj[categoria]:
            otras = [c for c in obj if 100 * por_cat.get(c, 0.0) / total < obj[c]]
            revisar.append(f"'{categoria}' ya está por encima del objetivo ({num(act_cat, 1)} % vs. "
                           f"{num(obj[categoria], 1)} %). Atrasadas: {', '.join(otras) or 'ninguna'}.")
        elif desp_cat > obj[categoria] + lim["banda"]:
            revisar.append(f"Con esta compra '{categoria}' quedaría en {num(desp_cat, 1)} %, "
                           f"más de {num(lim['banda'], 0)} puntos sobre el objetivo ({num(obj[categoria], 1)} %).")
        else:
            ok.append(f"'{categoria}' quedaría en {num(desp_cat, 1)} % (objetivo {num(obj[categoria], 1)} %).")

    # 2. Concentración en un solo activo.
    tope = limite_activo(data, {"tipo": tipo})
    peso = 100 * (por_activo.get(t, 0.0) + monto_base) / nuevo_total
    if tope is None:
        ok.append(f"{t} es tipo '{tipo}' (ya diversificado): sin tope por activo.")
    elif total == 0:
        revisar.append(f"Es tu primera compra: {t} sería el 100 % de la cartera. Está bien para arrancar "
                       f"si es parte del plan, pero el tope para '{tipo}' es {num(tope, 0)} %.")
    elif peso > tope:
        no.append(f"{t} quedaría en {num(peso, 1)} % de la cartera; el tope para tipo '{tipo}' es {num(tope, 0)} %.")
    else:
        ok.append(f"{t} quedaría en {num(peso, 1)} % de la cartera (tope {num(tope, 0)} %).")

    # 3. ¿Sabés por qué lo comprás?
    if args.motivo or (a and a.get("motivo")):
        ok.append(f"Motivo: {args.motivo or a['motivo']}")
    else:
        revisar.append("No anotaste por qué lo comprás. Si no lo podés explicar en una frase, esperá.")

    # 4. Monto mínimo (comisiones).
    if lim["minimo_operacion"] > 0 and monto_base < lim["minimo_operacion"]:
        revisar.append(f"El monto es menor a tu compra mínima ({num(lim['minimo_operacion'])} "
                       f"{data['moneda_base']}): las comisiones pesan más.")

    # 5. Impulso: recomprar algo que vendiste con pérdida hace poco.
    v = venta_con_perdida_reciente(data, t)
    if v:
        revisar.append(f"Vendiste {t} con pérdida el {v['fecha']}. ¿Lo recomprás por plan o para "
                       f"'recuperar'? Las decisiones por bronca suelen salir mal.")

    # 6. Datos viejos.
    if a and (dias_desde(a.get("precio_fecha")) or 0) > DIAS_PRECIO_VIEJO:
        revisar.append(f"El precio de {t} está desactualizado; el cálculo puede no ser exacto.")

    veredicto = "NO" if no else "REVISAR" if revisar else "OK"
    print(f"Chequeo antes de comprar {num(args.monto)} {moneda} de {t}: {veredicto}\n")
    for etiqueta, lista in (("NO", no), ("REVISAR", revisar), ("OK", ok)):
        for x in lista:
            print(f"  [{etiqueta}] {x}")
    print({
        "NO": "\nNo coincide con tu plan. Si igual querés hacerlo, primero cambiá el plan a conciencia.",
        "REVISAR": "\nNo es un 'no', pero pensá cada punto antes de comprar.",
        "OK": "\nCoincide con tu plan. La decisión final es tuya.",
    }[veredicto])
    data["chequeos"].append({"fecha": hoy(), "activo": t, "monto": args.monto, "moneda": moneda,
                             "veredicto": veredicto})
    guardar(path, data)


def cmd_revision(args, path):
    data = cargar(path)
    rev = data["revision"]
    if args.hecha:
        proxima = sumar_meses(date.today(), data["limites"]["meses_revision"]).isoformat()
        rev["historial"].append({"fecha": hoy(), "nota": args.nota or ""})
        rev["proxima"] = proxima
        guardar(path, data)
        print(f"Revisión registrada. Próxima: {proxima}")
        return

    por_activo, por_cat, total = valuar(data)
    obj, banda = data["objetivo"], data["limites"]["banda"]
    revisar, atencion = [], []
    if total:
        revisar += alertas_concentracion(data, por_activo, total)
        for c in set(obj) | set(por_cat):
            act = 100 * por_cat.get(c, 0.0) / total
            if abs(act - obj.get(c, 0.0)) > banda:
                atencion.append(f"'{c}' está en {num(act, 1)} % (objetivo {num(obj.get(c, 0.0), 1)} %): "
                                f"ver cartera.py aporte / rebalanceo")
    viejos = precios_viejos(data)
    if viejos:
        atencion.append(f"Precios desactualizados: {', '.join(viejos)}")
    sin_motivo = [t for t, a in data["activos"].items() if a["cantidad"] > 0 and not a.get("motivo")]
    if sin_motivo:
        atencion.append(f"Activos sin motivo anotado: {', '.join(sin_motivo)}")
    toca = rev["proxima"] <= hoy()

    estado = "REVISAR" if revisar else "ATENCIÓN" if atencion or toca else "OK"
    print(f"Estado de la cartera: {estado}")
    print(f"Revisión periódica: {'toca ahora' if toca else 'próxima el ' + rev['proxima']}"
          f"{' (última: ' + rev['historial'][-1]['fecha'] + ')' if rev['historial'] else ''}\n")
    for x in revisar:
        print(f"  [REVISAR] {x}")
    for x in atencion:
        print(f"  [ATENCIÓN] {x}")
    if toca:
        print("\nPreguntas de la revisión:")
        for p in ("¿Cambió tu situación (trabajo, ingresos, objetivo, horizonte)?",
                  "¿Seguís cómodo con tu perfil? ¿Dormiste tranquilo con las últimas subas y bajas?",
                  "¿El motivo por el que compraste cada activo sigue valiendo?",
                  "¿Tu fondo de emergencia sigue completo?"):
            print(f"  - {p}")
        print("\nCuando termines: cartera.py revision --hecha --nota \"...\"")
    print("\nNada de esto implica vender: son puntos para pensar con calma.")


def cmd_diario(args, path):
    data = cargar(path)
    movs = data["movimientos"][-args.ultimos:]
    if not movs:
        print("Todavía no hay movimientos.")
    for m in movs:
        extra = f" | resultado {num(m['resultado'])} {m['moneda']}" if "resultado" in m else ""
        print(f"{m['fecha']}  {m['tipo']:<6} {cant(m['cantidad'])} {m['activo']} a {num(m['precio'])} {m['moneda']}{extra}")
        if m.get("motivo"):
            print(f"            Motivo: {m['motivo']}")
    activos = [(t, a) for t, a in data["activos"].items() if a["cantidad"] > 0]
    if activos:
        print("\nPor qué tenés cada activo:")
        for t, a in activos:
            print(f"  {t}: {a.get('motivo') or '(sin motivo anotado)'}")
    if data["revision"]["historial"]:
        print("\nRevisiones:")
        for r in data["revision"]["historial"][-5:]:
            print(f"  {r['fecha']}: {r['nota'] or '-'}")


def cmd_resultados(args, path):
    data = cargar(path)
    anio = str(args.anio) if args.anio else None
    ventas = [m for m in data["movimientos"] if m["tipo"] == "venta" and (not anio or m["fecha"].startswith(anio))]
    print(f"Resultados realizados (ventas){' en ' + anio if anio else ''}, método FIFO, sin comisiones:\n")
    if not ventas:
        print("  No hay ventas.")
    tot = {}
    for m in ventas:
        r = m.get("resultado", 0.0)
        tot[m["moneda"]] = tot.get(m["moneda"], 0.0) + r
        print(f"  {m['fecha']}  {cant(m['cantidad'])} {m['activo']}: {num(r)} {m['moneda']}")
    for mon, v in tot.items():
        print(f"  Total {mon}: {num(v)}")

    print("\nResultados sin realizar por lote (lo que pasaría si vendieras hoy):\n")
    print(f"  {'Activo':<9}{'Compra':<12}{'Días':>6}{'Cantidad':>12}{'Costo':>13}{'Hoy':>13}{'Resultado':>13}")
    for t, a in data["activos"].items():
        for l in a["lotes"]:
            g = l["cantidad"] * (a["precio"] - l["precio"])
            d = dias_desde(l["fecha"])
            print(f"  {t:<9}{l['fecha']:<12}{d if d is not None else '-':>6}{num(l['cantidad'], 2):>12}"
                  f"{num(l['precio']):>13}{num(a['precio']):>13}{num(g):>13}  {a['moneda']}")
    print("\nEsto es aritmética, no asesoramiento impositivo. Cómo tributa cada activo en Argentina "
          "(CEDEARs, acciones, bonos) cambia: confirmalo con un contador.")


def main():
    p = argparse.ArgumentParser(description="Seguimiento de cartera de inversión")
    p.add_argument("--archivo", type=Path, default=ARCHIVO_DEFAULT, help="ruta del JSON de la cartera")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="crear la cartera con su objetivo")
    s.add_argument("--perfil", choices=["conservador", "moderado", "agresivo"])
    s.add_argument("--moneda-base", choices=MONEDAS, default="USD")
    s.add_argument("--tipo-cambio", type=float, help="ARS por USD (MEP)")
    s.add_argument("--objetivo", nargs="+", required=True, metavar="CATEGORIA=PCT")
    s.add_argument("--forzar", action="store_true", help="reemplazar una cartera existente")
    s.set_defaults(f=cmd_init)

    s = sub.add_parser("limites", help="topes de concentración, banda, compra mínima y frecuencia de revisión")
    s.add_argument("--max-accion", type=float, help="%% máximo en una sola acción")
    s.add_argument("--max-activo", type=float, help="%% máximo en un solo bono u otro activo no diversificado")
    s.add_argument("--banda", type=float, help="puntos de desvío tolerados por categoría")
    s.add_argument("--minimo", type=float, help="compra mínima, en moneda base")
    s.add_argument("--meses-revision", type=int)
    s.set_defaults(f=cmd_limites)

    s = sub.add_parser("objetivo", help="cambiar los porcentajes objetivo")
    s.add_argument("pares", nargs="+", metavar="CATEGORIA=PCT")
    s.set_defaults(f=cmd_objetivo)

    s = sub.add_parser("tipo-cambio", help="actualizar ARS por USD")
    s.add_argument("valor", type=float)
    s.set_defaults(f=cmd_tipo_cambio)

    for nombre, fn in (("compra", cmd_compra), ("venta", cmd_venta)):
        s = sub.add_parser(nombre, help=f"registrar una {nombre}")
        s.add_argument("activo")
        s.add_argument("--cantidad", type=float, required=True)
        s.add_argument("--precio", type=float, required=True, help="precio por unidad")
        s.add_argument("--fecha", help="AAAA-MM-DD (por defecto hoy)")
        s.add_argument("--motivo", help="por qué comprás o vendés")
        if nombre == "compra":
            s.add_argument("--categoria")
            s.add_argument("--tipo", choices=TIPOS)
            s.add_argument("--moneda", choices=MONEDAS, default="ARS")
        s.set_defaults(f=fn)

    s = sub.add_parser("editar", help="corregir categoría, tipo o motivo de un activo")
    s.add_argument("activo")
    s.add_argument("--categoria")
    s.add_argument("--tipo", choices=TIPOS)
    s.add_argument("--motivo")
    s.set_defaults(f=cmd_editar)

    s = sub.add_parser("precio", help="actualizar precios")
    s.add_argument("pares", nargs="+", metavar="TICKER=PRECIO")
    s.set_defaults(f=cmd_precio)

    s = sub.add_parser("estado", help="valuación, desvío vs. objetivo y avisos")
    s.set_defaults(f=cmd_estado)

    s = sub.add_parser("evolucion", help="historial de valor vs. plata puesta")
    s.add_argument("--ultimas", type=int, default=24)
    s.set_defaults(f=cmd_evolucion)

    s = sub.add_parser("aporte", help="repartir un aporte nuevo")
    s.add_argument("monto", type=float)
    s.add_argument("--moneda", choices=MONEDAS)
    s.add_argument("--minimo", type=float, help="compra mínima en la moneda del aporte")
    s.set_defaults(f=cmd_aporte)

    s = sub.add_parser("rebalanceo", help="qué ajustar para volver al objetivo")
    s.add_argument("--banda", type=float, help="puntos de tolerancia (por defecto, el de 'limites')")
    s.set_defaults(f=cmd_rebalanceo)

    s = sub.add_parser("chequear", help="chequeo antes de comprar: OK / REVISAR / NO")
    s.add_argument("activo")
    s.add_argument("--monto", type=float, required=True)
    s.add_argument("--moneda", choices=MONEDAS)
    s.add_argument("--categoria")
    s.add_argument("--tipo", choices=TIPOS)
    s.add_argument("--motivo")
    s.set_defaults(f=cmd_chequear)

    s = sub.add_parser("revision", help="revisión periódica de la cartera")
    s.add_argument("--hecha", action="store_true", help="registrar que hiciste la revisión")
    s.add_argument("--nota")
    s.set_defaults(f=cmd_revision)

    s = sub.add_parser("diario", help="movimientos y motivos")
    s.add_argument("--ultimos", type=int, default=20)
    s.set_defaults(f=cmd_diario)

    s = sub.add_parser("resultados", help="ganancias realizadas y por lote")
    s.add_argument("--anio", type=int)
    s.set_defaults(f=cmd_resultados)

    args = p.parse_args()
    args.f(args, args.archivo)


if __name__ == "__main__":
    main()
