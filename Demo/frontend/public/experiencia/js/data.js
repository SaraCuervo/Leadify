// Datos estáticos: preguntas del quiz, geometría del plano, catálogo de
// proyectos y avatares. Portado literalmente desde grua-del-futuro/src/App.jsx
// (mismos campos, mismo orden, mismas opciones) — la única pieza nueva es GENDERS.
(function () {
  'use strict';

  // EL ORDEN NO ES ARBITRARIO, y tiene una regla dura y una decision de
  // producto.
  //
  // LA REGLA DURA ES SOBRE LA ULTIMA. El plano se cierra al contestar la 6.a
  // pregunta (`cierran=6` en tools/analizar_planos.py) porque la 7.a salta a
  // resultados y lo que revelara no lo veria nadie. Asi que la ultima tiene que
  // ser la que MENOS mueva el plano, o se veria cambiar la recomendacion sin
  // tiempo de redibujarla. Medido sobre 600 quices al azar, cuanto mueve el
  // plano cada una: ingresos 69 %, habitaciones 66 %, tipo 51 %, zona 45 %,
  // personas 16 %, entorno 7 %, edad 3 %. Por eso `edad` sigue de ultima.
  //
  // LA DECISION DE PRODUCTO ES QUE `zona` VA PRIMERA. Antes iba 5.a, detras de
  // capacidad de compra y necesidad, ordenando de lo que mas pesa en el score a
  // lo que menos. Se movio porque es la unica pregunta que la persona ya trae
  // contestada de casa —nadie empieza a buscar vivienda sin una idea de donde
  // quiere vivir— y porque es la que da la pantalla de entrada: el mapa de
  // Bogota ocupando el lienzo, en vez de un plano todavia vacio. Ver la llave
  // `escena` de esa pregunta.
  //
  // Lo que NO cambia por moverla: el reparto de piezas de la escena va por
  // NUMERO DE RESPUESTAS y no por posicion (ver scene.js), el contador de pasos
  // tambien, y `qListFor` no filtra nada. Lo que si cambio es la barra de
  // encaje, que ahora aparece desde la 2.a respuesta (ver matching.js).
  //
  // ERAN OCHO. La que se fue es `piso_preferido`, y es la que menos duele: era
  // la unica que NO puntuaba en nada (0 % de movimiento del plano, y ni los
  // proyectos ni las tipologias guardan en que piso esta nada). El contrato
  // del modelo tambien la da por opcional. Ver js/machea.js.
  var QUESTIONS = [
    {
      // LAS OPCIONES SON LAS 20 LOCALIDADES DE BOGOTA, Y SALEN DEL CONTRATO
      // DEL MODELO (js/machea.js), no del catálogo del tenant. Esto ES un
      // cambio: antes se derivaban del catálogo, con la lógica de "no ofrecer
      // un sitio donde no hay nada".
      //
      // Ya no vale, y el motivo es que quien recomienda es el modelo, que
      // indexa por `Localidad` 1..20 y solo conoce Bogotá. Los catálogos de las
      // cuatro constructoras son NACIONALES (Cali 19, Barranquilla, Medellín,
      // Pereira…) y, donde sí están en Bogotá, la ficha suele nombrar el barrio
      // y no la localidad ("Bella Suiza", "El Salitre", "Lagos de Torca").
      // Derivando de ahí, la respuesta no cruzaba con ningún id y el modelo
      // devolvía 400 con "Localidad debe estar entre 1 y 20".
      //
      // Se ofrecen las 20 aunque no todas tengan oferta: el contrato lo
      // permite en §4 y el modelo expande la búsqueda a las localidades
      // vecinas por su grafo de colindancia, así que nunca es un callejón sin
      // salida.
      //
      // TIPO `mapa`, Y YA NO UNA GRILLA DE 20 BOTONES. Nadie dice "quiero
      // vivir en Barrios Unidos": dice "por el Polo" o "cerca de Cedritos".
      // Ahora hay dos formas de contestar lo mismo, sincronizadas — un
      // buscador de barrios y un mapa clicable — y las dos terminan
      // guardando el NOMBRE de la localidad, que es lo que ya esperaban
      // matching.js, planta.js, recommender.js y el localidadId() de
      // machea.js. El contrato de la respuesta no cambia.
      //
      // `options` se queda vacío a propósito: las localidades salen de
      // GDF_MAPA (las 20, dibujadas sobre el mapa) y de GDF_BARRIOS (las
      // 1.256 entradas del buscador: el gazetteer mas los sectores
      // catastrales), ambos generados por tools/generar_mapa.py. El contorno
      // de los barrios va aparte, en GDF_BARRIOS_GEO.
      //
      // DOS LLAVES Y NO UNA. `escena: 'mapa'` dice que esta pregunta ocupa
      // el lienzo grande con el mapa en vez del plano armándose; `type:
      // 'zona'` dice cómo se pinta su panel. Van separadas porque son dos
      // decisiones distintas, y porque así la escena se elige por una
      // propiedad declarada y no por el ÍNDICE de la pregunta: si mañana
      // vuelve a moverse de sitio, no hay nada que ajustar.
      id: 'zona',
      escena: 'mapa',
      type: 'zona',
      title: '¿Dónde te gustaría vivir?',
      // Las tres formas de contestar, en el orden en que aparecen en pantalla.
      // El lugar cercano se nombra explícitamente porque es lo que no se
      // espera: quien no se sabe los barrios da por hecho que no puede
      // contestar, y se va con lo primero que encuentre.
      sub: 'Busca tu barrio, un lugar cercano, o tócalo en el mapa.',
      options: [],
    },
    {
      id: 'tipo',
      title: '¿Qué tipo de vivienda buscas?',
      sub: 'Esto define a qué proyectos y subsidios puedes acceder.',
      cols: 1,
      options: [
        { v: 'VIS', label: 'VIS', hint: 'Vivienda de interés social · aplica subsidio' },
        { v: 'No VIS', label: 'No VIS', hint: 'Financiación flexible · sin subsidio' },
      ],
    },
    {
      id: 'ingresos',
      title: '¿Cuánto suman los ingresos de tu hogar?',
      sub: 'Esto define a qué proyectos y subsidios puedes acceder.',
      cols: 1,
      options: [
        // Las cifras salen del SMMLV que usa js/simulador.js (SUPUESTOS.smmlv,
        // 2026): moverlo allá obliga a rehacer estas pistas.
        { v: '≤2 SMMLV', label: 'Hasta 2 SMMLV', hint: '≈ hasta $3.5M al mes' },
        { v: '2–4 SMMLV', label: '2 a 4 SMMLV', hint: '≈ $3.5M – $7.0M' },
        { v: '4–8 SMMLV', label: '4 a 8 SMMLV', hint: '≈ $7.0M – $14.0M' },
        { v: '8+ SMMLV', label: 'Más de 8 SMMLV', hint: '≈ más de $14.0M' },
      ],
    },
    {
      id: 'personas',
      title: '¿Cuántas personas tienes a cargo?',
      sub: 'Cuenta a quienes dependen económicamente de ti.',
      cols: 5,
      options: [
        { v: '0', label: '0' },
        { v: '1', label: '1' },
        { v: '2', label: '2' },
        { v: '3', label: '3' },
        { v: '4+', label: '4+' },
      ],
    },
    {
      id: 'habitaciones',
      title: '¿Cuántas habitaciones necesitas?',
      sub: 'Así ajustamos el tamaño de tu hogar.',
      cols: 3,
      options: [
        { v: '1', label: '1' },
        { v: '2', label: '2' },
        { v: '3+', label: '3+' },
      ],
    },
    // `entorno_deseado` es OPCIONAL en el contrato del modelo, pero se
    // pregunta a proposito: alli declaran que vale el 20 % del score, y sin
    // ella todas las amenidades pesan igual y el ranking pierde precision.
    {
      id: 'entorno_deseado',
      title: '¿Buscas algo en particular del entorno?',
      sub: 'Opcional — elige todas las que apliquen.',
      type: 'multiselect',
      // ⚠️ Los `v` son las etiquetas EXACTAS que espera el backend y viajan tal
      // cual en `entorno_deseado` (ver js/leads.js). No son slugs nuestros: se
      // respetan sus erratas a propósito — "gymnasio" con y, "cancha e padel"
      // (no "de"), "zona de lavanderia" sin tilde, "zona kid" en singular. Una
      // letra distinta y el backend deja de cruzarlas, en silencio.
      // Esta misma lista está DUPLICADA en tools/scrape_proyectos.py
      // (VOCABULARIO, que tools/generar_seed_backend.py reusa); si cambia una,
      // cambia la otra. "cancha multiple" se sumó tras revisar los 31
      // proyectos reales: "Cancha múltiple", "Cancha fútbol 5" y "Zona sport
      // con cancha múltiple" no encajaban en ninguna de las 25 claves
      // originales (la única cancha del vocabulario era "cancha e padel",
      // específica de pádel).
      // El `label` sí es libre: es solo lo que ve el usuario.
      options: [
        { v: 'lobby', label: 'Lobby' },
        { v: 'piscina', label: 'Piscina' },
        { v: 'zona de lavanderia', label: 'Zona de lavandería' },
        { v: 'zona bbq', label: 'Zona BBQ' },
        { v: 'zona pet', label: 'Zona pet' },
        { v: 'zona kid', label: 'Zona kids' },
        { v: 'locales comerciales', label: 'Locales comerciales' },
        { v: 'zona fitness', label: 'Zona fitness' },
        { v: 'salon social', label: 'Salón social' },
        { v: 'spa mascotas', label: 'Spa mascotas' },
        { v: 'zona cool', label: 'Zona cool' },
        { v: 'zona cine', label: 'Zona cine' },
        { v: 'coworking', label: 'Coworking' },
        { v: 'sala vip', label: 'Sala VIP' },
        { v: 'zona cafe', label: 'Zona café' },
        { v: 'gymnasio', label: 'Gimnasio' },
        { v: 'parqueadero', label: 'Parqueadero' },
        { v: 'zona verde', label: 'Zona verde' },
        { v: 'parque', label: 'Parque' },
        { v: 'sala de juegos', label: 'Sala de juegos' },
        { v: 'pista de trote', label: 'Pista de trote' },
        { v: 'voleibol playa', label: 'Voleibol playa' },
        { v: 'cancha e padel', label: 'Cancha de pádel' },
        { v: 'taller de bicicletas', label: 'Taller de bicicletas' },
        { v: 'sauna', label: 'Sauna' },
        { v: 'cancha multiple', label: 'Cancha múltiple' },
      ],
    },
    {
      // VA DE ULTIMA A PROPOSITO: es la pregunta que menos mueve el plano
      // (3 % de las veces) y la que menos pesa en el match — `FACTOR_EDAD` en
      // matching.js solo corre el techo de precio, y es un SUPUESTO sin
      // verificar. Contestarla salta a resultados, asi que cualquier pregunta
      // de mas peso aqui cambiaria la recomendacion sin que la escena llegue
      // a redibujar el plano.
      //
      // Entero exacto (no rango): el contrato de leads con el backend
      // (SenalBowl, ver js/leads.js) pide `edad` como number, no un bucket.
      // quiz() en templates.js renderiza un input numérico para q.type
      // === 'number' en vez de la grilla de botones de siempre.
      id: 'edad',
      title: '¿Cuántos años tienes?',
      sub: 'Algunos proyectos tienen condiciones especiales según tu edad.',
      type: 'number',
      min: 18,
      max: 99,
      placeholder: 'Ej: 31',
    },
  ];

  // NOTA: aquí vivían ROOM_GEO (geometría fija de la planta) y FURN (muebles).
  // Se fueron cuando el quiz pasó a armar el PLANO REAL de un apartamento del
  // catálogo: ya no se dibujan cuartos ni muebles, se recortan piezas de la
  // imagen que publica la ficha. Ver js/planta.js y js/planos.js.

  // Vocabulario fijo de amenidades/zonas comunales — icono (SVG inline,
  // 24x24, stroke=currentColor) + etiqueta por categoría. `PROJECTS[].amenities`
  // solo usa estas 9 claves (ver docs/proyectos-amenidades.md para el mapeo
  // desde el texto real de cada página de proyecto a estas categorías).
  var AMENITIES = {
    porteria: { label: 'Portería con lobby', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21V9l8-6 8 6v12"/><path d="M9 21v-6h6v6"/></svg>' },
    cancha: { label: 'Cancha múltiple', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18M5.6 5.6c3 3 3 9.8 0 12.8M18.4 5.6c-3 3-3 9.8 0 12.8"/></svg>' },
    recreativa: { label: 'Zona recreativa', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 7 9h3l-4 6h4v7h4v-7h4l-4-6h3z"/></svg>' },
    biosaludable: { label: 'Parque biosaludable', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 6.5l11 11"/><rect x="2" y="9" width="4" height="6" rx="1"/><rect x="18" y="9" width="4" height="6" rx="1"/><path d="M6 12h2M16 12h2"/></svg>' },
    infantil: { label: 'Parque infantil', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4v16M20 4v16M4 4h16"/><path d="M9 8v6"/><circle cx="9" cy="15.4" r="1.4" fill="currentColor" stroke="none"/><path d="M15 8v8"/><circle cx="15" cy="17.4" r="1.4" fill="currentColor" stroke="none"/></svg>' },
    salon: { label: 'Salón social', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3"/><path d="M3 21v-2a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v2"/><circle cx="17.5" cy="9" r="2.3"/><path d="M15.8 21v-1.6a3.3 3.3 0 0 1 4.9 0V21"/></svg>' },
    gimnasio: { label: 'Gimnasio', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8v8M20 8v8M2 10.5v3M22 10.5v3M6 12h12"/></svg>' },
    piscina: { label: 'Piscina', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8c1.5 1.5 3 1.5 4.5 0S9.5 6.5 11 8s3 1.5 4.5 0 3-1.5 4.5 0"/><path d="M2 14c1.5 1.5 3 1.5 4.5 0s3-1.5 4.5 0 3 1.5 4.5 0 3-1.5 4.5 0"/><path d="M2 20c1.5 1.5 3 1.5 4.5 0s3-1.5 4.5 0 3 1.5 4.5 0 3-1.5 4.5 0"/></svg>' },
    parqueadero: { label: 'Parqueadero visitantes', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 16V8h4a3 3 0 0 1 0 6H9"/></svg>' },
  };

  // NO HAY CATALOGO DE RESPALDO, y es a proposito.
  //
  // Aqui vivian 26 proyectos de Colsubsidio escritos a mano, por si
  // `tenants/<slug>/proyectos.js` no cargaba. Ya no tiene sentido: el catalogo
  // SIEMPRE viene del tenant (lo genera plataforma/motor/generar.py), y un
  // respaldo de otra constructora seria peor que una lista vacia — la app se
  // veria llena de proyectos que no son de quien esta mirando la demo.
  //
  // Si el tenant no carga, la lista queda vacia y se ve que falta, que es la
  // unica lectura correcta.
  var PROJECTS_RESPALDO = [];

  // (La tabla de cercanía entre MUNICIPIOS se eliminó: la demo es solo de
  // Bogotá y la cercanía que importa ahora es entre LOCALIDADES, que llega
  // ya calculada de los límites oficiales en GDF_LOCALIDADES_VECINAS.)

  // Selección de personaje: puramente cosmético (carné + marcador en la
  // escena). No entra en computeLeadQualification — el PDF del hackathon
  // marca el género como variable opcional de bajo valor de negocio.
  var GENDERS = [
    { v: 'f', label: 'Constructora', emoji: '👷‍♀️' },
    { v: 'm', label: 'Constructor', emoji: '👷‍♂️' },
    { v: 'x', label: 'Sin especificar', emoji: '👷' },
  ];

  // El catalogo lo genera plataforma/motor/generar.py en
  // tenants/<slug>/proyectos.js, que index.html carga ANTES que este archivo.
  var PROJECTS = window.GDF_PROYECTOS && window.GDF_PROYECTOS.length
    ? window.GDF_PROYECTOS
    : PROJECTS_RESPALDO;

  // Las 20 localidades del contrato del modelo (ver LOCALIDADES en
  // js/machea.js, que es la única copia de esa tabla). Se ordenan por cuántos
  // proyectos del catálogo caen en cada una, para que las que sí tienen oferta
  // salgan primero — pero se ofrecen TODAS, porque el modelo sabe expandir a
  // las vecinas y el catálogo del tenant no es el suyo.
  //
  // Ojo con el orden de carga: machea.js va DESPUÉS de data.js en index.html,
  // así que aquí no se puede leer `GDF.machea`. La lista va en este archivo y
  // machea.js la traduce a ids.
  var LOCALIDADES_BOGOTA = [
    'Usaquén', 'Chapinero', 'Santa Fe', 'San Cristóbal', 'Usme',
    'Tunjuelito', 'Bosa', 'Kennedy', 'Fontibón', 'Engativá',
    'Suba', 'Barrios Unidos', 'Teusaquillo', 'Los Mártires', 'Antonio Nariño',
    'Puente Aranda', 'La Candelaria', 'Rafael Uribe Uribe', 'Ciudad Bolívar',
    'Sumapaz',
  ];

  // CUANTOS PROYECTOS TIENE CADA LOCALIDAD. Antes esto ordenaba los 20
  // botones de la pregunta `zona`, de más oferta a menos. Ya no hay botones
  // —hay un mapa—, pero el conteo sigue haciendo falta: es lo que decide qué
  // zonas se pintan atenuadas.
  //
  // Seis localidades están hoy en cero (Tunjuelito, Antonio Nariño, La
  // Candelaria, Rafael Uribe Uribe, Ciudad Bolívar y Sumapaz) y AUN ASÍ se
  // pueden elegir: el modelo expande a las vecinas por su grafo, así que
  // devuelve resultados igual. Se marcan, no se bloquean.
  var OFERTA = {};
  LOCALIDADES_BOGOTA.forEach(function (n) {
    OFERTA[n] = 0;
  });
  PROJECTS.forEach(function (p) {
    if (p.localidad && OFERTA[p.localidad] !== undefined) OFERTA[p.localidad] += 1;
  });

  // Localidades que colindan, calculadas de los límites oficiales del Distrito
  // por tools/scrape_proyectos.py (ver GDF_LOCALIDADES_VECINAS en
  // js/proyectos.js). matching.js las usa para no castigar a un proyecto que
  // queda en la localidad de al lado. Si el archivo generado no cargó, queda
  // un objeto vacío y el scoring simplemente trata todo como "lejos".
  var VECINAS = window.GDF_LOCALIDADES_VECINAS || {};

  window.GDF = window.GDF || {};
  window.GDF.data = {
    QUESTIONS: QUESTIONS,
    PROJECTS: PROJECTS,
    AMENITIES: AMENITIES,
    VECINAS: VECINAS,
    GENDERS: GENDERS,
    LOCALIDADES: LOCALIDADES_BOGOTA,
    OFERTA: OFERTA,
  };
})();
