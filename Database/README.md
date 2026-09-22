# Base de datos

Hay dos cosas distintas bajo "datos" en Leadify, y conviene no confundirlas:
**los leads** —quién llenó el formulario y qué se le recomendó— sí viven en un
motor de base de datos de verdad; **el catálogo con el que el modelo
recomienda** no, y esa parte del documento sigue vigente tal cual estaba.

## Los leads: Postgres, en Supabase

Cuando alguien llena el carné y termina el cuestionario, se guarda quién es,
qué respondió y qué se le recomendó — para que si vuelve y escribe su cédula y
su teléfono, no tenga que repetir las siete preguntas. También queda anotado
qué proyecto le interesó y si la llamada de Manuela terminó en una cita
agendada con un asesor.

Vive en un proyecto de Supabase (Postgres gestionado) aparte del catálogo del
modelo. El esquema real, tal como está aplicado, está en
[`esquema/`](esquema/):

| Archivo | Qué crea |
|---|---|
| [`01_tablas.sql`](esquema/01_tablas.sql) | Las tres tablas: `leads`, `consultas`, `intereses`. Row Level Security activado y sin políticas — cerradas a cal y canto. |
| [`02_funciones.sql`](esquema/02_funciones.sql) | Las cuatro funciones que sí puede llamar el navegador: `guardar_consulta`, `buscar_resultados`, `marcar_interes`, `marcar_intencion`. |

### Sin login, pero sin dejar los datos al aire

El navegador lleva una clave *publicable* (en
[`Demo/frontend/public/experiencia/js/config.js`](../Demo/frontend/public/experiencia/js/config.js),
`SUPABASE_KEY`) que cualquiera puede ver con "ver código fuente". Por eso las
tablas están cerradas por completo —ni `anon` ni `authenticated` pueden leer
una fila directo— y todo pasa por las cuatro funciones de `02_funciones.sql`.

La que importa es `buscar_resultados`: exige **cédula Y teléfono** a la vez, y
si no coinciden los dos no devuelve nada, ni siquiera confirma que la cédula
exista. Es lo único que impide que alguien con el número de documento de otra
persona vea su nombre, su correo y sus recomendaciones — no hay una cuenta ni
una contraseña de por medio, así que esa pareja de datos es la única cerradura
que hay.

El teléfono guardado tampoco se sobreescribe en una consulta nueva: si se
pisara, cualquiera podría reclamar una cédula ajena mandándola una vez con su
propio número, y desde ahí controlar los dos datos que hacen falta para leer
las consultas de esa persona.

### Qué cuenta como intención de compra

`intereses.intencion_compra` se pone en `true` cuando Dapta devuelve
`fecha_de_seguimiento` en el análisis posterior a la llamada — la señal de que
quedó una cita puesta con un asesor (ver el webhook en
[`Demo/backend/api/app.py`](../Demo/backend/api/app.py)). Sin fecha, queda en
`false`: pedir la llamada por sí solo no cuenta, tiene que haber agendado.

### El cliente

[`Demo/frontend/public/experiencia/js/datos.js`](../Demo/frontend/public/experiencia/js/datos.js)
es el único módulo que le habla a Supabase. Ninguna de sus funciones puede
tumbar el formulario: si la base no responde, el cuestionario sigue su curso
normal y solo se pierde el guardado — guardar es un efecto secundario, nunca
un requisito para que la persona vea sus recomendaciones.

---

## El catálogo del modelo: JSON, no un motor de base de datos

Esto es aparte de los leads de arriba. El motor de recomendación no consulta
Postgres para decidir qué proyectos mostrar: los datos con los que recomienda
son archivos JSON y viajan **dentro del código**, en
[`Demo/backend/Model/data_projects/`](../Demo/backend/Model/data_projects/).

Esta carpeta no los duplica a propósito. Dos copias del catálogo se
desincronizan sin que nada falle —el modelo simplemente recomienda sobre datos
viejos—, así que aquí solo está el índice de qué hay y para qué sirve.

### Qué hay

| Archivo | Peso | Qué es |
|---|---:|---|
| `proyectos_bogota.json` | 0,37 MB | El catálogo crudo: 96 proyectos de vivienda de Bogotá D.C. scrapeados de Amarilo, Cusezar, Constructora Bolívar y Colsubsidio. Incluye los descartados y los fusionados, cada uno con su motivo. |
| `proyectos_model.json` | 0,22 MB | El mismo catálogo ya etiquetado: a cada proyecto se le derivó el comprador al que apunta (salario objetivo, personas a cargo, edad) y la simulación de su crédito. **Es el que lee el motor.** |
| `clientes_simulados.json` | 0,86 MB | 1.000 clientes sintéticos, 100 variaciones de cada uno de los 10 arquetipos de comprador. |
| `historial_simulado.json` | 3,38 MB | 8.700 interacciones simuladas (vista, lead, compra) de esos clientes. Es lo que entrena el componente colaborativo. |
| `localidades_bogota.json` | 2,26 MB | Los límites oficiales de las 20 localidades (Datos Abiertos Bogotá). Resuelve la localidad de una coordenada. |
| `barrios_bogota.json` | 0,27 MB | El grafo de 1.164 barrios: nombre, localidad, centroide y vecinos de cada sector catastral. Es el que mide la cercanía en kilómetros. |
| `barrios_bogota_vecinos.txt` | 0,16 MB | La **fuente** de las aristas de ese grafo: los vecinos de cada sector, calculados sobre la capa catastral oficial. |
| `barrios_bogota_geo.json` | 0,67 MB | Los polígonos de esos sectores, simplificados. De aquí salen los centroides. |
| `usuario_ejemplo.json` · `usuario_minimo.json` | — | Dos formularios de prueba, para llamar al motor sin levantar el front. |

### Por qué no están en esta carpeta

Son los datos **con los que el modelo fue entrenado** y contra los que
recomienda, así que viajan con el código que los interpreta: quien clona el
repositorio puede llamar a `recomendar()` sin scrapear ni entrenar nada. Además,
`Demo/backend/Model/rutas.py` es la única fuente de las rutas del proyecto, y
moverlos de sitio obliga a tocarla.

Cómo se construye cada uno: el catálogo lo arma
`Demo/backend/scraping/scraper_projects.py` y lo etiqueta `Model/prep.py`; el
grafo de barrios lo compila `Model/grafo_barrios.py`; y los clientes e
historial simulados salen de `Model/simulacion/`. La vista de conjunto está en
[Arquitectura y Diseño](https://github.com/SaraCuervo/Leadify/wiki/Arquitectura-y-Dise%C3%B1o), en la wiki.
