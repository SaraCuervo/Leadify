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
  Leadify_BASE: 'http://localhost:8100',

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
  SIN_BACKEND: true,

  // El backend de Leadify (api.py, ver el repo de la landing), NO el mismo
  // servicio que Leadify_BASE. Este SÍ corre siempre, incluso con
  // SIN_BACKEND:true — ese flag solo apaga el cálculo de recomendaciones, no
  // la llamada de Manuela, que no puede hacerse desde el navegador porque
  // necesita la API key de Dapta, y esa nunca puede viajar al cliente.
  DAPTA_LLAMADA_BASE: 'https://machea.onrender.com',

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
