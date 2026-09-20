# simulacion/

Base de clientes sintéticos para entrenar y evaluar el recomendador.

No hay datos reales de compradores, así que hay que fabricarlos. El problema
de fabricarlos mal es concreto: el componente colaborativo del modelo busca
**usuarios parecidos entre sí**, y si cada perfil se muestrea campo a campo de
forma independiente, no hay nadie a quien parecerse — los "vecinos" que
encuentra son ruido correlacionado y el modelo no aprende nada.

Por eso la base se construye en dos pasos:

```
10 arquetipos  ──100 variaciones cada uno──▶  1.000 clientes  ──8 eventos──▶  8.000 interacciones
  arquetipos.py        generar_clientes.py      data_projects/           data_projects/
                                                clientes_simulados.json  historial_simulado.json
```

---

## Los 10 arquetipos

Cada uno es un tipo de comprador real del mercado de Bogotá, con su rango de
edad, capacidad de pago, tamaño de hogar, dónde busca y qué amenidades le
importan.

| id | Arquetipo | Perfil |
|---|---|---|
| `joven_profesional` | Joven profesional, primer apartamento | 25–32, 1–2 alcobas, Chapinero/Teusaquillo, coworking y gimnasio |
| `pareja_sin_hijos` | Pareja joven sin hijos | 27–36, doble ingreso, 2 alcobas, compra a cinco años |
| `familia_joven` | Familia joven con hijo pequeño | 30–40, VIS, 3 alcobas, zona kids y parque |
| `familia_numerosa_vis` | Familia numerosa con subsidio | 33–48, ingreso bajo, 3 alcobas, Bosa/Usme |
| `reposicion` | Comprador de reposición | 40–55, No VIS, mejora de vivienda, piscina y sauna |
| `inversionista` | Inversionista | 35–58, área pequeña, buena ubicación, no va a vivir ahí |
| `nido_vacio` | Nido vacío | 54–70, reduce metros, zonas verdes y parqueadero |
| `cabeza_de_hogar` | Cabeza de hogar con subsidio | 28–44, decide por cuota mensual y transporte |
| `teletrabajo_mascota` | Teletrabajador con mascota | 28–42, coworking y zona pet |
| `primer_comprador_caja` | Primer comprador afiliado a caja | 24–34, VIS, sensible a la cuota inicial |

Las localidades de cada uno se eligieron mirando dónde hay oferta —Suba,
Fontibón, Bosa, Engativá y Usme concentran el 80 % del catálogo— pero sin
dejar sin demanda a las que tienen poca: **las 20 localidades reciben
búsquedas**.

`arquetipos.validar()` corre en cada generación y verifica que los pesos sumen
1, que los códigos estén en su dominio y que ninguna zona esté a la vez en el
núcleo y en las opcionales. Un arquetipo mal escrito produciría clientes
inválidos y un historial contaminado, sin que nada falle de forma visible.

## Las 100 variaciones

Cada variación muestrea dentro de su arquetipo y además se deja **derivar** un
poco, a propósito:

| Deriva | Prob. | Por qué |
|---|---:|---|
| Busca en una localidad que su arquetipo no lista | 12 % | La gente mira fuera de su zona |
| Se corre un tramo de ingreso | 15 % | El arquetipo es un centro, no una caja |
| Cambia el tamaño del hogar | 15 % | Idem |
| No marca una de sus amenidades características | 20 % | Nadie llena el formulario igual dos veces |

Sin esa deriva, las 100 variaciones serían 100 copias con ruido cosmético: el
modelo colaborativo vería 10 puntos en vez de 1.000 y el K de vecinos dejaría
de significar nada.

Hay una corrección de coherencia: un hogar de 3 o más personas nunca queda
buscando un aparta-estudio. Se corrige al alza en vez de descartar la
variación, para no sesgar el muestreo.

## Formato de salida

`clientes_simulados.json` trae los clientes **en el mismo contrato JSON que
manda el front** (las 15 llaves del formulario). Eso les da doble uso:

```python
from main import recomendar
import json

clientes = json.load(open("Model/data_projects/clientes_simulados.json", encoding="utf-8"))["clientes"]
resultado = recomendar(clientes[0])          # se le pasa tal cual, sin adaptar nada
```

Los nombres son sintéticos y evidentes (`Cliente 042`, `joven_profesional-042@ejemplo.local`):
estos registros van a un JSON que se comparte y no deben poder confundirse con
personas reales.

---

## Uso

```bash
# 1. Los 1.000 clientes
python Model/simulacion/generar_clientes.py --semilla 42

# 2. Las 8.000 interacciones (desde la raíz)
python Model/simulacion/generar_historial.py --semilla 42

# 3. ¿Está sirviendo el historial?
python Model/simulacion/evaluar.py --clientes-prueba 300 --top 18
```

Opciones:

```bash
python Model/simulacion/generar_clientes.py --variaciones 200   # 2.000 clientes
python Model/simulacion/generar_historial.py --interacciones 12  # 12.000 registros
python Model/simulacion/generar_historial.py --demografico --n 4000  # el muestreo antiguo
```

## La evaluación

> **Desde la v0.3 `evaluar.py` no basta solo.** Su "verdad" —la utilidad con
> la que estos clientes eligen— trata el precio de forma truncada: solo
> penaliza cuando el proyecto no alcanza al ingreso, así que entre uno de 182
> millones y uno de 262 que el comprador puede pagar le da igual cuál se le
> muestre. El modelo ya no da eso igual, así que hay un segundo instrumento,
> `calibrar_cota.py`, que mide recall **y** precio, años de pago y
> alcanzabilidad del top. Ver [Métricas de Calidad](https://github.com/SaraCuervo/Leadify/wiki/M%C3%A9tricas-de-Calidad), en la wiki.
>
> Si algún día esta utilidad se actualiza para preferir lo barato entre lo
> pagable, todas las cifras de recall de la documentación hay que rehacerlas.
>
> **Desde la v0.4 hay un tercer instrumento, `calibrar_barrios.py`.** Los
> clientes simulados no traen barrio, así que a cada uno se le sortea un
> sector urbano de su localidad y se mide a cuántos kilómetros —por el grafo
> de barrios— queda lo que se le recomienda, con y sin ese dato, junto al
> recall y al precio. Es lo que fijó `RADIO_CERCANIA_KM` y
> `PESO_LOCALIDAD_CON_BARRIO` en `modelo.py`. Ver [Métricas de Calidad](https://github.com/SaraCuervo/Leadify/wiki/M%C3%A9tricas-de-Calidad).
>
> ```bash
> python Model/simulacion/calibrar_barrios.py --clientes 300
> ```

`evaluar.py` responde una sola pregunta: **¿el componente colaborativo acierta
más que el de contenido solo?**

Cómo lo mide sin hacer trampa:

1. Genera clientes de prueba con **otra semilla**: el modelo nunca los vio.
2. Les hace "comprar" un proyecto con el mismo modelo de utilidad que produjo
   el historial. Esa utilidad incluye el **atractivo latente** de cada
   proyecto: una señal que el recomendador no puede deducir de
   `proyectos_model.json` y que solo puede aprender de las interacciones de
   otros clientes parecidos.
3. Compara el Top 6 de los dos modos contra esa compra.

Como el atractivo latente es lo único que los separa, la diferencia de recall
**es** lo que aporta el historial.

Resultado con los parámetros actuales, sobre 600 clientes no vistos:

```
recall@6 solo contenido      :  69.3%
recall@6 con historial       :  77.5%
mejora que aporta el historial:  +8.2 puntos
posición media del acierto   :   2.68
```

Esta evaluación fue también la que detectó que `K_VECINOS` estaba mal
calibrado: con el tope anterior de 200 el colaborativo rendía 68.8 %, por
debajo del contenido solo. Ver [Arquitectura y Diseño](https://github.com/SaraCuervo/Leadify/wiki/Arquitectura-y-Dise%C3%B1o), en la wiki.

## Advertencia

Todo lo que hay aquí es **sintético**. Sirve para que el modelo tenga con qué
entrenar y para poder medirlo, no para sacar conclusiones de mercado. Cuando
haya interacciones reales, `historial_simulado.json` se reemplaza por ellas y
`modelo.py` no necesita ningún cambio: espera el mismo formato.
