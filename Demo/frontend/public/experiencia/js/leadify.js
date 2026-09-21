// Comunicación con el modelo de recomendación — contrato "Leadify v0.1".
//
// Módulo aparte, con una sola responsabilidad: TRADUCIR el estado del quiz al
// formulario que espera el modelo, y llamarlo. Igual que matching.js o
// qualification.js, no toca el DOM y state.js sigue sin hacer I/O.
//
// EL MODELO NO ES UN ENDPOINT: el contrato es `from main import recomendar`,
// una función de Python. Quien lo expone por HTTP es
// integracion/servicio_leadify.py, que además resuelve las fotos de cada
// proyecto — el contrato las deja fuera de la respuesta a propósito: viven en
// `imagenes_proyectos/<id_proyecto>/`, numeradas 01, 02… y sin decir con qué
// extensión. Para probar sin el repo del modelo está integracion/fake_leadify.py.
(function () {
  'use strict';

  // --- Las 20 localidades de Bogotá (§4 del contrato) ----------------------
  // El id NO es nuestro: es el oficial del Distrito y el que indexa el modelo.
  // Se pueden ofrecer las 20 aunque hoy solo unas cuantas tengan oferta — si el
  // usuario pide una vacía, el modelo expande la búsqueda a las localidades
  // vecinas por su grafo de colindancia y nunca devuelve lista vacía.
  var LOCALIDADES = {
    'Usaquén': 1, 'Chapinero': 2, 'Santa Fe': 3, 'San Cristóbal': 4,
    'Usme': 5, 'Tunjuelito': 6, 'Bosa': 7, 'Kennedy': 8,
    'Fontibón': 9, 'Engativá': 10, 'Suba': 11, 'Barrios Unidos': 12,
    'Teusaquillo': 13, 'Los Mártires': 14, 'Antonio Nariño': 15,
    'Puente Aranda': 16, 'La Candelaria': 17, 'Rafael Uribe Uribe': 18,
    'Ciudad Bolívar': 19, 'Sumapaz': 20,
  };

  // Marcas diacriticas de Unicode. Se construye con new RegExp para que el
  // archivo no lleve caracteres combinantes sueltos, que son invisibles en el
  // editor y se pierden con cualquier copiar/pegar.
  var RE_DIACRITICOS = new RegExp('[̀-ͯ]', 'g');

  function plano(s) {
    return String(s || '')
      .normalize('NFD')
      .replace(RE_DIACRITICOS, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }

  // Indice sin tildes: el catálogo escribe "Fontibón", pero cualquier dato que
  // venga de otra fuente puede traer "Fontibon", y una tilde no puede ser la
  // diferencia entre recomendar y no recomendar.
  var POR_NOMBRE_PLANO = {};
  Object.keys(LOCALIDADES).forEach(function (n) {
    POR_NOMBRE_PLANO[plano(n)] = LOCALIDADES[n];
  });

  function localidadId(nombre) {
    return POR_NOMBRE_PLANO[plano(nombre)] || null;
  }

  /**
   * Los ids de TODAS las zonas pedidas, sin repetir y sin nulos.
   *
   * El formulario dejó de admitir una sola: en el mapa se pueden señalar
   * varios sectores, y esos caen en localidades distintas. El modelo lo recibe
   * como lista y mide la distancia de cada proyecto a la MÁS CERCANA de todas
   * (ver `ids_localidades` y el BFS multi-origen de catalogos.py).
   *
   * `answers.zonas` es la lista de nombres; `answers.zona` es la primera, y se
   * usa de respaldo para cualquier respuesta guardada antes de que existiera
   * la selección múltiple.
   */
  function localidadIds(a) {
    var nombres = (a && a.zonas && a.zonas.length) ? a.zonas : [a && a.zona];
    var ids = [];
    nombres.forEach(function (nombre) {
      var id = localidadId(nombre);
      if (id && ids.indexOf(id) < 0) ids.push(id);
    });
    return ids;
  }

  // --- Las escalas del contrato -------------------------------------------
  // salario: 1 hasta 2 SMMLV · 2 de 2 a 4 · 3 de 4 a 8 · 4 más de 8. Las claves
  // son los `v` de la pregunta 'ingresos' en data.js.
  var SALARIO = { '≤2 SMMLV': 1, '2–4 SMMLV': 2, '4–8 SMMLV': 3, '8+ SMMLV': 4 };

  /**
   * Las zonas comunes, y aquí está el detalle que decide el 20 % del score.
   *
   * La pregunta guarda dos cosas por opción: `v` y `label`. El `v` son SLUGS
   * CON ERRATAS a propósito ('gymnasio' con y, 'cancha e padel', 'zona kid' en
   * singular, 'zona de lavanderia' sin tilde) porque así los quería el backend
   * anterior. Lo que espera el contrato de Leadify son los nombres bien
   * escritos, con tildes — y resulta que son EXACTAMENTE los `label` de la
   * pregunta: los 25, ninguno de más.
   *
   * Mandar los `v` no daría ningún error: §5 dice que una zona desconocida se
   * ignora y se reporta aparte. Simplemente anularía en silencio el 20 % del
   * score. Por eso se traduce, y por eso la traducción se lee de data.js en vez
   * de copiarse: el vocabulario ya vive duplicado y el propio repo avisa de que
   * una letra de diferencia rompe el match sin decir nada.
   */
  var ZONAS_DEL_CONTRATO = [
    'Lobby', 'Locales comerciales', 'Coworking', 'Parque',
    'Piscina', 'Zona fitness', 'Sala VIP', 'Sala de juegos',
    'Zona de lavandería', 'Salón social', 'Zona café', 'Pista de trote',
    'Zona BBQ', 'Spa mascotas', 'Gimnasio', 'Voleibol playa',
    'Zona pet', 'Zona cool', 'Parqueadero', 'Cancha de pádel',
    'Zona kids', 'Zona cine', 'Zona verde', 'Taller de bicicletas',
    'Sauna',
  ];

  function preguntaEntorno() {
    var qs = (window.GDF.data && window.GDF.data.QUESTIONS) || [];
    for (var i = 0; i < qs.length; i++) {
      if (qs[i].id === 'entorno_deseado') return qs[i];
    }
    return null;
  }

  function etiquetasDeEntorno() {
    var q = preguntaEntorno();
    var mapa = {};
    ((q && q.options) || []).forEach(function (o) {
      mapa[o.v] = o.label;
    });
    return mapa;
  }

  function zonasComunesDe(answers) {
    var elegidas = (answers && answers.entorno_deseado) || [];
    if (!elegidas.length) return null;
    var etiquetas = etiquetasDeEntorno();
    var salida = [];
    var fuera = [];
    elegidas.forEach(function (v) {
      var label = etiquetas[v] || v;
      if (ZONAS_DEL_CONTRATO.indexOf(label) > -1) salida.push(label);
      else fuera.push(label);
    });
    // La pregunta tiene una 26.ª, "Cancha múltiple", que el contrato no conoce.
    // No es un fallo nuestro: se añadió al revisar proyectos reales donde
    // "Cancha múltiple" no encajaba en ninguna de las 25. Se descarta y se
    // dice, en vez de mandarla y que el modelo la ignore en silencio.
    if (fuera.length) {
      console.warn('[GDF/leadify] fuera del vocabulario de 25, no se envían:', fuera);
    }
    return salida.length ? salida : null;
  }

  /**
   * El camino de vuelta: la etiqueta que devuelve el modelo ('Gimnasio') a la
   * clave del quiz ('gymnasio').
   *
   * Hace falta porque la tarjeta resalta con un ✓ las zonas comunes que el
   * usuario pidió, y para eso compara contra `answers.entorno_deseado`, que
   * guarda los `v`. Sin esta vuelta, `zonas_en_comun` llegaría correcta y no
   * se resaltaría ni una.
   */
  function claveDe(label) {
    var etiquetas = etiquetasDeEntorno();
    var claves = Object.keys(etiquetas);
    for (var i = 0; i < claves.length; i++) {
      if (etiquetas[claves[i]] === label) return claves[i];
    }
    return null;
  }

  // El contrato quiere un entero, sin indicativo ni espacios ni signos.
  function telefonoEntero(raw) {
    var d = String(raw || '').replace(/[^0-9]/g, '');
    // "+57 300…" llega como "57300…": el indicativo sobra y dejaría el número
    // en 12 dígitos.
    if (d.length === 12 && d.indexOf('57') === 0) d = d.slice(2);
    return d ? parseInt(d, 10) : null;
  }

  /**
   * El formulario del contrato (§3) a partir del estado del quiz.
   *
   * Las seis obligatorias salen directas de las respuestas. De las opcionales
   * se manda `zonas_comunes` (ver arriba) y los datos de contacto; `piso` va
   * fijo en 4 ("sin preferencia") porque esa pregunta se quitó del quiz: no
   * puntúa en nada, ya que ninguna constructora publica el piso por unidad.
   */
  function construirFormulario(state) {
    var a = state.answers || {};

    // El contrato exige 1..4 y el quiz ofrece 0. Quien no tiene personas a
    // cargo levantaría un ValueError y se quedaría sin recomendación, así que
    // se manda 1. Es un ajuste NUESTRO, no un dato del usuario.
    var personas = a.personas === '4+' ? 4 : parseInt(a.personas || '1', 10);
    if (!(personas >= 1)) personas = 1;

    var cuerpo = {
      nombres: (state.nombre || '').trim() || null,
      apellidos: (state.apellido || '').trim() || null,
      correo: (state.correo || '').trim() || null,
      telefono: telefonoEntero(state.telefono),

      tipo_vivienda: a.tipo === 'VIS' ? 1 : 0,
      salario: SALARIO[a.ingresos] || null,
      personas_a_cargo: personas,
      edad: parseInt(a.edad, 10) || null,
      // OJO: `Localidad` con L MAYUSCULA y sin ceros a la izquierda. Lo avisa
      // el contrato en §1, y es de los errores que no dan mensaje claro: llega
      // como dato inválido, no como campo ausente.
      //
      // VA COMO ENTERO, no como lista. Aquí decía que "el contrato admite las
      // dos formas" y no es cierto: el contrato pide un entero 1..20, e
      // `indice_localidad()` (Model/catalogos.py) acepta int, float o texto,
      // nunca una lista — con `[7]` devuelve None y el modelo responde 400:
      // "Localidad debe estar entre 1 y 20 (recibido: [7])".
      //
      // El fallo estuvo oculto porque SIN_BACKEND:true hace que las
      // recomendaciones salgan del motor local sin llegar a tocar el modelo.
      // Se descubrió al conectar el servicio de verdad.
      //
      // Si se eligen varias zonas se manda LA PRIMERA: el contrato admite una
      // sola. Que el quiz permita elegir varias y el modelo solo entienda una
      // es una diferencia de alcance a resolver en producto, no a callar aquí.
      Localidad: localidadIds(a)[0] || null,
      numero_habitaciones: a.habitaciones === '3+' ? 3 : parseInt(a.habitaciones || '1', 10),
      piso: 4,
      zonas_comunes: zonasComunesDe(a),
    };

    // La afiliación a caja solo se pregunta cuando la marca ES una caja de
    // compensación (ver pideAfiliacion() en templates.js). Con una constructora
    // privada no se pregunta, y entonces no se manda: el campo es opcional, y
    // mandar un 0 sería AFIRMAR que no está afiliado, que no es lo mismo que no
    // saberlo — y de eso depende que el modelo le cuente o no el subsidio.
    if (state.afiliado === 'Sí' || state.afiliado === 'No') {
      cuerpo.afiliado = state.afiliado === 'Sí' ? 1 : 0;
    }
    return cuerpo;
  }

  function base() {
    return (window.GDF_CONFIG && window.GDF_CONFIG.Leadify_BASE) || '';
  }

  /**
   * La constructora de esta demo, con la clave del CATALOGO (`bolivar`), que no
   * es el slug del tenant (`constructora-bolivar`). La escribe
   * generar_tenants.py en marca.js, que es donde conviven las dos.
   */
  function constructoraDelTenant() {
    var m = window.GDF_MARCA || {};
    return m.constructora || '';
  }

  /**
   * VA EN LA URL, NO EN EL CUERPO, y no es un capricho: el formulario del §3
   * esta verificado llave por llave contra el ejemplo del contrato, y meterle
   * un campo que el contrato no declara lo rompe — el modelo puede rechazarlo,
   * y aunque no lo rechace ya no seria el cuerpo que dice el contrato.
   *
   * El contrato no tiene forma de pedir una sola constructora. Esto es una
   * extension NUESTRA que el motor local entiende; el modelo real la ignora, y
   * de eso se encarga la red de seguridad de recommender.js.
   */
  function urlDeRecomendar() {
    var c = constructoraDelTenant();
    return base() + '/recomendar' + (c ? '?constructora=' + encodeURIComponent(c) : '');
  }

  /**
   * Llama al modelo. `cb` recibe siempre la misma forma:
   *   { estado: 'listo' | 'vacio' | 'error', items, total, motor, error }
   *
   * `vacio` se distingue de `error` a propósito, aunque el contrato promete que
   * nunca devuelve lista vacía (expande a las localidades vecinas). Si algún
   * día pasara, hay que decirlo — no dejarlo caer en una pantalla de error de
   * red, que invita a reintentar algo que reintentar no arregla.
   */
  function pedirRecomendaciones(state, cb) {
    var cuerpo = construirFormulario(state);
    var url = base();

    if (!url) {
      console.error('[GDF/leadify] Falta window.GDF_CONFIG.Leadify_BASE (ver js/config.js).', cuerpo);
      cb({ estado: 'error', items: [], error: 'Leadify_BASE no configurado' });
      return;
    }

    fetch(urlDeRecomendar(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo),
    })
      .then(function (res) {
        // 400 = el formulario no cumple el contrato. El modelo junta TODOS los
        // errores en un solo texto en vez de parar en el primero, justamente
        // para poder corregirlos de una vez; por eso se registra entero.
        if (res.status === 400) {
          return res.json().then(function (d) {
            console.error(
              '[GDF/leadify] 400 — el formulario no cumple el contrato:\n' + (d.error || '(sin detalle)'),
              cuerpo
            );
            cb({ estado: 'error', items: [], error: 'El formulario no cumple el contrato del modelo.' });
          });
        }
        if (!res.ok) {
          return res.text().then(function (t) {
            console.error('[GDF/leadify] /recomendar respondió ' + res.status + ':', t);
            cb({ estado: 'error', items: [], error: 'El modelo respondió ' + res.status + '.' });
          });
        }
        return res.json().then(function (d) {
          var items = d.apartamentos || [];
          console.log('[GDF/leadify] motor:', d.motor, '| preseleccionados:',
            d.total_preseleccionados, '| devueltos:', items.length);
          cb({
            estado: items.length ? 'listo' : 'vacio',
            items: items,
            total: d.total_preseleccionados || null,
            motor: d.motor || null,
            // Lo que el backend dice haber filtrado. Si se pidió una
            // constructora y aquí no viene, es que no hizo caso, y quien
            // arregla eso es la red de seguridad de recommender.js.
            constructoraFiltrada: d.constructora_filtrada || null,
            error: null,
          });
        });
      })
      .catch(function (err) {
        console.error('[GDF/leadify] No se pudo contactar al modelo:', err);
        cb({ estado: 'error', items: [], error: 'No se pudo conectar con el modelo.' });
      });
  }

  window.GDF = window.GDF || {};
  window.GDF.leadify = {
    construirFormulario: construirFormulario,
    pedirRecomendaciones: pedirRecomendaciones,
    constructoraDelTenant: constructoraDelTenant,
    urlDeRecomendar: urlDeRecomendar,
    localidadId: localidadId,
    localidadIds: localidadIds,
    zonasComunesDe: zonasComunesDe,
    claveDe: claveDe,
    LOCALIDADES: LOCALIDADES,
    ZONAS_DEL_CONTRATO: ZONAS_DEL_CONTRATO,
  };
})();
