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
| Juan Diego Ortiz Guerrero | DevOps Engineer y Configuration Manager | [diego131t-max](https://github.com/diego131t-max) |
| Carlos Andrés Figueroa Vega | Scrum Master | [FigueroaCarlos](https://github.com/FigueroaCarlos) |
| Santiago Díaz Sabogal | Quality Assurance Lead | [santiagodiazsabogal](https://github.com/santiagodiazsabogal) |
| Sara Cuervo Avendaño | Product Owner y Sprint Planner | [SaraCuervo](https://github.com/SaraCuervo) |

## Tecnologías

**Backend (motor de recomendación)**

- Python 3.11
- FastAPI y Uvicorn: capa HTTP
- scikit-learn y NumPy: Nearest Neighbors sobre el perfil del comprador
- Requests, BeautifulSoup y lxml: scraper del catálogo de proyectos
- Dapta: agente de voz que hace la llamada de calificación y agendamiento

**Base de datos (leads)**

- PostgreSQL, gestionado en Supabase
- PL/pgSQL: las cuatro funciones que exponen la única API que ve el
  navegador (ver [`Database/esquema/`](Database/esquema/))

**Frontend (formulario interactivo)**

- JavaScript sin framework: el quiz son ~7.400 líneas de JS y ~5.000 de CSS propios
- three.js: el plano del apartamento en 3D (`Demo/frontend/public/experiencia/js/plano3d/`)
- Vite: servidor de desarrollo y empaquetado
- Leaflet: el mapa de la pregunta de ubicación
- Photon (OpenStreetMap): búsqueda de lugares

## Instalación y ejecución

```bash
git clone https://github.com/SaraCuervo/Leadify.git
cd Leadify/Demo
```

### El formulario interactivo

Es lo que ve el comprador: siete preguntas y un plano que se arma a medida que responde. No necesita el backend.

```bash
cd frontend
npm install
npm run dev
```

Abrir <http://localhost:5173>. Si el puerto está ocupado, falla en vez de moverse a otro, para que la URL sea siempre la misma.

Por defecto el formulario corre con `SIN_BACKEND: true` (en `public/experiencia/js/config.js`): recomienda con el motor de reglas del navegador y no llama a la API.

### El motor de recomendación (opcional)

Es el modelo de Python: filtro duro, Nearest Neighbors y capa económica. Se puede usar sin levantar nada:

```bash
cd backend
pip install -r requirements.txt
python main.py --usuario Model/data_projects/usuario_ejemplo.json
```

Para exponerlo por HTTP con FastAPI:

```bash
uvicorn api.app:app --port 8000
```

Para comprobar que el motor funciona (carga los datos, recomienda y cumple el contrato del formulario):

```bash
python pruebas/prueba_humo.py
```

Debe terminar con "Todo en orden". Todos los comandos del backend se corren desde `Demo/backend/`.

### Llamada con Dapta (opcional)

El endpoint `POST /api/llamar` dispara la llamada automática. Sin configurar responde en modo simulado (`mock_enqueued`) y no llama a nadie. Para conectarlo a un flow real, definir la variable de entorno antes de levantar la API:

```bash
export DAPTA_FLOW_WEBHOOK_URL="https://..."
```

## Requisitos

- Python 3.11 o superior
- Node.js 20.19 o superior, con npm (solo para el formulario)
- Git
- Un navegador actualizado
- Opcional: una cuenta y un flow de Dapta para las llamadas reales

## Estructura del proyecto

```
Leadify/
├── Demo/                             EL PROYECTO
│   ├── backend/
│   │   ├── Model/                    Motor: filtro duro, Nearest Neighbors, capa económica y grafos
│   │   │   ├── data_projects/        Catálogo de 96 proyectos y datos simulados de entrenamiento
│   │   │   └── simulacion/           Generación de clientes e historial, evaluación y calibración
│   │   ├── api/                      API FastAPI: valida, traduce y delega en el motor
│   │   ├── scraping/                 Scraper del catálogo de proyectos
│   │   ├── dapta/                    Catálogo compacto para el prompt del agente de voz
│   │   ├── pruebas/                  Prueba de humo del motor
│   │   ├── main.py                   Lanzador de consola del motor
│   │   └── requirements.txt          Dependencias de Python
│   ├── frontend/
│   │   ├── index.html                Cascarón que sirve el formulario a pantalla completa
│   │   └── public/experiencia/       El formulario: siete preguntas y el plano que se arma
│   │       ├── js/ · css/            Lógica y estilos propios, sin framework
│   │       ├── tenants/              Una carpeta por marca (leadify, amarilo, colsubsidio, ...)
│   │       └── tools/                Utilidades para enriquecer los catálogos de las marcas
│   └── render.yaml                   Despliegue de la API
├── Database/                         Qué datos usa el motor y dónde viven
├── Docs/
│   ├── Dailys/                       Actas de los dailys (Daily1 a Daily5)
│   ├── Mockups/                      Capturas de las pantallas del formulario
│   ├── Guia-de-Usuario.md            Cómo usar el formulario, paso a paso
│   └── lean-canvas.pdf               Lean canvas del proyecto
├── Script/                           Qué scripts hay y cómo se corren, más tres verificaciones
├── estimación/                       Capturas del planning poker de HU-1 a HU-5
└── README.md
```

## Contacto

Para dudas sobre el proyecto, escribir a cualquier integrante del equipo a través de su perfil de GitHub:

- [diego131t-max](https://github.com/diego131t-max) — Juan Diego Ortiz Guerrero
- [FigueroaCarlos](https://github.com/FigueroaCarlos) — Carlos Andrés Figueroa Vega
- [santiagodiazsabogal](https://github.com/santiagodiazsabogal) — Santiago Díaz Sabogal
- [SaraCuervo](https://github.com/SaraCuervo) — Sara Cuervo Avendaño
