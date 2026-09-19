"""
Model/cota_minima.py
====================
`Cota_minimaBG` — la capa que pone el **dinero** en el centro del ranking.

El recomendador nació ordenando por parecido demográfico, cobertura de
amenidades y cercanía. Todo eso importa, pero ninguna de esas tres cosas es la
que decide una compra de vivienda: lo que la decide es cuánto cuesta y en
cuánto tiempo se termina de pagar. Esta capa corrige esa jerarquía en dos
movimientos, y corre **después** de `modelo()` y **antes** de
`post_arreglos()`:

    primer_filtro -> modelo -> Cota_minimaBG -> post_arreglos

1. **Verificación de esfuerzo** (`anos_de_pago`). Cuántos años tardaría *esta*
   persona, con *su* tramo de ingreso, en terminar de pagar *ese* proyecto.
   No es el ingreso que el proyecto exige —eso ya lo etiqueta `prep.py`— sino
   el tiempo real de pago, que es lo que un comprador entiende y sufre. El
   proyecto que ni siquiera amortiza (la cuota que la persona puede pagar no
   cubre los intereses) queda marcado como inalcanzable.

2. **Cota mínima de precio** (`_aplicar_cota_precio`). Recorre el top por
   pares consecutivos y, cuando el de arriba cuesta más que el de abajo por
   encima de `COTA_MINIMA_COP`, **los invierte** — aunque el de abajo esté en
   una localidad que el usuario no pidió. Esa es la inversión de prioridad que
   define esta capa: por encima de cierta diferencia de plata, el ahorro pesa
   más que la ubicación.

Lo que la cota **no** rompe es el invariante 4 del GUIA_TECNICA.md: un proyecto
admitido relajando requisitos (menos habitaciones de las pedidas, ninguna zona
común en común) no adelanta a uno que cumple todo por ser más barato. Cambiar
de barrio es una concesión que se puede compensar con dinero; recibir una
vivienda que no cumple lo que se pidió, no. El intercambio solo ocurre dentro
del mismo tramo de `_prioridad_filtro`, y `respetar_prioridad=False` lo
levanta para quien quiera medir el efecto.

Las funciones de cálculo (`anos_de_pago`, `score_esfuerzo`) las usa también
`modelo.py`, para que el esfuerzo pese en **qué** proyectos entran al top y no
solo en el orden en que salen. Este módulo no importa `modelo` — la dependencia
va en un solo sentido.
"""

from __future__ import annotations

import math

from Model.prep import (
    SMMLV,
    cuota_mensual,
    monto_financiado,
    parametros_credito,
    tasa_mensual,
)

# ---------------------------------------------------------------------------
# Parámetros de la cota
# ---------------------------------------------------------------------------
# Diferencia de precio a partir de la cual el ahorro le gana a la ubicación.
#
# Es EL parámetro de esta capa, así que conviene entender qué controla. Con la
# cota en 0 el top queda ordenado por precio ascendente y el modelo deja de
# decidir; con la cota en infinito nada se mueve y esta capa no existe. En
# medio, la cota define BANDAS de precio: dentro de una banda manda el score
# del modelo, y entre bandas manda el precio.
#
# 50 millones sobre un catálogo cuya VIS típica ronda los 200-280 millones son
# ~20% del precio. No es una diferencia de matiz: es la que separa un proyecto
# de otro segmento, y son unos 500.000 pesos menos de cuota al mes durante 30
# años. Por eso justifica cruzar de localidad. Diferencias menores no la
# justifican y no mueven nada, que es exactamente lo que hace que el orden del
# modelo sobreviva dentro de cada banda.
#
# Medido con `simulacion/calibrar_cota.py` sobre 300 clientes de prueba no
# vistos (precio medio del Top 3, que es lo que la landing muestra):
#
#   cota    | recall@18 | pos. media | precio Top 3 | ahorro
#   --------|-----------|------------|--------------|--------
#   sin cota|   70,3%   |    7,10    |  349.576.853 |    0 %
#   0 M     |   70,3%   |    9,55    |  277.912.514 | 20,5 %
#   20 M    |   70,3%   |    8,86    |  286.274.972 | 18,1 %
#   50 M    |   70,3%   |    8,16    |  299.538.061 | 14,3 %   <- elegida
#
# El recall sale PLANO en toda la tabla, y tiene que salir plano: la cota
# reordena las 18 posiciones, no cambia cuáles son. Si alguna vez se mueve, es
# que algo está eliminando candidatos y hay un bug.
#
# 50 millones es el punto que más respeta el trabajo del modelo: captura el 70%
# del ahorro máximo y es el que menos degrada la posición media (8,16 contra
# 9,55 del caso degenerado). La curva es de rendimientos decrecientes en las
# dos direcciones — bajar a 20 compra 3,8 puntos de ahorro a cambio de 0,7 de
# posición— así que el rango 20-50 es una decisión de producto, no de
# ingeniería: cuánto se quiere que el precio pise al modelo.
#
# Lo que sí es un error es ponerla en una cifra que sobre precios de cientos
# de millones sea ruido (50 MIL, por ejemplo): ahí se invierten prácticamente
# todos los pares, el top queda ordenado por precio a secas y el recomendador
# se convierte en un buscador de lo más barato. Es la fila "0 M".
#
# --- LO QUE UNA COTA EN PESOS NO PUEDE HACER -------------------------------
# Los dos segmentos del catálogo no viven en la misma escala de precio:
#
#     VIS     58 proyectos   148.500.000 .. 383.600.000   mediana 246.413.350
#     No VIS  38 proyectos   276.000.000 .. 4.200.000.000 mediana 602.625.000
#
# Una cota FIJA es, por tanto, un porcentaje distinto en cada uno: 50 millones
# son el 8% de la No VIS mediana pero el 20% de la VIS mediana. Y eso se ve
# en el efecto, medido sobre 200 clientes separados por lo que buscan:
#
#   cota | VIS: % con movimiento | ahorro | No VIS: % con mov. | ahorro
#   -----|----------------------|--------|--------------------|--------
#   10 M |        100 %         | 16,0 % |       100 %        | 23,3 %
#   20 M |        100 %         | 12,4 % |       100 %        | 22,7 %
#   30 M |        100 %         |  9,2 % |       100 %        | 22,6 %
#   50 M |         91 %         |  3,0 % |       100 %        | 20,5 %
#
# En No VIS la cota funciona igual de bien en todo el rango: el ahorro apenas
# cae de 23,3% a 20,5%. En VIS, en cambio, 50 millones la dejan casi inactiva
# —del 12,4% de ahorro a 3,0%—, porque entre dos VIS es raro que haya ese
# salto. El promedio global de 14,3% esconde esa asimetría: la mayor parte de
# ese ahorro lo está produciendo el lado No VIS.
#
# Es una limitación del parámetro, no un bug. Si se quiere que la cota actúe
# parejo en los dos segmentos hay dos caminos, ninguno implementado todavía
# porque los dos cambian el comportamiento que se acaba de calibrar:
#   1. Una cota por segmento (p. ej. 20 M en VIS, 50 M en No VIS).
#   2. Una cota relativa: un % del precio del más barato del par, que se
#      adapta sola y no habría que revisar cuando cambien los precios.
COTA_MINIMA_COP = 50_000_000

# Cuánto pesa el esfuerzo de pago dentro del score final. Ver `PESOS_SCORE` en
# modelo.py, donde entra mezclado con los demás componentes.
PESO_ESFUERZO = 0.25

# Ingreso representativo de cada tramo del formulario, en SMMLV. El formulario
# captura rangos, no cifras, así que hay que elegir un punto por rango: se usa
# el centro de cada uno. El tramo 4 es abierto (">8 SMMLV") y se representa con
# 12, no con algo mayor: sobreestimarlo haría parecer alcanzable cualquier
# proyecto del catálogo y el componente dejaría de discriminar.
INGRESO_REPRESENTATIVO_SMMLV = {1: 1.5, 2: 3.0, 3: 6.0, 4: 12.0}

# Por debajo de estos años el crédito no aprieta y el esfuerzo puntúa perfecto.
# Por encima, decae linealmente hasta el plazo máximo del segmento (30 años en
# VIS, 20 en No VIS), donde llega a 0: pagar durante todo el plazo máximo
# disponible es, por definición, el peor encaje financiero posible.
ANOS_HOLGADOS = 5.0

# Un proyecto que la persona no puede amortizar ni en el plazo máximo. No se
# elimina del top —la lista quedaría corta y sin explicación— sino que se hunde
# al final con `_alcanzable: False`, para que la vista pueda decirlo en vez de
# esconderlo.
ANOS_INALCANZABLE = float("inf")

# Techo del score de un proyecto inalcanzable.
#
# Existe porque un 0 plano rompía el componente justo para quien más lo
# necesita: con el tramo de ingreso más bajo (1,5 SMMLV) NINGÚN proyecto del
# catálogo bogotano amortiza, así que los 18 salían con esfuerzo 0, el
# componente se volvía una constante y dejaba de ordenar nada. Pero no todos
# los imposibles son igual de imposibles: al que le falta un 5% de cuota no
# está en la misma situación que al que le falta la mitad, y el primero es el
# que hay que mostrar arriba —es el que se vuelve alcanzable con un subsidio,
# un codeudor o un ingreso familiar sumado—.
#
# Así que el inalcanzable puntúa en proporción a lo cerca que quedó, dentro de
# esta franja. El techo es bajo a propósito: un imposible nunca puede
# adelantar a un alcanzable real, por poco que le falte.
FRACCION_INALCANZABLE = 0.15


# ---------------------------------------------------------------------------
# A. Verificación de esfuerzo: ¿en cuántos años se paga esto?
# ---------------------------------------------------------------------------
def ingreso_mensual_cop(salario_cod):
    """Ingreso mensual representativo del tramo 1..4 del formulario, en COP."""
    representativo = INGRESO_REPRESENTATIVO_SMMLV.get(
        int(salario_cod or 2), INGRESO_REPRESENTATIVO_SMMLV[2]
    )
    return representativo * SMMLV


def cuota_que_puede_pagar(salario_cod, tipo_cod):
    """Cuota mensual máxima según el tope regulatorio de cuota/ingreso.

    El tope no es el mismo para los dos segmentos: 40% en VIS y 30% en No VIS
    (Decreto 257 de 2021). Es la norma que hace que un hogar de bajos ingresos
    alcance una VIS que con el 30% no alcanzaría.
    """
    return ingreso_mensual_cop(salario_cod) * parametros_credito(tipo_cod)["cuota_ingreso_max"]


def anos_de_pago(precio, salario_cod, tipo_cod=0, aplica_subsidio=False):
    """Años que tardaría en pagarse el proyecto con el ingreso de esa persona.

    Se despeja el número de cuotas de la fórmula de anualidad vencida:

        n = -ln(1 - F*i / C) / ln(1 + i)

    donde F es lo financiado, i la tasa mensual del segmento y C la cuota que
    la persona puede pagar. Si `C <= F*i` la cuota no alcanza a cubrir ni los
    intereses del primer mes: el saldo nunca baja y el logaritmo no existe.
    Ese caso devuelve infinito en vez de un número grande, porque no es "muy
    lento", es imposible — y el score tiene que poder distinguir las dos cosas.

    Returns:
        float: años (puede ser 0.0 si no hay nada que financiar, o inf).
    """
    financiado = monto_financiado(precio, tipo_cod, aplica_subsidio)
    if financiado <= 0:
        return 0.0, 1.0                  # el subsidio y la inicial lo cubren

    cuota = cuota_que_puede_pagar(salario_cod, tipo_cod)
    i = tasa_mensual(parametros_credito(tipo_cod)["tasa_ea"])
    interes_primer_mes = financiado * i

    # `cobertura` es qué fracción del interés del primer mes cubre la cuota que
    # la persona puede pagar. Por encima de 1 el saldo empieza a bajar y el
    # crédito termina algún día; en 1 o por debajo, no.
    cobertura = cuota / interes_primer_mes
    if cobertura <= 1.0:
        return ANOS_INALCANZABLE, cobertura

    n_cuotas = -math.log(1 - 1.0 / cobertura) / math.log(1 + i)
    return n_cuotas / 12.0, cobertura


def score_esfuerzo(anos, tipo_cod=0, cobertura=None):
    """Convierte los años de pago en una afinidad [0, 1].

    1.0 hasta `ANOS_HOLGADOS`, y de ahí decae linealmente hasta 0 en el plazo
    máximo del segmento. Se normaliza contra el plazo de CADA segmento, no
    contra un plazo único: 25 años son holgados en una VIS a 30 años e
    imposibles en una No VIS a 20, y un score que no distinga eso premiaría a
    la No VIS cara por el mero hecho de tener un plazo más corto.

    Si el proyecto es inalcanzable se cae a la franja de
    `FRACCION_INALCANZABLE`, proporcional a `cobertura`: entre dos imposibles,
    arriba el que quedó más cerca de serlo.
    """
    if anos is None or math.isinf(anos) or math.isnan(anos):
        if cobertura is None:
            return 0.0
        return round(FRACCION_INALCANZABLE * max(0.0, min(1.0, cobertura)), 6)
    plazo_maximo = parametros_credito(tipo_cod)["plazo_meses"] / 12.0
    if anos <= ANOS_HOLGADOS:
        return 1.0
    if anos >= plazo_maximo:
        # Ni siquiera cabe en el plazo máximo del segmento: no es imposible,
        # pero ningún banco lo presta así. Puntúa en la misma franja baja que
        # el inalcanzable, graduado por cuánto se pasa.
        return round(FRACCION_INALCANZABLE * (plazo_maximo / anos), 6)
    return (plazo_maximo - anos) / (plazo_maximo - ANOS_HOLGADOS)


def evaluar_esfuerzo(proyecto, salario_cod, usar_subsidio=False):
    """Los tres números de esfuerzo de un proyecto para una persona.

    Returns:
        dict con `anos_de_pago` (None si es inalcanzable, para que sea
        serializable a JSON), `score_esfuerzo` y `alcanzable`.
    """
    tipo_cod = proyecto.get("tipo_vivienda_cod")
    aplica = bool(usar_subsidio and proyecto.get("aplica_subsidio_caja") and tipo_cod == 1)
    anos, cobertura = anos_de_pago(proyecto.get("precio_desde_cop"), salario_cod,
                                   tipo_cod, aplica)
    alcanzable = not math.isinf(anos)
    return {
        "anos_de_pago": round(anos, 2) if alcanzable else None,
        "score_esfuerzo": round(score_esfuerzo(anos, tipo_cod, cobertura), 4),
        "alcanzable": alcanzable,
        "cobertura_cuota": round(cobertura, 4),
        "cuota_que_puede_pagar_cop": round(cuota_que_puede_pagar(salario_cod, tipo_cod)),
        "cuota_del_proyecto_cop": round(
            cuota_mensual(monto_financiado(proyecto.get("precio_desde_cop"), tipo_cod, aplica),
                          tipo_cod)
        ),
    }


# ---------------------------------------------------------------------------
# B. La cota de precio
# ---------------------------------------------------------------------------
def _precio(proyecto):
    """Precio del proyecto, o infinito si no lo publica.

    Infinito y no cero: un proyecto sin precio no puede reclamar ser el barato
    del par. Mismo criterio que `_precio_desempate` en modelo.py.
    """
    try:
        valor = float(proyecto.get("precio_desde_cop"))
    except (TypeError, ValueError):
        return float("inf")
    return valor if valor > 0 else float("inf")


def _aplicar_cota_precio(orden, cota_cop, respetar_prioridad=True):
    """Invierte los pares consecutivos cuyo salto de precio supera la cota.

    Es un `bubble sort` con umbral: solo intercambia cuando la diferencia es
    material. Eso es lo que produce el comportamiento por bandas — dentro de
    una banda de precio manda el score del modelo, entre bandas manda el
    precio — en vez de degenerar en un simple orden ascendente por plata.

    Termina siempre: cada intercambio mueve un precio estrictamente mayor
    hacia atrás, así que la suma de (posición x precio) decrece en cada uno.
    El tope de pasadas es una red de seguridad, no el mecanismo de parada.

    Args:
        respetar_prioridad: no cruza proyectos de distinto `_prioridad_filtro`
            (invariante 4). Ponerlo en False deja que el precio lo mande todo;
            existe para poder medir el efecto, no para producción.

    Returns:
        (lista reordenada, cuántos intercambios se hicieron)
    """
    orden = list(orden)
    intercambios = 0
    if cota_cop is None or cota_cop < 0:
        return orden, 0

    for _ in range(len(orden)):
        hubo_cambio = False
        for i in range(len(orden) - 1):
            arriba, abajo = orden[i], orden[i + 1]
            if respetar_prioridad and \
                    arriba.get("_prioridad_filtro", 0) != abajo.get("_prioridad_filtro", 0):
                continue
            if _precio(arriba) - _precio(abajo) > cota_cop:
                orden[i], orden[i + 1] = abajo, arriba
                intercambios += 1
                hubo_cambio = True
        if not hubo_cambio:
            break
    return orden, intercambios


# ---------------------------------------------------------------------------
# C. La función pública
# ---------------------------------------------------------------------------
def Cota_minimaBG(top, usuario_modelo=None, *, cota_cop=COTA_MINIMA_COP,
                  usar_subsidio=False, respetar_prioridad=True, verbose=False):
    """Reordena el top poniendo el precio y el esfuerzo de pago por delante.

    Args:
        top: la lista que devuelve `modelo()`, ya puntuada y ordenada.
        usuario_modelo: `{"salario":.., "personas_a_cargo":.., "edad":..}`.
            Sin él no se puede calcular el esfuerzo (depende del ingreso de la
            persona) y solo se aplica la cota de precio.
        cota_cop: la diferencia de precio que justifica una inversión.
        usar_subsidio: si la persona es afiliada a la caja y busca VIS, el
            subsidio baja lo financiado y con eso los años de pago.
        respetar_prioridad: ver `_aplicar_cota_precio`.

    Returns:
        La misma lista, reordenada, con cada proyecto anotado:
            `_anos_de_pago`         años estimados (None si es inalcanzable)
            `_score_esfuerzo`       afinidad [0,1] del esfuerzo de pago
            `_alcanzable`           False si la cuota no cubre ni intereses
            `_cuota_*_cop`          lo que puede pagar vs. lo que cuesta
            `_orden_cota`           posición final; `post_arreglos` la respeta
            `_movido_por_cota`      cuántas posiciones lo movió la cota
    """
    if not top:
        return []

    salario_cod = (usuario_modelo or {}).get("salario")

    # --- 1. Filtro de verificación: años de pago -------------------------
    anotados = []
    for proyecto in top:
        copia = dict(proyecto)
        if salario_cod is not None:
            esfuerzo = evaluar_esfuerzo(proyecto, salario_cod, usar_subsidio)
            copia.update({
                "_anos_de_pago": esfuerzo["anos_de_pago"],
                "_score_esfuerzo": esfuerzo["score_esfuerzo"],
                "_alcanzable": esfuerzo["alcanzable"],
                "_cuota_que_puede_pagar_cop": esfuerzo["cuota_que_puede_pagar_cop"],
                "_cuota_del_proyecto_cop": esfuerzo["cuota_del_proyecto_cop"],
            })
        anotados.append(copia)

    # Lo que la persona no puede pagar se va al fondo de su tramo antes de
    # aplicar la cota: sin esto, un inalcanzable barato podría ganar
    # intercambios y subir, que es justo lo contrario de lo que se busca.
    posicion_original = {id(p): i for i, p in enumerate(anotados)}
    anotados.sort(key=lambda p: (
        p.get("_prioridad_filtro", 0),
        not p.get("_alcanzable", True),
        posicion_original[id(p)],
    ))

    # --- 2. La cota de precio --------------------------------------------
    ordenados, intercambios = _aplicar_cota_precio(anotados, cota_cop, respetar_prioridad)

    # --- 3. Trazabilidad --------------------------------------------------
    for destino, proyecto in enumerate(ordenados):
        proyecto["_orden_cota"] = destino
        proyecto["_movido_por_cota"] = posicion_original[id(proyecto)] - destino

    if verbose:
        movidos = sum(1 for p in ordenados if p["_movido_por_cota"])
        inalcanzables = sum(1 for p in ordenados if p.get("_alcanzable") is False)
        print(f"[cota] {intercambios} intercambio(s), {movidos} proyecto(s) movidos, "
              f"{inalcanzables} inalcanzable(s) con salario={salario_cod}")

    return ordenados
