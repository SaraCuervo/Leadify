import { defineConfig } from 'vite'

// Esta copia del repo NO compila nada: la landing de React se borro y lo unico
// que queda es `index.html` (un cascaron) mas `public/experiencia/`, que Vite
// sirve tal cual sin tocarlo. Por eso se fueron los plugins de React y de
// Tailwind: no hay JSX que transformar ni clases que generar, y dejarlos
// pasaria el bundle vanilla por un pipeline que no lo necesita.
//
// `strictPort` se queda: si 5173 esta ocupado, FALLA en vez de moverse solo,
// para que la URL de la demo sea siempre la misma.
export default defineConfig({
  server: {
    port: process.env.PORT ? Number(process.env.PORT) : 5173,
    strictPort: true,
  },
})
