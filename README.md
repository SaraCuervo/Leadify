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

El asesor recibe al lead con la cita ya puesta, no solo con un dato de contacto. El modelo de negocio completo está en el [lean canvas](Docs/lean-canvas.pdf).

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

**Frontend (formulario interactivo)**

- JavaScript sin framework: el quiz son ~7.400 líneas de JS y ~5.000 de CSS propios
- Vite: servidor de desarrollo y empaquetado
- Leaflet: el mapa de la pregunta de ubicación
- Photon (OpenStreetMap): búsqueda de lugares

## Requisitos

- Python 3.11 o superior
- Node.js 20.19 o superior, con npm (solo para el formulario)
- Git
- Un navegador actualizado
- Opcional: una cuenta y un flow de Dapta para las llamadas reales

## Estructura del proyecto

```
Leadify/
├── Demo/                       EL PROYECTO
│   ├── backend/
│   │   ├── Model/              Motor: filtro duro, Nearest Neighbors, capa económica y grafos
│   │   │   └── data_projects/  Catálogo de 96 proyectos y datos simulados de entrenamiento
│   │   ├── api/                API FastAPI: valida, traduce y delega en el motor
│   │   ├── scraping/           Scraper del catálogo de proyectos
│   │   └── dapta/              Catálogo compacto para el prompt del agente de voz
│   ├── frontend/
│   │   ├── index.html          Cascarón que sirve el formulario a pantalla completa
│   │   └── public/experiencia/ El formulario: las siete preguntas y el plano que se arma
│   ├── render.yaml             Despliegue de la API
│   └── README.md               Instrucciones del demo
├── Database/                   Qué datos usa el motor y dónde viven
├── Docs/
│   ├── Dailys/                 Actas de los dailys (Daily1 a Daily5)
│   └── lean-canvas.pdf         Lean canvas del proyecto
├── Graficas/                   Gráficas de las métricas del lean canvas
├── Script/                     Qué scripts hay y cómo se corren
├── estimación/                 Capturas del planning poker de HU-1 a HU-5
└── README.md
```

La rama `develop` conserva una copia anterior del demo, con la landing de React
que esta versión ya no tiene.
