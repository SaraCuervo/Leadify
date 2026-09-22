// Configuración de entorno para este front vanilla (sin build step, sin
// bundler => sin process.env ni import.meta.env nativos). Es el único sitio
// donde se edita a mano a dónde apunta la app.
//
// Se carga ANTES que js/leadify.js en index.html.
window.GDF_CONFIG = {
  // El servicio del modelo de recomendación (Leadify). Ver
  // integracion/servicio_leadify.py: envuelve `recomendar()` en HTTP y además
  // resuelve las fotos de cada proyecto por su `id_proyecto`.
  //
  // Si el modelo no está levantado, integracion/fake_leadify.py habla el mismo
  // contrato y recomienda sobre el MISMO catálogo real (los 96 proyectos de
  // Bogotá) con sus fotos. No es el modelo —son reglas— y lo dice en el campo
  // `motor` de cada respuesta, que sale por consola:
  //   python integracion/fake_leadify.py     -> escucha en el mismo puerto
  //
  // En localhost apunta al modelo corriendo en tu máquina (`uvicorn
  // api.app:app --port 8100` desde Demo/backend); en cualquier otro host
  // (Vercel) apunta al servicio desplegado en Render. Mismo patrón que
  // DAPTA_LLAMADA_BASE de más abajo: son el MISMO backend (Demo/backend/api),
  // así que las dos constantes resuelven igual — se dejan separadas porque
  // cada una documenta un propósito distinto, no dos servicios distintos.
  Leadify_BASE:
    location.hostname === 'localhost' || location.hostname === '127.0.0.1'
      ? 'http://localhost:8100'
      : 'https://leadify-gmqj.onrender.com',

  // De dónde salen los proyectos recomendados (ver js/recommender.js):
  //   'leadify' -> las 7 respuestas viajan al modelo, que devuelve el Top 6 con
  //               su compatibilidad y las fotos de cada proyecto.
  //   'local'  -> solo el motor de reglas de js/matching.js, sin tocar la red.
  //               Es el respaldo cuando el servicio no responde, y se marca
  //               siempre como aproximado para no engañar a nadie.
  RECOMMENDER: 'leadify',

  // MODO DEMO SIN RED. En true la app no llama al modelo en ningún momento y
  // las recomendaciones salen del motor local. Existe para la versión de UN
  // SOLO ARCHIVO (tools/empaquetar_demo.py), pensada para compartir por link:
  // ahí la política de seguridad del visor bloquea cualquier petición externa.
  //
  // El modelo YA está desplegado (leadify-gmqj.onrender.com), así que la
  // publicada conecta con él de verdad. Si el servicio gratuito de Render
  // está dormido, la primera visita del día puede tardar 30-60 segundos en
  // responder mientras despierta — no es un error, es la condición del plan
  // gratuito. El motor local de respaldo (RECOMMENDER 'local', ver
  // js/recommender.js) sigue existiendo como red de seguridad si el servicio
  // no responde en absoluto, no como modo por defecto.
  SIN_BACKEND: false,

  // El mismo backend de Leadify (Demo/backend/api/app.py) — apunta al mismo
  // sitio que Leadify_BASE, en apariencia redundante, pero el flag
  // SIN_BACKEND lo trata distinto: con SIN_BACKEND:true el cálculo de
  // recomendaciones se apaga y cae al motor local, pero la llamada de Manuela
  // SIGUE yendo al backend igual, porque necesita la API key de Dapta y esa
  // nunca puede viajar al cliente. Antes de este flujo, este apuntaba a
  // machea.onrender.com (otro proyecto, otra cuenta de Dapta); se consolidó
  // aquí porque el flujo de Dapta ya se creó específicamente para Leadify.
  DAPTA_LLAMADA_BASE:
    location.hostname === 'localhost' || location.hostname === '127.0.0.1'
      ? 'http://localhost:8100'
      : 'https://leadify-gmqj.onrender.com',

  // El número al que escribe el botón "WhatsApp" de la tarjeta elegida, en
  // formato internacional y sin "+" (57 + celular de 10 dígitos). Vacío, el
  // enlace abre WhatsApp con el mensaje listo y la persona elige el contacto.
  WHATSAPP_NUMERO: '',

  // La base de datos (Postgres en Supabase). Ver js/datos.js.
  //
  // ESTA CLAVE VA AQUI A PROPOSITO Y NO ES UN DESCUIDO: es la clave
  // *publicable*, pensada para viajar al navegador, y por si sola no abre
  // nada. Las tablas estan cerradas y solo se exponen cuatro funciones del
  // lado del servidor; la de lectura exige cedula Y telefono. Quien tenga esta
  // clave puede llamar a esas cuatro funciones, nada mas -- no puede listar
  // leads ni leer una fila sin conocer los dos datos de esa persona.
  //
  // La que NO puede aparecer nunca aqui es la `service_role`, que si salta
  // todas las restricciones. Esa vive solo en el panel de Supabase.
  //
  // Vacias, la app funciona igual pero sin guardar nada (ver `activo()` en
  // js/datos.js): la falta de un servicio opcional no es un fallo.
  SUPABASE_URL: 'https://jovuwfqmxcxectjwmeqq.supabase.co',
  SUPABASE_KEY: 'sb_publishable_LTtDM90Kub2pNI7pjr6iuA_U_dQQMAi',
};
