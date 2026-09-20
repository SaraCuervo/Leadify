# frontend — el formulario

Esta mitad del repo sirve **una sola cosa**: la experiencia de 7 preguntas de
`public/experiencia/`, a pantalla completa.

Aquí hubo una landing (React 19 + Tailwind v4 + Framer Motion, con Navbar,
Hero, FAQ, Offer y el resto) y se borró: en esta copia el formulario es todo.
Quedaron dos piezas.

| | |
|---|---|
| `index.html` | Un cascarón de ~20 líneas: un `<iframe>` a `/experiencia/index.html?marca=leadify`, a viewport completo. |
| `public/experiencia/` | **El formulario.** JS vanilla, sin build; Vite lo sirve tal cual desde `public/`. No se tocó. |

```bash
npm install
npm run dev        # :5173, falla si el puerto está ocupado (strictPort)
npm run build      # copia public/ a dist/ y minifica el cascarón
npm run preview
```

Tres cosas que no hay que deshacer sin querer:

- **`?marca=leadify`** es el tenant neutro: sin ese parámetro el bundle cae en
  `constructora-bolivar` y filtra el catálogo a una sola constructora.
- **Se nombra `index.html`**, no el directorio: en `npm run dev` una ruta sin
  extensión devuelve el cascarón, y el iframe se cargaría a sí mismo.
- **Sigue siendo un iframe** porque el quiz inyecta el tenant con
  `document.write` en el punto del parser: pasarlo por el build de Vite o
  ponerle `defer` borra el documento entero.

El backend que consume está en `../backend` (`uvicorn api.app:app --port
8000`). Ojo: la copia publicada del bundle lleva `SIN_BACKEND: true` en
`js/config.js`, así que por defecto recomienda con el motor de reglas de
`matching.js` y no llama al modelo.

La documentación completa: [GUIA_TECNICA.md §8](../../Docs/GUIA_TECNICA.md).
