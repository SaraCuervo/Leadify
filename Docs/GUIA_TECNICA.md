# Leadify — guía técnica

Recomendador de proyectos de vivienda en Bogotá D.C. Recibe el formulario de
un usuario y devuelve los 18 proyectos más compatibles (`TOP_N`), cada uno
con un porcentaje de compatibilidad listo para mostrar.

El repo está partido en dos: **`backend/`** —el motor (`Model/`), la capa HTTP
(`api/`, FastAPI) y el scraper— y **`frontend/`**, que en esta copia es **solo
el formulario**: la experiencia de 7 preguntas de `public/experiencia/`
servida a pantalla completa. La landing de GO FEST que la envolvía se borró
(§8). Ver §1 para el mapa completo.

**Novedad de la v0.4: la cercanía se mide en kilómetros.** El grafo de 20
localidades se queda para decidir *quién entra* (§3.3), pero encima hay ahora
un grafo de **1.164 barrios** —sectores catastrales oficiales, con aristas
que pesan kilómetros— que decide *qué tan cerca queda de verdad* (§3.5). Un
usuario que pide Suba y dice su barrio ya no ve a la misma distancia La
Colina y Lisboa, que están a 8 km. El formulario gana un campo opcional,
`barrio`; sin él, el resultado es idéntico al de la v0.3.

**De la v0.3: el dinero decide.** El ranking dejó de ordenarse
principalmente por parecido demográfico. El crédito se simula distinto
para VIS y para No VIS (§4.1), el score incluye cuántos años tardaría esa
persona en pagar el proyecto (§4.3), y `Cota_minimaBG` deja que una diferencia
de precio suficiente —50 millones— invierta dos posiciones aunque saque al
usuario de la localidad que pidió (§4.5). El Top 3 sale un 20 % más barato.

Este documento describe el contrato de datos, los dos grafos de proximidad
—localidades y barrios—, la resolución de localidad y barrio por dirección y
coordenada, la API y el formulario.
Para correr el proyecto, ver [README.md](../Demo/README.md); para el formulario
mínimo que espera el modelo, [CONTRATO_FRONT.md](CONTRATO_FRONT.md).

---

## 1. Arquitectura en una página

El repo está partido en dos mitades que no se pisan: **`backend/`** (el motor y
lo que lo expone) y **`frontend/`** (el formulario y lo que se le sirve al
navegador). Dentro del backend, todo lo que *decide* vive en **`Model/`**.

```
Leadify/
├── backend/
│   ├── main.py                     lanzador de consola -> Model/pipeline.py
│   ├── requirements.txt
│   ├── Model/                      EL MODELO. Lo único que decide qué se recomienda.
│   │   ├── rutas.py                dónde vive cada archivo. Única fuente de rutas.
│   │   ├── catalogos.py            vocabularios canónicos + el grafo de localidades
│   │   ├── grafo_barrios.py        el grafo de 1.164 barrios: km, Dijkstra, resolución (§3.5)
│   │   ├── prep.py                 catálogo crudo -> perfil objetivo por proyecto
│   │   ├── modelo.py               filtro duro + NearestNeighbors + porcentaje
│   │   ├── cota_minima.py          Cota_minimaBG: precio y esfuerzo de pago (§4.5)
│   │   ├── pipeline.py             encadena las etapas -> recomendar()
│   │   ├── data_projects/          LA DATA CON LA QUE SE ENTRENÓ (§1.2)
│   │   │   ├── proyectos_bogota.json      catálogo crudo del scraper
│   │   │   ├── proyectos_model.json       catálogo etiquetado (lo lee el modelo)
│   │   │   ├── clientes_simulados.json    1.000 clientes de los 10 arquetipos
│   │   │   ├── historial_simulado.json    8.700 interacciones simuladas
│   │   │   ├── localidades_bogota.json    límites oficiales de las 20 localidades
│   │   │   ├── barrios_bogota_vecinos.txt vecinos de cada sector catastral (FUENTE)
│   │   │   ├── barrios_bogota_geo.json    polígonos simplificados (Datos Abiertos)
│   │   │   ├── barrios_bogota.json        el grafo compilado que lee el modelo
│   │   │   └── usuario_ejemplo.json       formularios de prueba
│   │   └── simulacion/             cómo se fabricó ese historial (§4.6)
│   │       ├── arquetipos.py · generar_clientes.py · generar_historial.py
│   │       ├── evaluar.py          recall con y sin historial
│   │       ├── calibrar_cota.py    calibra COTA_MINIMA_COP (§4.5)
│   │       └── calibrar_barrios.py calibra RADIO_CERCANIA_KM y el peso (§3.5)
│   ├── api/app.py                  capa HTTP (FastAPI). No decide nada (invariante 8).
│   ├── scraping/scraper_projects.py construye el catálogo desde 4 constructoras
│   ├── dapta/                      catálogo compacto para el prompt de Manuela
│   └── salidas/                    resultado de UNA consulta. En .gitignore.
└── frontend/
    ├── index.html                  cascaron de una pagina: monta la experiencia (§8)
    └── public/
        ├── recursos/imagenes_proyectos/<id_proyecto>/   las fotos (§1.3)
        └── experiencia/            el quiz embebido, bundle estático autocontenido
```

### 1.1 El flujo de una recomendación

```
     proyectos_bogota.json                    formulario del usuario
     (scraping/scraper_projects.py)           (frontend, o usuario_ejemplo.json)
                 |                                        |
                 v                                        |
             prep.py                                      |
     etiqueta el perfil objetivo                          |
     y simula el crédito por segmento (§4.1)              |
                 |                                        v
       proyectos_model.json                        leer_info_user()
                 |                                        |
                 |          +-------------------+---------+---------+
                 |          |                   |                   |
                 |    usuario_modelo    usuario_segmentado    info_contacto
                 |    (3 features)      (4 llaves duras)      (no entra al modelo)
                 |          |                   |
                 +----------+-------------------+
                            |
                      primer_filtro()          A
                 filtro duro + BFS sobre el
                 grafo de localidades
                 + km por el grafo de barrios (§3.5)
                            |
                 proyectos_preseleccionados (>= 30)
                            |
                        modelo()               B
              NearestNeighbors contenido + colaborativo
              + esfuerzo de pago en el score (§4.3)
                            |
                 proyectos_seleccionados (Top TOP_N)
                            |
                     Cota_minimaBG()           C   <-- nuevo en v0.3
              verifica años de pago y deja que el
              precio invierta posiciones (§4.5)
                            |
                     post_arreglos()           D
              score -> porcentaje de compatibilidad
                            |
              salidas/proyectos_listos_llamativos.json
```

Y la capa que lo expone al mundo:

```
   frontend/ (el formulario)                 backend/api/app.py (FastAPI, :8000)
   -------------------------                 -----------------------------------
   experiencia/  --- POST /api/recomendar -->  recomendar() + respuesta_json()
   (el quiz)     --- GET  /api/catalogos  -->  Model/catalogos.py (ids canónicos)
                 --- GET  /api/barrios    -->  Model/grafo_barrios.py (barrios de una localidad)
                 --- POST /api/llamar     -->  payload de 19 campos
                                                        |
                                                        v
                                          DAPTA_FLOW_WEBHOOK_URL
                                          (flow de voz de Manuela)
```

| Archivo | Responsabilidad |
|---|---|
| `Model/rutas.py` | Dónde vive cada archivo. **Única fuente de verdad** de las rutas (§1.2). |
| `Model/catalogos.py` | Vocabularios canónicos y el grafo de localidades. **Única fuente de verdad** de los ids. |
| `Model/grafo_barrios.py` | El grafo de barrios: parsea el TXT de vecinos, baja la geometría, resuelve barrios por nombre y coordenada, y mide km (Dijkstra). |
| `Model/prep.py` | Convierte el catálogo crudo en `proyectos_model.json`: perfil objetivo y simulación de crédito por segmento. |
| `Model/modelo.py` | Filtro duro, Nearest Neighbors y normalización comercial. |
| `Model/cota_minima.py` | `Cota_minimaBG`: años de pago y la cota de precio que reordena el top. |
| `Model/pipeline.py` | Encadena las etapas y expone `recomendar()`, el punto de entrada del front. |
| `main.py` | Lanzador de consola. Delgado: delega en `Model/pipeline.py`. |
| `api/app.py` | Wrapper HTTP (FastAPI) sobre `recomendar()`. Endpoints + el disparo a Dapta (§5.2). |
| `scraping/scraper_projects.py` | Construye el catálogo desde 4 constructoras, asigna localidad y baja imágenes. |
| `frontend/` | El formulario: el bundle de `public/experiencia/` servido por Vite (§8). |
| `Model/simulacion/generar_historial.py` | Convierte los clientes simulados en el historial de interacciones. |
| `Model/simulacion/arquetipos.py` | Los 10 arquetipos de comprador. |
| `Model/simulacion/generar_clientes.py` | 100 variaciones por arquetipo → 1.000 clientes. |
| `Model/simulacion/evaluar.py` | Mide el recall del top con y sin historial contra clientes no vistos. |
| `Model/simulacion/calibrar_cota.py` | Calibra `COTA_MINIMA_COP`: recall vs. ahorro (§4.5). |
| `Model/simulacion/calibrar_barrios.py` | Calibra `RADIO_CERCANIA_KM` y `PESO_LOCALIDAD_CON_BARRIO`: km del top vs. recall y precio (§3.5). |

El entrenamiento entra por la izquierda del diagrama:

```
arquetipos.py ──▶ generar_clientes.py ──▶ data_projects/clientes_simulados.json
                                                         |
                                                generar_historial.py
                                                         |
                                  data_projects/historial_simulado.json ──▶ modelo()
```

### 1.2 Dónde vive cada cosa, y por qué

Tres reglas, y las tres las declara **`Model/rutas.py`**. Ningún otro módulo
calcula rutas: antes cada uno hacía su `os.path.dirname(__file__)` y colgaba
los datos de donde cayera, que es la versión del invariante 1 aplicada a
archivos — un desfase que no falla, solo lee otra cosa.

| Carpeta | Qué guarda | ¿Se versiona? |
|---|---|---|
| `backend/Model/data_projects/` | **Entradas**: el catálogo, los clientes simulados, el historial con el que se entrenó, los límites oficiales de las localidades, y el grafo de barrios (TXT fuente + geometría + JSON compilado). | Sí. Son lo que hace que `recomendar()` funcione recién clonado, sin scrapear ni entrenar. ~5,7 MB. |
| `backend/salidas/` | **Salidas** de una consulta concreta: `proyectos_listos_llamativos.json`, `respuesta.json`. | No. Cambian en cada llamada. |
| `frontend/public/recursos/imagenes_proyectos/<id>/` | Las fotos de cada proyecto. | No: son ~285 MB y los regenera el scraper. |

`data_projects` está **dentro de `Model/`** a propósito: son los datos con los
que el modelo fue entrenado y contra los que recomienda, así que viajan con
él. Separarlos del código que los interpreta es lo que hace que un catálogo
regenerado y un modelo viejo terminen conviviendo sin que nadie se entere.

### 1.3 Las imágenes viven del lado del front

`frontend/public/recursos/imagenes_proyectos/<id_proyecto>/01.webp, 02.jpg, …`
— una carpeta por proyecto, **nombrada con su `id_proyecto`**. Están del lado
del front porque el front es quien las sirve; el backend nunca las abre, solo
compone la ruta. El scraper escribe directamente ahí (`DIR_IMAGENES` en
`Model/rutas.py`).

Que el id **sea** el nombre de la carpeta es lo que permite que la vista pase
de un `id_proyecto` de la respuesta a sus fotos sin ninguna tabla intermedia.
El costo es que renumerar los ids —lo que pasa cuando una constructora publica
o retira un proyecto— renumera también las carpetas: es el mismo contrato de
siempre (§2.4), ahora con la carpeta en su sitio.

`frontend/public/experiencia/` tiene su **propia** copia de imágenes y no usa
esta. Es un bundle estático autocontenido con rutas relativas a sí mismo, y
sacarle los assets rompería un artefacto que este repo no compila.

---

## 2. El contrato JSON

Usuario y proyecto comparten estructura a propósito: el modelo compara campo
a campo, así que las dos mitades del cruce tienen que hablar el mismo idioma.

### 2.1 Campos

| Campo | Tipo | Dominio | Lo aporta |
|---|---|---|---|
| `id_proyecto` | `int` | 1 … N, consecutivo | proyecto |
| `nombres` | `string` | libre | usuario |
| `apellidos` | `string` | libre | usuario |
| `correo` | `string` | libre | usuario |
| `telefono` | `int` | libre | usuario |
| `afiliado` | `bool` | `0` no · `1` sí | usuario |
| `tipo_vivienda` | `bool` | `0` No VIS · `1` VIS | **ambos** |
| `salario` | `int` | `1` ≤2 SMMLV · `2` 2–4 · `3` 4–8 · `4` >8 | **ambos** |
| `personas_a_cargo` | `int` | `1`–`4`, donde `4` es "4 o más" | **ambos** |
| `edad` | `int` | 18–125 | **ambos** |
| `Localidad` | `int` | `1`–`20`, sin ceros a la izquierda | **ambos** |
| `barrio` | `string` | **opcional**. Nombre o código de sector catastral (`GET /api/barrios`) | usuario |
| `numero_habitaciones` | `int` | `1`–`3`, donde `3` es "3 o más" | **ambos** |
| `piso` | `int` | `0` bajo · `1` medio · `3` alto · `4` sin preferencia | usuario |
| `zonas_comunes` | `string[]` | vocabulario de 25 (§2.3) | **ambos** |
| `link_proyecto` | `string` | URL de la ficha oficial | proyecto |

**"Ambos" es la clave del diseño.** En el JSON del usuario esos campos son la
*preferencia declarada*; en el del proyecto son el *perfil objetivo*, es decir
el comprador al que apunta. `salario`, `personas_a_cargo` y `edad` no se leen
de la web de la constructora —ninguna los publica— sino que los **deriva
`prep.py`** del precio, el área y las amenidades (§4.1). El scraper los deja
en `null` y `prep.py` los llena.

Los campos que solo puede aportar la persona (`nombres`, `apellidos`, `correo`,
`telefono`, `afiliado`) salen en `null` en el JSON del proyecto. Se emiten
igual, y en el mismo orden, para que las dos estructuras sean idénticas.

**`barrio` es el único campo opcional que cambia el resultado y no filtra.**
Del lado del usuario es un nombre o código de sector catastral; del lado del
proyecto es `barrio_id` (§2.2), que lo resuelve el scraper. Cuando los dos
existen, el score mide la cercanía en kilómetros por el grafo de barrios en
vez de en saltos de localidad (§3.5). Si el barrio contradice a `Localidad`
—"Cedritos" con `Localidad = 11`— es un error del formulario y sale con los
demás; si no está en el grafo, se reporta en `barrio_no_reconocido` y el
score usa la localidad. Si viene sin `Localidad`, la localidad se deduce de
él.

### 2.2 Campos extra del proyecto

El formulario no contempla precio ni dirección, pero el modelo los necesita.
Van después del contrato, agrupados aparte:

| Campo | Para qué |
|---|---|
| `nombre_proyecto` | Identificación legible. |
| `constructora` | `amarilo` · `cusezar` · `bolivar` · `colsubsidio`. |
| `direccion` | Entrada de la resolución de localidad (§6). |
| `precio_desde_cop` | `prep.py` deriva de aquí `salario` objetivo. |
| `area_desde_m2` | Alimenta `precio_por_m2` y el segmento de precio. |
| `lat` / `lon` | Respaldo de localidad y **señal principal del barrio**. `null` en Cusezar, que no las publica. |
| `barrio_id` / `barrio_nombre` | Sector catastral del proyecto, nodo del grafo de barrios (§3.5). `null` en 13 de 96: sin coordenada, o con el pin en otra localidad. |
| `_barrio_confianza` / `_barrio_evidencia` | `alta` (nombre en la dirección o polígono) · `media` (centroide cercano, o barrio de localidad vecina). Qué dato lo resolvió (§6.4). |
| `imagenes_origen` | URLs de las que salen `imagenes_proyectos/<id>/`. |
| `zonas_comunes_idx` | Los mismos nombres como índices 0–24, listos para el vector binario. |
| `zonas_comunes_no_mapeadas` | Amenidades que no encajan en las 25. **No se fuerzan**: se reportan. |
| `tipo_vivienda_publicado` | El texto original (`TOPE VIS`, `VIP`, `No aplica`…) antes de codificar. |
| `constructoras` / `links_alternos` | Solo en los 6 proyectos que publican dos constructoras (§7). |
| `localidad_nombre` | Nombre oficial, para que el JSON se lea sin tabla al lado. |
| `_localidad_confianza` | `alta` · `media` · `baja` (§6.2). |
| `_localidad_evidencia` | Qué dato disparó la asignación. Permite auditar el catálogo. |

### 2.3 Vocabulario de zonas comunes

25 posiciones, el índice **es** el identificador. Viven en
`catalogos.ZONAS_COMUNES` y viajan como vector binario de 25 al modelo.

```
 0 Lobby                6 Locales comerciales  12 Coworking       18 Parque
 1 Piscina              7 Zona fitness         13 Sala VIP        19 Sala de juegos
 2 Zona de lavandería   8 Salón social         14 Zona café       20 Pista de trote
 3 Zona BBQ             9 Spa mascotas         15 Gimnasio        21 Voleibol playa
 4 Zona pet            10 Zona cool            16 Parqueadero     22 Cancha de pádel
 5 Zona kids           11 Zona cine            17 Zona verde      23 Taller de bicicletas
                                                                  24 Sauna
```

Cada web usa sus propias etiquetas ("Terraza BBQ", "Gimnasio semidotado",
"Social kitchen"). `scraper_projects.mapear_zonas_comunes` las traduce con una
tabla de alias **explícita**. Nada de coincidencias difusas: una amenidad
desconocida ("Chute de basura", "Ascensores", "Administración") va a
`zonas_comunes_no_mapeadas` en vez de asignarse a una categoría que no le
corresponde.

### 2.4 Ejemplo

Proyecto:

```json
{
  "id_proyecto": 61,
  "nombres": null, "apellidos": null, "correo": null,
  "telefono": null, "afiliado": null,
  "tipo_vivienda": 1,
  "salario": null, "personas_a_cargo": null, "edad": null,
  "Localidad": 7,
  "numero_habitaciones": 3,
  "piso": 4,
  "zonas_comunes": ["Lobby", "Piscina", "Zona de lavandería", "Zona BBQ"],
  "link_proyecto": "https://www.colsubsidio.com/vivienda/proyectos/bogota/acanto",

  "nombre_proyecto": "Acanto",
  "constructora": "colsubsidio",
  "direccion": "Carrera 95A # 78 Sur, Bosa Recreo",
  "precio_desde_cop": 231290000,
  "area_desde_m2": 50.6,
  "aplica_subsidio_caja": true,
  "localidad_nombre": "Bosa",
  "_localidad_confianza": "alta",
  "_localidad_evidencia": "nombre de localidad en la direccion: Bosa"
}
```

Los ids son consecutivos desde 1 y se asignan **después** de resolver la
localidad, ordenando por constructora y nombre: dos corridas seguidas dan los
mismos ids mientras el catálogo publicado no cambie. Cambian, eso sí, cuando
una constructora publica o retira un proyecto — y las carpetas de
`imagenes_proyectos/` se renumeran con ellos.

Usuario: mismas 15 llaves, con los campos de persona llenos y los de proyecto
en su lugar (`usuario_ejemplo.json`).

### 2.5 Notas sobre `piso`

`piso` es una preferencia del comprador. Un proyecto no tiene *un* piso, tiene
torres de muchos, así que el scraper emite siempre `4` (sin preferencia), el
mismo valor neutro que `Model/modelo.py` asume cuando el dato falta. Hoy el campo se
captura pero no filtra nada: ninguna constructora publica el piso por unidad.

---

## 3. El grafo de proximidad entre localidades

### 3.1 Qué es

`Model/catalogos.py` define un grafo **no dirigido, no ponderado y conexo**
`G = (V, E)` donde:

- **V** = las 20 localidades de Bogotá D.C., con su id oficial 1–20.
- **E** = 43 aristas, una por cada par de localidades que **colindan**.
- **W** = todas las aristas pesan 1 (`PESO_ARISTA`). La distancia entre dos
  localidades es el número mínimo de fronteras que hay que cruzar.

```
V = 20 nodos · E = 43 aristas · diámetro = 5 · radio = 3
grado máximo: Teusaquillo (7)      grado mínimo: Usaquén, Bosa, Sumapaz (2)
centro del grafo: Fontibón y Puente Aranda (excentricidad 3)
```

### 3.2 Cómo se construye

La adyacencia se declara a mano en `_ADYACENCIA_DECLARADA` y luego
`_construir_grafo` la **simetriza**: por cada `a → b` declarada se agrega
también `b → a`. Así el grafo queda no dirigido aunque la declaración tenga
omisiones, que es exactamente el tipo de error que se cuela al transcribir 20
listas de vecinos a mano.

```python
GRAFO_LOCALIDADES = {1: [2, 11], 2: [1, 3, 12, 13], ...}   # dict{id: [ids]}
```

### 3.3 Para qué sirve

Para **expandir la búsqueda hacia afuera** cuando en la localidad pedida no
hay suficientes proyectos. `primer_filtro` recorre el grafo por niveles con un
BFS desde la localidad del usuario y va sumando candidatos hasta llegar al
mínimo de 10.

Al pesar todas las aristas 1, el número de saltos del BFS **es** la distancia
mínima del grafo, así que no hace falta Dijkstra.

```
BFS desde Fontibón (9):
  d=0  Fontibón
  d=1  Kennedy · Engativá · Teusaquillo · Puente Aranda
  d=2  Chapinero · Santa Fe · Tunjuelito · Bosa · Suba · Barrios Unidos ·
       Los Mártires · Antonio Nariño · Ciudad Bolívar
  d=3  Usaquén · San Cristóbal · Usme · La Candelaria · Rafael Uribe · Sumapaz
```

**Un nivel se completa antes de decidir si hace falta seguir.** Si al terminar
`d=1` ya hay 10 candidatos, no se entra a `d=2`; pero nunca se corta a la
mitad de un nivel, porque todas las localidades de un mismo nivel están
igual de cerca y partirlas sería un desempate arbitrario.

### 3.4 API

| Función | Devuelve |
|---|---|
| `localidades_por_distancia(origen, max=None)` | `dict{distancia: [ids]}`, BFS por niveles. |
| `orden_expansion(origen, max=None)` | `[(id, distancia), ...]` plano, ordenado por cercanía. |
| `distancia_localidades(a, b)` | Saltos mínimos entre dos localidades. |

El BFS está cacheado con `lru_cache` sobre una estructura inmutable —el grafo
no cambia— pero `localidades_por_distancia` devuelve una copia mutable nueva
en cada llamada: se cachea el cálculo, no el resultado compartido.

### 3.5 El grafo de barrios (v0.4)

El grafo de 20 localidades es grueso para el problema real: Suba concentra 31
de los 96 proyectos y "misma localidad" cubre desde La Colina hasta Lisboa,
que están a 8 km. Un usuario que pide Suba recibía distancia 0 para los dos y
el score no podía distinguir el que le queda al lado del que le queda
cruzando la localidad entera. La v0.4 pone debajo un segundo grafo, en
`Model/grafo_barrios.py`:

```
V = 1.164 sectores catastrales (código oficial de 6 dígitos, p. ej. 009128 El Plan)
E = 3.446 aristas: pares de sectores cuyos polígonos comparten frontera
W = kilómetros entre los centroides de los dos sectores (haversine)
conexo · mediana de arista 0,71 km · media 1,0 km · grado medio 5,9
```

#### De dónde sale

| Archivo | Qué es | Quién lo produce |
|---|---|---|
| `data_projects/barrios_bogota_vecinos.txt` | 1.164 listas de vecinos, una por sector, calculadas sobre la capa oficial de sectores catastrales (UAECD / IDECA, captura 2018) con tolerancia de ~0,2 m. Un vecino marcado `(L#)` está en otra localidad. | **La fuente.** Se generó fuera del repo con la geometría oficial; no se edita a mano. |
| `data_projects/barrios_bogota_geo.json` | Los polígonos de la capa "Sector Catastral" de Datos Abiertos Bogotá, simplificados a ~10 m (0,7 MB). | `grafo_barrios.py` los baja del servicio Esri REST la primera vez. |
| `data_projects/barrios_bogota.json` | El grafo compilado: por sector, nombre, localidad, centroide y vecinos. | `python Model/grafo_barrios.py`. Se versiona para que `recomendar()` no dependa de la red. |

El parser (`parsear_vecinos_txt`) resuelve cada nombre de vecino a su código
**dentro de la localidad que corresponda** y luego simetriza. Hay 62 nombres
repetidos en la ciudad y algunos repetidos dentro de la misma localidad
—catastro parte "El Bagazal" o "Sierra Morena" en dos o tres sectores
homónimos—, y el TXT no dice a cuál se refiere: se elige el homónimo cuya
caja envolvente toca la del origen, y si los dos la tocan se conecta con
ambos (88 casos, anotados en `meta.avisos`). La arista sobrante une dos
polígonos que ya se tocan entre sí, así que no acorta ningún camino que no
exista. 1.152 de los 1.164 códigos coinciden con la capa viva; los 12
restantes son sectores rurales renumerados, sin centroide, cuyas aristas
pesan la mediana.

#### Qué se resolvió de la lista de pendientes de la v0.3

- **Las funciones del §3.4 siguen intactas.** `primer_filtro` expande por
  localidades exactamente igual. El grafo de barrios entra por otra puerta:
  `distancia_barrios(a, b)` en kilómetros, `saltos_barrios(a, b)` en
  fronteras, `barrios_por_distancia(origen)` como lista ordenada.
- **Las aristas ya no pesan 1, y por eso la distancia la da Dijkstra**
  (`_dijkstra`, cacheado por origen), no el BFS. Entre barrios un salto puede
  ser 300 m o 3 km; contarlos iguales devolvería el problema que este grafo
  viene a resolver. El BFS en saltos se conserva porque "está a dos barrios"
  sigue siendo la forma legible de decirlo.
- **Los proyectos tienen `barrio_id`.** Lo asigna el scraper (§6.4) y
  `prep.py` lo conserva. 83 de 96 lo tienen.
- **`score_localidad` se recalibró** (abajo, y §3.6).

#### Cómo entra al modelo

El barrio **no filtra**. La admisión sigue siendo el BFS de localidades: el
barrio solo cambia cuánto pesa la distancia y en qué orden salen los
candidatos. Cuando el usuario da barrio, cada candidato recibe
`_distancia_km`:

```
proyecto con barrio_id   ->  km por el grafo (Dijkstra) desde el barrio del usuario
proyecto sin barrio_id   ->  3,1 km + 3,7 km × saltos de localidad, marcado _distancia_km_estimada
usuario sin barrio       ->  None: el score cae a la fórmula por saltos de la v0.3
```

La estimación para el proyecto sin barrio es el mismo criterio que
`COBERTURA_ZONAS_SIN_DATO`: lo que no se sabe vale lo esperado, no lo mejor.
Las dos constantes salen de medir 20.000 pares de sectores urbanos al azar:
la mediana de distancia es 3,1 km en la misma localidad, 6,8 en la vecina,
10,3 a dos saltos, 14,3 a tres y 19,3 a cuatro — casi lineal en 3,7 km por
salto. Regalarle el 1,0 de "misma localidad" a un proyecto que no publica
coordenada lo pondría por delante de uno que sí demostró estar a 6 km.

`score_cercania` convierte los km en afinidad, `max(0, 1 − km / 12)`, y en
esa consulta la cercanía pesa `PESO_LOCALIDAD_CON_BARRIO = 0,12` en vez de
`0,08`, quitándole la diferencia a `modelo`. Un dato más fino merece más
peso; y aplicarlo solo con barrio es lo que hace que **un formulario sin
barrio dé exactamente lo de la v0.3** y todas las tablas de §4.3–4.5 sigan
valiendo.

#### La calibración

`Model/simulacion/calibrar_barrios.py`. Los clientes simulados no traen
barrio, así que a cada uno se le sortea un sector urbano de su localidad, y
se mide a cuántos kilómetros de ese barrio queda lo recomendado, con y sin
el dato. 300 clientes de prueba no vistos:

| config | recall@18 | pos. media | km Top 3 | km Top 18 | precio Top 3 |
|---|---:|---:|---:|---:|---:|
| sin barrio (v0.3) | 71,2 % | 7,95 | 9,51 | 10,51 | 299.273.417 |
| r=20 km, w=0,08 | 73,6 % | 7,30 | 9,34 | 10,23 | −0,4 % |
| r=12 km, w=0,08 | 74,2 % | 7,41 | 9,28 | 10,28 | −0,3 % |
| **r=12 km, w=0,12** | **73,2 %** | **7,29** | **8,96** | **9,97** | **−0,5 %** |
| r=12 km, w=0,16 | 72,2 % | 7,22 | 8,53 | 9,70 | −0,6 % |
| r=8 km, w=0,16 | 70,9 % | 7,08 | 8,91 | 10,05 | −0,4 % |

Tres cosas que dice la tabla. **El barrio no le cuesta nada al reenfoque
económico**: el precio del Top 3 no sube en ninguna fila, porque la cota
sigue ordenando encima. **El recall sube**, no baja: el barrio no filtra,
pero ordena mejor a los candidatos del margen que entran al 18. Y **el
efecto es moderado a propósito**: 12 km / 0,12 acerca el Top 3 un 6 % sin
ceder recall frente a la base; 0,16 acerca un 10 % pero ya empieza a costar.
Cuánto se quiere que la geografía le dispute al dinero es una decisión de
producto, y por eso son dos parámetros y no dos números enterrados.

Por qué el efecto no es mayor: la mayor parte de las recomendaciones quedan
en otra localidad de todos modos —solo 14 tienen oferta y el mínimo de 30
candidatos obliga a expandir—, y a 7–10 km un barrio u otro cambia poco. El
grafo se nota donde había que notarlo: dentro de Suba, Bosa, Fontibón o
Engativá, entre proyectos que antes empataban a distancia 0.

#### Lo que falta

- **El front todavía no pregunta el barrio.** El formulario vivo es el
  bundle de `public/experiencia/`, que este repo no compila. `GET
  /api/barrios?localidad=N` ya sirve la lista para un desplegable
  dependiente, y `lib/api.ts` ya tipa el campo.
- **13 proyectos sin barrio.** Los 8 de Colsubsidio sin coordenada
  ("La Colina, Bogotá. Cl. 152 # 58C-39"), más los que publican el pin en
  otra localidad. Geocodificar la malla vial los resolvería; hoy usan la
  distancia típica de su salto.
- **Los clientes simulados no tienen barrio**, así que el historial
  colaborativo no lo aprende. Darles uno cambiaría la simulación y todas las
  cifras de recall.

### 3.6 Cómo entra al score

La distancia del grafo aparece dos veces, con papeles distintos:

1. **Como criterio de admisión** en `primer_filtro`: define el orden en que
   entran los candidatos.
2. **Como penalización** en el score final, cuando el usuario **no** dio
   barrio: `score_localidad = max(0, 1 − 0.25 × distancia)`.
   Misma localidad → 1.0 · vecina → 0.75 · a dos saltos → 0.5 · a cuatro → 0.0.
   Con barrio, la misma casilla la llena `score_cercania` en kilómetros por
   el grafo de barrios, `max(0, 1 − km / 12)` (§3.5).

Ese componente pesa `0.08` del score (§4.3) — bajó de `0.10` en la v0.3,
porque la cercanía es justamente la concesión que `Cota_minimaBG` está
autorizada a intercambiar por precio (§4.5)— y `0.12` cuando hay barrio. Un proyecto en localidad vecina
**no** queda marcado como "relajado" (`_nivel_relajacion = 1`, pero
`_prioridad_filtro = 0`): ya paga su distancia en el score, castigarlo dos
veces lo hundiría injustamente.

---

## 4. El modelo de clustering

### 4.1 `prep.py` — etiquetar el perfil objetivo

Lleva cada proyecto al mismo espacio de features que el usuario:

```
perfil_vector = [salario_objetivo, personas_objetivo, edad_objetivo]
```

**`salario_objetivo`** sale de una simulación de crédito, no del precio a
secas — y desde la v0.3 esa simulación es **distinta para VIS y para No VIS**.

Hasta la v0.2 los supuestos eran uno solo para todo el catálogo: 30% de cuota
inicial, 240 meses y una cuota tope del 30% del ingreso, tanto para una VIS de
200 millones como para una No VIS de 800. Así no se financia vivienda en
Colombia, y el sesgo no era neutro: le exigía a la VIS un ingreso que la banca
no le exige, y con eso empujaba a los compradores de menor ingreso fuera de
los proyectos que están hechos para ellos.

| Supuesto | VIS | No VIS | De dónde sale |
|---|---:|---:|---|
| Cuota inicial | **10 %** | **30 %** | la banca financia hasta 90 % en VIS, 70–80 % en No VIS |
| Plazo máximo | **360 m** (30 años) | **240 m** (20 años) | tarifario BBVA vigente marzo 2026 |
| Tasa E.A. | **12,5 %** | **13,5 %** | VIS 10,9–15,9 %, No VIS 11,5–17 %, mercado ~13 % |
| Cuota / ingreso | **40 %** | **30 %** | Decreto 257 de 2021 (Minvivienda) |
| SMMLV | $2.000.000 | | 2026 — actualizar cada año |
| Subsidio VIS con caja | 30 SMMLV | | |

Viven en `PARAMETROS_CREDITO`, indexado por el mismo código de
`tipo_vivienda` del contrato, y se leen con `parametros_credito(tipo_cod)`.
**El default de un proyecto sin tipo declarado es No VIS**, que es el
escenario más exigente: así ninguno se abarata por accidente.

El **40 % de cuota/ingreso en VIS** es el cambio con más efecto. No es una
licencia: el Decreto 257 de 2021 subió el límite regulatorio de la primera
cuota de 30 % a 40 % precisamente para que hogares de bajos ingresos que
quedaban excluidos de la financiación pudieran acceder. El modelo no lo
estaba reflejando.

La tasa se convierte con `tasa_mensual()`, que hace la conversión correcta
—`(1+i)^(1/12) − 1`— y no la división entre 12: a 13,5 % E.A. la diferencia
son ~7 puntos básicos al mes, que sobre 240 cuotas son millones.

Con eso se calcula la cuota mensual, de ahí el ingreso requerido, y ese
ingreso se corta en los tramos del formulario (`TOPES_SALARIO_SMMLV = [2,4,8]`).
Se guarda también `salario_objetivo_con_subsidio`, que es el mismo cálculo
descontando el subsidio: un proyecto VIS puede bajar un tramo entero. El
subsidio se descuenta **antes** de la cuota inicial, porque es un aporte al
precio y no al crédito: es plata que el hogar no tiene que financiar ni poner.

Efecto sobre el catálogo de 96 proyectos — la VIS baja de tramo y la No VIS
sube, que es exactamente lo que la diferenciación debía corregir:

| `salario_objetivo` | 1 | 2 | 3 | 4 |
|---|---:|---:|---:|---:|
| antes (supuesto único) | 3 | 52 | 25 | 16 |
| **ahora (por segmento)** | **4** | **55** | **17** | **20** |

Cada proyecto guarda además una llave `credito` con los supuestos exactos con
los que se calculó su cuota (`cuota_inicial_pct`, `plazo_meses`, `tasa_ea`,
`cuota_ingreso_max`, `monto_financiado_cop`): es el número que Manuela le dice
al comprador por teléfono, y tiene que poder auditarse sin reconstruirlo.

**`personas_objetivo`** sale de las habitaciones. **`edad_objetivo`** sale del
`perfil_amenidades`: las 25 zonas comunes se agrupan en cuatro perfiles
(`familiar`, `joven_profesional`, `bienestar`, `practico`) y el dominante
sugiere la edad del comprador al que apunta el proyecto.

### 4.2 `primer_filtro` — el filtro duro

Criterio base, coincidencia exacta:

- mismo `tipo_vivienda`
- al menos las `numero_habitaciones` pedidas (`>=`, porque `3` es "3 o más")
- misma `Localidad`
- al menos 1 coincidencia en las zonas comunes pedidas

**Un dato que la fuente no publica no es un incumplimiento.** Cinco proyectos
del catálogo no listan habitaciones y tres no listan zonas comunes. Tratar ese
vacío como un "no cumple" los volvía **inalcanzables**: 7 de los 102 no
aparecían jamás en un Top 6, por un hueco de la web de la constructora y no
por su ficha. Ahora entran, se marcan en `_dato_incompleto` y el score les
descuenta `PENALIZACION_DATO_INCOMPLETO` (0,05) por campo faltante, para que
no le ganen a una ficha completa que sí demostró cumplir. La cobertura del
catálogo pasó de **93 % a 100 %**.

Cuando el proyecto no publica amenidades, `_cobertura_zonas` no vale 0 —eso
afirmaría que no tiene ninguna— sino `COBERTURA_ZONAS_SIN_DATO` (0,35):
deliberadamente por debajo de una coincidencia parcial real.

El barrio del usuario no aparece en esa lista: **no es criterio de
admisión**. Solo anota `_distancia_km` en cada candidato (§3.5) y, dentro de
un mismo salto de localidad, ordena los preseleccionados del más cercano al
más lejano.

Si salen menos de `MINIMO_PRESELECCIONADOS = 30`, se relaja en dos ejes, en
este orden:

1. **Geográfico primero**: BFS sobre el grafo (§3.3), completando cada nivel.
2. **Escalera `PASOS_RELAJACION`**, solo si recorrer todo el grafo no alcanzó:

| Paso | Zonas | Habitaciones | `_nivel_relajacion` |
|---|---|---|---|
| 1 | exige | exige | 0 (o 1 si es localidad vecina) |
| 2 | suelta | exige | 2 |
| 3 | suelta | suelta | 3 |

**`tipo_vivienda` no se relaja nunca.** VIS y No VIS son categorías legales y
financieras distintas, no una preferencia: cambiarla cambia si el usuario
puede o no acceder al subsidio.

Las habitaciones se sueltan de últimas porque son el requisito más duro de una
búsqueda de vivienda.

### 4.3 `modelo` — Nearest Neighbors en dos modos

**Contenido (siempre activo).** Se ajusta un `NearestNeighbors` euclidiano
sobre el `perfil_vector` de los preseleccionados y se consulta con el vector
del usuario. Las tres features se escalan a [0,1] con **rangos de dominio
fijos**, no con un scaler ajustado a los candidatos: con 10 candidatos un
scaler empírico sería inestable y cambiaría de escala en cada consulta.

| Feature | Rango | Peso |
|---|---|---|
| `salario` | 1–4 | **0,50** |
| `personas_a_cargo` | 1–4 | 0,30 |
| `edad` | 18–75 | 0,20 |

La capacidad de pago manda: es lo que decide si la compra es viable.

**Colaborativo (si hay `historial_simulado.json`).** Segundo
`NearestNeighbors`, esta vez sobre los vectores de usuarios históricos. Se
buscan los K más parecidos al usuario actual y se acumulan sus interacciones
por proyecto, ponderadas por cercanía (`peso = 1 / (1 + distancia)`). **Este
es el componente que forma los clústeres**: los vecinos en el espacio
demográfico definen el grupo cuyo comportamiento se extrapola.

**K se cuenta en perfiles, no en registros.** Es la corrección más importante
del modelo. El historial repite a la misma persona en cada evento que vive, y
el vector del modelo son solo tres features, así que clientes distintos
colapsan además en el mismo punto: 8.710 registros caen sobre **453 perfiles
distintos**, 19 registros por perfil. El K anterior, tope 200, consultaba unos
10 perfiles y se quedaba corto — tanto que el colaborativo rendía *por debajo*
del contenido solo.

Ahora `K = PERFILES_A_CONSULTAR × (registros por perfil)`, donde el factor de
repetición se mide del propio historial, así que se reajusta solo si cambia la
simulación. Con 30 perfiles objetivo da K ≈ 577. Medido sobre 600 clientes de
prueba no vistos (`simulacion/evaluar.py`):

| K | 200 | 450 | **600** | 900 |
|---|---:|---:|---:|---:|
| recall@6 | 68,8 % | 75,5 % | **77,3 %** | 76,5 % |

El óptimo es un plateau ancho entre 520 y 820. Por debajo el vecindario es
demasiado pequeño para promediar; por encima la personalización se diluye
hasta degenerar en popularidad global.

**Mezcla:**

```
score_modelo = 0.50 · colaborativo + 0.50 · contenido      (si hay historial)
score_modelo = contenido                                    (si no)

score = 0.50 · score_modelo
      + 0.25 · score_esfuerzo     (años que ESTA persona tardaría en pagarlo)
      + 0.17 · score_zonas        (cobertura de las amenidades pedidas)
      + 0.08 · score_localidad    (max(0, 1 − 0.25 · saltos de localidad))

score -= 0.05 · (campos que el proyecto no publica)

con barrio (v0.4):   0.46 · score_modelo  +  0.12 · score_cercania   (max(0, 1 − km / 12))
```

`pesos_score()` decide cuál de las dos mezclas aplica en cada consulta: si
los candidatos traen `_distancia_km` —el usuario dio barrio— la cercanía es
una medida y pesa `PESO_LOCALIDAD_CON_BARRIO`; si no, es un dato grueso y
pesa lo de siempre. La calibración de ese par está en §3.5.

**`score_esfuerzo` es nuevo en la v0.3 y es la mitad del reenfoque económico**
(la otra mitad es `Cota_minimaBG`, §4.5). Hasta la v0.2 la mezcla era
`{modelo: 0.70, zonas: 0.20, localidad: 0.10}`: el parecido demográfico
decidía y lo demás desempataba. El problema es que ese parecido es un **proxy
del dinero** —el salario objetivo del proyecto contra el tramo del usuario— y
es un proxy grueso: dos proyectos etiquetados en el mismo tramo de salario
pueden diferir en 80 millones, y el modelo los veía idénticos.

`score_esfuerzo` mide lo que el proxy no: cuántos años tardaría *esta* persona
en pagar *ese* proyecto (`cota_minima.anos_de_pago`, §4.5). Entra aquí —y no
solo en el reordenamiento— para que afecte **qué** proyectos ocupan las 18
casillas, no únicamente el orden en que salen: un proyecto que esta persona no
puede pagar no debería gastar una casilla por parecerse a ella.

El peso está **calibrado, no elegido**. Medido sobre 400 clientes de prueba no
vistos, con la cota de precio ya activa en sus 50 millones:

| `esfuerzo` | `modelo` | recall@18 | pos. media | precio Top 3 | ahorro |
|---:|---:|---:|---:|---:|---:|
| 0,00 | 0,75 | 75,0 % | 7,67 | 306.374.341 | 0 % |
| 0,15 | 0,60 | 73,2 % | 7,72 | 298.328.794 | 2,6 % |
| 0,20 | 0,55 | 72,5 % | 7,71 | 296.608.477 | 3,2 % |
| **0,25** | **0,50** | **72,0 %** | **7,70** | **294.620.989** | **3,8 %** |
| 0,35 | 0,40 | 70,5 % | 7,80 | 291.620.627 | 4,8 % |

0,25 se queda con el 80 % del ahorro que este componente puede aportar; de ahí
en adelante cada punto de recall cedido compra la mitad de ahorro que al
principio. El grueso del efecto económico no lo hace este peso sino la cota
—otro 14 % de precio, y ese sin costar recall— y por eso subirlo más solo
cuesta.

La columna de recall es **idéntica** a la del mismo barrido con la cota en 20
millones, y tiene que serlo: la cota reordena el top, no cambia qué proyectos
lo componen, y el recall@18 mide pertenencia. Lo que sí mejora con la cota más
alta es que la posición media deja de degradarse al subir el peso (7,67 → 7,80
aquí, contra 8,38 → 8,67 con la cota en 20 M).

Con esto **la plata explica cerca de la mitad del score** aun sin contar la
cota: `esfuerzo` 0,25 más `salario`, que pesa 0,50 dentro de las features del
modelo (0,50 × 0,50 = 0,25 efectivo). `localidad` baja a 0,08 porque es
justamente la concesión que la cota está autorizada a comprar, y `zonas` a
0,17 porque las amenidades son preferencia, no viabilidad.

`ALPHA_HISTORIAL` bajó de 0,60 a 0,50: medido sobre los mismos 600 clientes,
0,4 y 0,5 empatan en 77,7 % y de ahí hacia arriba baja de forma sostenida
(0,6 → 77,3 %, 0,9 → 75,7 %). El colaborativo aporta, pero no debe tapar al de
contenido, que es el que sostiene a los proyectos con pocas interacciones —el
arranque en frío—.

**Subsidio.** Un afiliado a la caja que busca VIS accede al subsidio, y eso
baja el ingreso que el proyecto le exige: se compara contra
`salario_objetivo_con_subsidio`. Hasta ahora `afiliado` se capturaba en el
formulario y no se usaba para nada.

**El score ordena dentro de cada tramo de prioridad, nunca entre tramos.** Lo
que cumple todos los requisitos va primero; lo admitido relajando zonas o
habitaciones va después, por mucho score que saque. Devuelve el Top `TOP_N`.

**`TOP_N = 18`, y `MINIMO_PRESELECCIONADOS` tiene que seguir por encima.** Si
el filtro entregara exactamente 18 candidatos, el Nearest Neighbors no
elegiría nada —devolvería el filtro entero— y el score dejaría de ordenar; por
eso el mínimo es 30, ~1,7× el tamaño del top, la misma proporción que había
con Top 6. `recomendar()` además pide `max(MINIMO_PRESELECCIONADOS, top_n)`,
para que un `--top` grande no devuelva una lista corta. El techo real es el
tipo de vivienda, que nunca se relaja: 58 proyectos VIS y 38 No VIS.

### 4.4 `post_arreglos` — el porcentaje comercial

> **Corre al final del pipeline**, después de `Cota_minimaBG` (§4.5). El
> porcentaje tiene que describir el orden definitivo, no uno que todavía va a
> cambiar.

El score crudo (0,68) no se le muestra a nadie. Se convierte en porcentaje de
compatibilidad en **dos capas**, y el orden entre ellas importa.

**Capa 0 — la cota decide el orden, el modelo decide la escala.** Si
`Cota_minimaBG` ya corrió, cada proyecto trae un `_orden_cota` y ese es el
orden bueno: volver a ordenar por score desharía el reordenamiento por precio
que se acaba de hacer. Pero entonces los scores dejan de ser monótonos —un
proyecto hundido al 14º por caro puede traer el 3er score más alto del top— y
la cadena de porcentajes de la Capa 1 se leería al revés de como está
ordenada la lista.

`_scores_por_posicion` lo resuelve repartiendo **los mismos scores que el
modelo produjo**, de mayor a menor según la posición final. El conjunto de
porcentajes que ve el usuario es exactamente el que saldría sin la cota; lo
único que cambia es quién ocupa cada puesto. Así la caída de la lista sigue
midiendo lo que mide el modelo —qué tan rápido empeora el encaje— y no se
inventa una escala nueva. El reparto se hace **dentro de cada tramo de
`_prioridad_filtro`**, nunca entre tramos: mezclarlos le prestaría el score
alto de un proyecto relajado a uno que cumple todo, o al revés (invariante 4).

**Capa 1 — normalización encadenada.** El primero muestra su propio score como
porcentaje, elevado a `PORCENTAJE_TOP_MINIMO = 85` si se queda corto: quien
abre la lista es lo mejor que hay para esa persona y no puede presentarse con
un 60 %. De ahí hacia abajo, cada proyecto resta **los puntos de score que lo
separan del inmediatamente anterior**, no del líder:

```
pct[1] = max(score[1] × 100, 85)
pct[i] = pct[i-1] − (score[i-1] − score[i]) × 100
```

Como la cadena arranca en el score del líder, el resultado es que **el
porcentaje de cada uno es su propio score**, desplazado por lo que se haya
elevado el líder. La resta se acota en 0: un proyecto admitido relajando
requisitos puede traer score bruto mayor y aun así ir detrás (invariante 4),
y ahí el porcentaje se queda quieto en vez de subir.

**En caída libre, sin piso.** Sobre el catálogo actual el último de los 18
aterriza entre 2 % y 64 %, con mediana 45 %. Comprimir la escala para que no
baje tanto obligaría a mentir sobre el encaje del final de la lista; un 27 %
dice la verdad y sigue siendo información útil.

**Capa 2 — el empate lo rompe el precio.** La capa 1 produce empates *a
propósito*: dos scores parecidos redondean al mismo número. Y ningún proyecto
puede mostrar el mismo porcentaje que otro —dos 84 % dejan al usuario sin
criterio para elegir—. Entre los empatados se queda con el número alto **el
más barato**: entre dos que el modelo ve igual de compatibles, la vivienda más
barata es la mejor oferta. El resto baja de a un punto (`PASO_MINIMO = 1`).

```
85 · 84 · 84   ->   85 · 84 · 83
                         ^    ^
                         |    el otro
                         el más barato de los dos empatados
```

`_desempatar_por_precio` reordena solo **dentro del mismo tramo de
`_prioridad_filtro`**: un proyecto admitido relajando requisitos no adelanta a
uno que cumple todo por ser más barato (invariante 4). Un proyecto que no
publica precio se va al final de su grupo de empate, no al principio: sin
precio no puede reclamar ser la mejor oferta.

El último puesto tiene reservado un punto por cada uno de los que van detrás
suyo, de modo que el de más abajo pueda aterrizar en 0 sin que dos choquen
contra el suelo y terminen mostrando el mismo número. Es una garantía
mecánica de que no haya repetidos, no un piso comercial.

**`post_arreglos` ya no tiene nada aleatorio.** El parámetro `semilla` se
sigue aceptando por compatibilidad con la CLI y con `recomendar()`, pero no
hace nada: el mismo formulario da siempre el mismo porcentaje.

---

### 4.5 `Cota_minimaBG` — el precio manda

`Model/cota_minima.py`. Es la etapa nueva de la v0.3 y corre **entre `modelo()`
y `post_arreglos()`**:

```
primer_filtro -> modelo -> Cota_minimaBG -> post_arreglos
```

El recomendador nació ordenando por parecido demográfico, amenidades y
cercanía. Las tres importan, pero ninguna es lo que decide una compra de
vivienda: lo que la decide es **cuánto cuesta y en cuánto tiempo se paga**.
Esta capa corrige esa jerarquía en dos movimientos.

#### Movimiento 1 — el filtro de verificación: ¿en cuántos años se paga?

`anos_de_pago(precio, salario_cod, tipo_cod, aplica_subsidio)` despeja el
número de cuotas de la fórmula de anualidad vencida:

```
n = −ln(1 − F·i / C) / ln(1 + i)
```

donde `F` es lo financiado, `i` la tasa mensual del segmento (§4.1) y `C` la
cuota que la persona puede pagar. `C` sale de su **tramo de ingreso**, no del
proyecto: el formulario captura rangos, así que se usa el centro de cada uno
(`INGRESO_REPRESENTATIVO_SMMLV = {1: 1,5 · 2: 3 · 3: 6 · 4: 12}` SMMLV; el
tramo 4 es abierto y se representa con 12 — sobreestimarlo haría parecer
alcanzable cualquier cosa y el componente dejaría de discriminar).

Si `C ≤ F·i` la cuota no cubre ni los intereses del primer mes: el saldo nunca
baja y el logaritmo no existe. Ese caso devuelve **infinito y no un número
grande**, porque no es "muy lento", es imposible, y el score tiene que poder
distinguir las dos cosas.

`score_esfuerzo` convierte esos años en una afinidad [0,1]: **1,0** hasta
`ANOS_HOLGADOS` (5 años) y de ahí decae linealmente hasta 0 en el plazo máximo
**de su segmento**, no de un plazo único — 25 años son holgados en una VIS a
30 e imposibles en una No VIS a 20, y no distinguirlo premiaría a la No VIS
cara por el mero hecho de tener el plazo más corto.

**El inalcanzable no puntúa 0, puntúa poco y graduado.** Un 0 plano rompía el
componente justo para quien más lo necesita: con el tramo de ingreso más bajo
(1,5 SMMLV) **ningún** proyecto del catálogo bogotano amortiza, así que los 18
salían con esfuerzo 0, el componente se volvía una constante y dejaba de
ordenar nada. Pero no todos los imposibles son igual de imposibles: al que le
falta un 5 % de cuota no está en la misma situación que al que le falta la
mitad, y el primero es el que hay que mostrar arriba — es el que se vuelve
alcanzable con un subsidio, un codeudor o un ingreso familiar sumado. Así que
el inalcanzable puntúa proporcional a lo cerca que quedó
(`cobertura = C / F·i`), dentro de la franja de `FRACCION_INALCANZABLE` (0,15).
El techo es bajo a propósito: **un imposible nunca adelanta a un alcanzable
real**, por poco que le falte.

```
VIS 197M, tramo 1  ->  no paga, score 0,103
VIS 230M, tramo 1  ->  no paga, score 0,088     ordena por precio
VIS 280M, tramo 1  ->  no paga, score 0,072     entre los imposibles
VIS 280M, tramo 1, con subsidio -> no paga, score 0,092   (el subsidio acerca)

VIS 200M, tramo 2  ->  11,4 años, score 0,743
VIS 200M, tramo 3  ->   3,9 años, score 1,000
```

Lo que la persona no puede pagar se **hunde al fondo de su tramo**, no se
elimina: quitarlo dejaría la lista corta y sin explicación. Sale marcado con
`_alcanzable: False` para que la vista pueda decirlo en vez de esconderlo.

#### Movimiento 2 — la cota de precio

`_aplicar_cota_precio` recorre el top por **pares consecutivos** y, cuando el
de arriba cuesta más que el de abajo por encima de `COTA_MINIMA_COP`, **los
invierte** — aunque el de abajo esté en una localidad que el usuario no pidió.
Esa es la inversión que define la capa: **por encima de cierta diferencia de
plata, el ahorro pesa más que la ubicación**.

Es un *bubble sort con umbral*, y el umbral es lo que evita que degenere. Con
la cota en 0 el top queda ordenado por precio ascendente y el modelo deja de
decidir; con la cota en infinito nada se mueve y la capa no existe. En medio,
la cota define **bandas de precio**: dentro de una banda manda el score del
modelo, entre bandas manda el precio.

Termina siempre: cada intercambio mueve un precio estrictamente mayor hacia
atrás, así que la suma de (posición × precio) decrece en cada uno. El tope de
pasadas es una red de seguridad, no el mecanismo de parada.

**Lo que la cota no rompe es el invariante 4.** Un proyecto admitido relajando
requisitos —menos habitaciones de las pedidas, ninguna zona común en común— no
adelanta a uno que cumple todo por ser más barato. Cambiar de barrio es una
concesión que se puede compensar con dinero; recibir una vivienda que no
cumple lo que se pidió, no. El intercambio solo ocurre **dentro del mismo
tramo de `_prioridad_filtro`**, y `respetar_prioridad=False` levanta el
candado solo para poder medir el efecto.

#### La calibración de `COTA_MINIMA_COP`

`Model/simulacion/calibrar_cota.py`. Medido sobre 300 clientes de prueba no
vistos, con el precio medio del **Top 3** —lo primero que ve el usuario—:

| cota | recall@18 | pos. media | precio Top 3 | ahorro | años Top 3 |
|---:|---:|---:|---:|---:|---:|
| sin cota | 70,3 % | 7,10 | 349.576.853 | 0 % | 10,1 |
| 0 M | 70,3 % | 9,55 | 277.912.514 | 20,5 % | 7,8 |
| 20 M | 70,3 % | 8,86 | 286.274.972 | 18,1 % | 8,5 |
| 40 M | 70,3 % | 8,27 | 296.383.806 | 15,2 % | 9,3 |
| **50 M** | **70,3 %** | **8,16** | **299.538.061** | **14,3 %** | **9,5** |
| 60 M | 70,3 % | 8,14 | 301.947.913 | 13,6 % | 9,7 |
| 80 M | 70,3 % | 7,91 | 307.217.877 | 12,1 % | 9,9 |

**El recall sale plano en toda la tabla, y tiene que salir plano**: la cota
reordena las 18 posiciones, no cambia cuáles son. Si alguna vez se mueve, es
que algo está eliminando candidatos y hay un bug — esa fila es el test.

**50 millones es el punto que más respeta el trabajo del modelo.** Sobre un
catálogo cuya VIS típica ronda los 200–280 millones son ~20 % del precio: no
es un matiz, es la diferencia que separa un proyecto de otro segmento, y son
unos 500.000 pesos menos de cuota al mes durante 30 años. Captura el 70 % del
ahorro máximo posible y es el que menos degrada la posición media (8,16 contra
9,55 del caso degenerado).

El **plateau entre 40 y 60 millones** —el ahorro se mueve de 15,2 % a 13,6 % y
la posición media de 8,27 a 8,14— dice que 50 no es un punto elegido al filo:
mover el parámetro dentro de ese rango casi no cambia el resultado, así que la
configuración es robusta.

#### Lo que una cota en pesos no puede hacer

Los dos segmentos del catálogo no viven en la misma escala de precio:

| Segmento | n | Mínimo | Mediana | Máximo |
|---|---:|---:|---:|---:|
| VIS | 58 | 148.500.000 | 246.413.350 | 383.600.000 |
| No VIS | 38 | 276.000.000 | 602.625.000 | 4.200.000.000 |

Una cota **fija en pesos** es, por tanto, un porcentaje distinto en cada uno:
50 millones son el 8 % de la No VIS mediana pero el 20 % de la VIS mediana. Y
eso se ve en el efecto, medido sobre 200 clientes separados por lo que buscan:

| cota | VIS: % con movimiento | ahorro | No VIS: % con mov. | ahorro |
|---:|---:|---:|---:|---:|
| 10 M | 100 % | 16,0 % | 100 % | 23,3 % |
| 20 M | 100 % | 12,4 % | 100 % | 22,7 % |
| 30 M | 100 % | 9,2 % | 100 % | 22,6 % |
| **50 M** | **91 %** | **3,0 %** | **100 %** | **20,5 %** |

En **No VIS la cota funciona igual de bien en todo el rango**: el ahorro apenas
cae de 23,3 % a 20,5 %. En **VIS, 50 millones la dejan casi inactiva** —del
12,4 % de ahorro a 3,0 %—, porque entre dos VIS es raro que haya ese salto.

**El promedio global de 14,3 % esconde esa asimetría**: la mayor parte de ese
ahorro lo produce el lado No VIS. Es una limitación del parámetro, no un bug,
y conviene tenerla presente antes de leer el número agregado como si aplicara
por igual a todos los usuarios.

Si se quiere que la cota actúe parejo en los dos segmentos hay dos caminos,
ninguno implementado todavía porque los dos cambian el comportamiento recién
calibrado:

1. **Cota por segmento** — p. ej. 20 M en VIS y 50 M en No VIS. Es el cambio
   mínimo: `COTA_MINIMA_COP` pasa a ser un dict indexado por `tipo_vivienda`,
   igual que `PARAMETROS_CREDITO` (§4.1).
2. **Cota relativa** — un % del precio del más barato del par. Se adapta sola
   y no habría que revisarla cuando cambien los precios del catálogo, que es
   la ventaja de fondo: una cifra en pesos envejece con la inflación.

**El rango 20–50 es una decisión de producto, no de ingeniería.** La curva
tiene rendimientos decrecientes en las dos direcciones: bajar a 20 millones
compra 3,8 puntos de ahorro a cambio de 0,7 de posición media. Cuánto se
quiere que el precio pise al modelo es una elección, y por eso es un
parámetro y no un número enterrado.

**Lo que sí es un error es ponerla en una cifra que sobre estos precios sea
ruido** — 50 *mil* pesos, por ejemplo. Ahí se invierten prácticamente todos
los pares, el top queda ordenado por precio ascendente a secas y el
recomendador se convierte en un buscador de lo más barato. Es la fila "0 M":
ahorra 6 puntos más que 50 M y a cambio manda la posición media de 8,16 a
9,55, porque el modelo deja de aportar orden. Entonces sobra el modelo.

#### Qué anota en cada proyecto

| Campo | Qué dice |
|---|---|
| `_anos_de_pago` | Años estimados. `null` si es inalcanzable. |
| `_score_esfuerzo` | La afinidad [0,1] de arriba. |
| `_alcanzable` | `False` si la cuota no cubre ni los intereses. |
| `_cuota_que_puede_pagar_cop` / `_cuota_del_proyecto_cop` | Los dos números del contraste, para poder explicarlo. |
| `_orden_cota` | Posición final. La respeta `post_arreglos` (§4.6). |
| `_movido_por_cota` | Cuántas posiciones lo movió la cota. `+` subió, `−` bajó. |

Todos viajan a la respuesta del front (§5.1), porque son la explicación de por
qué la lista está en ese orden.

#### El costo, dicho de frente

El reenfoque económico completo —crédito por segmento, `score_esfuerzo` y la
cota— **baja el recall**. Sobre los mismos 300 clientes de prueba:

| | v0.2 | v0.3 sin cota | **v0.3 completa** |
|---|---:|---:|---:|
| recall@18 solo contenido | 70,7 % | 68,7 % | 68,7 % |
| recall@18 con historial | 72,7 % | 70,3 % | **70,3 %** |
| posición media del acierto | 6,98 | 7,10 | **8,16** |
| precio medio del Top 3 | 375.943.386 | 349.576.853 | **299.538.061** (−20,3 %) |
| años de pago del Top 3 | — | 10,1 | **9,5** |
| proyectos inalcanzables en el Top 3 | — | 1,32 | **1,07** |

La columna del medio aísla lo que aporta cada pieza: el crédito por segmento y
`score_esfuerzo` bajan el precio un 7 % por sí solos —y ahí es donde se pagan
los 2,4 puntos de recall—, y la cota aporta los otros 14 %, gratis en recall
porque solo reordena. La v0.2 no calculaba años ni alcanzabilidad, así que
esas dos filas no tienen con qué compararse.

Esos −2,4 puntos hay que leerlos sabiendo **contra qué se mide el recall**. La
"verdad" que simula `generar_historial.utilidad` trata el precio de forma
asimétrica y truncada: `_ajuste_precio` solo penaliza cuando el proyecto exige
más ingreso del que el usuario declara, y devuelve `0.0` en cuanto hay
holgura. Para esa verdad, entre un proyecto de 182 millones y uno de 262 que
el comprador puede pagar, **da exactamente igual cuál se le muestre**.

El reenfoque de la v0.3 dice justo lo contrario. Así que el recall no está
midiendo que el modelo empeore: está midiendo el desacuerdo con un simulador
que no comparte el objetivo. Por eso la calibración se hizo con
`calibrar_cota.py`, que mide las dos cosas a la vez — lo que se cede de
fidelidad al criterio anterior y lo que se gana en plata, años y
alcanzabilidad.

**Si el simulador se actualiza para preferir lo barato entre lo pagable, esta
tabla hay que rehacerla entera** y los números dejarán de ser comparables con
los históricos. Es la razón de que se conserven aquí los dos.

---

### 4.6 Entrenamiento: la base de clientes simulados

No hay interacciones reales, así que se fabrican. La forma de fabricarlas
importa: el colaborativo busca **usuarios parecidos entre sí**, y si cada
perfil se muestrea campo a campo de forma independiente no hay nadie a quien
parecerse.

```
10 arquetipos ──100 variaciones──▶ 1.000 clientes ──8 eventos──▶ 8.000 interacciones
```

Los arquetipos (`Model/simulacion/arquetipos.py`) son tipos de comprador reales
—joven profesional, familia numerosa con subsidio, inversionista, nido
vacío…— con su rango de edad, capacidad de pago, dónde buscan y qué
amenidades les importan. Cada uno produce 100 variaciones que se dejan
**derivar** a propósito (12 % busca fuera de su localidad, 15 % se corre un
tramo de ingreso, 20 % olvida una amenidad característica): sin esa deriva
serían 100 copias y el modelo vería 10 puntos en vez de 1.000.

Los clientes salen **en el mismo contrato JSON que manda el front**, así que
sirven también de banco de pruebas: se le pasan tal cual a `recomendar()`.

Cada cliente vive 8 eventos (`vista` 0.2 · `lead` 0.6 · `compra` 1.0),
elegidos con un softmax sobre una utilidad que mezcla afinidad de perfil,
cobertura de zonas, cercanía, capacidad de pago y un **atractivo latente** por
proyecto. Ese atractivo es la pieza clave: representa lo que las etiquetas de
`prep.py` no capturan y **solo el historial puede revelar**. Son 8.000
registros de los arquetipos más ~600 de relleno, porque hay un piso de 30
interacciones por proyecto: sin él un proyecto nunca aparecería por la vía
colaborativa.

Detalle completo en [Model/simulacion/README.md](../Demo/backend/Model/simulacion/README.md).

### 4.7 Evaluación

`Model/simulacion/evaluar.py` responde si el historial está sirviendo de algo.
Genera clientes con **otra semilla** —el modelo nunca los vio—, les hace
comprar con la misma utilidad que produjo el historial, y compara el Top 6 de
los dos modos. Como el atractivo latente es lo único que los separa, la
diferencia **es** lo que aporta el historial:

```
recall@6 solo contenido      :  69.3%
recall@6 con historial       :  77.5%
mejora que aporta el historial:  +8.2 puntos
posición media del acierto   :   2.68
```

(Las cifras del bloque de arriba son las de la v0.1, con Top 6 sobre pool ≥10.
Las de hoy están en la tabla del final de esta sección.)

Es la misma evaluación que destapó el K mal calibrado (§4.3). Conviene
correrla después de cada cambio del catálogo o de la simulación: si la mejora
se vuelve negativa, el historial está desactualizado.

**La ventana del recall está fijada en 6 y no sigue a `TOP_N`.**
`TOP_N_EVALUACION = 6` vive en `evaluar.py` a propósito: los números que
calibraron `K_VECINOS` y `ALPHA_HISTORIAL` se midieron sobre 6 posiciones, y
si la ventana se moviera con el producto dejarían de ser comparables. Para
medir la lista que se entrega hoy, `--top 18`.

**Cuidado al comparar entre configuraciones distintas:** la evaluación sortea
la compra *dentro del pool de candidatos*, así que un pool más grande hace la
tarea más difícil por construcción y los recalls de dos pools distintos no se
pueden poner lado a lado. Lo comparable es la proporción entregada. Medido
sobre 300 clientes de prueba:

| Configuración | Entregado | recall contenido | con historial |
|---|---|---:|---:|
| Top 6 sobre pool ≥10 (v0.1) | 60 % del pool | 67,3 % | 73,0 % |
| Top 18 sobre pool ≥30 (v0.2) | 60 % del pool | 70,7 % | 72,7 % |
| **Top 18 sobre pool ≥30 (v0.3, hoy)** | **60 % del pool** | **68,7 %** | **70,3 %** |
| Top 18 sobre pool ≥24 (v0.2) | 75 % del pool | 81,7 % | 84,7 % |
| Top 18 sobre pool ≥18 (v0.2) | 100 % del pool | 87,7 % | 90,0 % |

Las dos últimas filas suben porque se entrega casi todo lo que pasó el filtro:
el modelo deja de elegir y solo ordena. Por eso el mínimo se dejó en 30, que
mantiene la misma proporción de siempre y conserva la selección.

**La v0.3 cede 2,4 puntos, y es un costo asumido a sabiendas.** El reenfoque
económico (§4.1, §4.3, §4.5) hace que el modelo prefiera lo barato entre lo
pagable; la utilidad con la que este evaluador simula la compra **no** tiene
esa preferencia, así que el número que baja es la fidelidad al criterio
anterior, no la calidad. A cambio, el Top 3 sale **20,3 % más barato**
(375.943.386 → 299.538.061) y se paga medio año antes. La tabla completa del
intercambio está en §4.5.

**Por eso este evaluador ya no es suficiente solo.** Para medir la v0.3 hay
que correr también `calibrar_cota.py`, que reporta recall, precio, años de
pago y alcanzabilidad en la misma tabla:

```bash
python Model/simulacion/evaluar.py --clientes-prueba 300 --top 18
python Model/simulacion/calibrar_cota.py --clientes 300
```

`evaluar.py` acepta además `--cota N` para aplicar `Cota_minimaBG` dentro de
su propia medición. Sirve para ver el efecto sobre la **posición media del
acierto**; el recall no se mueve, porque la cota reordena y no selecciona.

---

## 5. Integración con el front

### 5.1 En proceso: `Model.recomendar()`

`Model.recomendar()` (definido en `Model/pipeline.py`) es el punto de entrada. Acepta el payload **como dict**,
sin pasar por disco:

```python
from Model import recomendar, respuesta_json        # desde backend/

payload = {                       # las 15 llaves del formulario (§2.1)
    "nombres": "Ana", "apellidos": "Torres", "correo": "ana@ejemplo.com",
    "telefono": 3009998877, "afiliado": 1,
    "tipo_vivienda": 1, "salario": 2, "personas_a_cargo": 3, "edad": 34,
    "Localidad": 7, "numero_habitaciones": 3, "piso": 1,
    "zonas_comunes": ["Lobby", "Zona kids", "Parque", "Salón social", "Gimnasio"],
}

resultado = recomendar(payload, ruta_salida=None, verbose=False)
payload_respuesta = respuesta_json(resultado, ruta_salida=None)
```

También acepta un string JSON o una ruta a archivo, para la CLI.

`respuesta_json()` devuelve solo lo que necesita la vista, sin la metadata
interna del pipeline:

```json
{
  "generado_en": "2026-08-26T...",
  "motor": "colaborativo+contenido",
  "total_preseleccionados": 14,
  "usuario": {
    "nombre_completo": "Ana Torres", "correo": "...", "telefono": ..., "afiliado": true,
    "perfil": {"salario": 2, "personas_a_cargo": 3, "edad": 34},
    "busqueda": {"tipo_vivienda": "VIS", "localidad": "Bosa", "barrio": "Bosa Nova",
                 "barrio_no_reconocido": null, "numero_habitaciones": 3,
                 "piso": "medio", "zonas_comunes": ["Lobby", "Zona kids", ...]}
  },
  "apartamentos": [
    {"posicion": 1, "compatibilidad": 98, "compatibilidad_texto": "98%",
     "id_proyecto": 93, "nombre_proyecto": "La Gratitud I de la Marlene",
     "tipo_vivienda": "VIS", "localidad": "Bosa",
     "barrio": "Campo Verde", "distancia_km": 4.3, "distancia_km_estimada": false,
     "direccion": "...",
     "precio_desde_cop": 231000000, "area_construida_m2": 44.0, "habitaciones": 3,
     "cumple_habitaciones": true, "aplica_subsidio_caja": true,
     "cuota_mensual_estimada_cop": ..., "ingreso_requerido_smmlv": ...,
     "zonas_comunes": [...], "zonas_en_comun": [...],
     "url_ficha": "https://...", "score": 0.87,

     "anos_de_pago": 8.5, "alcanzable": true,
     "cuota_que_puede_pagar_cop": 2400000, "cuota_del_proyecto_cop": 1563669,
     "movido_por_cota": 1}
  ]
}
```

Validación: `leer_info_user` levanta `ValueError` con **todos** los errores del
formulario juntos, no el primero que encuentra, para que el front pueda
marcarlos todos de una vez.

Las zonas comunes que el front mande y no estén en el vocabulario de 25 no
rompen nada: viajan en `usuario_info_contacto_v1["zonas_comunes_no_reconocidas"]`.

### 5.2 Por HTTP: `api/app.py`

`backend/api/app.py` es un wrapper **delgado** de FastAPI sobre `recomendar()`.
Es lo que consume la experiencia (§8). No tiene lógica de recomendación propia:
valida con Pydantic, llama al pipeline y devuelve `respuesta_json()`.

```bash
cd backend && uvicorn api.app:app --reload --port 8000
```

En Render lo levanta `render.yaml` con `rootDir: backend`, que es lo que hace
que el paquete `Model` sea importable.

| Endpoint | Qué hace |
|---|---|
| `GET /api/health` | Latido. Lo usa el front para saber si el motor está encendido antes de que el usuario llene nada. |
| `GET /api/catalogos` | Las 20 localidades con su id y las 25 zonas comunes, leídas de `Model/catalogos.py`. **Es la vía para que el front no invente ids.** |
| `GET /api/barrios?localidad=N` | Los sectores catastrales de esa localidad (`{id, nombre}`), de `Model/grafo_barrios.py`, para un desplegable dependiente. `disponible: false` si el backend corre sin grafo. |
| `POST /api/recomendar` | Recibe el formulario, devuelve `respuesta_json()`. |
| `POST /api/llamar` | Dispara la llamada de Manuela (§5.3). |

`FormularioUsuario` (Pydantic) marca obligatorios **solo los seis campos del
contrato mínimo** —`tipo_vivienda`, `salario`, `personas_a_cargo`, `edad`,
`Localidad`, `numero_habitaciones`—; el resto, `barrio` incluido, es
opcional y el payload se pasa
con `exclude_none=True`, para que un campo ausente no viaje como `null` y
`leer_info_user` lo trate como "no declarado" en vez de como valor inválido.

El `ValueError` de `leer_info_user` sale como **HTTP 400** con **todos** los
errores del formulario juntos en `detail`, que es justamente para lo que
`leer_info_user` los acumula (§5.1).

**CORS abierto y sin auth**: es una demo local para el stand de GO FEST. Está
anotado en el docstring del módulo y no debe exponerse así a internet.

### 5.3 `POST /api/llamar` — el flow de Dapta

Cierra el ciclo: con el Top 1 en la mano, dispara la llamada de **Manuela**,
la agente de voz que corre en un flow de Dapta (Flow Studio).

- **El teléfono se normaliza a E.164 de móvil colombiano** (`+573XXXXXXXXX`)
  en `normalizar_telefono_e164`: quita el `00`, quita el indicativo `57` si
  viene duplicado y exige 10 dígitos que empiecen por `3`. Lo que no encaja
  —fijo, extranjero, incompleto— se rechaza con **400 antes** de gastar una
  llamada, no después.
- **`subsidio_estimado` se calcula aquí**: `30 × SMMLV` solo si el proyecto
  aplica subsidio de caja **y** la persona es afiliada. `SMMLV_COP` **ya no
  está duplicado**: se importa de `Model.prep`, que es donde vive el supuesto
  económico. Antes había una copia en cada archivo y el invariante 5 pedía
  actualizar los dos a mano; ahora desfasarlos es imposible.
- **El payload del flow tiene 19 campos y no es el contrato de §2.** Es el
  vocabulario de Dapta: `zona_interes`, `urgencia`, `entorno_deseado`,
  `piso_preferido`, `external_lead_id`, `current_time` en hora de Bogotá
  (`TZ_BOGOTA`, UTC−5)… La traducción completa vive en `api_llamar` y es el
  único sitio donde hay que tocarla si el flow cambia de campos.
- **La URL del webhook sale de `DAPTA_FLOW_WEBHOOK_URL`, nunca hardcodeada.**
  Sin esa variable el endpoint responde `status: "mock_enqueued"` con el
  payload que *habría* enviado: se puede probar el recorrido entero, incluido
  el botón de llamar, sin llamarle a nadie.

```bash
export DAPTA_FLOW_WEBHOOK_URL="https://..."   # antes de levantar uvicorn
```

---

## 6. Resolución de localidad por dirección

La función nueva del catálogo, en `scraping/scraper_projects.py`. Es la pieza que
conecta el scraping con el grafo: **si la localidad sale mal, el BFS expande
hacia vecinas equivocadas y el top completo queda sesgado.**

### 6.1 API

```python
from scraping.scraper_projects import localidad_desde_direccion, asignar_localidades

localidad_desde_direccion("Carrera 95A # 78 Sur, Bosa Recreo")
# {'localidad': 7, 'nombre': 'Bosa', 'confianza': 'alta',
#  'evidencia': 'nombre de localidad en la direccion: Bosa'}

catalogo = asignar_localidades(proyectos)   # agrega `Localidad` a cada uno
```

`asignar_localidades` es la función pedida: recibe el JSON de proyectos, lee
la dirección de cada uno y devuelve **el mismo JSON** con el atributo
`Localidad`. No muta la entrada. Acepta lista, dict con llave `proyectos`,
string JSON o ruta a un `.json`, y devuelve la misma forma que recibió.

### 6.2 Las tres pasadas

Se resuelve de más a menos confiable, y cada proyecto queda marcado con la
pasada que lo resolvió:

| Confianza | Cómo | Ejemplo |
|---|---|---|
| **alta** | La dirección nombra la localidad | `"Bosa, Bogotá. Cra. 95A #90-42 Sur"` → Bosa |
| **media** | La dirección nombra un barrio/sector del gazetteer | `"La Colina, Bogotá. Cra. 55 #152b-71"` → Suba |
| **baja** | Se infiere de la malla vial | `"Calle 13 # 28-52"` → Los Mártires |
| — | Otro municipio, o sin coincidencia | `"La Calera, Cundinamarca…"` → `null` |

**Gazetteer.** 311 barrios, sectores y UPZ. Es explícito: solo entra lo que se
puede afirmar. Los nombres que existen en dos localidades se dejan **fuera a
propósito** —"Unicentro" es el del norte en Usaquén y el de Occidente en
Engativá— y caen a la malla vial, que es preferible a resolver mal con aire de
certeza. Las frases se prueban de la más larga a la más corta, para que
"san cristobal norte" (Usaquén) le gane a "san cristobal" (localidad 4).

**Malla vial.** La cuadrícula de Bogotá es regular y eso la hace utilizable
como último recurso: las calles crecen hacia el **norte** (y hacia el sur con
el sufijo *Sur*) y las carreras hacia el **occidente** (y hacia el oriente con
*Este*). El parser lleva ambos números a un eje con signo:

```
calle_normalizada  = +N al norte, −N si dice "Sur"
carrera_normalizada = +N al occidente, −N si dice "Este"
```

y los busca en una tabla de 19 rectángulos, evaluada **en orden**: primero las
localidades pequeñas y bien delimitadas, para que no se las trague un
rectángulo grande que las contiene. Maneja avenidas con nombre
(`Av. Boyacá` → carrera 72, `Av. El Dorado` → calle 26), avenidas numeradas
(`Av. 70` → carrera 70), el prefijo `Av. Calle` / `Av. Carrera`, y el número
tras `#` como cruce del eje contrario. Es aproximado por construcción, por eso
queda marcado `baja` y no pisa a las otras dos pasadas.

**Fuera de Bogotá.** Cusezar y Bolívar filtran por área metropolitana, no por
ciudad: sus listados traen Cali, Cartagena, La Calera, Soacha, Zipaquirá.
Una dirección que nombra otro municipio devuelve `null` y el proyecto se
descarta del catálogo, con el motivo registrado.

### 6.3 Por qué la dirección le gana a la coordenada

Tres de las cuatro fuentes publican coordenadas, y los límites oficiales del
Distrito (`Model/data_projects/localidades_bogota.json`, Datos Abiertos Bogotá) permiten
convertirlas en localidad de forma exacta con point-in-polygon.

Aun así **la coordenada no manda**, y la razón es empírica: en varias fichas
el pin apunta a la **sala de ventas**, no al proyecto.

| Proyecto | Dirección publicada | Pin del mapa |
|---|---|---|
| Eskala (Colsubsidio) | Av. carrera 50 # 5F-19 → **Puente Aranda** | Bosa |
| Reserva del Nogal (Colsubsidio) | Calle 59B sur # 86a-15, **Bosa** Nova | San Cristóbal |

La dirección es lo que la constructora afirma del proyecto, así que decide
ella. La coordenada entra **solo cuando la dirección no alcanza**, y cuando
ambas discrepan queda anotado en `_localidad_evidencia` — que es justamente
como se detectaron estos casos.

Sobre el catálogo actual: **84 de 88** proyectos con coordenada coinciden con
lo que dice su dirección (95 %). De los 4 restantes, 2 son los errores de pin
de la tabla de arriba y 2 son fronteras reales —direcciones sobre la Carrera
30 y sobre la Avenida Ciudad de Cali, justo encima del límite entre dos
localidades—, donde ninguna de las dos respuestas es "la mala".

El contraste dirección/coordenada es además la herramienta con la que se
afinó la malla vial: cada desacuerdo señalaba un rectángulo mal puesto o un
sector que le faltaba al gazetteer.

El point-in-polygon está verificado: los 20 centroides de los polígonos
oficiales caen dentro de su propia localidad.

### 6.4 El barrio: al revés que la localidad

`asignar_barrios` corre después de `asignar_localidades` y **subordinado a
ella**: un barrio que contradiga la localidad ya asignada no se acepta. Y la
jerarquía de señales se invierte, porque casi ninguna dirección del catálogo
nombra un barrio ("Calle 235 # 52-50" no dice nada) y en cambio 88 de 96
publican coordenada:

| Confianza | Cómo | Cuántos |
|---|---|---:|
| **alta** | La dirección nombra un sector del grafo dentro de su localidad | 6 |
| **alta** | La coordenada cae en el polígono de un sector de su localidad | 48 |
| **media** | La coordenada queda a < 1,5 km del centroide de un sector suyo (huecos entre polígonos, sectores que la capa viva tiene y el TXT no) | 27 |
| **media** | La dirección nombra un sector de una localidad **vecina** ("Montevideo" es Kennedy en catastro, pero el proyecto está en Fontibón) | 2 |
| — | Nada de lo anterior | 13 |

La coordenada se descarta cuando cae fuera de la localidad del proyecto: es
el mismo pin de la sala de ventas del §6.3 (Eskala queda sin barrio por
eso). Cada proyecto sale con `barrio_id`, `barrio_nombre`,
`_barrio_confianza` y `_barrio_evidencia`.

```bash
python scraping/scraper_projects.py --solo-barrios   # releer el catálogo y reasignar, sin scrapear
```

Es lo que hay que correr cuando cambia el grafo y no el catálogo: no toca
ids, localidades ni imágenes. Después, `python Model/prep.py`.

---

## 7. El scraper

Las cuatro webs cargan sus proyectos por JavaScript, así que **ninguna se
puede leer del HTML plano del listado**. En vez de montar un navegador
headless se usa la misma fuente de datos que consume el front de cada sitio,
que además llega ya estructurada:

| Fuente | Cómo se obtiene | Detalle |
|---|---|---|
| **Amarilo** | API interna `apiweb.amarilo.com.co/search/v1/proyecto` | El listado renderiza en cliente (`<div id="proyectos" class="loading">`). La API trae el nodo completo: dirección, cifras, galería y zonas comunes. |
| **Cusezar** | HTML del listado + ficha por proyecto | Es la única que sí trae las tarjetas (`article.project-card`), con dirección y precio en `data-gtm-props`. Amenidades y galería salen de la ficha. |
| **Bolívar** | API interna `/api/proyectos-vivienda/20/all/all/all/all` + ficha | App Vue: el HTML trae la plantilla, no los datos. Cada ficha publica un **JSON-LD `ApartmentComplex`** con dirección postal, coordenadas, amenidades y alcobas. |
| **Colsubsidio** | `/api/basicProjectSearch` + `__NEXT_DATA__` de cada ficha | Los 29 de Bogotá son los que traen `field_housing_project_department == "Bogotá"` (el campo `city` guarda el sector comercial —Norte, Occidente, Centro—, no el municipio). Su JSON:API responde vacío a usuarios anónimos. El sitemap corrige las URLs viejas. |

### Detalles que cuestan tiempo si se descubren dos veces

- **Amarilo tiene la cadena TLS incompleta.** No envía el certificado
  intermedio, así que `requests` falla con `CERTIFICATE_VERIFY_FAILED`. Su
  propio front arranca axios con `rejectUnauthorized: false` por lo mismo.
  `_get` reintenta sin verificar **por host** y solo tras haberlo intentado
  bien primero.
- **Colsubsidio sirve páginas de ~1,7 MB** y corta conexiones bajo
  concurrencia: con 6 hilos se caían 12 de 29 fichas y esos proyectos quedaban
  sin dirección. Se baja a 3 hilos (`HILOS_POR_FUENTE`), hay backoff
  exponencial en `_get`, y al final `_reintentar_sin_direccion` relee una a una
  las fichas que quedaron vacías. Sin eso la corrida no es reproducible.
- **En Colsubsidio, `field_address_2` es la sala de ventas**, no el proyecto.
  La dirección del proyecto está en `field_long_description_two` del mismo
  paragraph. Las dos conviven; confundirlas manda proyectos de Bogotá a Soacha.
- **Las imágenes de Colsubsidio no están en `www`.** Las rutas del nodo
  (`/sites/default/files/…`) son del Drupal de atrás: sobre `www` devuelven
  **404 con una página de error de 800 KB**, que además pesa más que la foto.
  Hay que pedirlas a `cms.colsubsidio.com`.
- **El buscador de Colsubsidio publica alguna URL vieja.** Para "Abeto"
  apunta a `/abeto`, que responde **200 pero sin nodo** —no 404—, así que el
  proyecto se caía del catálogo sin error visible. La ficha viva es
  `/abeto-v2`. El sitemap sí está al día, así que se usa para corregir las
  URLs cuyo slug tiene una versión más nueva.
- **`?ciudad=bogota` de Cusezar no filtra del lado del servidor.** El listado
  trae Cali, Cartagena y La Calera igual. El filtro real lo hace la localidad.
- **Los proyectos comerciales se descartan** ("Zona Comercial", "Locales",
  "Oficina", "Parque Empresarial"): no son vivienda, no tienen habitaciones ni
  subsidio y no le sirven a quien busca dónde vivir.
- **Seis proyectos salen dos veces.** Constructora Bolívar los construye y
  Colsubsidio los comercializa, cada uno con su ficha y su precio —el de
  Colsubsidio suele ser el de afiliado, hasta un 19 % más bajo—: Álamo
  Veramonte, Austro de Cuatro Vientos, Baviera Park, Novum Ricaurte, Senderos
  de Fontibón y Urbana 30. Sin fusionarlos, el top gasta dos casillas en el
  mismo edificio. `fusionar_duplicados` los une conservando **las dos fichas**
  (`links_alternos`, `constructoras`), el precio más bajo, y la unión de zonas
  comunes e imágenes.

  Para decidir que son el mismo proyecto se exige el mismo nombre **y** que
  las localidades coincidan o sean vecinas en el grafo. Lo segundo no sobra:
  la dirección que publica cada constructora difiere, y Novum Ricaurte cae en
  Puente Aranda por una y en Los Mártires por la otra. Sin ese margen no se
  fusionaría; sin el límite de un salto, dos proyectos distintos con el mismo
  nombre en extremos opuestos de la ciudad se fusionarían por error.

### Imágenes

`frontend/public/recursos/imagenes_proyectos/<id_proyecto>/01.webp, 02.jpg, …`
— una carpeta por proyecto, nombrada con su id (§1.3). Se numeran en el orden en que las publica la
fuente, así que la primera es siempre la de portada. La extensión sale del
`Content-Type` que declara el servidor, no de la URL.

Son varios cientos de MB, así que esa carpeta está en `.gitignore`: se
regeneran corriendo el scraper. Una imagen que no baja no aborta nada —
falla rápido (25 s, 2 intentos) y se sigue, porque bloquear la descarga
entera por un archivo opcional no compensa.

### Estado del catálogo

Última corrida: **96 proyectos** en 14 de las 20 localidades (102 fichas menos
las 6 fusionadas).

| Constructora | Proyectos | | Tipo | Proyectos |
|---|---:|---|---|---:|
| Amarilo | 37 | | VIS | 58 |
| Colsubsidio | 23 | | No VIS | 38 |
| Bolívar | 22 | | | |
| Cusezar | 14 | | | |

Concentración por localidad: Suba 31 · Bosa 14 · Fontibón 13 · Engativá 12 ·
Usme 10, y el resto con 3 o menos. **Seis localidades se quedan sin oferta**:
Tunjuelito, Antonio Nariño, La Candelaria, Rafael Uribe Uribe, Ciudad Bolívar
y Sumapaz. Ese es exactamente el caso para el que existe la expansión por el
grafo (§3.3): un usuario de Rafael Uribe Uribe no se queda sin resultados,
recibe los de sus vecinas con la penalización de distancia correspondiente.

Descartados: 21. Dieciséis por estar fuera de Bogotá —Cusezar y Bolívar
mezclan Cali, Cartagena, La Calera, Funza, Cajicá, Zipaquirá y Soacha— y
cinco por no ser vivienda (zonas comerciales, locales, oficinas). Todos
quedan listados con su motivo en la llave `descartados` del JSON, y las
fusiones en `fusionados`: **nada se cae en silencio**.

Barrio resuelto en **83 de los 96** (42 sectores distintos); el resto usa la
distancia típica de su salto de localidad (§3.5).

Cobertura: con estos 96 proyectos, **todos son alcanzables** por el
recomendador en modo contenido. Con el historial activo el sesgo de
popularidad del colaborativo deja fuera a unos pocos de las localidades
sobreofertadas; el piso de 30 interacciones por proyecto y `ALPHA_HISTORIAL`
en 0,50 son lo que evita que sean muchos más.

---

## 8. El formulario (`frontend/`)

**Aquí hubo una landing y ahora solo está el formulario.** Esta copia del repo
existe para mostrar la experiencia y nada más: se borró `src/` entero —React
19, Tailwind v4, Framer Motion, y con ellos `Navbar · Hero · Marquee ·
Benefits · LiveDemo · Credibility · FlowDiagram · FAQ · Offer · Footer`, más
`lib/api.ts`, `lib/catalogos.ts`, `lib/content.ts` y `lib/offerConfig.ts`—.

Lo que queda son **dos piezas**: `index.html`, un cascarón de una sola página,
y `public/experiencia/`, el bundle del quiz, que **no se tocó** (§8.3). Es el
mismo que servía el modal de la landing: el formulario, tal cual estaba.

**Stack:** Vite 8, y nada más. No hay build de TypeScript (`npm run build` ya
no corre `tsc -b`, porque no queda código que compilar), ni oxlint, ni React.
El bundle es JS vanilla que Vite sirve desde `public/` sin pasarlo por el
pipeline.

### 8.1 Correr las dos mitades

```bash
cd backend && uvicorn api.app:app --port 8000   # terminal 1
cd frontend && npm install && npm run dev       # terminal 2, el quiz en :5173
```

`vite.config.ts` usa `strictPort: true` en 5173 (respeta `PORT` si está): si
el puerto está ocupado **falla en vez de moverse solo**, para que la URL del
stand sea siempre la misma.

La copia publicada del bundle va con `SIN_BACKEND: true` en `js/config.js`, así
que el quiz calcula su Top 6 con el motor de reglas de `matching.js` y **no
llama al modelo**. Para probarlo contra `recomendar()` de verdad hay que
apagar ese flag y levantar el servicio que espera `Leadify_BASE`.

### 8.2 `index.html` — el cascarón

Son ~20 líneas: un `<iframe>` a pantalla completa con

```
/experiencia/index.html?marca=leadify
```

y tres decisiones que conviene no deshacer sin querer:

- **`?marca=leadify` no es opcional.** El bundle es multi-tenant y sin ese
  parámetro cae en `constructora-bolivar`, que filtra el catálogo a una sola
  constructora. `leadify` es el tenant neutro: puntúa sobre los 96 y salen las
  cuatro marcas juntas.
- **Se nombra `index.html`, no el directorio.** `/experiencia/` funciona
  publicado, pero en `npm run dev` Vite trata una ruta sin extensión como
  navegación y devuelve el cascarón: el iframe cargaría esa misma página
  dentro de sí misma, con 200 y sin un solo error en consola.
- **Ya no va `embed=1`.** Hacía dos cosas: saltarse el splash de bienvenida
  y mover la escena de la casa a la derecha, que era lo que le convenía al
  modal. Lo primero ya no hace falta —**el splash se borró** del bundle
  (§8.3)— y lo segundo nunca se quiso aquí.

**Por qué sigue siendo un iframe y no el bundle servido en la raíz.** El
arranque del quiz inyecta los archivos del tenant con `document.write` **en el
punto del parser**; bajo `defer`, dentro de un `DOMContentLoaded` o pasado por
el build de Vite, borra el documento entero. El iframe lo deja intacto —
aislamiento de parser y de CSS sin reescribir una línea— y mantiene la URL de
la demo en `/`.

**La paleta ya no vive en ningún `@theme`.** Con Tailwind se fue
`src/index.css`, que era donde estaban los tokens de marca. Los valores quedan
anotados en un comentario de `index.html`, porque `js/tema.js` del bundle los
duplica a mano (§8.3) y hay que tener contra qué compararlos: coral `#ff6259`,
navy `#2d3b4e`, beige `#fdf6f0`, emerald `#2dd4a7`, titulares Sora, cuerpo
Manrope.

### 8.3 `public/experiencia/` — el quiz, vestido de Leadify

El bundle trae su propio sistema visual, gobernado por **tokens en el `:root`
de `css/styles.css`** que reescribe `js/tema.js` según el tenant. Los valores
por defecto son los de la **consola negra** de las cuatro constructoras; el
tenant `leadify` es el único que los cambia: es la identidad de Leadify, la que
tenía la landing que envolvía a este quiz y hoy es la única que queda.

| | Las cuatro constructoras | Leadify |
|---|---|---|
| Superficie | `--fondo #0a0b0d` (consola) | `#fdf6f0` beige, papel blanco |
| Primario | `#ff7a18` naranja estándar | `#FF6259` coral |
| Titulares | Poppins | **Sora** |
| Radios | 12 · 14 · 16 px | **16 · 18 · 24 px**, CTA en pastilla |
| CTA | `--acento`, su segundo color | **coral**, el primario de Leadify |
| Sombras | duras, para fondo negro | `--shadow-soft` / `--shadow-coral` |

El CTA es el único cambio con una razón que no es de estilo: el verde es el
color de que **algo encaja** —compatibilidad, match, llamada— y gastarlo en
"Continuar" le quitaba ese significado justo donde hace falta, en las
tarjetas de resultado.

Las dos piezas que lo deciden viven en `js/tema.js`: **`SUPERFICIE_Leadify`**
(fondo, papel, borde, tinta) y **`SISTEMA_Leadify`** (fuente, radios, sombras,
CTA). Los valores están escritos a mano: el bundle **no compila con Vite**
—vive en `public/` y se sirve tal cual— así que no hay forma de importarlos.
Su referencia era el `@theme` de `frontend/src/index.css`, que se fue con la
landing; hoy está en el comentario de `frontend/index.html` (§8.2), que existe
justamente para eso.

Lo que no cabe en un token —una versalita, un interletrado— va en el bloque
`[data-marca='leadify']` al final de `styles.css`. El atributo lo pone
`tema.js`, que es quien sabe de qué marca se trata; **no** se usa la clase
`.gdf-con-senal`, que significa "hay fondo animado detrás" y la pone
`senal.js`.

**Se entra rellenando los datos: el splash se borró.** Era la pantalla de
bienvenida —la casita ilustrada, "Encuentra tu próximo hogar", el botón
"¡Construir mi casa!"— y `createInitial()` en `js/state.js` arranca ahora en
`escarapela`, la del carné de constructor. Dentro de la landing esa pantalla
ya era una segunda puerta, y por eso el modal la saltaba con `embed=1`; sin
landing delante pasó a ser la única puerta, que es peor: tres frases entre el
usuario y el formulario.

Se fue con lo que colgaba de ella: la acción `goSplash`, el "← Atrás" de la
escarapela —que llevaba a una pantalla que ya no existe— y el caso del
`switch` de `renderApp`, cuyo `default` cae ahora en la escarapela. Lo que
**no** se borró son sus textos (`splashTitulo`, `splashLead`, `splashQuote`,
`splashCta` en el manifiesto de cada tenant), su CSS (`.gdf-hero*`) ni las dos
funciones que solo ella llamaba (`houseIllustration`, `logoHtml`): son datos y
piezas de marca, quietas no estorban, y son exactamente lo que haría falta si
la entrada vuelve.

**La pregunta de ubicación tiene un solo buscador.** Hubo dos pestañas
—"Conozco el barrio" y "Sé un lugar cerca"— y se quitaron: obligaban a
clasificarse antes de escribir. Hoy se escribe y ya, y los resultados bajan en
**una lista con dos encabezados**, de tres capas (`renderZonaSugerencias` en
`js/main.js`):

| Capa | Fuente | Cuándo |
|---|---|---|
| Barrios y localidades | `GDF_BARRIOS`, 1.258 entradas | local, desde la 1.ª letra |
| Lugares | `GDF_LUGARES`, sitios de OSM ya resueltos a `{loc, bi}` | local, desde la 2.ª |
| Lugares (cola larga) | Photon (`photon.komoot.io`) | en vivo, con debounce de 300 ms |

Photon y no Nominatim porque Nominatim **prohíbe** el uso tipo autocompletar
en su política. Si no hay red, las dos capas locales ya están en pantalla y no
se muestra ningún error. Todo resultado en vivo se resuelve a su localidad con
`mapa.zonaEnPunto` **antes** de pintarse, así que lo que cae fuera de las 20
localidades (Chía, Soacha) nunca se ofrece. El barrio sigue sin filtrar
(invariante 12): un lugar solo cambia lo que dice el chip ("Cerca de
Unicentro"), no lo que viaja al modelo.

**Hay dos copias del bundle y hay que tocar las dos.** `experiencia/` en la
raíz es la fuente de trabajo (sin versionar) y `frontend/public/experiencia/`
es la que se sirve y se versiona. Fuera de `js/config.js` —que en la publicada
fuerza `SIN_BACKEND: true`— son idénticas, y dejarlas divergir es la versión
de este bundle del invariante 1.

---

## 9. Invariantes que no se pueden romper

1. **`Model/catalogos.py` es la única fuente de los ids.** Los índices de
   `ZONAS_COMUNES` (0–24) y los de `LOCALIDADES_BOGOTA` (1–20) viajan dentro
   de `proyectos_model.json` y del perfil del usuario. Si un módulo define su
   propia copia, cualquier desfase produce cruces mal hechos **en silencio**:
   nada falla, solo se recomienda peor.
2. **Una amenidad desconocida se reporta, no se adivina.** Ese es el contrato
   de `mapear_zonas_comunes`.
3. **`tipo_vivienda` nunca se relaja** en el filtro.
4. **Nada relajado queda por encima de algo que cumple todo**, sin importar el
   score.
5. **`SMMLV` se actualiza cada año, y ahora vive en un solo sitio**:
   `Model/prep.py`. Todo el eje de `salario` depende de él, y `api/app.py` lo
   importa de ahí (`from Model.prep import SMMLV as SMMLV_COP`) en vez de
   tener su propia copia. Antes había dos y este invariante pedía acordarse de
   los dos; ahora desfasarlos es imposible. Lo que **sí** hay que revisar cada
   año, además del SMMLV, son las tasas y plazos de `PARAMETROS_CREDITO`
   (§4.1): son datos de mercado y se mueven.
6. **Todo espejo de `Model/catalogos.py` en el front hereda el invariante 1.**
   `frontend/src/lib/catalogos.ts` ya no existe —se fue con la landing (§8)—,
   pero el bundle de `public/experiencia/` sigue trayendo los suyos: si se
   desincronizan, el front manda ids que apuntan a otra localidad o zonas que
   el modelo descarta **sin error visible**. `GET /api/catalogos` sirve la
   versión buena y es la vía para verificarlo.
7. **`DAPTA_FLOW_WEBHOOK_URL` nunca se hardcodea.** Sin la variable el
   endpoint responde en modo mock, que es el comportamiento correcto en
   desarrollo — no un fallo que haya que "arreglar" poniendo la URL en el
   código.
8. **`api/app.py` no toma decisiones de recomendación.** Valida, traduce y
   delega. Cualquier regla de negocio nueva va en `Model/`, o quedará
   invisible para la CLI, la evaluación y los clientes simulados.
9. **`Model/rutas.py` es la única fuente de las rutas.** Ningún módulo
   calcula la suya con `os.path.dirname(__file__)`. Es el invariante 1
   aplicado a archivos: dos módulos con ideas distintas de dónde está
   `proyectos_model.json` no fallan, leen cosas distintas.
10. **La cota de precio no rompe el invariante 4.** `Cota_minimaBG` puede
    sacar al usuario de la localidad que pidió si el ahorro lo justifica, pero
    **nunca** cruza tramos de `_prioridad_filtro`: lo admitido relajando
    requisitos no adelanta a lo que cumple todo por ser más barato.
    `respetar_prioridad=False` levanta el candado y existe solo para medir.
11. **El recall de `evaluar.py` no es la métrica del reenfoque económico.**
    La "verdad" que simula `generar_historial.utilidad` solo penaliza el
    precio cuando el proyecto no alcanza (`_ajuste_precio` devuelve 0.0 si hay
    holgura), así que le da igual mostrar el de 182 millones o el de 262. Para
    medir esta versión hay que usar `calibrar_cota.py`, que reporta el recall
    **y** el precio, los años y la alcanzabilidad del top (§4.5).
12. **El barrio nunca filtra, y nunca contradice a la localidad.** La
    admisión es el BFS de localidades (§3.3); el grafo de barrios solo pesa
    la distancia (§3.5). En el catálogo, un barrio que caiga en otra
    localidad que la asignada se descarta (§6.4); en el formulario, es un
    error que se reporta. Un formulario **sin** barrio tiene que dar
    exactamente lo de la v0.3: es lo que mantiene válidas las tablas de
    §4.3–4.5.
13. **`barrios_bogota.json` se genera, no se edita.** La fuente es
    `barrios_bogota_vecinos.txt` (aristas) más la geometría oficial
    (centroides); `python Model/grafo_barrios.py` los compila. Tocar el JSON
    a mano es la versión de barrios del invariante 1: nada falla, solo se
    mide otra cosa. Después de recompilarlo hay que reasignar los barrios del
    catálogo (`--solo-barrios`) y volver a correr `prep.py`.
