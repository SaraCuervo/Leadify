# Scripts

Los scripts del proyecto —el clustering y la calificación del lead— no son
sueltos: son módulos del motor y viven en
[`Demo/backend/`](../Demo/backend/), porque se importan entre ellos.

| Qué | Dónde | Cómo se corre |
|---|---|---|
| Clustering y ranking | `Demo/backend/Model/modelo.py` | `python main.py --usuario Model/data_projects/usuario_ejemplo.json` |
| Filtro duro y expansión geográfica | `Demo/backend/Model/modelo.py` | (lo llama el pipeline) |
| Capa económica: años de pago y cota de precio | `Demo/backend/Model/cota_minima.py` | (lo llama el pipeline) |
| Etiquetado del catálogo y simulación de crédito | `Demo/backend/Model/prep.py` | `python Model/prep.py` |
| Grafo de barrios (compila el JSON desde la fuente) | `Demo/backend/Model/grafo_barrios.py` | `python Model/grafo_barrios.py` |
| Scraper del catálogo | `Demo/backend/scraping/scraper_projects.py` | `python scraping/scraper_projects.py` |
| Generación de clientes e historial simulados | `Demo/backend/Model/simulacion/` | `python Model/simulacion/generar_clientes.py` |
| Evaluación del modelo (recall con y sin historial) | `Demo/backend/Model/simulacion/evaluar.py` | `python Model/simulacion/evaluar.py --top 18` |
| Calibración de la cota de precio y de los barrios | `Demo/backend/Model/simulacion/calibrar_*.py` | `python Model/simulacion/calibrar_cota.py` |

Todos se corren desde `Demo/backend/`, que es donde el paquete `Model` es
importable. Cada archivo explica en su cabecera qué hace y por qué; la vista de
conjunto está en [Arquitectura y Diseño](https://github.com/SaraCuervo/Leadify/wiki/Arquitectura-y-Dise%C3%B1o), en la wiki.

## Los que sí viven aquí

Tres comprobaciones que se corren **desde la raíz del repositorio**:

| Script | Qué revisa | ¿Necesita `pip install`? |
|---|---|---|
| `verificar_sintaxis.py` | Que todos los `.py` del repositorio compilen, sin correr nada. Es la comprobación más barata: un archivo que nadie tocó en semanas puede romperse por un cambio en otro lado, y esto lo detecta al instante. | No. Solo usa `py_compile`, de la librería estándar. |
| `verificar_catalogo.py` | Que `proyectos_model.json` —que se versiona— corresponda al código que lo genera. Lo regenera en otro archivo y compara, ignorando la marca de tiempo, así que no toca lo versionado. | **Sí.** Su propio código no usa numpy ni scikit-learn, pero llama a `Model/prep.py`, y entrar al paquete `Model/` ejecuta su `__init__.py`, que sí las importa. |
| `verificar_enlaces.py` | Que ningún enlace relativo de los `.md` apunte al vacío. | No. Solo usa la librería estándar de Python. |

```bash
python Script/verificar_sintaxis.py
python Script/verificar_enlaces.py

# esta necesita el backend instalado antes, desde Demo/backend/:
pip install -r requirements.txt
cd .. && python Script/verificar_catalogo.py
```

La cuarta comprobación, la del motor entero, vive con el motor:
`Demo/backend/pruebas/prueba_humo.py`, y también necesita las dependencias
instaladas. Conviene correr las cuatro antes de subir un cambio: tardan menos
de un minuto entre todas.
