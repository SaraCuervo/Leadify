# Leadify

Proyecto del curso **Fundamentos de Ingeniería de Software** de la **Pontificia Universidad Javeriana**.

## Descripción

Leadify convierte visitantes anónimos de una constructora en citas agendadas con el asesor comercial.

**El problema.** Las constructoras generan tráfico, pero el formulario de "contáctenos" no filtra nada: los asesores pierden tiempo con leads fríos o sin capacidad real de compra. Además, el comprador no logra comparar entre decenas de proyectos y tipologías (precio, área, subsidio, ubicación) y termina en portales genéricos, donde la constructora compite con toda la oferta y pierde marca.

**La solución.**

- Una landing gamificada white-label: un cuestionario visual en el que la persona arma su "casa ideal".
- Un motor de recomendación que cruza el perfil del lead con el catálogo de la constructora y devuelve los proyectos más compatibles, cada uno con su porcentaje de compatibilidad.
- Calificación automática del lead: "listo para asesor" o "en maduración".
- Una llamada automática con Dapta que confirma datos, resuelve dudas y agenda la cita.

El asesor recibe al lead con la cita ya puesta, no solo con un dato de contacto. El modelo de negocio completo está en el [lean canvas](Leadfy%20lean%20canvas%20(1).pdf).

**Sobre el demo.** El motor de recomendación es una adaptación de Machea, un recomendador de vivienda en Bogotá D.C. El demo funcional está en la carpeta `Demo/` de la rama `develop` y usa datos sintéticos (clientes e historial simulados), no leads reales.

## Equipo del proyecto

| Nombre | Rol | Usuario de GitHub |
|---|---|---|
| Diego Ortiz | Documentación | [diego131t-max](https://github.com/diego131t-max) |
| Carlos Figueroa | Base de datos, scripts y gráficas | [FigueroaCarlos](https://github.com/FigueroaCarlos) |
| Santiago Díaz | Historias de usuario y cuestionario | [BGsanti](https://github.com/BGsanti) |
| Sara Cuervo | Repositorio y estimaciones | [SaraCuervo](https://github.com/SaraCuervo) |

## Tecnologías

**Backend (motor de recomendación)**

- Python 3.11
- FastAPI y Uvicorn: capa HTTP
- scikit-learn y NumPy: Nearest Neighbors sobre el perfil del comprador
- Requests, BeautifulSoup y lxml: scraper del catálogo de proyectos
- Dapta: agente de voz que hace la llamada de calificación y agendamiento

**Frontend (landing y quiz interactivo)**

- React 19 y TypeScript
- Vite
- Tailwind CSS v4
- Framer Motion y Lucide

## Instalación y ejecución

El código del demo está en la rama `develop`, dentro de la carpeta `Demo/`.

```bash
git clone https://github.com/SaraCuervo/Leadify.git
cd Leadify
git checkout develop
cd Demo
```

### Opción rápida: solo el quiz interactivo

El quiz es estático y no necesita el backend.

```bash
cd frontend/public/experiencia
python -m http.server 8000
```

Abrir <http://localhost:8000>. Son siete preguntas y toma unos dos minutos. Con `?marca=<slug>` se cambia la marca: `amarilo`, `colsubsidio`, `cusezar`, `machea` (por defecto, Constructora Bolívar).

Hace falta el servidor local: abrir `index.html` con doble clic no funciona, porque el navegador bloquea la carga de los catálogos por `file://`.

### Motor completo: API y landing

En una terminal, la API:

```bash
cd backend
pip install -r requirements.txt
uvicorn api.app:app --port 8000
```

En otra terminal, la landing:

```bash
cd frontend
npm install
npm run dev
```

La landing queda en <http://localhost:5173> y consulta la API en vivo.

### Usar el motor desde Python

Desde la carpeta `backend/`:

```python
from Model import recomendar, respuesta_json

resultado = recomendar({
    "tipo_vivienda": 1, "salario": 2, "personas_a_cargo": 3, "edad": 34,
    "Localidad": 7, "numero_habitaciones": 3,
})
print(respuesta_json(resultado)["apartamentos"][0])
```

### Llamada con Dapta (opcional)

El endpoint `POST /api/llamar` dispara la llamada automática. Sin configuración responde en modo simulado (`mock_enqueued`) y no llama a nadie. Para conectarlo a un flow real, definir la variable de entorno antes de levantar la API:

```bash
export DAPTA_FLOW_WEBHOOK_URL="https://..."
```

## Requisitos

- Python 3.11 o superior
- Node.js 20.19 o superior, con npm (solo para la landing)
- Git
- Un navegador actualizado
- Opcional: una cuenta y un flow de Dapta para las llamadas reales

## Estructura del proyecto

Rama `main`:

```
Leadify/
├── Database/                   Base de datos
├── Docs/
│   └── Dailys/                 Actas de los dailys (Daily1 a Daily5)
├── Graficas/                   Gráficas de las métricas del lean canvas
├── Script/                     Scripts (clustering y calificación de leads)
├── estimación/                 Capturas del planning poker de HU-1 a HU-5
├── Leadfy lean canvas (1).pdf  Lean canvas del proyecto
└── README.md
```

Rama `develop`, carpeta `Demo/`:

```
Demo/
├── backend/
│   ├── Model/                  Motor: filtro duro, Nearest Neighbors, capa económica y grafos
│   │   └── data_projects/      Catálogo de 96 proyectos y datos simulados de entrenamiento
│   ├── api/                    API FastAPI: valida, traduce y delega en el motor
│   ├── scraping/               Scraper del catálogo de proyectos
│   └── dapta/                  Catálogo compacto para el prompt del agente de voz
├── frontend/
│   ├── src/                    Landing en React
│   └── public/experiencia/     Quiz interactivo estático
├── CLAUDE.md                   Guía técnica completa del motor
├── CONTRATO_FRONT.md           Contrato del formulario y de la respuesta JSON
└── README.md                   Instrucciones del demo
```

## Contacto

Para dudas sobre el proyecto, escribir a cualquier integrante del equipo a través de su perfil de GitHub:

- [diego131t-max](https://github.com/diego131t-max)
- [FigueroaCarlos](https://github.com/FigueroaCarlos)
- [BGsanti](https://github.com/BGsanti)
- [SaraCuervo](https://github.com/SaraCuervo)
