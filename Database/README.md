# Base de datos

Leadify no usa un motor de base de datos: los datos con los que recomienda son
archivos JSON y viajan **dentro del código**, en
[`Demo/backend/Model/data_projects/`](../Demo/backend/Model/data_projects/).

Esta carpeta no los duplica a propósito. Dos copias del catálogo se
desincronizan sin que nada falle —el modelo simplemente recomienda sobre datos
viejos—, así que aquí solo está el índice de qué hay y para qué sirve.

## Qué hay

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

## Por qué no están en esta carpeta

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
