"""
simulacion/arquetipos.py
========================
Los 10 arquetipos de cliente sobre los que se construye la base simulada.

Un arquetipo NO es un cliente: es la descripción de un tipo de comprador
—rango de edad, capacidad de pago, tamaño del hogar, dónde busca y qué
amenidades le importan—. `generar_clientes.py` produce 100 variaciones de cada
uno, y de ahí salen los 1.000 clientes que alimentan el historial.

Por qué arquetipos y no una distribución pura:

- **Se pueden leer.** "Familia joven con hijo pequeño, VIS en Bosa, 3 alcobas"
  es revisable por alguien que conoce el negocio; una matriz de probabilidades
  condicionadas no lo es.
- **Producen clústeres de verdad.** El componente colaborativo del modelo
  busca usuarios parecidos entre sí. Si los perfiles salen de un muestreo
  independiente campo a campo, los "vecinos" que encuentra son ruido
  correlacionado; con arquetipos hay grupos reales que compartir.
- **Cubren el catálogo a propósito.** Las localidades de cada arquetipo se
  eligieron mirando dónde hay oferta (Suba, Fontibón, Bosa, Engativá, Usme
  concentran el 80 %), pero sin dejar sin demanda a las que tienen poca.

Las bandas de edad y de ingreso siguen el perfil de comprador de vivienda de
Camacol para Bogotá–Cundinamarca que ya documentaba `generar_historial.py`:
25–35 años es el grupo más numeroso (~37 %) y se concentra en 2–4 SMMLV;
36–50 (~31 %) es donde está el pico de capacidad de pago.

Índices de `zonas_comunes` (ver catalogos.ZONAS_COMUNES):

     0 Lobby              7 Zona fitness      14 Zona café        21 Voleibol playa
     1 Piscina            8 Salón social      15 Gimnasio         22 Cancha de pádel
     2 Zona lavandería    9 Spa mascotas      16 Parqueadero      23 Taller bicicletas
     3 Zona BBQ          10 Zona cool         17 Zona verde       24 Sauna
     4 Zona pet          11 Zona cine         18 Parque
     5 Zona kids         12 Coworking         19 Sala de juegos
     6 Locales comerc.   13 Sala VIP          20 Pista de trote
"""

from __future__ import annotations

# Cada arquetipo declara:
#   edad              (min, max)
#   salario           pesos para los códigos 1..4
#   personas_a_cargo  pesos para 1..4
#   prob_vis          probabilidad de buscar VIS
#   localidades       ids donde busca, con su peso relativo
#   habitaciones      pesos para 1..3
#   piso              pesos para los códigos 0 (bajo), 1 (medio), 3 (alto), 4 (sin pref.)
#   zonas_nucleo      amenidades que definen al arquetipo: casi siempre las pide
#   zonas_opcionales  amenidades que a veces añade
#   prob_afiliado     afiliación a caja de compensación
ARQUETIPOS = [
    {
        "id": "joven_profesional",
        "nombre": "Joven profesional, primer apartamento",
        "descripcion": (
            "Vive solo o con pareja, prioriza ubicación y espacios de trabajo "
            "sobre metros cuadrados. Es el grupo más numeroso del mercado."
        ),
        "edad": (25, 32),
        "salario": {1: 0.10, 2: 0.45, 3: 0.35, 4: 0.10},
        "personas_a_cargo": {1: 0.70, 2: 0.25, 3: 0.05, 4: 0.00},
        "prob_vis": 0.35,
        "localidades": {2: 3, 13: 3, 11: 2, 12: 2, 1: 1, 10: 1},
        "habitaciones": {1: 0.40, 2: 0.50, 3: 0.10},
        "piso": {0: 0.10, 1: 0.30, 3: 0.40, 4: 0.20},
        "zonas_nucleo": [12, 15, 0],
        "zonas_opcionales": [14, 10, 13, 16, 23, 11],
        "prob_afiliado": 0.55,
    },
    {
        "id": "pareja_sin_hijos",
        "nombre": "Pareja joven sin hijos",
        "descripcion": (
            "Doble ingreso, sin hijos todavía. Compra pensando en los "
            "próximos cinco años, así que pide una alcoba de más."
        ),
        "edad": (27, 36),
        "salario": {1: 0.05, 2: 0.35, 3: 0.45, 4: 0.15},
        "personas_a_cargo": {1: 0.30, 2: 0.60, 3: 0.10, 4: 0.00},
        "prob_vis": 0.40,
        "localidades": {11: 3, 10: 2, 9: 2, 12: 1, 13: 1, 1: 1},
        "habitaciones": {1: 0.10, 2: 0.60, 3: 0.30},
        "piso": {0: 0.10, 1: 0.35, 3: 0.35, 4: 0.20},
        "zonas_nucleo": [15, 1, 3],
        "zonas_opcionales": [12, 17, 8, 16, 10, 24],
        "prob_afiliado": 0.65,
    },
    {
        "id": "familia_joven",
        "nombre": "Familia joven con hijo pequeño",
        "descripcion": (
            "El primer hijo cambia la prioridad: zonas infantiles, parque y "
            "colegio cerca pesan más que el gimnasio."
        ),
        "edad": (30, 40),
        "salario": {1: 0.20, 2: 0.50, 3: 0.25, 4: 0.05},
        "personas_a_cargo": {1: 0.05, 2: 0.25, 3: 0.55, 4: 0.15},
        "prob_vis": 0.75,
        "localidades": {7: 3, 8: 2, 9: 2, 10: 2, 11: 2, 5: 1},
        "habitaciones": {1: 0.02, 2: 0.38, 3: 0.60},
        "piso": {0: 0.35, 1: 0.35, 3: 0.10, 4: 0.20},
        "zonas_nucleo": [5, 18, 8],
        "zonas_opcionales": [17, 3, 16, 19, 6, 2],
        "prob_afiliado": 0.80,
    },
    {
        "id": "familia_numerosa_vis",
        "nombre": "Familia numerosa con subsidio",
        "descripcion": (
            "Cuatro o más personas, ingreso bajo y compra apalancada en "
            "subsidio. Es el núcleo de la demanda VIS del catálogo."
        ),
        "edad": (33, 48),
        "salario": {1: 0.45, 2: 0.45, 3: 0.10, 4: 0.00},
        "personas_a_cargo": {1: 0.00, 2: 0.10, 3: 0.30, 4: 0.60},
        "prob_vis": 0.95,
        "localidades": {7: 3, 5: 3, 19: 2, 8: 2, 6: 1, 18: 1},
        "habitaciones": {1: 0.00, 2: 0.25, 3: 0.75},
        "piso": {0: 0.45, 1: 0.30, 3: 0.05, 4: 0.20},
        "zonas_nucleo": [5, 18, 2],
        "zonas_opcionales": [8, 17, 6, 16, 3, 19],
        "prob_afiliado": 0.92,
    },
    {
        "id": "reposicion",
        "nombre": "Comprador de reposición",
        "descripcion": (
            "Ya tiene vivienda y busca mejorar. No le urge, así que compara "
            "amenidades y acabados antes que precio."
        ),
        "edad": (40, 55),
        "salario": {1: 0.02, 2: 0.18, 3: 0.45, 4: 0.35},
        "personas_a_cargo": {1: 0.15, 2: 0.35, 3: 0.35, 4: 0.15},
        "prob_vis": 0.15,
        "localidades": {1: 3, 11: 3, 2: 2, 12: 1, 13: 1, 10: 1},
        "habitaciones": {1: 0.05, 2: 0.30, 3: 0.65},
        "piso": {0: 0.10, 1: 0.25, 3: 0.45, 4: 0.20},
        "zonas_nucleo": [1, 15, 8],
        "zonas_opcionales": [24, 17, 22, 20, 16, 11],
        "prob_afiliado": 0.45,
    },
    {
        "id": "inversionista",
        "nombre": "Inversionista",
        "descripcion": (
            "No va a vivir ahí. Busca área pequeña, buena ubicación y "
            "amenidades que ayuden a arrendar rápido."
        ),
        "edad": (35, 58),
        "salario": {1: 0.00, 2: 0.10, 3: 0.35, 4: 0.55},
        "personas_a_cargo": {1: 0.65, 2: 0.25, 3: 0.10, 4: 0.00},
        "prob_vis": 0.25,
        "localidades": {2: 3, 13: 2, 1: 2, 9: 2, 11: 2, 12: 1},
        "habitaciones": {1: 0.55, 2: 0.40, 3: 0.05},
        "piso": {0: 0.05, 1: 0.20, 3: 0.35, 4: 0.40},
        "zonas_nucleo": [0, 12, 15],
        "zonas_opcionales": [6, 16, 10, 13, 14, 1],
        "prob_afiliado": 0.35,
    },
    {
        "id": "nido_vacio",
        "nombre": "Nido vacío",
        "descripcion": (
            "Los hijos se fueron y sobra casa. Reduce metros, pero no "
            "tranquilidad: zonas verdes y buen parqueadero."
        ),
        "edad": (54, 70),
        "salario": {1: 0.10, 2: 0.30, 3: 0.40, 4: 0.20},
        "personas_a_cargo": {1: 0.55, 2: 0.40, 3: 0.05, 4: 0.00},
        "prob_vis": 0.30,
        "localidades": {1: 3, 12: 2, 13: 2, 11: 2, 10: 1, 9: 1},
        "habitaciones": {1: 0.20, 2: 0.60, 3: 0.20},
        "piso": {0: 0.50, 1: 0.30, 3: 0.05, 4: 0.15},
        "zonas_nucleo": [17, 16, 8],
        "zonas_opcionales": [20, 24, 18, 1, 6, 0],
        "prob_afiliado": 0.50,
    },
    {
        "id": "cabeza_de_hogar",
        "nombre": "Cabeza de hogar con subsidio",
        "descripcion": (
            "Sostiene sola o solo el hogar. Decide por cuota mensual y por "
            "qué tan cerca queda el colegio y el transporte."
        ),
        "edad": (28, 44),
        "salario": {1: 0.50, 2: 0.42, 3: 0.08, 4: 0.00},
        "personas_a_cargo": {1: 0.05, 2: 0.30, 3: 0.40, 4: 0.25},
        "prob_vis": 0.93,
        "localidades": {7: 3, 5: 2, 8: 2, 19: 2, 10: 1, 18: 1},
        "habitaciones": {1: 0.05, 2: 0.50, 3: 0.45},
        "piso": {0: 0.40, 1: 0.30, 3: 0.05, 4: 0.25},
        "zonas_nucleo": [5, 2, 6],
        "zonas_opcionales": [18, 8, 17, 16, 3, 19],
        "prob_afiliado": 0.90,
    },
    {
        "id": "teletrabajo_mascota",
        "nombre": "Teletrabajador con mascota",
        "descripcion": (
            "La casa es también la oficina. Pide espacio de trabajo y zonas "
            "pensadas para el perro; el pico de demanda desde 2021."
        ),
        "edad": (28, 42),
        "salario": {1: 0.08, 2: 0.40, 3: 0.40, 4: 0.12},
        "personas_a_cargo": {1: 0.50, 2: 0.40, 3: 0.10, 4: 0.00},
        "prob_vis": 0.45,
        "localidades": {11: 3, 10: 2, 9: 2, 13: 2, 12: 1, 1: 1},
        "habitaciones": {1: 0.20, 2: 0.55, 3: 0.25},
        "piso": {0: 0.20, 1: 0.35, 3: 0.25, 4: 0.20},
        "zonas_nucleo": [12, 4, 17],
        "zonas_opcionales": [9, 15, 14, 10, 23, 3],
        "prob_afiliado": 0.60,
    },
    {
        "id": "primer_comprador_caja",
        "nombre": "Primer comprador afiliado a caja",
        "descripcion": (
            "Entra al mercado con el subsidio de la caja. Ingreso bajo, "
            "expectativa alta y mucha sensibilidad a la cuota inicial."
        ),
        "edad": (24, 34),
        "salario": {1: 0.40, 2: 0.50, 3: 0.10, 4: 0.00},
        "personas_a_cargo": {1: 0.35, 2: 0.40, 3: 0.20, 4: 0.05},
        "prob_vis": 0.90,
        "localidades": {7: 3, 10: 2, 9: 2, 5: 2, 11: 2, 8: 1},
        "habitaciones": {1: 0.15, 2: 0.60, 3: 0.25},
        "piso": {0: 0.25, 1: 0.35, 3: 0.15, 4: 0.25},
        "zonas_nucleo": [0, 15, 3],
        "zonas_opcionales": [8, 16, 17, 5, 12, 6],
        "prob_afiliado": 0.95,
    },
]

ARQUETIPOS_POR_ID = {a["id"]: a for a in ARQUETIPOS}


def validar():
    """Comprueba que los 10 arquetipos estén bien formados.

    Se ejecuta al generar clientes: un peso mal escrito o un índice de zona
    fuera de rango produciría clientes silenciosamente inválidos, y el
    historial que salga de ahí contamina el componente colaborativo sin que
    nada falle de forma visible.
    """
    from Model.catalogos import LOCALIDADES_BOGOTA, ZONAS_COMUNES

    errores = []
    if len(ARQUETIPOS) != 10:
        errores.append(f"se esperaban 10 arquetipos, hay {len(ARQUETIPOS)}")
    if len(ARQUETIPOS_POR_ID) != len(ARQUETIPOS):
        errores.append("hay ids de arquetipo repetidos")

    for a in ARQUETIPOS:
        etiqueta = a.get("id", "?")
        edad_min, edad_max = a["edad"]
        if not (18 <= edad_min <= edad_max <= 125):
            errores.append(f"{etiqueta}: rango de edad inválido {a['edad']}")

        for campo, validos in (("salario", {1, 2, 3, 4}),
                               ("personas_a_cargo", {1, 2, 3, 4}),
                               ("habitaciones", {1, 2, 3}),
                               ("piso", {0, 1, 3, 4})):
            pesos = a[campo]
            if set(pesos) - validos:
                errores.append(f"{etiqueta}: {campo} tiene códigos fuera de {sorted(validos)}")
            if abs(sum(pesos.values()) - 1.0) > 1e-6:
                errores.append(f"{etiqueta}: {campo} suma {sum(pesos.values())}, debería sumar 1")

        for loc in a["localidades"]:
            if not 1 <= loc <= len(LOCALIDADES_BOGOTA):
                errores.append(f"{etiqueta}: localidad {loc} fuera de 1..20")

        zonas = list(a["zonas_nucleo"]) + list(a["zonas_opcionales"])
        for z in zonas:
            if not 0 <= z < len(ZONAS_COMUNES):
                errores.append(f"{etiqueta}: zona {z} fuera de 0..24")
        if len(set(zonas)) != len(zonas):
            errores.append(f"{etiqueta}: una zona está en núcleo y en opcionales a la vez")

        if not 0.0 <= a["prob_vis"] <= 1.0:
            errores.append(f"{etiqueta}: prob_vis fuera de [0,1]")
        if not 0.0 <= a["prob_afiliado"] <= 1.0:
            errores.append(f"{etiqueta}: prob_afiliado fuera de [0,1]")

    if errores:
        raise ValueError("Arquetipos inválidos:\n  - " + "\n  - ".join(errores))
    return True
