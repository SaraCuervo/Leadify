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
importable. Qué hace cada uno y por qué está en
[`Docs/GUIA_TECNICA.md`](../Docs/GUIA_TECNICA.md).

## Los que sí viven aquí

Dos comprobaciones que no dependen del motor y se corren **desde la raíz del
repositorio**:

| Script | Qué revisa |
|---|---|
| `verificar_catalogo.py` | Que `proyectos_model.json` —que se versiona— corresponda al código que lo genera. Lo regenera en otro archivo y compara, ignorando la marca de tiempo, así que no toca lo versionado. |
| `verificar_enlaces.py` | Que ningún enlace relativo de los `.md` apunte al vacío. |

```bash
python Script/verificar_catalogo.py
python Script/verificar_enlaces.py
```

La tercera comprobación, la del motor, vive con el motor:
`Demo/backend/pruebas/prueba_humo.py`. Las tres, y cuándo correrlas, están en
[`Docs/CONTRIBUTING.md`](../Docs/CONTRIBUTING.md).
