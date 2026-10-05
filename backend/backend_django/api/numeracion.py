"""Consecutivos de los documentos (SC-0001, OS-0001, E-000001, VIN-0001, 160-2026).

Se calculan con el MAYOR número existente, no contando filas: desde que se
pueden borrar solicitudes, cotizaciones y órdenes, contar daba un número ya
usado (con SC-0001..SC-0003 y SC-0002 borrada, el conteo proponía SC-0003 otra
vez y fallaba por duplicado). Si se borra uno del medio queda el hueco; si se
borra el último, su número se vuelve a usar.
"""
import re


def _max_numero(qs, patron, campo="numero"):
    regex = re.compile(patron)
    mayor = 0
    for valor in qs.values_list(campo, flat=True):
        m = regex.fullmatch(valor or "")
        if m:
            mayor = max(mayor, int(m.group(1)))
    return mayor


def siguiente(modelo, prefijo, campo="numero", digitos=4):
    """"SC-" → "SC-0004" si el mayor existente es SC-0003."""
    qs = modelo.objects.filter(**{f"{campo}__startswith": prefijo})
    n = _max_numero(qs, re.escape(prefijo) + r"(\d+)", campo) + 1
    return f"{prefijo}{n:0{digitos}d}"


def siguiente_anual(modelo, anio, inicial=0, campo="numero"):
    """"160-2026": consecutivo por año que arranca después de `inicial`."""
    qs = modelo.objects.filter(**{f"{campo}__endswith": f"-{anio}"})
    n = max(_max_numero(qs, rf"(\d+)-{anio}", campo), inicial) + 1
    return f"{n}-{anio}"
