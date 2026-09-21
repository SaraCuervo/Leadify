// Bootstrap: estado vivo, listener delegado único y el ciclo de render.
(function () {
  'use strict';

  var state = window.GDF.state.createInitial();
  var root = null;

  // Pantalla mostrada en el último render, para distinguir "entré a una
  // pantalla nueva" de "seguimos en la misma pantalla pero cambió algo"
  // (afiliado, consent, proyecto elegido, pregunta del quiz...). Cada
  // render() reconstruye TODO el innerHTML, así que sin este chequeo la
  // animación de entrada .gdf-screen (screenIn) se repetiría en cada click
  // dentro de la misma pantalla — un flash visible cada vez que tocas un
  // botón. Las animaciones internas (cuartos cayendo, progreso, chips) no
  // dependen de esto y siguen disparándose siempre, como debe ser.
  var lastScreen = null;

  // Selección en curso de la pregunta 'entorno_deseado' (buscador con chips).
  // Vive fuera de `state` a propósito, igual que los inputs no controlados:
  // cada tecla en el buscador o cada clic en una opción actualizaría
  // `state.answers` y forzaría un re-render completo de la pantalla, que
  // perdería el foco del buscador. Se compromete a `state` recién al pulsar
  // "Continuar" (ver 'answerQuizMultiselect' en onRootClick). Se reinicia
  // sola cada vez que se entra de nuevo a esta pregunta, porque
  // attachInputListeners() solo encuentra '#entornoSearch' en el DOM justo
  // después de un render que aterriza en ella.
  var entornoSeleccion = [];

  // Selección en curso de la pregunta 'zona' (buscador de barrios + mapa).
  // Vive fuera de `state` por lo mismo que `entornoSeleccion`, y además
  // porque aquí hay DOS controles que tienen que quedar de acuerdo: al tocar
  // el mapa se escribe el nombre en el buscador, y al elegir un barrio se
  // marca su localidad en el mapa. Con un re-render por clic, el buscador
  // perdería el foco a media escritura.
  //
  // ES UNA LISTA: se pueden pedir VARIOS sectores. Nadie busca casa en un solo
  // sitio —"por Cedritos, o por el Polo, o por Suba"— y el modelo ya sabe
  // recibir varias localidades y medir la distancia a la más cercana de todas
  // (ver `ids_localidades` y el BFS multi-origen de catalogos.py).
  //
  // Cada elemento es `{ localidad, barrio }`. Los NOMBRES de localidad son lo
  // que viaja a `state.answers.zona` (la primera, para todo lo que espera una
  // sola) y a `state.answers.zonas` (todas, que es lo que se manda al modelo).
  // El barrio es solo para mostrar: el catálogo no guarda el barrio de cada
  // proyecto, así que el filtro real es y sigue siendo por localidad.
  var zonaSeleccion = [];

  function render() {
    var sameScreen = state.screen === lastScreen;
    // Reconstruir TODO el innerHTML también destruye y recrea el nodo que
    // tenía el scroll (p. ej. .gdf-escarapela, que scrollea internamente), así
    // que sin esto cada click en "afiliado" o en el check de consentimiento
    // volvía el scroll a 0 — se sentía como si la página se recargara.
    // Restauramos tanto el scroll interno del propio .gdf-screen como el de
    // la página, para pantallas que scrollean como página normal.
    var prevScrollTop = 0;
    var prevWindowScroll = 0;
    if (sameScreen) {
      var prevScreenEl = root.querySelector('.gdf-screen');
      prevScrollTop = prevScreenEl ? prevScreenEl.scrollTop : 0;
      prevWindowScroll = window.scrollY;
    }
    var derived = window.GDF.state.computeDerived(state);
    // El mapa muere ANTES de arrasar el innerHTML. `render()` reconstruye
    // #root entero, asi que el nodo del mapa se destruye si o si; si Leaflet
    // no se entera, se queda con listeners sobre un nodo huerfano y la
    // siguiente vez que se monte falla con "Map container is already
    // initialized". Es no-op si no habia mapa.
    if (window.GDF.mapa) window.GDF.mapa.desmontar();
    root.innerHTML = window.GDF.templates.renderApp(state, derived);
    if (sameScreen) {
      var screenEl = root.querySelector('.gdf-screen');
      if (screenEl) {
        screenEl.style.animation = 'none';
        screenEl.scrollTop = prevScrollTop;
      }
      window.scrollTo(0, prevWindowScroll);
      // Las tarjetas de proyecto entran con floatUp escalonado (hasta 0.44s
      // de delay). Eso está bien la primera vez que se ve la lista, pero al
      // marcar un proyecto se reconstruye el innerHTML y las 6 volvían a
      // animarse: un parpadeo completo de la lista en cada clic.
      var cards = root.querySelectorAll('.gdf-project-card');
      for (var c = 0; c < cards.length; c++) cards[c].style.animation = 'none';
    }
    lastScreen = state.screen;
    attachInputListeners();
    // sceneBlock ya dejo el hueco del mapa en el HTML nuevo; esto lo llena.
    updateMapaDOM(derived);
    // root.innerHTML desprendio el canvas del 3D (si existia) sin destruir su
    // contexto WebGL; esto lo vuelve a enganchar. Ver updatePlano3D.
    updatePlano3D(derived);
  }

  // Puente hacia plano3d/ (mejora progresiva sobre el plano 2D de recortes).
  // GDF3D puede no existir (el bundle no cargo) o quedar apagado por hardware
  // sin WebGL: en los dos casos `actualizar` no esta o devuelve false, y el 2D
  // de siempre sigue siendo lo que se ve, sin que haga falta comprobarlo aqui.
  function updatePlano3D(derived) {
    if (window.GDF3D && window.GDF3D.actualizar) window.GDF3D.actualizar(state, derived);
  }

  // Los inputs de nombre/apellido/correo/teléfono son "no controlados":
  // reconstruir todo el innerHTML en cada tecla perdería el foco y el
  // cursor. En vez de eso, actualizamos el preview del carné directamente
  // por DOM y solo comprometemos el valor a `state` (ya lo hace este mismo
  // listener). También engancha los inputs de preguntas "libres" del quiz
  // (edad numérica, entorno de texto) — ver 'answerQuizNumber'/
  // 'answerQuizText' en onRootClick.
  function attachInputListeners() {
    var nombreInput = document.getElementById('nombreInput');
    var apellidoInput = document.getElementById('apellidoInput');
    var correoInput = document.getElementById('correoInput');
    var telefonoInput = document.getElementById('telefonoInput');

    function refreshCarnetName() {
      var nameEl = document.getElementById('carnetName');
      if (!nameEl) return;
      var fullName = (state.nombre.trim() + ' ' + state.apellido.trim()).trim();
      nameEl.textContent = fullName || 'Tu nombre';
    }

    if (nombreInput) {
      nombreInput.addEventListener('input', function (e) {
        state.nombre = e.target.value;
        refreshCarnetName();
        updateStartButton();
      });
    }
    if (apellidoInput) {
      apellidoInput.addEventListener('input', function (e) {
        state.apellido = e.target.value;
        refreshCarnetName();
        updateStartButton();
      });
    }
    if (correoInput) {
      correoInput.addEventListener('input', function (e) {
        state.correo = e.target.value;
        updateStartButton();
      });
    }
    if (telefonoInput) {
      telefonoInput.addEventListener('input', function (e) {
        state.telefono = e.target.value;
        var phoneEl = document.getElementById('carnetPhone');
        if (phoneEl) phoneEl.textContent = e.target.value.trim() || 'Tu teléfono';
        updateStartButton();
      });
    }

    var quizNumberInput = document.getElementById('quizNumberInput');
    if (quizNumberInput) {
      quizNumberInput.addEventListener('input', updateQuizNumberButton);
      quizNumberInput.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        var btn = document.querySelector('[data-action="answerQuizNumber"]');
        if (btn && btn.classList.contains('enabled')) btn.click();
      });
    }

    // Los <details> se abren/cierran solos (comportamiento nativo, sin JS ni
    // re-render). Lo único que hace falta es ANOTAR si quedaron abiertos,
    // para que un re-render posterior — marcar el proyecto, por ejemplo — los
    // vuelva a pintar como estaban. No se despacha por el listener delegado
    // porque 'toggle' no es un clic.
    //
    // Además funcionan como ACORDEÓN: abrir el plano de un proyecto cierra el
    // del anterior. Con seis desplegables abiertos a la vez la lista se volvía
    // kilométrica y se perdía la referencia de qué se estaba comparando.
    // Cerrar el otro dispara su propio 'toggle', así que `detalleAbierto`
    // queda al día sin tocarlo aquí.
    var detalles = root.querySelectorAll('.gdf-project-detalle');
    for (var d = 0; d < detalles.length; d++) {
      (function (el) {
        el.addEventListener('toggle', function () {
          // Este chequeo evita una pasada inútil del acordeón en cada render.
          // Cerrar otro <details> por código sí contradice el estado, así que
          // el acordeón sigue funcionando.
          if (state.detalleAbierto[el.dataset.proyecto] === el.open) return;
          state.detalleAbierto[el.dataset.proyecto] = el.open;
          if (!el.open) return;
          for (var o = 0; o < detalles.length; o++) {
            if (detalles[o] !== el && detalles[o].open) detalles[o].open = false;
          }
        });
      })(detalles[d]);
    }
    var quizTextInput = document.getElementById('quizTextInput');
    if (quizTextInput) {
      quizTextInput.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        var btn = document.querySelector('[data-action="answerQuizText"]');
        if (btn) btn.click();
      });
    }

    engancharScrollResultados();

    var entornoSearch = document.getElementById('entornoSearch');
    if (entornoSearch) {
      entornoSeleccion = [];
      renderEntornoChips();
      var entornoLista = document.getElementById('entornoOpciones');
      // AL ENFOCAR, EL LISTADO COMPLETO. Son las 25 zonas comunes del
      // vocabulario, pre-renderizadas de una vez (a diferencia del buscador
      // de barrios de 'zona', que sí arma sus opciones al vuelo porque son
      // 1.258 — ver renderZonaSugerencias): mostrarlas todas de entrada no
      // cuesta nada y deja hojear en vez de obligar a escribir una palabra
      // exacta. Escribir sigue filtrando igual que antes; el campo vacío
      // —recién enfocado, o borrado hasta el final— muestra todo en vez de
      // nada. Flota pegado al input (ver '.gdf-multi-opt-list' en CSS); el
      // cierre por "clic afuera" vive en boot() (ver 'cerrarEntornoSiTocaAfuera').
      function filtrarEntorno() {
        var termino = normalizarTexto(entornoSearch.value);
        var botones = document.querySelectorAll('#entornoOpciones .gdf-multi-opt');
        var hayVisibles = false;
        for (var i = 0; i < botones.length; i++) {
          var visible = termino === '' || normalizarTexto(botones[i].textContent).indexOf(termino) > -1;
          botones[i].classList.toggle('oculto', !visible);
          if (visible) hayVisibles = true;
        }
        if (entornoLista) entornoLista.classList.toggle('abierto', hayVisibles);
      }
      entornoSearch.addEventListener('input', filtrarEntorno);
      // 'focus' cubre el caso normal (entrar al campo); 'click' cubre el
      // caso raro en que el campo ya tenía el foco pero el panel se había
      // cerrado por un clic afuera que no llegó a quitarle el foco al input
      // —'focus' no se dispara dos veces sin un blur de por medio—.
      entornoSearch.addEventListener('focus', filtrarEntorno);
      entornoSearch.addEventListener('click', filtrarEntorno);
    }

    // EL BUSCADOR DE LA PREGUNTA 'zona', uno solo para barrios y lugares. Igual
    // que el de arriba: solo aparece con texto escrito, y la selección en curso
    // se reinicia porque este código solo corre tras un render que aterriza
    // aquí.
    var zonaSearch = document.getElementById('zonaSearch');
    if (zonaSearch) {
      // Se RECUPERA lo ya elegido en vez de empezar en blanco: a esta pregunta
      // se vuelve con "Atrás", y encontrarse el mapa vacío después de haber
      // elegido tres zonas se lee como que se perdieron.
      zonaSeleccion = (state.zonaSectores || []).slice();
      zonaSearch.addEventListener('input', renderZonaSugerencias);
      // Enter elige la primera sugerencia —sea barrio o lugar, la lista es una
      // sola—; si ya hay algo elegido, continúa.
      zonaSearch.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        var primera = document.querySelector('#zonaOpciones .gdf-zona-opt');
        if (primera) {
          primera.click();
          return;
        }
        var btn = document.querySelector('[data-action="answerQuizZona"]');
        if (btn && zonaSeleccion.length) btn.click();
      });
    }
  }

  // ------------------------------------------------ scroll de los resultados

  var soltarScroll = null;

  /**
   * Marca `.gdf-result` mientras se está scrolleando, y congela el fondo
   * animado durante ese rato. Las dos cosas atacan el mismo síntoma: que bajar
   * por la lista de proyectos se sintiera a tirones.
   *
   * SON DOS CAUSAS DISTINTAS Y HACEN FALTA LAS DOS.
   *
   *   1. Las tarjetas SE MUEVEN SOLAS mientras la lista pasa bajo un cursor
   *      quieto: cada una recibe `:hover` al cruzarlo y se levanta 2px. Eso es
   *      lo que se lee como "salta todo". Lo corta la clase `scrolleando`,
   *      que les quita los punteros (ver el CSS de `.gdf-project-card:hover`).
   *
   *   2. Detrás de la lista hay un canvas a pantalla completa repintándose a
   *      60 fps (`js/senal.js`), y el panel que scrollea es TRANSPARENTE en la
   *      marca Leadify —`.gdf-con-senal .gdf-result { background: transparent }`—.
   *      Un contenedor transparente sobre un fondo que cambia en cada frame no
   *      se puede desplazar copiando píxeles: hay que repintarlo entero cada
   *      vez. Parar la red mientras dura el gesto deja el fondo quieto y el
   *      scroll vuelve a ser un simple desplazamiento. Nadie nota que una red
   *      ambiental se congela 140 ms.
   *
   * El listener va sobre el nodo, no sobre el documento, y se re-engancha en
   * cada render porque `render()` reconstruye el innerHTML entero: el
   * `.gdf-result` de ahora no es el mismo nodo que el de antes. `soltarScroll`
   * suelta el anterior para no dejar temporizadores de una pantalla que ya no
   * existe.
   */
  function engancharScrollResultados() {
    if (soltarScroll) soltarScroll();
    var panel = document.querySelector('.gdf-result');
    if (!panel) return;

    var quieto = null;
    function alScrollear() {
      if (!quieto) {
        panel.classList.add('scrolleando');
        if (window.GDF.senal) window.GDF.senal.pausar();
      }
      clearTimeout(quieto);
      // 140 ms sin un solo evento de scroll = el gesto terminó. Con menos, la
      // inercia de un trackpad lo reactiva a cada instante y el hover parpadea.
      quieto = setTimeout(function () {
        quieto = null;
        panel.classList.remove('scrolleando');
        if (window.GDF.senal) window.GDF.senal.reanudar();
      }, 140);
    }

    panel.addEventListener('scroll', alScrollear, { passive: true });
    soltarScroll = function () {
      clearTimeout(quieto);
      panel.removeEventListener('scroll', alScrollear);
      // Si se sale de la pantalla a mitad de un scroll, la red se quedaría
      // congelada para siempre.
      if (quieto && window.GDF.senal) window.GDF.senal.reanudar();
      soltarScroll = null;
    };
  }

  // ---------------------------------------------------------------- zona

  // El mismo escape de templates.js: las sugerencias del buscador se pintan
  // con innerHTML y llevan nombres de barrio que vienen de un archivo
  // generado, no de la maquetación.
  function esc(s) {
    return window.GDF.templates.esc(s);
  }

  // Nombre de localidad a partir del id 1..20 del índice de barrios.
  function localidadPorId(id) {
    var lista = (window.GDF.data && window.GDF.data.LOCALIDADES) || [];
    return lista[id - 1] || null;
  }

  // Las mejores coincidencias de barrio, hasta `tope`.
  //
  // ORDEN: primero lo que EMPIEZA por lo escrito, después lo que solo lo
  // contiene; dentro de cada grupo, la clave más corta primero. Ojo que esto
  // NO es la regla de _GAZETTEER_ORDENADO del scraper (más largo primero):
  // aquella resuelve qué frase reconocer dentro de una dirección completa,
  // donde la más larga es la más específica. Aquí el usuario está tecleando
  // un prefijo, y lo que espera ver arriba es "Suba", no "Suba Rincón".
  function sugerenciasZona(termino, tope) {
    var idx = window.GDF_BARRIOS || [];
    var empiezan = [];
    var contienen = [];
    for (var i = 0; i < idx.length; i++) {
      var pos = idx[i][0].indexOf(termino);
      if (pos === 0) empiezan.push(idx[i]);
      else if (pos > 0) contienen.push(idx[i]);
    }
    var porLargo = function (a, b) { return a[0].length - b[0].length; };
    empiezan.sort(porLargo);
    contienen.sort(porLargo);
    // UN SITIO, UNA FILA. El gazetteer trae alias del mismo lugar para poder
    // reconocerlo dentro de una dirección — "candelaria" y "la candelaria",
    // "martires" y "los martires", "tunal" y "el tunal" — y los dos aciertan
    // al buscar. Mostrarlos juntos daría dos filas idénticas y ninguna pista
    // de en qué se diferencian. Se dedupe al pintar, no en el índice: quitar
    // la clave de más rompería una de las dos formas de escribirlo.
    // La identidad es el POLÍGONO (`bi`, ver GDF_BARRIOS en mapa_bogota.js),
    // no el nombre: "chico" y "el chico" apuntan al mismo, y salen una vez.
    var vistos = {};
    var salida = [];
    var todos = empiezan.concat(contienen);
    for (var j = 0; j < todos.length && salida.length < tope; j++) {
      var llave = todos[j][1] + '|' + (todos[j][3] != null ? todos[j][3] : todos[j][2]);
      if (vistos[llave]) continue;
      vistos[llave] = true;
      salida.push(todos[j]);
    }
    return salida;
  }

  // ------------------------------------------- el buscador de la pregunta
  //
  // UNA SOLA LISTA, DOS CLASES DE RESULTADO. Hay dos formas de decir dónde se
  // quiere vivir —el nombre del barrio, o el de un sitio que uno reconozca— y
  // las dos salen del MISMO campo, cada una bajo su encabezado.
  //
  // Hubo aquí dos pestañas ("Conozco el barrio" / "Sé un lugar cerca") y se
  // quitaron: obligaban a clasificarse antes de poder escribir, y quien elegía
  // la que no era se encontraba un buscador que no encontraba algo que sí
  // existe. La pregunta que el usuario tiene en la cabeza es "dónde", no "cómo
  // sé decirlo".
  //
  // SON TRES CAPAS, y el orden es el de lo que tarda cada una:
  //   1. `GDF_BARRIOS` — el gazetteer más los sectores catastrales que trae el
  //      mapa, 1.258 entradas. Local, instantáneo.
  //   2. `GDF_LUGARES` — los sitios de Bogotá que baja tools/generar_mapa.py de
  //      OSM, ya resueltos a `{loc, bi}`. Local, instantáneo.
  //   3. Photon (photon.komoot.io) en vivo, para el sitio que el catálogo no
  //      tenga. Llega después y se agrega DEBAJO, dentro del grupo de lugares.
  // Si no hay internet o Photon no responde, las dos primeras ya están en
  // pantalla y no se muestra ningún error: el buscador sabe menos, nada más.
  //
  // Photon y no Nominatim porque Nominatim PROHÍBE el uso tipo autocompletar
  // en su política; Photon está hecho justamente para eso y no pide llave.
  var PHOTON_URL = 'https://photon.komoot.io/api/';
  // El mismo recuadro de Bogotá que OSM_BBOX en tools/generar_mapa.py, pero
  // en el orden que quiere Photon: minLon,minLat,maxLon,maxLat.
  var PHOTON_BBOX = '-74.25,4.45,-73.98,4.85';
  // Lo que devuelve OSM y NO sirve como punto de referencia: un paradero o un
  // portal no ubican a nadie, y ensucian la lista empujando hacia abajo el
  // centro comercial que sí se buscaba.
  var LUGAR_RUIDO = { highway: 1, building: 1, barrier: 1, entrance: 1, traffic_signals: 1 };
  var lugarPeticion = null;    // AbortController de la búsqueda en vuelo
  var lugarDebounce = null;

  // CUÁNTAS FILAS DE CADA CLASE. El tope no lo pone el sitio —el desplegable
  // scrollea a partir de 280px, ver `.gdf-multi-opt-list`— sino la atención:
  // con las ocho de barrio que se mostraban cuando era el único buscador, el
  // encabezado "Lugares" caía por debajo del borde y no se descubría nunca.
  // Cinco y cinco dejan las dos clases a la vista de entrada.
  var MAX_BARRIOS = 5;
  var MAX_LUGARES = 5;
  var MAX_LUGARES_VIVO = 5;

  /** Las mejores coincidencias del CATÁLOGO LOCAL de lugares. Sin red. */
  function sugerenciasLugar(termino, tope) {
    var idx = window.GDF_LUGARES || [];
    var empiezan = [];
    var contienen = [];
    for (var i = 0; i < idx.length; i++) {
      var pos = normalizarTexto(idx[i].n).indexOf(termino);
      if (pos === 0) empiezan.push(idx[i]);
      else if (pos > 0) contienen.push(idx[i]);
    }
    var porLargo = function (a, b) { return a.n.length - b.n.length; };
    empiezan.sort(porLargo);
    contienen.sort(porLargo);
    return empiezan.concat(contienen).slice(0, tope);
  }

  /**
   * Pregunta a Photon por `termino` y devuelve lo que caiga DENTRO de Bogotá.
   *
   * Cada resultado se resuelve aquí mismo a `{localidad, barrio, bi}` con los
   * polígonos que ya están cargados (`mapa.zonaEnPunto`), y lo que no cae en
   * ninguna de las 20 localidades —un sitio de Chía, de Soacha, de otro país—
   * se descarta ANTES de pintarse. Así toda sugerencia que se ve es elegible;
   * no hay forma de tocar una y que no pase nada.
   */
  function buscarLugaresEnVivo(termino, alLlegar) {
    if (lugarPeticion) lugarPeticion.abort();
    if (typeof AbortController === 'undefined' || typeof fetch !== 'function') return;
    lugarPeticion = new AbortController();
    var ctrl = lugarPeticion;
    // Si tarda, no se espera: lo local ya está en pantalla.
    var corte = setTimeout(function () { ctrl.abort(); }, 4000);

    fetch(PHOTON_URL + '?q=' + encodeURIComponent(termino) +
          '&limit=10&bbox=' + PHOTON_BBOX, { signal: ctrl.signal })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (datos) {
        clearTimeout(corte);
        if (!datos || !datos.features || ctrl !== lugarPeticion) return;
        var mapa = window.GDF.mapa;
        if (!mapa || !mapa.zonaEnPunto) return;
        var salida = [];
        datos.features.forEach(function (f) {
          var p = f.properties || {};
          var c = (f.geometry || {}).coordinates;
          if (!p.name || !c || LUGAR_RUIDO[p.osm_key]) return;
          var zona = mapa.zonaEnPunto(c[0], c[1]);
          if (!zona) return;                       // fuera de Bogotá
          salida.push({ n: p.name, cat: p.osm_value || '', zona: zona });
        });
        alLlegar(salida);
      })
      .catch(function () {
        clearTimeout(corte);
        // Sin red, Photon caído o petición cancelada: no se dice nada. Las
        // sugerencias locales ya están y el flujo sigue.
      });
  }

  /** El encabezado que separa las dos clases de resultado. No es pulsable. */
  function grupoHtml(texto) {
    return '<p class="gdf-opt-grupo">' + esc(texto) + '</p>';
  }

  /** La zona `{localidad, barrio, bi}` de una entrada del catálogo local. */
  function zonaDeLugar(l) {
    var mapa = window.GDF.mapa;
    var zona = { localidad: localidadPorId(l.loc), barrio: null, bi: l.bi };
    // El catálogo guarda `loc`+`bi`; el nombre del barrio sale del mapa, que
    // es quien tiene los contornos (mismo camino que `barrioPorIndice`).
    if (l.bi != null && mapa && mapa.nombreDeBarrio) zona.barrio = mapa.nombreDeBarrio(l.loc, l.bi);
    return zona;
  }

  /** Una fila de BARRIO. `f` es una entrada de GDF_BARRIOS. */
  function filaBarrio(f) {
    var loc = localidadPorId(f[1]);
    // `bi` es el polígono exacto de esta entrada (ver GDF_BARRIOS). Viaja en
    // el botón para que `mapa.marcar` pinte ESE y no el primero que se llame
    // igual: hay nombres repetidos dentro de una misma localidad.
    var bi = f[3] != null ? ' data-bi="' + f[3] + '"' : '';
    // El barrio grande, y debajo la localidad a la que resuelve: es lo que
    // evita prometer un filtro por barrio que el modelo no hace.
    return (
      '<button type="button" class="gdf-multi-opt gdf-zona-opt" data-action="elegirZona"' +
      ' data-loc="' + esc(loc) + '" data-barrio="' + esc(f[2]) + '"' + bi + '>' +
      '<span class="b">' + esc(f[2]) + '</span>' +
      (loc && normalizarTexto(loc) !== f[0] ? '<span class="l">' + esc(loc) + '</span>' : '') +
      '</button>'
    );
  }

  /** Una fila de LUGAR. `zona` es `{localidad, barrio, bi}`. */
  function filaLugar(nombre, zona) {
    // Debajo del nombre va DÓNDE queda, que es la respuesta a la pregunta
    // que el usuario está contestando — no la categoría de OSM, que a nadie
    // le dice nada.
    var donde = zona.barrio && zona.barrio !== zona.localidad
      ? zona.barrio + ' · ' + zona.localidad
      : zona.localidad;
    return (
      '<button type="button" class="gdf-multi-opt gdf-zona-opt" data-action="elegirLugar"' +
      ' data-loc="' + esc(zona.localidad) + '"' +
      ' data-barrio="' + esc(zona.barrio || '') + '"' +
      ' data-bi="' + (zona.bi == null ? '' : zona.bi) + '"' +
      ' data-lugar="' + esc(nombre) + '">' +
      '<span class="b">' + esc(nombre) + '</span>' +
      '<span class="l">' + esc(donde) + '</span>' +
      '</button>'
    );
  }

  /**
   * Pinta el desplegable: barrios y lugares del catálogo de inmediato, y
   * cuando (y si) llega la respuesta en vivo, lo que el catálogo no tenía.
   *
   * Se pinta al vuelo y no pre-renderizado como el de 'entorno_deseado': entre
   * las dos fuentes locales son miles de entradas, y crear esos nodos en cada
   * repintado del quiz para tenerlos ocultos no compensa.
   */
  function renderZonaSugerencias() {
    var input = document.getElementById('zonaSearch');
    var lista = document.getElementById('zonaOpciones');
    if (!input || !lista) return;
    var termino = normalizarTexto(input.value).trim();
    clearTimeout(lugarDebounce);
    if (!termino) {
      if (lugarPeticion) lugarPeticion.abort();
      lista.classList.remove('abierto');
      lista.innerHTML = '';
      return;
    }

    var barrios = sugerenciasZona(termino, MAX_BARRIOS);
    // LOS LUGARES PIDEN DOS LETRAS y los barrios no. Con una sola, el catálogo
    // de lugares devuelve cientos de sitios ordenados por longitud de nombre y
    // ninguno tiene que ver con lo que se está escribiendo; los barrios son
    // 1.258 y el prefijo ya discrimina desde la primera tecla.
    var lugares = termino.length >= 2 ? sugerenciasLugar(termino, MAX_LUGARES) : [];

    // Los encabezados solo aparecen cuando su grupo tiene filas: con "Cedritos"
    // no hay lugares, y un "Lugares" vacío al final se leería como un fallo.
    var html = '';
    if (barrios.length) html += grupoHtml('Barrios y localidades') + barrios.map(filaBarrio).join('');
    var vistos = {};
    if (lugares.length) {
      html += grupoHtml('Lugares') + lugares.map(function (l) {
        vistos[normalizarTexto(l.n)] = true;
        return filaLugar(l.n, zonaDeLugar(l));
      }).join('');
    }
    lista.innerHTML = html;
    lista.classList.toggle('abierto', html !== '');

    if (termino.length < 2) return;
    // La capa en vivo va con freno: se dispara cuando el usuario deja de
    // escribir, no en cada tecla.
    lugarDebounce = setTimeout(function () {
      buscarLugaresEnVivo(termino, function (remotos) {
        // Puede haber cambiado el texto mientras la red iba y venía.
        if (normalizarTexto(input.value).trim() !== termino) return;
        var nuevos = remotos.filter(function (r) {
          var clave = normalizarTexto(r.n);
          if (vistos[clave]) return false;         // ya lo trae el catálogo
          vistos[clave] = true;
          return true;
        }).slice(0, MAX_LUGARES_VIVO);
        if (!nuevos.length) return;
        // EL ENCABEZADO PUEDE NO ESTAR TODAVÍA. Si el catálogo local no tenía
        // ningún lugar, la lista salió sin ese grupo, y lo que llega de Photon
        // tiene que traerlo consigo o quedaría suelto bajo los barrios, leído
        // como si fuera uno más de ellos.
        var trozo = (lugares.length ? '' : grupoHtml('Lugares')) +
          nuevos.map(function (r) { return filaLugar(r.n, r.zona); }).join('');
        // `insertAdjacentHTML` y no `innerHTML +=`: lo segundo vuelve a
        // parsear la lista entera y destruye las filas locales que ya están
        // pintadas, que es justo lo que se ve como un parpadeo al escribir.
        lista.insertAdjacentHTML('beforeend', trozo);
        lista.classList.add('abierto');
      });
    }, 300);
  }

  // La identidad de un sector elegido. El barrio cuando lo hay y, si no, la
  // localidad: así "Suba" a secas y el barrio "Suba Rincón" son cosas
  // distintas y las dos se pueden tener a la vez.
  function claveZona(localidad, barrio) {
    return normalizarTexto(barrio || localidad || '');
  }

  /**
   * Agrega o quita un sector de la selección, y pone de acuerdo a los cuatro
   * controles: el buscador, los chips, el mapa y el botón Continuar. Sin pasar
   * por dispatch()/render(), por lo dicho en `zonaSeleccion`.
   *
   * ALTERNA, no fija: volver a tocar un sector ya elegido lo quita. Es la
   * única forma de deshacer directamente sobre el mapa —donde no hay una × que
   * pulsar— y es lo mismo que hace la grilla de `entorno_deseado`.
   */
  function alternarZonaValor(localidad, barrio, bi, origenLugar) {
    if (!localidad) return;
    var clave = claveZona(localidad, barrio);
    var yaEsta = -1;
    for (var i = 0; i < zonaSeleccion.length; i++) {
      if (claveZona(zonaSeleccion[i].localidad, zonaSeleccion[i].barrio) === clave) {
        yaEsta = i;
        break;
      }
    }
    if (yaEsta > -1) {
      // ALTERNAR SOLO CUANDO ES EL MISMO ORIGEN. Dos lugares distintos pueden
      // caer en el mismo sector catastral (dos centros comerciales de la misma
      // zona), y ahí quitar el que ya estaba se leería como "toqué uno nuevo y
      // me borró el anterior". Cuando el origen cambia se actualiza la
      // etiqueta y el sector se queda; solo se quita al repetir exactamente lo
      // mismo, que es lo que hace el clic en el mapa o en un barrio ya elegido.
      var mismoOrigen = zonaSeleccion[yaEsta].lugar === (origenLugar || null);
      if (mismoOrigen) zonaSeleccion.splice(yaEsta, 1);
      else zonaSeleccion[yaEsta].lugar = origenLugar || zonaSeleccion[yaEsta].lugar;
    }
    // `bi` es la posición del barrio dentro de su localidad y solo la trae el
    // mapa, que sabe exactamente qué polígono se tocó. Viaja para que
    // `mapa.marcar` resalte ESE y no otro con el mismo nombre: hay 46 nombres
    // de sector repetidos entre localidades y 23 repetidos dentro de una misma
    // (ver `porLoc` y `barrioPorIndice` en js/mapa.js). Es dato de pintado, no
    // de negocio: no entra en `answers` ni viaja al modelo, que sigue
    // filtrando por localidad.
    //
    // `lugar` es el nombre del sitio que el usuario buscó cuando el sector
    // vino del buscador de lugares (null si vino del de barrios o del mapa).
    // Tampoco es dato de negocio: solo cambia lo que dice el chip, para
    // devolverle lo que escribió y no un barrio que nunca nombró.
    else zonaSeleccion.push({
      localidad: localidad,
      barrio: barrio || null,
      bi: bi == null ? null : bi,
      lugar: origenLugar || null,
    });

    sincronizarZona();
  }

  /**
   * Quita un sector, pase lo que pase. Es lo que hace la × de un chip.
   *
   * No pasa por `alternarZonaValor` a propósito: esa ALTERNA según el origen
   * (ver el comentario de allá), así que la × de un chip que vino del
   * buscador de lugares habría caído en la rama de "origen distinto" y le
   * habría cambiado la etiqueta en vez de quitarlo. La × no alterna: quita.
   */
  function quitarZonaValor(localidad, barrio) {
    var clave = claveZona(localidad, barrio);
    for (var i = 0; i < zonaSeleccion.length; i++) {
      if (claveZona(zonaSeleccion[i].localidad, zonaSeleccion[i].barrio) === clave) {
        zonaSeleccion.splice(i, 1);
        sincronizarZona();
        return;
      }
    }
  }

  /** Repinta todo lo que depende de `zonaSeleccion`. */
  function sincronizarZona() {
    // El buscador se VACIA en vez de quedarse con lo último elegido: ahora la
    // confirmación de lo que hay elegido son los chips DENTRO del propio
    // campo, y dejar el texto puesto obligaría a borrarlo a mano para buscar
    // el siguiente.
    var input = document.getElementById('zonaSearch');
    if (input) {
      input.value = '';
      // El placeholder cambia una vez hay algo elegido: no hace falta seguir
      // explicando qué es esto, y "Agregar otra zona…" deja claro que se
      // puede seguir sumando. zonaPanel() ya lo pinta así al renderizar de
      // cero; esto es lo que lo mantiene correcto cuando se agrega o quita un
      // chip SIN pasar por un render completo (ver el comentario de
      // `zonaSeleccion` sobre por qué no se usa dispatch()/render() aquí).
      input.placeholder = zonaSeleccion.length
        ? 'Agregar otra zona…'
        : 'Tu barrio, o un lugar que reconozcas…';
    }

    // El mapa vive en el lienzo grande y lo pinta Leaflet, no este HTML: se
    // le pide a el que marque. Si no esta montado (sin red, o fuera de esta
    // pregunta) no pasa nada — el buscador funciona igual.
    if (window.GDF.mapa) window.GDF.mapa.marcar(zonaSeleccion);

    renderZonaChips();

    var eco = document.getElementById('zonaEco');
    if (eco && window.GDF.templates && window.GDF.templates.zonaEco) {
      eco.innerHTML = window.GDF.templates.zonaEco(zonaSeleccion);
    }

    var lista = document.getElementById('zonaOpciones');
    if (lista) {
      lista.classList.remove('abierto');
      lista.innerHTML = '';
    }

    var btn = document.querySelector('[data-action="answerQuizZona"]');
    if (btn) btn.classList.toggle('enabled', zonaSeleccion.length > 0);
  }

  /** Un chip por sector elegido, con su × para quitarlo. Mismo patrón que
   *  `renderEntornoChips`, y reusa sus estilos. */
  function renderZonaChips() {
    var cont = document.getElementById('zonaChips');
    if (!cont) return;
    cont.innerHTML = zonaSeleccion
      .map(function (sector) {
        // Si el sector vino del buscador de lugares, el chip dice el LUGAR,
        // no el barrio al que resolvió: es lo que la persona escribió y lo
        // único que reconoce. El barrio sigue estando en el dato (y es lo
        // que se pinta en el mapa), solo que no es lo que se muestra acá.
        var etiqueta = sector.lugar
          ? 'Cerca de ' + sector.lugar
          : (sector.barrio && sector.barrio !== sector.localidad
            ? sector.barrio + ' · ' + sector.localidad
            : sector.localidad);
        return (
          '<span class="gdf-entorno-chip">' + esc(etiqueta) +
          '<button type="button" class="gdf-entorno-chip-x" data-action="quitarZona"' +
          ' data-loc="' + esc(sector.localidad) + '"' +
          ' data-barrio="' + esc(sector.barrio || '') + '"' +
          ' aria-label="Quitar ' + esc(etiqueta) + '">×</button>' +
          '</span>'
        );
      })
      .join('');
  }

  // Sin tildes ni mayúsculas, para que "bano" encuentre "Baño" al buscar.
  function normalizarTexto(s) {
    return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  // Agrega o quita `valor` de la selección en curso de 'entorno_deseado' y
  // repinta tanto el botón de la opción como la fila de chips — sin pasar
  // por dispatch()/render() (ver comentario de `entornoSeleccion`).
  function toggleEntornoValor(valor) {
    var idx = entornoSeleccion.indexOf(valor);
    if (idx > -1) entornoSeleccion.splice(idx, 1);
    else entornoSeleccion.push(valor);
    var botones = document.querySelectorAll('#entornoOpciones .gdf-multi-opt');
    for (var i = 0; i < botones.length; i++) {
      if (botones[i].dataset.value === valor) {
        botones[i].classList.toggle('selected', entornoSeleccion.indexOf(valor) > -1);
      }
    }
    renderEntornoChips();
    // LA LISTA SE QUEDA ABIERTA. Antes se cerraba en cuanto se elegía algo, y
    // eso convertía "quiero piscina, gimnasio y zona BBQ" en tres viajes:
    // abrir, elegir uno, volver a abrir. Casi nadie pide una sola amenidad, así
    // que lo normal es seguir eligiendo — la lista se queda hasta que se toque
    // fuera de ella (ver `cerrarEntornoSiTocaAfuera` en boot()).
    //
    // La confirmación de lo elegido no se pierde por dejarla abierta: el botón
    // de la opción se queda marcado con `.selected` justo arriba, que es
    // feedback en el sitio donde está mirando la persona. El chip de abajo lo
    // dice otra vez cuando la lista se cierre.
  }

  function renderEntornoChips() {
    var cont = document.getElementById('entornoChips');
    if (!cont) return;
    var q = findQuestionById('entorno_deseado');
    cont.innerHTML = entornoSeleccion
      .map(function (valor) {
        var opt = q && q.options.filter(function (o) { return o.v === valor; })[0];
        var label = opt ? opt.label : valor;
        return (
          '<span class="gdf-entorno-chip">' + label +
          '<button type="button" class="gdf-entorno-chip-x" data-action="quitarEntorno" data-value="' + valor + '" aria-label="Quitar ' + label + '">×</button>' +
          '</span>'
        );
      })
      .join('');
  }

  function updateStartButton() {
    var btn = document.querySelector('.gdf-btn-primary');
    if (!btn) return;
    var isValidEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(state.correo.trim());
    var canStart = !!(
      state.nombre.trim() &&
      state.apellido.trim() &&
      state.correo.trim() &&
      isValidEmail &&
      state.telefono.trim() &&
      state.consent
    );
    btn.classList.toggle('enabled', canStart);
  }

  // El botón de la pregunta numérica del quiz (edad) empieza deshabilitado
  // (ver quiz() en templates.js) hasta que el valor tipeado esté dentro de
  // min/max — mismo patrón visual que el botón de escarapela.
  function updateQuizNumberButton() {
    var input = document.getElementById('quizNumberInput');
    var btn = document.querySelector('[data-action="answerQuizNumber"]');
    if (!input || !btn) return;
    var n = Number(input.value);
    var min = input.min !== '' ? Number(input.min) : -Infinity;
    var max = input.max !== '' ? Number(input.max) : Infinity;
    var valid = input.value !== '' && !isNaN(n) && n >= min && n <= max;
    btn.classList.toggle('enabled', valid);
  }

  function dispatch(action, dataset) {
    // "Empezar de nuevo" corta cualquier polling del resumen en curso — si
    // no, un intento tardío de la partida anterior podía repintar el
    // resumen sobre una partida nueva que ya no tiene nada que ver.
    if (action === 'restart' && pollingHandle) {
      clearInterval(pollingHandle);
      pollingHandle = null;
      telefonoEnCurso = null;
    }
    var prevScreen = state.screen;
    var changed = window.GDF.state.applyAction(state, action, dataset);
    if (!changed) return;
    // Cambios DENTRO de una tarjeta ya pintada. Un render() completo cerraría el <details> abierto y volvería
    // a crear los <img> de los planos (parpadeo). Se parchea el DOM y listo.
    if (action === 'verTipologia') {
      updateTipologiaDOM(dataset);
      return;
    }
    if (action === 'setDetalleAbierto') return; // el <details> ya se pintó solo
    // Se acaba de elegir el apartamento: se pide su plano ya, para que la
    // primera pieza que caiga no lo haga contra un hueco en blanco.
    if (action === 'startQuiz') precargarPlano();
    // Avanzar o retroceder DENTRO del quiz: la escena no se puede reconstruir
    // por innerHTML. Si se destruyen y recrean los .gdf-room no hay nodos que
    // persistan, y entonces cada respuesta rehace el plano entero en vez de
    // añadirle una pieza.
    if ((action === 'selectOption' || action === 'goBack') &&
        prevScreen === 'quiz' && state.screen === 'quiz') {
      updateQuizDOM();
      return;
    }
    render();

    // PASO 1 del contrato. El quiz termina y entra a 'result' exactamente una
    // vez por partida (desde selectOption, al contestar la última pregunta):
    // ese es el primer momento en que existen TODOS los campos requeridos.
    if (prevScreen !== 'result' && state.screen === 'result') {
      cargarRecomendaciones();
    }

    // PASO 2 del contrato. Ya no hace falta un botón de "Confirmar": tocar
    // "Llamar" en la tarjeta (llamarProyecto) ES la confirmación, así
    // que la llamada de Manuela se dispara sola al entrar a esta pantalla —
    // misma idea que el paso 1 con 'result'. La pantalla relata en qué estado
    // va (ver confirmacion() en templates.js, y js/llamada.js para el POST).
    if (prevScreen !== 'confirmacion' && state.screen === 'confirmacion') {
      dispararLlamada();
    }
    // Botón "Reintentar" tras un error de envío: 'reintentarLlamada' ya dejó
    // state.llamada en 'cargando' (ver state.js) y render() de arriba lo
    // pinta; solo falta relanzar el POST.
    if (action === 'reintentarLlamada') {
      window.GDF.llamada.disparar(state, onLlamadaResuelta);
    }
    // Botón "Buscar resumen" tras agotar los intentos automáticos: relanza
    // SOLO el polling, la llamada ya se hizo.
    if (action === 'reintentarResumen') {
      iniciarPolling(telefonoEnCurso);
    }
  }

  // Paso 2 del contrato: POST /api/llamar (ver js/llamada.js). Mismo patrón
  // que cargarRecomendaciones() arriba: marca 'cargando', llama, repinta.
  function dispararLlamada() {
    window.GDF.state.applyAction(state, 'llamadaCargando', {});
    render();
    window.GDF.llamada.disparar(state, onLlamadaResuelta);
  }

  // Compartido entre el disparo automático y el botón "Reintentar": aplica
  // el resultado del POST y, si fue un envío real (no el mock del backend),
  // arranca el paso 3 — el polling del resumen. `telefono` se guarda aparte
  // porque state.resumen se resetea a null en cada intento nuevo y
  // 'reintentarResumen' lo necesita después de que la respuesta ya pasó.
  var telefonoEnCurso = null;
  function onLlamadaResuelta(resultado) {
    window.GDF.state.applyAction(state, 'llamadaResuelta', resultado);
    if (resultado.estado === 'lista' && resultado.real && resultado.telefono) {
      telefonoEnCurso = resultado.telefono;
      iniciarPolling(resultado.telefono);
    } else {
      render();
    }
  }

  // Paso 3: polling corto de /api/llamar/resultado hasta que Dapta empuje el
  // análisis post-llamada, o hasta agotar los intentos. Cada intento nuevo
  // (disparo, reintento de llamada, o "Buscar resumen") cancela cualquier
  // ciclo anterior — no tiene sentido seguir preguntando por una llamada
  // vieja mientras hay una nueva en curso.
  var pollingHandle = null;
  var POLL_INTERVALO_MS = 4000;
  var POLL_MAX_INTENTOS = 45; // ~3 minutos — de sobra para una llamada de <2 min más el margen del webhook

  function iniciarPolling(telefono) {
    if (pollingHandle) { clearInterval(pollingHandle); pollingHandle = null; }
    if (!telefono) return;
    telefonoEnCurso = telefono;
    window.GDF.state.applyAction(state, 'resumenEsperando', {});
    render();

    var intentos = 0;
    function intentar() {
      intentos++;
      window.GDF.llamada.verificarResultado(telefono, function (r) {
        if (r && r.listo) {
          clearInterval(pollingHandle);
          pollingHandle = null;
          window.GDF.state.applyAction(state, 'resumenListo', r);
          render();
          return;
        }
        if (intentos >= POLL_MAX_INTENTOS) {
          clearInterval(pollingHandle);
          pollingHandle = null;
          window.GDF.state.applyAction(state, 'resumenAgotado', {});
          render();
        }
      });
    }
    intentar();
    pollingHandle = setInterval(intentar, POLL_INTERVALO_MS);
  }

  // POST /recomendaciones. Se usa igual en la primera carga y al reintentar.
  function cargarRecomendaciones() {
    window.GDF.state.applyAction(state, 'recoCargando', {});
    render();
    window.GDF.recommender.recomendar(state, function (resultado) {
      window.GDF.state.applyAction(state, 'recoResuelta', resultado);
      render();
    });
  }

  // Salida de emergencia cuando el backend no responde: se muestran los
  // proyectos del catálogo local marcados como aproximados. Nunca se hace en
  // silencio — `aproximado: true` pinta un aviso permanente en la lista.
  function usarLocalAproximado() {
    window.GDF.recommender.recomendarLocal(state.answers, function (resultado) {
      window.GDF.state.applyAction(state, 'recoResuelta', resultado);
      render();
    });
  }

  // AQUI SE ENVIABA EL LEAD, en el sentido del backend anterior (contrato de
  // dos pasos: /recomendaciones daba un lead_id y /leads lo registraba). Ese
  // contrato no vuelve — el modelo de recomendación no registra leads — pero
  // dispararLlamada() de arriba SÍ es un envío real, solo que a otro backend
  // (api.py, ver js/llamada.js), y con otro propósito: no registrar, sino
  // marcar el teléfono. La pantalla de cierre relata su estado de verdad,
  // no un texto fijo. Ver confirmacion() en templates.js.

  // Busca la tarjeta del proyecto por nombre. Se usa el nombre y no el índice
  // porque el orden de la lista puede cambiar (clustering).
  function cardDe(nombreProyecto) {
    var cards = root.querySelectorAll('.gdf-project-detalle');
    for (var i = 0; i < cards.length; i++) {
      if (cards[i].dataset.proyecto === nombreProyecto) return cards[i];
    }
    return null;
  }

  // Cambio de pestaña Tipo A / Tipo B: solo mueve la clase .active entre los
  // botones y entre los paneles de ESA tarjeta.
  function updateTipologiaDOM(ds) {
    var card = cardDe(ds.proyecto);
    if (!card) return;
    var idx = String(parseInt(ds.idx, 10) || 0);

    var tabs = card.querySelectorAll('.gdf-tipo-tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.toggle('active', tabs[i].dataset.idx === idx);
    }
    var panels = card.querySelectorAll('.gdf-tipo-panel');
    for (var j = 0; j < panels.length; j++) {
      panels[j].classList.toggle('active', panels[j].dataset.panel === idx);
    }
  }

  // -------------------------------------------------------------------------
  // Quiz: avanzar de pregunta sin reconstruir la escena
  // -------------------------------------------------------------------------

  /**
   * El panel de la pregunta SÍ se repinta entero (no tiene nada que preservar);
   * la escena se parchea nodo a nodo para que las piezas ya pintadas se muevan
   * en vez de volver a caer.
   */
  function updateQuizDOM() {
    var derived = window.GDF.state.computeDerived(state);
    var panel = root.querySelector('.gdf-quiz');
    // La losa y la silueta existen desde antes de la primera respuesta y no se
    // van ni retrocediendo hasta el principio, así que a mitad del quiz nunca
    // hace falta reconstruir la escena por innerHTML.
    if (!panel) return render();
    panel.outerHTML = window.GDF.templates.quizPanel(state, derived);
    // IMPRESCINDIBLE: el panel nuevo trae nodos nuevos. Sin volver a enganchar,
    // mueren el input numérico de 'edad' (pregunta 4) y el buscador con chips
    // de 'entorno_deseado' (la 8), y el fallo es silencioso hasta que alguien
    // llega hasta ahí.
    attachInputListeners();
    updatePlantaDOM(derived);
    updateEscenaExtrasDOM(derived);
    updateMapaDOM(derived);
  }

  /**
   * Pone o quita el mapa del lienzo segun la pregunta en la que se este.
   *
   * Es una operacion QUIRURGICA sobre un solo nodo, igual que la que hace
   * updateEscenaExtrasDOM con `.gdf-halo`: no toca `.gdf-losa` ni los
   * `.gdf-room`, asi que la escena nunca se reconstruye por innerHTML.
   *
   * El orden importa en los dos sentidos:
   *   - al quitarlo, `desmontar()` va ANTES de sacar el nodo del DOM. Al reves,
   *     Leaflet se queda con listeners sobre un nodo huerfano y la siguiente
   *     vuelta a esta pregunta falla con "Map container is already initialized".
   *   - al ponerlo, primero el nodo y despues `montar()`, que necesita medirlo.
   */
  function updateMapaDOM(derived) {
    if (!window.GDF.mapa) return;
    var escena = root.querySelector('.gdf-scene');
    if (!escena) return;
    var toca = !!(derived.q && derived.q.escena === 'mapa');
    var nodo = document.getElementById('zonaMapa');

    if (toca && !nodo) {
      // Caso updateQuizDOM: se llega a la pregunta desde otra y el nodo no
      // existe todavia, porque la escena no se repinta.
      escena.insertAdjacentHTML('beforeend', '<div class="gdf-mapa-real" id="zonaMapa"></div>');
      window.GDF.mapa.montar(document.getElementById('zonaMapa'), elegirZonaDesdeMapa);
      sincronizarZona();
    } else if (toca && nodo && !window.GDF.mapa.montado()) {
      // Caso render completo: sceneBlock ya emitio el nodo, pero vacio.
      window.GDF.mapa.montar(nodo, elegirZonaDesdeMapa);
      // DESPUES de montar, no antes: `marcar()` sobre un mapa que aun no
      // existe no pinta nada, y este es el camino por el que se vuelve a la
      // pregunta con las zonas ya elegidas.
      sincronizarZona();
    } else if (!toca && nodo) {
      window.GDF.mapa.desmontar();
      nodo.remove();
    }
  }

  // Lo que ocurre al tocar una zona en el mapa. Se separa en una funcion con
  // nombre porque se le pasa a js/mapa.js como callback y conviene que en un
  // stack trace se lea de donde sale.
  //
  // El mapa manda las DOS cosas: la localidad, que es lo que entiende el
  // modelo, y el barrio que hay bajo el dedo, que es lo que la persona cree
  // que esta tocando. `barrio` viene null donde no hay sector catastral
  // —huecos entre barrios, zona rural—, y ahi vale la localidad sola.
  // `bi` es la posicion del sector dentro de su localidad y solo existe por
  // esta via: el mapa sabe exactamente cual toco el dedo. Ver el comentario de
  // `alternarZonaValor`.
  function elegirZonaDesdeMapa(nombre, barrio, bi) {
    alternarZonaValor(nombre, barrio, bi);
  }

  /**
   * Lo que rodea a la planta y tampoco puede repintarse por innerHTML sin
   * matar la escena: la altura según el piso, el nombre de la localidad y el
   * halo con las zonas comunes reales del proyecto.
   */
  function updateEscenaExtrasDOM(derived) {
    var escena = root.querySelector('.gdf-scene');
    if (!escena) return;
    var planta = derived.planta;
    var a = state.answers || {};

    if (a.piso_preferido) escena.dataset.piso = a.piso_preferido;
    else delete escena.dataset.piso;

    // El halo solo existe una vez contestada la pregunta de entorno.
    var halo = escena.querySelector('.gdf-halo');
    var htmlHalo = a.entorno_deseado ? window.GDF.templates.haloAmenidadesHtml(planta, a) : '';
    if (halo && halo.parentNode) halo.parentNode.removeChild(halo);
    if (htmlHalo) {
      var losa = escena.querySelector('.gdf-losa');
      if (losa) losa.insertAdjacentHTML('afterend', htmlHalo);
      else escena.insertAdjacentHTML('beforeend', htmlHalo);
    }
  }

  /**
   * Casa las piezas pintadas con las que toca mostrar, por `data-room`:
   *   - la que no existía -> cae de la grúa (.animated)
   *   - la que ya estaba  -> se deja quieta (solo se le quita .animated)
   *   - la que sobra      -> se la lleva la grúa (.saliendo) y queda el hueco
   */
  function updatePlantaDOM(derived) {
    // Primero y sin condiciones: el 3D no depende de la losa 2D de abajo ni
    // de en cual de sus ramas entra esta funcion (cambio de plano, armado en
    // curso, pieza nueva...). Si se dejara solo al final, un cambio de plano
    // -que corta por `cambiarDePlano` y retorna antes- se perderia.
    updatePlano3D(derived);

    var losa = root.querySelector('.gdf-losa');
    if (!losa) return;

    // Mientras se esta retirando el plano anterior no se toca nada: quien
    // levanta el nuevo es `reconstruirPlano` al terminar, releyendo el estado
    // de ESE momento. Si el usuario contesta otra vez durante el cambio, lo
    // que se levanta es el plano que toca entonces y no uno caducado.
    if (losa.dataset.cambiando) return;
    // Mientras se arma el plano nuevo, lo unico que puede interrumpir es otro
    // CAMBIO de plano (que derriba y vuelve a empezar). El resto —altas y bajas
    // de piezas— lo lleva el propio armado.
    if (losa.dataset.construyendo && derived.planta &&
        losa.dataset.sello === derived.planta.sello) return;

    if (derived.planta && losa.dataset.sello !== derived.planta.sello) {
      cambiarDePlano(losa);
      return;
    }
    if (derived.planta && derived.planta.ajustada) {
      // Se contestó lo de las alcobas y el plano provisional YA las tenía, así
      // que no hay nada que reacomodar. Se anima igual: si no, la misma
      // respuesta unas veces mueve el plano y otras no hace nada, y se lee
      // como que la app se quedó colgada. Ver `ajustarPlantaAHabitaciones`.
      var puestas = losa.querySelectorAll('.gdf-room');
      for (var k = 0; k < puestas.length; k++) marcarReacomodo(puestas[k]);
    }

    var vivos = {};
    var nuevas = 0;
    derived.rooms.forEach(function (room) {
      vivos[room.id] = true;
      apagarHueco(losa, room.id, true);
      var el = losa.querySelector('[data-room="' + room.id + '"]');
      if (el) {
        // Ya estaba: se le quita .animated para que NO vuelva a caer de la
        // grúa. Su geometría no cambia nunca —el apartamento es fijo—, así que
        // no hay nada más que tocarle.
        el.classList.remove('animated');
        return;
      }
      losa.insertAdjacentHTML('beforeend', window.GDF.templates.cuartoHtml(room, true));
      // Escalonadas: cuando una respuesta destapa varias piezas caen una
      // detrás de otra en vez de todas de golpe.
      losa.lastElementChild.style.animationDelay = nuevas * 0.12 + 's';
      nuevas++;
    });

    var todos = losa.querySelectorAll('.gdf-room');
    for (var i = 0; i < todos.length; i++) {
      if (vivos[todos[i].dataset.room]) continue;
      retirarPieza(todos[i]);
      apagarHueco(losa, todos[i].dataset.room, false);
    }
  }

  /**
   * Enciende o apaga el hueco gris que hay DEBAJO de una pieza.
   *
   * Las piezas van en `mix-blend-mode: multiply` para que el papel blanco del
   * plano desaparezca contra el fondo de la escena (si no, las esquinas donde
   * el apartamento no llega se ven como bloques blancos, o sea como piezas que
   * faltan). Multiplicar contra el gris del hueco entintaría el plano entero,
   * así que el hueco se apaga en cuanto su pieza está puesta y se vuelve a
   * encender si la grúa se la lleva.
   */
  function apagarHueco(losa, id, apagar) {
    var hueco = losa.querySelector('.gdf-hueco[data-hueco="' + id + '"]');
    if (hueco) hueco.style.opacity = apagar ? '0' : '';
  }

  // Los planos pesan ~78 KB de media y hasta 240 KB. Se pide en cuanto se
  // elige el apartamento (al empezar el quiz) para que la primera pieza que
  // cae ya tenga la imagen decodificada y no aparezca en blanco.
  var planoPrecargado = null;
  function precargarPlano() {
    var src = state.planta && state.planta.plano;
    if (!src || src === planoPrecargado) return;
    planoPrecargado = src;
    var img = new Image();
    img.src = src;
  }

  // Cuanto tarda una pieza en irse. Tiene que cuadrar con `.gdf-room.saliendo`
  // en el CSS: si aqui fuera menos, `reconstruirPlano` vaciaria la losa con las
  // piezas viejas todavia a medio salir.
  var MS_RETIRADA = 300;
  // Las piezas del plano viejo no se van todas a la vez sino en barrido, para
  // que se lea como que la losa se despeja y no como un parpadeo.
  var MS_ENTRE_RETIRADAS = 35;

  var cambioTimer = null;
  var construccionTimers = [];

  /**
   * El plano cambio: se retira el anterior y se levanta el nuevo, pieza a
   * pieza.
   *
   * AQUI HABIA UNA BOLA DE DEMOLICION. Colgaba de una grua fuera de cuadro,
   * entraba por la izquierda, golpeaba el plano, la losa acusaba el impacto y
   * cada celda reventaba en esquirlas irregulares con su onda expansiva y su
   * nube de polvo. Se quito a peticion.
   *
   * Lo que SI se queda es el gesto contrario: el plano nuevo sigue llegando en
   * pedazos que convergen (`ensamblarPieza`). Por eso `trocear`, `esquirlasDe`
   * y `jitter` no se fueron con la bola — son la maquinaria de ARMAR, no la de
   * romper.
   *
   * OJO: cambiar de plano es la TRANSICION, no una resta. El numero de piezas
   * al terminar nunca es menor que antes; lo garantiza el suelo de
   * `scene.celdasVisibles`.
   */
  function cambiarDePlano(losa) {
    // Un armado a medias se cancela: sus temporizadores meterian piezas del
    // plano viejo encima del nuevo.
    construccionTimers.forEach(clearTimeout);
    construccionTimers = [];
    delete losa.dataset.construyendo;

    var piezas = [].slice.call(losa.querySelectorAll('.gdf-room'));
    if (!piezas.length) {
      // La losa esta vacia (el cambio que cae con la primera respuesta): no hay
      // nada que retirar, se levanta directamente.
      reconstruirPlano(losa);
      return;
    }

    losa.dataset.cambiando = '1';
    piezas.forEach(function (el, i) {
      setTimeout(function () { retirarPieza(el); }, i * MS_ENTRE_RETIRADAS);
    });
    // Los huecos grises NO se vuelven a encender aqui, a proposito: las piezas
    // que se van llevan `mix-blend-mode: multiply` y se multiplicarian contra
    // el gris, entintandolas mientras salen. `reconstruirPlano` repinta la
    // silueta entera al terminar, asi que la huella vuelve igual.

    clearTimeout(cambioTimer);
    cambioTimer = setTimeout(function () {
      delete losa.dataset.cambiando;
      reconstruirPlano(losa);
    }, (piezas.length - 1) * MS_ENTRE_RETIRADAS + MS_RETIRADA);
  }

  // Ruido determinista por pieza: mismo id -> mismo cascote, siempre. Sin esto
  // habria que usar Math.random() y el derribo no seria reproducible, que es
  // justo lo que hace imposible verificarlo.
  function jitter(id, sal) {
    var h = 2166136261;
    var s = String(id) + '|' + sal;
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
    }
    return (h % 1000) / 1000; // 0..1
  }

  /**
   * Trocea una celda en pedazos irregulares que TESELAN su rectangulo.
   *
   * Se toma un centro desplazado y un punto intermedio jitterado en cada lado;
   * de ahi salen cuatro cuadrilateros que cubren la celda entera sin huecos ni
   * solapes — el patron de un cristal agrietado. Con 2 pedazos se parte por la
   * diagonal jitterada.
   *
   * Los polignos se CRECEN un pelo desde su centro: en el borde compartido las
   * dos esquirlas pintan cobertura parcial y, con `multiply`, eso sale mas
   * oscuro que una pasada entera — se veia la cuadricula de cortes en el primer
   * fotograma. Es el mismo problema que la SANGRIA de geometriaCeldas, y la
   * misma solucion: solapar.
   */
  // Las esquirlas se SOLAPAN un pelo para tapar el antialiasing del corte. Ojo:
  // esto solo es seguro porque van dentro de `.gdf-cascotes`, que aisla la
  // mezcla. Con el `multiply` en cada esquirla, solapar multiplicaba dos veces
  // esa banda y la costura salia MAS oscura — mas solape, peor.
  var CRECE = 1.2;

  function poligono(pts) {
    // Centro del pedazo, para crecerlo hacia afuera desde ahi.
    var cx = 0, cy = 0;
    pts.forEach(function (q) { cx += q[0]; cy += q[1]; });
    cx /= pts.length;
    cy /= pts.length;
    return 'polygon(' + pts.map(function (q) {
      var vx = q[0] - cx, vy = q[1] - cy;
      var m = Math.sqrt(vx * vx + vy * vy) || 1;
      return (q[0] + (vx / m) * CRECE).toFixed(2) + '% ' + (q[1] + (vy / m) * CRECE).toFixed(2) + '%';
    }).join(', ') + ')';
  }

  function trocear(id, n) {
    var j = function (s) { return jitter(id, s); };
    if (n <= 2) {
      // Diagonal jitterada: dos mitades.
      var a = 30 + j('d1') * 40;
      var b = 30 + j('d2') * 40;
      return [
        poligono([[0, 0], [a, 0], [b, 100], [0, 100]]),
        poligono([[a, 0], [100, 0], [100, 100], [b, 100]]),
      ];
    }

    // Centro desplazado + un punto jitterado en cada arista: cuatro
    // cuadrilateros que TESELAN la celda entera. El patron de un cristal
    // agrietado.
    var cx = 50 + (j('cx') - 0.5) * 36;
    var cy = 50 + (j('cy') - 0.5) * 36;
    var tx = 30 + j('t') * 40;
    var ry = 30 + j('r2') * 40;
    var bx = 30 + j('b') * 40;
    var ly = 30 + j('l') * 40;
    var cuatro = [
      [[0, 0], [tx, 0], [cx, cy], [0, ly]],
      [[tx, 0], [100, 0], [100, ry], [cx, cy]],
      [[cx, cy], [100, ry], [100, 100], [bx, 100]],
      [[0, ly], [cx, cy], [bx, 100], [0, 100]],
    ];
    // Con 3 hay que FUSIONAR dos cuadrilateros contiguos, no devolver cuatro:
    // comparten la arista [tx,0]-[cx,cy], asi que su union sigue teselando la
    // celda exacta. Antes el 3 caia en la rama del 4 y se pedian 3 pedazos pero
    // salian 4 — en movil eso era un tercio mas de nodos de los previstos.
    if (n === 3) {
      return [
        poligono([[0, 0], [100, 0], [100, ry], [cx, cy], [0, ly]]),
        poligono(cuatro[2]),
        poligono(cuatro[3]),
      ];
    }
    if (n <= 4) return cuatro.map(poligono);

    // Para 5 o 6 se parten en dos los cuadrilateros mas grandes, por una
    // diagonal jitterada. Mas pedazos = se lee mas como algo que revienta,
    // pero hay que seguir teselando: por eso se PARTE uno existente en vez de
    // inventar geometria nueva.
    var area = function (q) {
      var s = 0;
      for (var i = 0; i < q.length; i++) {
        var a2 = q[i], b2 = q[(i + 1) % q.length];
        s += a2[0] * b2[1] - b2[0] * a2[1];
      }
      return Math.abs(s) / 2;
    };
    var orden = cuatro.slice().sort(function (a2, b2) { return area(b2) - area(a2); });
    var extra = n - 4;
    var salida = [];
    cuatro.forEach(function (q, k) {
      var idx = orden.indexOf(q);
      if (idx >= extra) {
        salida.push(poligono(q));
        return;
      }
      // Corte por la diagonal entre dos vertices opuestos, movida un poco.
      var f = 0.35 + j('p' + k) * 0.3;
      var m1 = [q[0][0] + (q[1][0] - q[0][0]) * f, q[0][1] + (q[1][1] - q[0][1]) * f];
      var m2 = [q[2][0] + (q[3][0] - q[2][0]) * f, q[2][1] + (q[3][1] - q[2][1]) * f];
      salida.push(poligono([q[0], m1, m2, q[3]]));
      salida.push(poligono([m1, q[1], q[2], m2]));
    });
    return salida;
  }

  /**
   * Sustituye una celda por sus esquirlas. Cada una es un CLON del room con un
   * `clip-path` distinto: hereda su posicion y su `.lienzo` tal cual, asi que no
   * hay que recalcular ni un offset de la imagen.
   *
   * Comprobado que `clip-path` NO rompe el `mix-blend-mode: multiply` — que era
   * el riesgo de todo esto, porque si lo rompiera volveria a verse el papel
   * blanco del plano (ver la seccion de templates.js en CLAUDE.md).
   */
  function esquirlasDe(room, n, bolsa) {
    var out = [];
    trocear(room.dataset.room, n).forEach(function (poly, k) {
      var c = room.cloneNode(true);
      c.classList.remove('animated', 'reacomodo');
      c.classList.add('esquirla');
      c.dataset.esquirla = k;
      c.style.clipPath = poly;
      c.style.webkitClipPath = poly;
      bolsa.appendChild(c);
      out.push(c);
    });
    room.remove();
    return out;
  }

  /**
   * La bolsa donde vuelan los cascotes.
   *
   * Existe por el `mix-blend-mode: multiply`. Si cada esquirla se mezclara por
   * su cuenta, las bandas donde dos se solapan se multiplicarian DOS veces y
   * saldria una costura oscura marcando cada corte. Metiendolas en un
   * contenedor con `isolation: isolate` + `multiply`, entre ellas componen
   * normal y el grupo entero se multiplica UNA vez contra la losa — que es lo
   * que sigue haciendo desaparecer el papel blanco del plano.
   *
   * Va con `inset: 0`, asi que es del tamano de la losa y los % de posicion de
   * las esquirlas siguen resolviendo igual.
   */
  function bolsaDeCascotes(losa) {
    var vieja = losa.querySelector('.gdf-cascotes');
    if (vieja) vieja.remove();
    var bolsa = document.createElement('div');
    bolsa.className = 'gdf-cascotes';
    losa.appendChild(bolsa);
    return bolsa;
  }

  // Cuanto se espera entre pieza y pieza al levantar el plano nuevo. Con 0.06 s
  // las 12 caian en 0.7 s y se leia como que aparecian todas de golpe; con 0.13
  // el armado dura 1.6 s y se ve pieza por pieza.
  var MS_ENTRE_PIEZAS = 130;
  // Lo que tarda una pieza en ARMARSE desde sus pedazos. Tiene que cuadrar con
  // `roomEnsambla` en el CSS.
  var MS_ENSAMBLA = 700;
  // En cuantos pedazos llega cada pieza. Menos que al romperse: al construir
  // solo hay una pieza armandose a la vez, pero el gesto tiene que leerse sin
  // llenar la escena de nodos.
  var ESQUIRLAS_ENSAMBLA = 6;

  /**
   * Una pieza del plano nuevo llega EN PEDAZOS y se arma sola.
   *
   * Es el gesto inverso del derribo, y por eso usa la misma maquinaria:
   * `trocear` + `esquirlasDe`. Los pedazos aparecen dispersos —cada uno con su
   * `--dx/--dy/--rot` de PARTIDA, no de llegada— y convergen a su sitio. Al
   * terminar se retiran y entra la pieza entera: mantener 12 celdas x 4
   * pedazos vivos el resto del quiz seria tirar nodos a la basura, y ademas el
   * derribo siguiente tiene que poder trocear una pieza, no un puzzle ya roto.
   */
  function ensamblarPieza(losa, room, estrecha) {
    var bolsa = losa.querySelector('.gdf-cascotes') || bolsaDeCascotes(losa);

    // Pieza de partida solo para clonarla en pedazos; `esquirlasDe` la retira.
    var tmp = document.createElement('div');
    tmp.innerHTML = window.GDF.templates.cuartoHtml(room, false);
    var base = tmp.firstElementChild;
    bolsa.appendChild(base);

    var trozos = esquirlasDe(base, estrecha ? 2 : ESQUIRLAS_ENSAMBLA, bolsa);
    trozos.forEach(function (el, k) {
      var sal = room.id + '@' + k;
      // De donde VIENE cada pedazo: repartidos alrededor, no todos del mismo
      // sitio, para que se lea como que se juntan.
      var ang = (k / trozos.length) * Math.PI * 2 + jitter(sal, 'a') * 1.4;
      var dist = 90 + jitter(sal, 'd') * 70;
      el.style.setProperty('--dx', Math.round(Math.cos(ang) * dist) + 'px');
      el.style.setProperty('--dy', Math.round(Math.sin(ang) * dist - 60) + 'px');
      el.style.setProperty('--rot', Math.round((jitter(sal, 'r') - 0.5) * 90) + 'deg');
      el.classList.add('ensamblando');
    });

    construccionTimers.push(setTimeout(function () {
      trozos.forEach(function (el) { el.remove(); });
      if (!losa.isConnected) return;
      // Si la pieza ya esta puesta no se duplica. Puede pasar si algo repinto
      // la escena mientras esta se armaba.
      if (!losa.querySelector('.gdf-room[data-room="' + room.id + '"]:not(.esquirla)')) {
        losa.insertAdjacentHTML('beforeend', window.GDF.templates.cuartoHtml(room, false));
      }
      apagarHueco(losa, room.id, true);
    }, MS_ENSAMBLA));
  }

  /**
   * Levanta el plano nuevo de cero, UNA PIEZA A LA VEZ y cada una armandose
   * desde sus pedazos.
   *
   * Relee el estado AHORA (no el `derived` de cuando empezo el derribo) para
   * que contestar durante la animacion no levante un plano ya caducado.
   *
   * OJO CON LA SILUETA: `siluetaHtml(huecos, rooms)` apaga de golpe el hueco
   * gris de TODAS las piezas del plano nuevo. Con las piezas llegando
   * escalonadas eso dejaba, durante mas de un segundo, celdas sin hueco y sin
   * pieza — o sea agujeros. Por eso aqui la silueta se pinta ENTERA (sin
   * `rooms`) y cada hueco se apaga cuando SU pieza acaba de armarse.
   */
  function reconstruirPlano(losa) {
    var derived = window.GDF.state.computeDerived(state);
    if (!derived.planta || !losa.isConnected) return;

    construccionTimers.forEach(clearTimeout);
    construccionTimers = [];

    losa.dataset.sello = derived.planta.sello;
    losa.style.setProperty('--ratio', derived.planta.ratio);
    losa.style.setProperty('--wmax', derived.planta.wmax + 'px');

    var escena = losa.closest('.gdf-scene');
    var estrecha = !!(escena && escena.clientWidth < 520);

    // Solo la silueta: las piezas entran despues, cada una a su hora.
    losa.innerHTML = window.GDF.templates.siluetaHtml(derived.huecos, []);

    // Mientras dura el armado, `updatePlantaDOM` no puede meter piezas por su
    // cuenta: veria la losa medio vacia, insertaria las que faltan y luego el
    // temporizador del armado insertaria LAS MISMAS otra vez. Se vieron 16
    // piezas en un plano de 12.
    losa.dataset.construyendo = '1';

    derived.rooms.forEach(function (room, i) {
      construccionTimers.push(setTimeout(function () {
        if (losa.isConnected) ensamblarPieza(losa, room, estrecha);
      }, i * MS_ENTRE_PIEZAS));
    });
    construccionTimers.push(setTimeout(function () {
      delete losa.dataset.construyendo;
    }, (derived.rooms.length - 1) * MS_ENTRE_PIEZAS + MS_ENSAMBLA + 40));
  }

  // La clase se quita al terminar para que la animación pueda volver a
  // dispararse si el plano cambiara otra vez.
  function marcarReacomodo(el) {
    el.classList.remove('reacomodo');
    void el.offsetWidth;
    el.classList.add('reacomodo');
    setTimeout(function () {
      el.classList.remove('reacomodo');
    }, 700);
  }

  function retirarPieza(el) {
    el.classList.remove('animated');
    el.classList.add('saliendo');
    setTimeout(function () {
      if (el.parentNode) el.parentNode.removeChild(el);
    }, 300);
  }

  function findQuestionById(qid) {
    var QUESTIONS = window.GDF.data.QUESTIONS;
    for (var i = 0; i < QUESTIONS.length; i++) {
      if (QUESTIONS[i].id === qid) return QUESTIONS[i];
    }
    return null;
  }

  function onRootClick(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;

    // 'noop' es el freno del burbujeo del <details> de planos de cada tarjeta:
    // un clic ahí dentro no debe despachar ninguna acción del estado.
    if (el.dataset.action === 'noop') {
      if (el.tagName === 'A') e.preventDefault();
      return;
    }

    // Acciones que hacen I/O: no pasan por applyAction/dispatch porque no son
    // un cambio de estado puro, sino el disparo de una llamada de red.
    if (el.dataset.action === 'reintentarReco') {
      cargarRecomendaciones();
      return;
    }
    if (el.dataset.action === 'usarLocalAproximado') {
      usarLocalAproximado();
      return;
    }

    // Mover la tira de planos. HACEN FALTA FLECHAS, no basta el `overflow-x`:
    // cada lámina es un <a> —abre la imagen a tamaño completo— así que
    // arrastrarla inicia un arrastre de enlace en vez de un desplazamiento, y
    // la barra va oculta a propósito. En un ratón sin rueda horizontal no
    // había NINGUNA forma de ver el plano 2 de 3.
    if (el.dataset.action === 'planoMover') {
      e.preventDefault();
      e.stopPropagation();
      var tira = el.closest('.gdf-planos');
      tira = tira && tira.querySelector('.gdf-planos-strip');
      if (tira) {
        var paso = tira.clientWidth || 320;
        tira.scrollBy({ left: el.dataset.value === 'sig' ? paso : -paso, behavior: 'smooth' });
      }
      return;
    }

    // Las preguntas 'number'/'text' del quiz no tienen data-value estático
    // (dependen de lo que el usuario tipeó): se lee el input al vuelo y se
    // reusa 'selectOption', que ya sabe avanzar/calificar sin cambios.
    if (el.dataset.action === 'answerQuizNumber') {
      var numInput = document.getElementById('quizNumberInput');
      var q = findQuestionById(el.dataset.qid);
      var n = numInput ? Number(numInput.value) : NaN;
      var valid = numInput && numInput.value !== '' && !isNaN(n) && (!q || (n >= q.min && n <= q.max));
      if (!valid) return;
      dispatch('selectOption', { qid: el.dataset.qid, value: String(Math.round(n)) });
      return;
    }
    if (el.dataset.action === 'answerQuizText') {
      var txtInput = document.getElementById('quizTextInput');
      dispatch('selectOption', { qid: el.dataset.qid, value: txtInput ? txtInput.value.trim() : '' });
      return;
    }
    // 'entorno_deseado' se responde con el buscador con chips de arriba
    // (selección no controlada, igual que los inputs de texto — ver
    // `entornoSeleccion`). Al continuar se despacha ese arreglo tal cual: son
    // las etiquetas `v` exactas que espera el backend (ver data.js), no se
    // aplanan a texto ni se traducen al `label`.
    if (el.dataset.action === 'answerQuizMultiselect') {
      dispatch('selectOption', { qid: el.dataset.qid, value: entornoSeleccion.slice() });
      return;
    }
    if (el.dataset.action === 'toggleEntorno' || el.dataset.action === 'quitarEntorno') {
      toggleEntornoValor(el.dataset.value);
      return;
    }
    // 'zona': tocar el mapa o elegir un barrio del buscador. NO avanza de
    // pregunta —solo agrega a la selección y pone de acuerdo los controles—;
    // se compromete al pulsar Continuar, abajo. Con varias zonas esto importa
    // más que antes: autoavanzar al primer clic haría imposible pedir dos.
    if (el.dataset.action === 'elegirZona') {
      // El polígono exacto de la sugerencia (ver `renderZonaSugerencias`).
      // Sin él —los 20 nombres de localidad— se pinta la localidad sola.
      var bi = el.dataset.bi === undefined ? null : parseInt(el.dataset.bi, 10);
      alternarZonaValor(el.dataset.loc, el.dataset.barrio, bi);
      // Solo desde el buscador se mueve el mapa. Al tocar una zona no: la
      // persona ya esta mirando donde toco, y recentrarle la vista debajo del
      // dedo se siente como si el mapa se le escapara.
      //
      // Y vuela al BARRIO cuando lo hay, no a la localidad entera: quien
      // escribio "Cedritos" quiere ver Cedritos, no Usaquen.
      if (window.GDF.mapa) window.GDF.mapa.volarA(el.dataset.loc, el.dataset.barrio, bi);
      return;
    }
    // Una fila de LUGAR del mismo desplegable. Mismo destino que `elegirZona`
    // —la selección de zonas es una sola— pero pasando además el nombre del
    // lugar, que es lo que dirá el chip.
    if (el.dataset.action === 'elegirLugar') {
      var biL = el.dataset.bi === '' ? null : parseInt(el.dataset.bi, 10);
      alternarZonaValor(el.dataset.loc, el.dataset.barrio || null, biL, el.dataset.lugar);
      if (window.GDF.mapa) window.GDF.mapa.volarA(el.dataset.loc, el.dataset.barrio || null, biL);
      // El campo se vacía y el desplegable se cierra en sincronizarZona(), que
      // es el mismo camino que sigue un barrio: la lista es una sola.
      return;
    }
    // La × de un chip. Quita siempre, sin importar de qué buscador salió.
    if (el.dataset.action === 'quitarZona') {
      quitarZonaValor(el.dataset.loc, el.dataset.barrio || null);
      return;
    }
    if (el.dataset.action === 'answerQuizZona') {
      if (!zonaSeleccion.length) return;
      // Los sectores se guardan aparte de `answers`: es solo para poder decir
      // "Cedritos · Usaquén" en la ficha, y el catálogo no indexa por barrio.
      state.zonaSectores = zonaSeleccion.slice();
      // `zonaBarrio` se conserva —lo leen templates.js y la ficha— con el
      // barrio de la PRIMERA zona: es la que también acaba en `answers.zona`.
      state.zonaBarrio = zonaSeleccion[0].barrio;
      // TODAS las localidades pedidas, sin repetir, para el modelo. Va dentro
      // de `answers` porque es lo que reciben matching.js y leadify.js, y no
      // cuenta como una pregunta más: computeDerived() filtra por id de
      // pregunta, no por las llaves de `answers`.
      var nombresLoc = [];
      zonaSeleccion.forEach(function (sector) {
        if (nombresLoc.indexOf(sector.localidad) < 0) nombresLoc.push(sector.localidad);
      });
      state.answers.zonas = nombresLoc;
      dispatch('selectOption', { qid: el.dataset.qid, value: nombresLoc[0] });
      return;
    }

    dispatch(el.dataset.action, el.dataset);
  }

  // Cierra el panel de opciones de 'entorno_deseado' al tocar fuera de él
  // (patrón típico de combobox). Registrado UNA sola vez a nivel de
  // documento — si viviera en attachInputListeners() se duplicaría en cada
  // render y se acumularían listeners fantasma. Comprueba los IDs en cada
  // clic porque el <input>/panel solo existen mientras esa pregunta está en
  // pantalla; en cualquier otra pantalla no hace nada.
  function cerrarEntornoSiTocaAfuera(e) {
    // SE RECORREN TODOS LOS COMBOS, no el primero. Hoy nunca hay más de uno en
    // pantalla —la pregunta de zona tuvo dos pestañas y volvió a un solo
    // buscador—, pero el recorrido se queda: con `querySelector` a secas, el
    // día que vuelva a haber dos el desplegable del segundo no se cerraría
    // nunca al tocar afuera, y es un fallo que ya ocurrió una vez. Cada combo
    // cierra su propia lista; no hace falta saber cuál es.
    var combos = document.querySelectorAll('.gdf-entorno-combo');
    for (var i = 0; i < combos.length; i++) {
      if (combos[i].contains(e.target)) continue;
      var lista = combos[i].querySelector('.gdf-multi-opt-list');
      if (lista) lista.classList.remove('abierto');
    }
  }

  function boot() {
    root = document.getElementById('root');
    root.addEventListener('click', onRootClick);
    document.addEventListener('click', cerrarEntornoSiTocaAfuera);
    // El fondo AI Signal. Va ANTES del primer render y una sola vez: cuelga
    // del <body>, así que los re-renders de #root no lo tocan y la red sigue
    // corriendo igual al pasar de la escarapela al quiz. Se monta solo con la
    // marca Leadify (ver senal.js).
    if (window.GDF.senal) window.GDF.senal.montar();
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
