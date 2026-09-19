# Leadify

Recomendador de proyectos de vivienda en Bogotá D.C.

Una persona llena un formulario —cuánto gana, con cuántos vive, en qué
localidad (y barrio) quiere estar, qué zonas comunes le importan— y Leadify le devuelve
los **18 proyectos más compatibles**, cada uno con un porcentaje de
compatibilidad listo para mostrar en pantalla.

El catálogo se construye scrapeando cuatro constructoras que publican en
Bogotá: **Amarilo, Cusezar, Constructora Bolívar y Colsubsidio**.

> **¿Vas a conectar el front?** Empieza por
> **[CONTRATO_FRONT.md](CONTRATO_FRONT.md)**: qué formulario mínimo hay que
> llenar, qué JSON se manda y qué JSON vuelve.
>
> Detalle técnico del contrato de datos, de los grafos de localidades y de
> barrios, y del modelo: **[GUIA_TECNICA.md](GUIA_TECNICA.md)**.

> **El front ya está conectado.** En esta copia el front es **solo el
> formulario**: la experiencia de 7 preguntas que vive en
> **[frontend/public/experiencia/](frontend/public/experiencia/)**, servida a
> pantalla completa por Vite (la landing de GO FEST que la envolvía se borró).
> Consume el modelo a través de **[backend/api/app.py](backend/api/app.py)**,
> un wrapper de FastAPI sobre `recomendar()`.
> Correr los dos a la vez:
>
> ```bash
> cd backend && uvicorn api.app:app --port 8000   # backend
> cd frontend && npm install && npm run dev       # el quiz, en otra terminal
> ```
>
> `api/app.py` también expone `POST /api/llamar`, que arma el payload de 19
> campos que espera el flow de Dapta y lo dispara — necesita
> `DAPTA_FLOW_WEBHOOK_URL` en el entorno; sin ella responde en modo mock.
> El webhook del flow exige el header `x-api-key`: pon también
> `DAPTA_API_KEY` (la API key de la cuenta de Dapta dueña del flow) o el
> POST falla con 401.

---

## Instalación

```bash
cd backend && pip install -r requirements.txt
```

Requiere Python 3.10+.

## Uso

### 1. Construir el catálogo

```bash
cd backend && python scraping/scraper_projects.py
```

Consulta las cuatro constructoras, resuelve la localidad de cada proyecto a
partir de su dirección, escribe `Model/data_projects/proyectos_bogota.json` y
baja las imágenes a
`frontend/public/recursos/imagenes_proyectos/<id_proyecto>/` — una carpeta por
proyecto, nombrada con su `id_proyecto`. Las rutas las declara
`Model/rutas.py`.

```bash
python scraping/scraper_projects.py --no-imagenes       # solo el JSON (rápido)
python scraping/scraper_projects.py --fuente amarilo cusezar
python scraping/scraper_projects.py --salida otro.json
python scraping/scraper_projects.py --sin-coordenadas   # localidad solo por dirección
python scraping/scraper_projects.py --rehacer-imagenes  # re-bajar las que ya están
python scraping/scraper_projects.py --solo-barrios      # sin scrapear: reasignar el barrio
```

Además de la localidad, a cada proyecto se le asigna su **barrio** (sector
catastral) con el grafo de `Model/grafo_barrios.py`: por el nombre en la
dirección si lo trae, y si no, por la coordenada dentro de los polígonos
oficiales. El grafo compilado (`Model/data_projects/barrios_bogota.json`) ya
viene en el repo; para regenerarlo desde el TXT de vecinos:

```bash
python Model/grafo_barrios.py            # parsea el TXT y baja la geometría oficial
python Model/grafo_barrios.py --sin-descargar
```

Las imágenes son varios cientos de MB, así que esa carpeta está en
`.gitignore`. Una corrida interrumpida se retoma sola: por defecto se omite el
proyecto cuya carpeta ya está completa.

Al terminar imprime un resumen: proyectos por constructora, por localidad, por
confianza de la localidad asignada, y la lista de descartados con su motivo.

### 2. Preparar los datos del modelo

```bash
python Model/prep.py
```

Lee el catálogo, simula el crédito hipotecario de cada proyecto **con los
supuestos de su segmento** —VIS y No VIS no se financian igual: 10 % vs. 30 %
de cuota inicial, 30 vs. 20 años, 40 % vs. 30 % de cuota/ingreso— y le etiqueta
el **perfil de comprador** al que apunta. Escribe
`Model/data_projects/proyectos_model.json`. Detalle en
[GUIA_TECNICA.md §4.1](GUIA_TECNICA.md).

### 3. Entrenar el componente colaborativo

```bash
python Model/simulacion/generar_clientes.py --semilla 42   # 10 arquetipos x 100 = 1.000 clientes
python Model/simulacion/generar_historial.py --semilla 42  # 1.000 x 8 eventos = 8.000 interacciones
python Model/simulacion/evaluar.py --clientes-prueba 300 --top 18
python Model/simulacion/calibrar_cota.py --clientes 300    # recall vs. ahorro
```

Sin `historial_simulado.json` el modelo funciona solo en modo **contenido**.
Con él se activa el componente **colaborativo**, que busca usuarios parecidos
y extrapola su comportamiento. La evaluación mide exactamente cuánto aporta:

```
recall@18 solo contenido      :  68.7%
recall@18 con historial       :  70.3%
mejora que aporta el historial:   +1.7 puntos
```

**Ojo con leer solo el recall.** La compra que simula el historial trata el
precio de forma truncada —solo penaliza si el proyecto no alcanza al ingreso—,
así que le da igual mostrar el de 182 millones o el de 262. Desde la v0.3 el
modelo **no** da eso igual, y por eso hay un segundo instrumento:
`calibrar_cota.py` mide el recall **y** lo que este cambio persigue —precio,
años de pago y alcanzabilidad del top—. Ver [GUIA_TECNICA.md §4.5](GUIA_TECNICA.md).

Detalle en [simulacion/README.md](simulacion/README.md).

### 4. Recomendar

```bash
cd backend && python main.py
python main.py --usuario Model/data_projects/usuario_ejemplo.json
```

Deja el resultado en `backend/salidas/proyectos_listos_llamativos.json`.

Desde el front, con el payload que llega por HTTP — sin pasar por disco:

```python
from Model import recomendar, respuesta_json   # con backend/ en el path

payload = {                       # las 15 llaves del formulario
    "nombres": "Ana", "apellidos": "Torres", "correo": "ana@ejemplo.com",
    "telefono": 3009998877, "afiliado": 1,
    "tipo_vivienda": 1, "salario": 2, "personas_a_cargo": 3, "edad": 34,
    "Localidad": 7, "numero_habitaciones": 3, "piso": 1,
    "zonas_comunes": ["Lobby", "Zona kids", "Parque", "Salón social", "Gimnasio"],
}

resultado = recomendar(payload, ruta_salida=None, verbose=False)
return respuesta_json(resultado, ruta_salida=None)   # el JSON que consume la vista
```

`recomendar()` acepta un dict, un string JSON o una ruta a archivo.
`respuesta_json()` deja solo lo que la vista necesita. Formato completo en
[GUIA_TECNICA.md §5](GUIA_TECNICA.md).

Si el formulario viene mal, `recomendar()` levanta `ValueError` con **todos**
los errores juntos, no el primero, para que el front pueda marcarlos de una vez.

---

## Cómo funciona

```
scraping/          Model/prep.py   Model/modelo.py   Model/cota_minima.py   Model/pipeline.py
scraper_projects   perfil del      filtro duro       el precio y los        orquesta
4 constructoras -> proyecto     -> + NN + score   -> años de pago        -> las etapas
+ localidad        + crédito                         reordenan el top
+ imágenes         por segmento
```

1. **Filtro duro.** Se descarta lo que no sirve: tipo de vivienda, número de
   habitaciones, localidad y zonas comunes. Si quedan menos de 30 candidatos,
   la búsqueda se abre hacia las **localidades vecinas** recorriendo un grafo
   de colindancia (BFS), y solo si eso no alcanza se sueltan requisitos, del
   menos al más costoso para el usuario. El tipo de vivienda nunca se suelta:
   VIS y No VIS son categorías legales distintas. Un dato que la constructora
   no publica no cuenta como incumplimiento: el proyecto entra marcado y el
   score le descuenta.

2. **Nearest Neighbors.** Los candidatos se puntúan contra el usuario en un
   espacio de tres features —salario, personas a cargo, edad— donde la
   capacidad de pago pesa la mitad. Si hay historial de interacciones, se suma
   un componente colaborativo que busca usuarios parecidos y extrapola su
   comportamiento.

3. **Score final.** `0.50` modelo + `0.25` **esfuerzo de pago** + `0.17`
   coincidencia de zonas comunes + `0.08` cercanía, menos lo que se descuenta
   por datos que el proyecto no publica. Todos los componentes se devuelven
   por separado para que el ranking sea auditable.

   La **cercanía** es nueva en la v0.4: si el usuario dice su barrio, se mide
   en kilómetros por un grafo de 1.164 sectores catastrales (`distancia_km` en
   la respuesta) y pesa `0.12`; si no lo dice, se mide por saltos de localidad
   como antes y pesa `0.08`. Sin barrio, el resultado es idéntico al de la
   v0.3.

   El **esfuerzo de pago** es nuevo en la v0.3: cuántos años tardaría *esta*
   persona, con *su* tramo de ingreso, en terminar de pagar *ese* proyecto.
   Con el peso del salario dentro del modelo, la plata explica cerca de la
   mitad del score.

4. **`Cota_minimaBG`.** El top pasa por una verificación económica y una cota
   de precio: cuando un proyecto cuesta más de **50 millones** por encima del
   que va debajo suyo, se invierten — **aunque eso saque al usuario de la
   localidad que pidió**. Lo que no puede pagar se hunde, marcado, en vez de
   desaparecer. Lo que nunca hace es adelantar un proyecto admitido relajando
   requisitos por encima de uno que cumple todo.

   Efecto medido sobre 300 clientes de prueba no vistos: el Top 3 pasa de
   **375.943.386 a 299.538.061** de precio medio (−20,3 %) y de 10,1 a 9,5
   años de pago. El costo son 2,4 puntos de `recall@18`, y hay que saber
   contra qué se mide: ver la nota de la sección anterior y
   [GUIA_TECNICA.md §4.5](GUIA_TECNICA.md).

   La cota es un parámetro (`COTA_MINIMA_COP`). El rango útil va de 20 a 50
   millones —más ahorro contra más respeto al orden del modelo— y bajarla a
   una cifra que sobre estos precios sea ruido convierte el recomendador en un
   buscador de lo más barato.

5. **Porcentaje comercial.** El score crudo se convierte en porcentaje de
   compatibilidad: el primero muestra su score, elevado a 85 % si se queda
   corto, y cada uno de los siguientes resta los puntos de score que lo
   separan del anterior. Sin piso. Ningún porcentaje se repite: cuando dos
   caen en el mismo número, el más barato se queda con el alto.

---

## Estructura

El repo está partido en dos mitades que no se pisan: **`backend/`** y
**`frontend/`**. Dentro del backend, todo lo que *decide* vive en **`Model/`**.

```
Leadify/
├── backend/
│   ├── main.py                 lanzador de consola
│   ├── requirements.txt
│   ├── Model/                  EL MODELO
│   │   ├── rutas.py            dónde vive cada archivo (única fuente de rutas)
│   │   ├── catalogos.py        vocabularios canónicos y grafo de localidades
│   │   ├── grafo_barrios.py    grafo de 1.164 barrios: nodos, km y resolución
│   │   ├── prep.py             perfil objetivo + crédito por segmento
│   │   ├── modelo.py           filtro duro, Nearest Neighbors y score
│   │   ├── cota_minima.py      Cota_minimaBG: el precio y los años de pago
│   │   ├── pipeline.py         orquesta el pipeline · recomendar()
│   │   ├── data_projects/      LA DATA CON LA QUE SE ENTRENÓ
│   │   │   ├── proyectos_bogota.json     catálogo scrapeado
│   │   │   ├── proyectos_model.json      catálogo etiquetado (lo genera prep.py)
│   │   │   ├── clientes_simulados.json   1.000 clientes de los 10 arquetipos
│   │   │   ├── historial_simulado.json   8.700 interacciones simuladas
│   │   │   ├── localidades_bogota.json   límites oficiales de las 20 localidades
│   │   │   ├── barrios_bogota_vecinos.txt vecinos de cada sector catastral (fuente)
│   │   │   ├── barrios_bogota_geo.json   polígonos simplificados de los sectores
│   │   │   ├── barrios_bogota.json       el grafo compilado (lo genera grafo_barrios.py)
│   │   │   └── usuario_ejemplo.json      formulario de ejemplo
│   │   └── simulacion/
│   │       ├── arquetipos.py           los 10 arquetipos de comprador
│   │       ├── generar_clientes.py     100 variaciones cada uno → 1.000 clientes
│   │       ├── generar_historial.py    los convierte en interacciones
│   │       ├── evaluar.py              recall con y sin historial
│   │       ├── calibrar_cota.py        calibra la cota: recall vs. ahorro
│   │       └── calibrar_barrios.py     calibra el radio y el peso de la cercanía
│   ├── api/app.py              capa HTTP (FastAPI). No decide nada.
│   ├── scraping/
│   │   └── scraper_projects.py catálogo desde 4 constructoras + localidad + barrio + imágenes
│   ├── dapta/                  catálogo compacto para el prompt de Manuela
│   └── salidas/                resultado de UNA consulta (en .gitignore)
├── frontend/
│   ├── index.html              cascarón de una página: monta la experiencia
│   └── public/
│       ├── recursos/imagenes_proyectos/
│       │   ├── 1/  01.webp 02.jpg ...        el id_proyecto ES el nombre
│       │   └── 2/  ...                        de la carpeta
│       └── experiencia/        EL FORMULARIO: el quiz (bundle estático)
├── render.yaml
├── GUIA_TECNICA.md                   guía técnica
└── README.md
```

Las tres reglas de dónde va cada cosa, y por qué, en
[GUIA_TECNICA.md §1.2](GUIA_TECNICA.md).

## El JSON, en corto

Usuario y proyecto comparten estructura a propósito: el modelo los compara
campo a campo.

```json
{
  "id_proyecto": 14,
  "nombres": null, "apellidos": null, "correo": null,
  "telefono": null, "afiliado": null,
  "tipo_vivienda": 1,
  "salario": null, "personas_a_cargo": null, "edad": null,
  "Localidad": 7,
  "numero_habitaciones": 3,
  "piso": 4,
  "zonas_comunes": ["Lobby", "Piscina", "Zona de lavandería", "Zona BBQ"],
  "link_proyecto": "https://www.colsubsidio.com/vivienda/proyectos/bogota/acanto"
}
```

En el JSON del **usuario** están llenos los campos de persona; en el del
**proyecto** están en `null`, porque un proyecto no tiene correo ni edad.
`salario`, `personas_a_cargo` y `edad` sí los tiene el proyecto —son el perfil
de comprador al que apunta— pero los deriva `prep.py`, no el scraper.

Dominios completos en [GUIA_TECNICA.md §2](GUIA_TECNICA.md).

## Localidad a partir de la dirección

`scraping/scraper_projects.py` resuelve la localidad leyendo la dirección, en tres
pasadas de mayor a menor confianza: nombre explícito de la localidad →
gazetteer de ~250 barrios y sectores → malla vial (calle/carrera). Cada
proyecto queda marcado con la pasada que lo resolvió.

```python
from scraper_projects import localidad_desde_direccion, asignar_localidades

localidad_desde_direccion("Carrera 95A # 78 Sur, Bosa Recreo")
# {'localidad': 7, 'nombre': 'Bosa', 'confianza': 'alta', ...}

asignar_localidades(proyectos)   # devuelve el mismo JSON con `Localidad`
```

Las coordenadas de los proyectos que las publican se usan solo como respaldo:
en varias fichas el pin del mapa apunta a la sala de ventas y no al proyecto.
Ver [GUIA_TECNICA.md §6.3](GUIA_TECNICA.md).

## Barrio a partir de la coordenada

Para el barrio es al revés: casi ninguna dirección lo nombra, así que manda la
coordenada, siempre subordinada a la localidad ya asignada (un pin que caiga
en otra localidad se descarta).

```python
from Model.grafo_barrios import barrio_desde_coordenadas, distancia_barrios

barrio_desde_coordenadas(4.742846, -74.067187, localidad=11)
# {'barrio': '009128', 'nombre': 'El Plan', 'localidad': 11, 'confianza': 'alta', ...}

distancia_barrios("Prado Veraniego", "El Plan")   # km por el grafo -> 2.8
```

Hoy 83 de los 96 proyectos tienen barrio. Los 13 restantes no publican
coordenada o la publican en otra localidad, y para ellos el modelo usa la
distancia típica de su salto de localidad. Ver [GUIA_TECNICA.md §3](GUIA_TECNICA.md).
