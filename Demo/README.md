# Demo — Machea

Recomendador de proyectos de vivienda en Bogotá D.C. Recibe el formulario de
una persona y devuelve los 18 proyectos más compatibles, cada uno con su
porcentaje de compatibilidad.

Esta carpeta es una **copia funcional** del proyecto al 19 de septiembre de
2026, puesta aquí para que se pueda ver y correr sin pedirle nada a nadie.
No es la fuente de verdad: el repo vivo es
[BGsanti/Machea](https://github.com/BGsanti/Machea).

---

## Lo más rápido: ver la experiencia

El quiz interactivo —el recorrido que hace la persona, con el plano del
apartamento armándose a medida que responde— es **estático y no necesita el
backend**. Va con `SIN_BACKEND: true`, así que se abre y funciona:

```bash
cd frontend/public/experiencia
python -m http.server 8000
```

Y abrir <http://localhost:8000>. Son siete preguntas y toma unos dos minutos.

Por defecto se viste de **Constructora Bolívar**. Con `?marca=<slug>` se
cambia de marca: `amarilo`, `colsubsidio`, `cusezar`, `machea`. Por ejemplo
<http://localhost:8000/?marca=colsubsidio>.

> Hace falta un servidor local (la línea de arriba). Abrir el `index.html` con
> doble clic no basta: el navegador bloquea la carga de los catálogos por
> `file://`.

---

## Correr el motor completo

Son dos mitades: el motor en Python y la landing en React.

```bash
# terminal 1 — la API
cd backend
pip install -r requirements.txt
uvicorn api.app:app --port 8000

# terminal 2 — la landing
cd frontend
npm install
npm run dev          # queda en http://localhost:5173
```

La landing consulta la API en vivo: se llena el formulario y salen los
proyectos reales del catálogo.

También se puede usar el motor sin levantar nada, desde Python:

```python
from Model import recomendar, respuesta_json      # desde backend/

resultado = recomendar({
    "tipo_vivienda": 1, "salario": 2, "personas_a_cargo": 3, "edad": 34,
    "Localidad": 7, "numero_habitaciones": 3,
})
print(respuesta_json(resultado)["apartamentos"][0])
```

---

## Qué hay en cada carpeta

| Carpeta | Qué es |
|---|---|
| `backend/Model/` | El motor. Es lo único que decide qué se recomienda: el filtro duro, el Nearest Neighbors, la capa económica y los dos grafos de proximidad. |
| `backend/Model/data_projects/` | Los datos con los que se entrenó: el catálogo de 96 proyectos, 1.000 clientes simulados, 8.700 interacciones y el grafo de 1.164 barrios. Por eso funciona recién clonado. |
| `backend/api/` | La capa HTTP (FastAPI). No decide nada: valida, traduce y delega en el motor. |
| `backend/scraping/` | Construye el catálogo desde las webs de cuatro constructoras. |
| `frontend/src/` | La landing en React 19 + Vite + Tailwind v4. |
| `frontend/public/experiencia/` | El quiz interactivo: bundle estático autocontenido. |

---

## Cómo funciona, en corto

1. **Filtro duro.** Se queda con los proyectos del mismo tipo de vivienda, con
   las habitaciones pedidas y en la localidad pedida. Si no llegan a 30, la
   búsqueda se abre a las localidades vecinas recorriendo un grafo de las 20
   localidades de Bogotá.
2. **Nearest Neighbors.** Compara el perfil de la persona (ingreso, personas a
   cargo, edad) contra el perfil al que apunta cada proyecto, y lo cruza con
   lo que hicieron usuarios parecidos.
3. **La plata manda.** Se simula el crédito —distinto para VIS y No VIS— y se
   calcula en cuántos años pagaría *esta* persona *ese* proyecto. Una
   diferencia de precio de 50 millones puede invertir dos posiciones.
4. **Porcentaje de compatibilidad.** El score se traduce a un número que se le
   puede mostrar a la persona, con el empate resuelto a favor del más barato.

El resultado del reenfoque económico: el Top 3 sale **20 % más barato** que en
la versión anterior.

La documentación completa —contrato de datos, los dos grafos, la calibración
de cada parámetro y los invariantes que no se pueden romper— está en
[`CLAUDE.md`](CLAUDE.md). El contrato que espera el formulario está en
[`CONTRATO_FRONT.md`](CONTRATO_FRONT.md), y las instrucciones originales del
repo en [`README-machea.md`](README-machea.md).

---

## Diferencias con el repo original

- **Las imágenes están recomprimidas.** Los planos y las fotos se redujeron al
  ancho en que se muestran (740 px y 900 px): 218 MB → 69 MB, sin cambiar
  nombre ni formato, así que los catálogos siguen cruzando igual. Se verificó
  que el plano del quiz se arma correctamente con ellas.
- **No viajan `node_modules` ni las imágenes crudas del scraper.** Las
  primeras salen con `npm install`; las segundas las regenera
  `backend/scraping/scraper_projects.py`.
