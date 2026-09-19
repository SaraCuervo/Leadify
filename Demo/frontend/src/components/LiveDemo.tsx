import { AnimatePresence, motion } from "framer-motion";
import { Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Reveal } from "./Reveal";

/**
 * AQUI HABIA UN FORMULARIO Y AHORA HAY UN IFRAME.
 *
 * El modal montaba `MacheaForm`: diez campos apilados (nombre, telefono, tipo,
 * salario, personas, edad, localidad, habitaciones, afiliado, zonas) que
 * llamaban a `/api/recomendar` y pintaban el Top 3. Se cambio por la
 * experiencia completa —las 7 preguntas que van ARMANDO el plano de un
 * apartamento pieza a pieza mientras se responde—, que es la parte que
 * distingue a Machea de cualquier otro formulario.
 *
 * POR QUE UN IFRAME Y NO UN PORTE A REACT. La experiencia son ~7.400 lineas de
 * JS vanilla y ~4.700 de CSS, todo bajo `.gdf-*`. Dos cosas lo hacen inviable
 * de traer aqui dentro:
 *   1. Su arranque usa `document.write` para inyectar los archivos del tenant
 *      EN EL PUNTO DEL PARSER. Bajo `defer` o dentro de un `DOMContentLoaded`
 *      —que es lo unico que React puede ofrecerle— borra el documento entero.
 *   2. El preflight de Tailwind y esas 4.700 lineas de CSS global se pisarian.
 *      Su propio repo ya documenta esa colision al reves, con los bundles de
 *      Next de otra pagina.
 * El iframe da aislamiento total de CSS y de parser, y no cuesta ni una linea
 * de reescritura.
 *
 * SE FUE TAMBIEN LA LLAMADA DE MANUELA, que colgaba del final de aquel
 * formulario: el recorrido ahora cierra dentro de la experiencia (resultado y
 * confirmacion son suyos). `src/lib/api.ts` NO se toca — lo sigue usando
 * `Benefits.tsx`.
 */

// LA EXPERIENCIA VIAJA DENTRO DE ESTA MISMA WEB, en `public/experiencia/`, y
// por eso la ruta es RELATIVA. Vite sirve `public/` tal cual, asi que en el
// despliegue queda en el mismo origen que la landing: un solo proyecto de
// Vercel, sin variable de entorno que configurar y sin un segundo dominio que
// pueda caducar por su cuenta.
//
// Antes apuntaba a `http://localhost:7000`, que es donde la sirve el repo del
// front en desarrollo. Publicado, eso resolvia contra la maquina DEL VISITANTE
// y el modal salia en blanco sin ningun error que lo delatara.
//
// Los dos parametros importan:
//   `marca=machea` -> el tenant NEUTRO. Los otros cuatro son de una
//      constructora y filtrarian el catalogo a la suya; este va con la clave
//      vacia, que es lo que hace que el motor puntue sobre los 96 y salgan
//      las cuatro marcas juntas, como corresponde a la demo de Machea.
//   `embed=1` -> entra directo a la escarapela (sin el splash, que dentro de
//      un modal es una puerta detras de otra) y deja la casa a la DERECHA.
//
// La copia publicada va con `SIN_BACKEND: true`: calcula el Top 6 con el motor
// de reglas de matching.js en vez de llamar al modelo, porque ahi fuera no hay
// ningun :8100 al que llamar. La propia tarjeta lo dice.
// SE NOMBRA `index.html`, no el directorio. `/experiencia/` funciona publicado
// —un servidor de estaticos resuelve el indice de la carpeta— pero NO en el
// servidor de desarrollo: Vite trata una ruta sin extension como navegacion de
// la SPA y devuelve el `index.html` de la landing. El iframe cargaba entonces
// la propia landing dentro de si misma, con 200 y sin un solo error, y el
// formulario simplemente no aparecia. Nombrar el archivo sirve lo mismo en los
// dos sitios.
const EXPERIENCIA_URL =
  import.meta.env.VITE_EXPERIENCIA_URL ??
  "/experiencia/index.html?marca=machea&embed=1";

export function LiveDemo() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <section className="relative overflow-hidden bg-beige py-24">
      <div className="dot-field-a pointer-events-none absolute inset-0 -z-10 opacity-40" aria-hidden="true" />
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
        <Reveal>
          <motion.div className="relative overflow-hidden rounded-[32px] border border-navy/10 bg-white p-10 shadow-soft md:p-16">

            <motion.div
              aria-hidden="true"
              className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-coral/10 blur-3xl"
              animate={{ scale: [1, 1.15, 1] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            />
            <motion.div
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
              className="mx-auto mb-6 grid h-16 w-16 place-items-center rounded-2xl bg-coral/10 text-coral"
            >
              <Sparkles size={28} />
            </motion.div>

            <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-coral/20 bg-coral/5 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-coral">
              Machea · Demo en vivo
            </p>
            <h2 className="text-3xl font-extrabold text-navy md:text-5xl">Arma tu match ideal.</h2>
            {/* Ya no se promete la llamada de Manuela: se fue con el formulario
                que la ofrecia. Lo que se promete ahora es lo que de verdad
                pasa al pulsar — el plano montandose mientras respondes. */}
            <p className="mx-auto mt-4 max-w-lg text-lg text-navy/70">
              Responde siete preguntas y mira cómo se levanta el plano de tu apartamento, pieza a pieza, mientras
              lo haces. Al final, lo que nuestro motor te recomienda sobre el catálogo real.
            </p>

            <motion.button
              type="button"
              onClick={() => setOpen(true)}
              whileHover={{ y: -3, boxShadow: "0 20px 40px -12px rgba(255,98,89,0.6)" }}
              whileTap={{ scale: 0.96 }}
              transition={{ type: "spring", stiffness: 400, damping: 20 }}
              className="mt-8 inline-flex items-center gap-2 rounded-full bg-coral px-8 py-4 text-lg font-bold text-white shadow-coral"
            >
              ¡Empezar mi match! <Sparkles size={18} />
            </motion.button>

            <p className="mt-4 flex items-center justify-center gap-1.5 text-sm font-medium text-navy/40">
              ⏱ 2 minutos · sin compromiso
            </p>
          </motion.div>
        </Reveal>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[70] flex items-center justify-center p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="absolute inset-0 bg-gradient-to-br from-white/90 via-beige/85 to-coral/20 backdrop-blur-md"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            {/*
              LA CAJA CRECIO, y no es cosmetico. La experiencia parte el
              escritorio en dos columnas a partir de 900px; con el `max-w-5xl`
              de antes (1024px) la columna de la casa se quedaba en ~440px y el
              plano salia diminuto. Con `max-w-7xl` respira.

              Y se le quita el padding y el `overflow-y-auto`: el iframe ocupa
              la caja entera y scrollea por dentro. Dejar los dos daba dos
              barras de scroll, una dentro de la otra.
            */}
            <motion.div
              initial={{ opacity: 0, scale: 0.92, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ type: "spring", stiffness: 300, damping: 28 }}
              className="relative flex h-[88vh] w-full max-w-7xl flex-col overflow-hidden rounded-[32px] border border-navy/10 bg-white shadow-2xl"
            >
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Cerrar"
                className="absolute right-5 top-4 z-10 grid h-9 w-9 place-items-center rounded-full border border-navy/10 bg-white text-navy/60 hover:text-coral"
              >
                <X size={18} />
              </button>

              {/* Cabecera al minimo: cada pixel que se lleve aqui se lo quita
                  al plano, que es lo que hay que ver. */}
              <div className="shrink-0 border-b border-navy/10 px-6 py-3 text-center">
                <p className="text-xs font-bold uppercase tracking-[0.15em] text-coral">Pruébalo tú mismo</p>
                <h3 className="text-lg font-extrabold text-navy md:text-xl">El motor real, en vivo.</h3>
              </div>

              {/* `min-h-0` es obligatorio: sin el, un hijo flex no baja de su
                  alto de contenido y el iframe desbordaria la caja. */}
              <iframe
                src={EXPERIENCIA_URL}
                title="Machea · arma tu match"
                className="min-h-0 w-full flex-1 border-0"
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
