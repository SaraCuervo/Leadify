// El mapa real de Bogotá de la primera pregunta. Leaflet + teselas de
// OpenStreetMap a color y sin filtros encima, con las 20 localidades como
// polígonos clicables y los 1.230 barrios debajo como datos: un clic en
// cualquier punto resuelve el barrio que hay ahí y lo pinta.
//
// POR QUE ESTE MODULO EXISTE Y NO ES UNA FUNCION MAS DE main.js
// -------------------------------------------------------------
// Es el PRIMER componente del quiz con vida propia: un objeto de Leaflet que
// hay que crear una vez y MATAR de verdad al salir de la pregunta. Todo lo
// demás en este front es HTML que se repinta; esto no. Si se quita el nodo sin
// llamar a `desmontar()`, Leaflet se queda con listeners sobre un nodo
// huérfano, y al ir y volver con "Atrás" se acumulan instancias hasta que la
// consola escupe "Map container is already initialized".
//
// `js/senal.js` es lo más parecido que había —canvas, referencias en ámbito de
// módulo, resize con rebote— pero se monta una vez y vive para siempre, así
// que no servía de molde para la parte de morir.
//
// LOS DATOS SON GENERADOS. `window.GDF_MAPA` y `window.GDF_BARRIOS_GEO` salen
// de tools/generar_mapa.py: los anillos en [lon, lat] listos para GeoJSON, un
// punto interior por localidad y los dos encuadres. Aquí no se calcula
// geometría, solo se pregunta por ella.
//
// LOS BARRIOS NO SON UNA CAPA DIBUJADA, y esa es la decisión de diseño de este
// archivo. Son 1.230 polígonos: pintarlos todos serían 1.230 <path> en el DOM,
// cada uno con su transición de CSS, y el mapa se arrastraría en móvil. En vez
// de eso viven como datos, el clic se resuelve con ray casting (`barrioEn`) y
// solo se dibujan DOS: el que está bajo el cursor y el elegido. En el DOM hay
// 22 paths: las 20 localidades, el resaltado del hover y el de la selección.
//
// EL RATON SEÑALA BARRIOS, NUNCA LOCALIDADES. Ni el globo de texto ni el
// resaltado nombran la localidad en ningún momento: se enciende el contorno
// del sector que hay debajo y su nombre, y donde no hay sector no se enciende
// nada. Señalar la localidad era encender 100 km² de Suba para decir dónde
// está el cursor, y repetir un dato que ya se lee bajo el buscador.
//
// NO SE OSCURECE LO QUE NO ES BOGOTA, y se intentó. Un polígono del tamaño del
// mundo con el Distrito recortado como agujero dejaba la ciudad como una
// calcomanía pegada sobre un fondo apagado —lo contrario de un mapa de calles—
// y además se le veían las costuras: los contornos de las localidades vienen
// simplificados a unos 38 m, así que donde el límite real es muy dentado (el
// río Bogotá al occidente, el borde norte de Suba) quedaba una franja negra
// entre el contorno simplificado y el límite de verdad. Que el mapa siga
// siendo un mapa fuera de Bogotá no estorba: lo que mantiene la atención
// dentro es que solo las localidades son clicables, y que `maxBounds` y
// `minZoom` no dejan irse a pasear.
//
// LA RUEDA DEL RATON SI HACE ZOOM. Antes iba apagada porque el quiz vive
// dentro de un iframe en un modal, y la rueda capturada podía atrapar a quien
// solo quería bajar por la página. Se prefiere el zoom fácil de un mapa
// normal: quien entra al mapa ya está DENTRO del modal, con scroll propio
// aparte, así que la rueda no compite con nada.
//
// Y NO SE PUEDE SALIR DE BOGOTA: `maxBounds` al Distrito entero, y `minZoom`
// calculado para que lo más lejos que se pueda ir sea justo el Distrito
// completo, Sumapaz incluida. Un mapa del mundo en una pregunta que solo
// admite 20 respuestas es una invitación a pasear por Berlín.
(function () {
  'use strict';

  // Teselas de OpenStreetMap, SIN filtro de color encima.
  //
  // SE PROBO EL MAPA BASE DE IDECA Y NO SIRVE PARA ESTO. El del Distrito tiene
  // Bogotá con muchísimo detalle, pero fuera de la ciudad no dibuja nada: pinta
  // un gris plano. Como la vista abre con la ciudad entera y sobra aire a los
  // lados —Bogotá es alta y angosta—, la ciudad quedaba como una calcomanía
  // clara pegada sobre un fondo apagado. OSM dibuja Cundinamarca con el mismo
  // criterio que Bogotá, así que el mapa se ve como un mapa en todas partes.
  //
  // Y NO LLEVA `filter` EN EL CSS. El que tenía —brightness(0.72)
  // saturate(0.75)— era lo que lo volvía gris y apagado; se quitó a propósito
  // (ver .gdf-mapa-real en css/styles.css).
  var TESELAS = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  // Requisito de la licencia de OpenStreetMap: la atribución va visible.
  var ATRIBUCION =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

  var mapa = null;
  var capa = null;
  var capasBarrio = [];    // un polígono por sector elegido (se pueden pedir varios)
  var porNombre = {};      // nombre de localidad -> capa de Leaflet
  var idPorNombre = {};    // nombre de localidad -> id 1..20
  // id de localidad -> { clave normalizada de barrio -> barrio }.
  //
  // ESTA INDEXADO POR LOCALIDAD Y NO POR CLAVE SUELTA, y es la diferencia
  // entre que el resaltado funcione o no. Los nombres de sector catastral se
  // REPITEN por toda la ciudad: 46 claves existen en dos o más localidades
  // ("Lisboa" está en Usaquén y en Suba, "Las Acacias" en Chapinero, Kennedy y
  // Ciudad Bolívar, "El Paraíso" en tres). Con un índice global el primero que
  // se cargaba se quedaba con la clave, y al tocar cualquiera de los otros el
  // resaltado no aparecía: la búsqueda devolvía el de la localidad equivocada
  // y `barrioPorNombre` lo descartaba por no coincidir. Con un índice por
  // localidad cada uno encuentra el suyo.
  var porLoc = {};
  var marcadas = [];       // nombres de las localidades con algo elegido dentro
  var capaHover = null;    // el contorno del barrio bajo el cursor
  var hoverActual = null;  // qué barrio pinta `capaHover`, para no repintarlo
  var alRedimensionar = null;
  var remedir = null;
  var ultimoHover = 0;

  function quieto() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  // La misma normalización que `catalogos.normalizar_texto`, que es con la que
  // el generador escribió las claves: minúsculas, sin tildes, y los signos de
  // separación como espacios. No vale la de main.js, que es más corta porque
  // allí solo limpia lo que teclea la persona.
  function clave(texto) {
    return (texto || '')
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[_\-.\/]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  // Las 6 localidades sin un solo proyecto se pintan apagadas. El conteo lo
  // arma data.js desde el catálogo del tenant, así que si mañana una
  // constructora publica en Tunjuelito, deja de estar apagada sola.
  function sinOferta(nombre) {
    var oferta = (window.GDF.data && window.GDF.data.OFERTA) || {};
    return !oferta[nombre];
  }

  // El aspecto vive en css/styles.css, no aquí: se le cuelga una clase a cada
  // polígono y el CSS hace el resto. Así la paleta sigue saliendo de los
  // tokens de marca que tema.js reescribe por constructora, en vez de quedar
  // congelada en colores dentro del JS.
  function claseDe(nombre) {
    return 'gdf-zona-poly' + (sinOferta(nombre) ? ' sin-oferta' : '');
  }

  function elementoDe(nombre) {
    var capaLoc = porNombre[nombre];
    return capaLoc && capaLoc.getElement ? capaLoc.getElement() : null;
  }

  // EL ROTULO NOMBRA EL BARRIO Y NADA MAS. Antes decía "Cedritos · Usaquén", y
  // sobre las zonas donde no hay sector catastral se quedaba con la localidad
  // sola — así que pasear el ratón por el mapa era ir viendo saltar el nombre
  // de la localidad, que es el dato que menos falta hace: la localidad se lee
  // debajo del buscador en cuanto se elige algo (ver `zonaEco` en
  // templates.js), y el aviso de "sin proyectos propios" también sale ahí.
  //
  // Lo que hace falta mientras el cursor se mueve es lo contrario: saber qué
  // barrio va a quedar elegido si se hace clic ahí. Sin barrio debajo no hay
  // rótulo — ver `mostrarHover`, que directamente esconde el globo.
  function rotulo(barrio) {
    return barrio ? barrio.n : '';
  }

  // --------------------------------------------------------------- barrios

  // Ray casting clásico sobre un anillo [[lon, lat], ...]. El mismo criterio
  // que `scraper_projects._punto_en_anillo` en Python, para que el mapa y el
  // catálogo no discrepen sobre dónde cae un punto.
  function puntoEnAnillo(x, y, anillo) {
    var dentro = false;
    var n = anillo.length;
    var j = n - 1;
    for (var i = 0; i < n; i++) {
      var xi = anillo[i][0], yi = anillo[i][1];
      var xj = anillo[j][0], yj = anillo[j][1];
      if ((yi > y) !== (yj > y)) {
        var corte = ((xj - xi) * (y - yi)) / (yj - yi) + xi;
        if (x < corte) dentro = !dentro;
      }
      j = i;
    }
    return dentro;
  }

  /**
   * El barrio que hay en (lng, lat) DENTRO de la localidad `idLoc`, o null.
   *
   * Se acota a una localidad porque ya se sabe cuál es —la dice la capa de
   * localidades, que es la autoritativa— y así el bucle mira 8 barrios en La
   * Candelaria o 134 en Ciudad Bolívar, nunca los 1.230. El `bb` de cada uno
   * descarta por rectángulo antes de entrar al ray casting, que es lo caro.
   *
   * Even-odd sobre todos los anillos: si el sector tiene un agujero, un punto
   * dentro del agujero NO cuenta como dentro del barrio.
   */
  function barrioEn(lng, lat, idLoc) {
    var lista = (window.GDF_BARRIOS_GEO || {})[idLoc] || [];
    for (var i = 0; i < lista.length; i++) {
      var b = lista[i];
      if (lng < b.bb[0] || lng > b.bb[2] || lat < b.bb[1] || lat > b.bb[3]) continue;
      var dentro = false;
      for (var k = 0; k < b.a.length; k++) {
        if (puntoEnAnillo(lng, lat, b.a[k])) dentro = !dentro;
      }
      if (dentro) return b;
    }
    return null;
  }

  /**
   * La localidad que contiene un punto, o null si cae fuera de Bogotá.
   *
   * Es el mismo ray casting de `barrioEn`, pero sobre las 20 localidades de
   * `GDF_MAPA` en vez de los sectores de una sola. Se separa en dos pasos —
   * primero localidad, después barrio— por lo mismo que el clic real sobre
   * el mapa: LOS LÍMITES DE LA LOCALIDAD SON LOS OFICIALES y son los que el
   * modelo entiende; el contorno del barrio está simplificado y en el borde
   * puede caer al otro lado. Deducir la localidad del barrio que contenga el
   * punto daría la respuesta equivocada justo en las fronteras.
   *
   * Even-odd sobre los anillos, igual que en `barrioEn`: Santa Fe trae La
   * Candelaria como agujero, y un punto en La Candelaria NO es de Santa Fe.
   *
   * Son 20 polígonos, así que no hace falta descartar por bbox antes: el
   * bucle completo cuesta menos que mantener esa tabla al día.
   */
  function localidadEnPunto(lng, lat) {
    var lista = (window.GDF_MAPA || {}).localidades || [];
    for (var i = 0; i < lista.length; i++) {
      var anillos = lista[i].anillos || [];
      var dentro = false;
      for (var k = 0; k < anillos.length; k++) {
        if (puntoEnAnillo(lng, lat, anillos[k])) dentro = !dentro;
      }
      if (dentro) return lista[i];
    }
    return null;
  }

  /**
   * (lng, lat) -> `{localidad, barrio, bi}`, la MISMA forma que produce un
   * clic real sobre el mapa. `null` si el punto no cae en ninguna de las 20
   * localidades, que es como se descartan los lugares de Chía o Soacha que
   * devuelve el buscador en vivo.
   *
   * `barrio`/`bi` vienen en null cuando el punto cae dentro de la localidad
   * pero fuera de todo sector catastral (huecos entre sectores, zona rural).
   * No es un fallo: es el mismo caso que ya maneja el clic en un hueco, y
   * aguas abajo vale la localidad sola.
   */
  function zonaEnPunto(lng, lat) {
    var loc = localidadEnPunto(lng, lat);
    if (!loc) return null;
    var b = barrioEn(lng, lat, loc.id);
    // `_i` lo escribe `montar()`, así que sin mapa montado todavía no está.
    // Se recalcula de la propia lista en vez de devolver un `bi` nulo: esta
    // función tiene que dar el mismo resultado se haya montado el mapa o no.
    var bi = null;
    if (b) {
      bi = b._i != null ? b._i : (window.GDF_BARRIOS_GEO || {})[loc.id].indexOf(b);
      if (bi < 0) bi = null;
    }
    return { localidad: loc.nombre, barrio: b ? b.n : null, bi: bi };
  }

  // Área con signo de un anillo [lon, lat] (fórmula del cordón). Los datos
  // vienen de Esri JSON, donde el contorno exterior va en sentido HORARIO
  // (área negativa en lon/lat) y los agujeros en antihorario.
  function areaAnillo(anillo) {
    var s = 0;
    for (var i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
      s += (anillo[j][0] * anillo[i][1]) - (anillo[i][0] * anillo[j][1]);
    }
    return s / 2;
  }

  // Los anillos [lon, lat] del generador, en la forma que quiere L.polygon:
  // `[[exterior, agujero, ...], [exterior2, ...]]`, es decir un MultiPolygon
  // en [lat, lng].
  //
  // NO SE PASAN LOS ANILLOS PLANOS. `L.polygon([a1, a2, a3])` toma el primero
  // como contorno y TODOS los demás como agujeros, así que un sector en dos
  // partes (El Paraíso, Tibaque Urbano, los Mochuelo...) pintaba la segunda
  // parte como un hueco. Se agrupan por orientación: cada anillo horario abre
  // un polígono nuevo y los antihorarios son agujeros del anterior.
  function aLatLng(anillos) {
    var poligonos = [];
    anillos.forEach(function (anillo) {
      var latlngs = anillo.map(function (p) { return [p[1], p[0]]; });
      if (areaAnillo(anillo) < 0 || !poligonos.length) {
        poligonos.push([latlngs]);
      } else {
        poligonos[poligonos.length - 1].push(latlngs);
      }
    });
    return poligonos;
  }

  function borrarBarrios() {
    if (mapa) {
      capasBarrio.forEach(function (capaB) {
        mapa.removeLayer(capaB);
      });
    }
    capasBarrio = [];
  }

  // Dibuja el barrio `b` como el polígono elegido. `interactive: false` es
  // imprescindible: Leaflet solo deja pasar el puntero por los paths que NO
  // son interactivos, y si este lo fuera taparía a la localidad de debajo, de
  // modo que el siguiente clic dentro del mismo barrio no llegaría a ninguna
  // parte y la selección se quedaría trabada.
  function pintarBarrio(b) {
    if (!b || !mapa) return;
    capasBarrio.push(
      window.L.polygon(aLatLng(b.a), {
        className: 'gdf-barrio-poly',
        interactive: false,
        noClip: true,
        weight: 2,
      }).addTo(mapa)
    );
  }

  // El barrio de nombre `nombre` dentro de `idLoc`, buscado por clave. Sirve
  // para el buscador de texto, que manda el nombre bonito y no el polígono.
  // Es el camino de RESPALDO: el buscador y el mapa mandan la posición exacta
  // (`bi`, ver `barrioPorIndice`) y solo caen aquí las selecciones antiguas
  // que la traen vacía. Devuelve null si ese nombre no tiene contorno.
  function barrioPorNombre(nombre, idLoc) {
    return (porLoc[idLoc] || {})[clave(nombre)] || null;
  }

  /**
   * El barrio que ocupa la posición `i` de la lista de `idLoc`.
   *
   * ES LA VIA EXACTA, y la que usan el mapa Y el buscador. El clic ya SABE qué
   * polígono hay bajo el dedo —`barrioEn` lo acaba de encontrar— y cada
   * sugerencia del buscador trae el suyo desde GDF_BARRIOS, así que buscar
   * por texto sería perder esa certeza por el camino: hay nombres que salen
   * dos veces DENTRO de una misma localidad (una celda de barrio de OSM y un
   * sector catastral que se llaman igual), donde ni saber la localidad
   * desempata.
   */
  function barrioPorIndice(idLoc, i) {
    var lista = (window.GDF_BARRIOS_GEO || {})[idLoc] || [];
    return lista[i] || null;
  }

  // ------------------------------------------------------------------ hover

  /**
   * Resalta el barrio bajo el cursor y le pone su nombre encima.
   *
   * EL RESALTADO ES DEL BARRIO, NO DE LA LOCALIDAD. Antes el `:hover` del CSS
   * teñía el polígono entero de la localidad, que en Suba son 100 km²: se
   * encendía media pantalla para señalar dónde estaba el ratón. Ahora se
   * dibuja el contorno del sector concreto, que es lo que el clic va a elegir.
   *
   * SE REUSA UNA SOLA CAPA. Crear y destruir un `L.polygon` en cada movimiento
   * dejaría a Leaflet añadiendo y quitando un `<path>` del DOM decenas de
   * veces por segundo; con `setLatLngs` se mueve el mismo. Y si el barrio no
   * cambió no se toca nada, que es el caso normal: el cursor recorre cientos
   * de píxeles dentro del mismo sector.
   */
  function mostrarHover(capaLoc, barrio) {
    if (barrio !== hoverActual) {
      hoverActual = barrio;
      if (capaHover && mapa) {
        // SE QUITA Y SE PONE LA CAPA; NO SE VACIA. Un `setLatLngs([])` sobre un
        // polígono que está en el mapa revienta dentro de Leaflet: al
        // reproyectar se queda sin `_rawPxBounds` y `_updateBounds` lee `.min`
        // de undefined. Y no revienta solo el resaltado — la excepción sube por
        // el manejador del evento y deja el mapa a medias. Con `removeLayer` el
        // polígono conserva sus vértices y el mapa no tiene que proyectar nada.
        if (!barrio) {
          mapa.removeLayer(capaHover);
        } else {
          capaHover.setLatLngs(aLatLng(barrio.a));
          if (!mapa.hasLayer(capaHover)) capaHover.addTo(mapa);
        }
      }
    }
    // El globo se esconde en vez de mostrar la localidad cuando no hay sector
    // debajo — huecos entre sectores, zona rural. Es `setOpacity` y no cerrar
    // el tooltip porque cerrarlo obliga a Leaflet a reabrirlo (y reposicionarlo)
    // en cuanto el cursor vuelva a entrar a un barrio, y eso se ve parpadear.
    var globo = capaLoc.getTooltip && capaLoc.getTooltip();
    if (!globo) return;
    // El contenido se reescribe SIEMPRE, también para vaciarlo: `setOpacity`
    // de Leaflet no solo cambia el elemento, también guarda el valor en
    // `options.opacity`, y esa opción es la que se reaplica en la siguiente
    // apertura. Sin vaciar el texto, entrar a una localidad nueva podía
    // asomar durante un instante el nombre del último barrio visitado.
    capaLoc.setTooltipContent(rotulo(barrio));
    globo.setOpacity(barrio ? 0.92 : 0);
  }

  function limpiarHover() {
    hoverActual = null;
    if (capaHover && mapa && mapa.hasLayer(capaHover)) mapa.removeLayer(capaHover);
  }

  // -------------------------------------------------------------- selección

  /**
   * Pinta la selección COMPLETA: `seleccion` es la lista de sectores elegidos,
   * `[{ localidad, barrio }, ...]`, y puede traer varios. Solo toca el mapa;
   * quien sincroniza buscador, chips y botón es main.js.
   *
   * SE REPINTA TODO EN VEZ DE APLICAR LA DIFERENCIA. Con una sola zona bastaba
   * con apagar la anterior y encender la nueva; con varias habría que llevar la
   * cuenta de cuál entró y cuál salió, y ese es justo el tipo de estado que se
   * desincroniza en silencio. Son 20 clases y un puñado de polígonos: repintar
   * cuesta nada y no puede quedar a medias.
   */
  function marcar(seleccion) {
    var lista = seleccion || [];
    marcadas.forEach(function (nombre) {
      var previo = elementoDe(nombre);
      if (previo) previo.classList.remove('sel');
    });
    marcadas = [];
    borrarBarrios();

    lista.forEach(function (sector) {
      var nombre = sector && sector.localidad;
      if (!nombre) return;
      var el = elementoDe(nombre);
      if (el) el.classList.add('sel');
      if (marcadas.indexOf(nombre) < 0) marcadas.push(nombre);
      // Un sector sin contorno —las UPZ del gazetteer— deja marcada su
      // localidad y no pinta polígono, igual que cuando había una sola.
      //
      // `bi` es la posición exacta y la manda el mapa; el buscador de texto no
      // la tiene y cae al nombre. Ver `barrioPorIndice`.
      if (sector.bi != null) {
        pintarBarrio(barrioPorIndice(idPorNombre[nombre], sector.bi));
      } else if (sector.barrio) {
        pintarBarrio(barrioPorNombre(sector.barrio, idPorNombre[nombre]));
      }
    });
  }

  // Centra el mapa en un barrio si lo hay, y si no en la localidad entera.
  // Lo usa el buscador.
  function volarA(nombre, barrio, bi) {
    if (!mapa) return;
    var b = bi != null
      ? barrioPorIndice(idPorNombre[nombre], bi)
      : barrio ? barrioPorNombre(barrio, idPorNombre[nombre]) : null;
    var limites = null;
    if (b) {
      limites = window.L.latLngBounds([b.bb[1], b.bb[0]], [b.bb[3], b.bb[2]]);
    } else {
      var capaLoc = porNombre[nombre];
      if (capaLoc && capaLoc.getBounds) limites = capaLoc.getBounds();
    }
    if (!limites) return;
    // fitBounds y no un zoom fijo: Suba y Sumapaz no caben con el mismo nivel
    // que La Candelaria, que mide 2 km². El tope de zoom es para que un barrio
    // de tres manzanas no aterrice a nivel de andén, sin contexto alrededor.
    mapa.fitBounds(limites, {
      padding: [24, 24],
      maxZoom: 15,
      animate: !quieto(),
    });
  }

  // --------------------------------------------------------------- montaje

  /**
   * Deja el mapa abriendo YA ACERCADO sobre la ciudad, pero sin encerrarlo ahí:
   * con la rueda o los botones se puede alejar hasta ver el Distrito entero, y
   * no más allá de eso.
   *
   * SON DOS ENCUADRES POR UNA RAZON GEOMETRICA, no de gusto. Bogotá D.C. es
   * mucho más alta que ancha —y el Distrito completo, con Sumapaz, más
   * todavía—; un panel apaisado nunca la llena bien. Si se abre encuadrando el
   * Distrito entero, `fitBounds` tiene que alejarse tanto para que quepa el
   * alto que el resultado es medio Cundinamarca en pantalla y la ciudad
   * reducida a una tira delgada en el centro — el zoom más lejano posible se
   * volvía el único disponible, que es lo contrario de "fácil de acercar".
   *
   *   - `datos.bbox` (la mancha urbana, sectores con SCATIPO 0) es el encuadre
   *     CON EL QUE SE ABRE: es el que más se parece al recuadro del panel, así
   *     que es el que menos aire desperdicia y dónde el mapa se ve más
   *     "cercano" desde el primer momento.
   *   - `datos.bboxDistrito` (los límites administrativos completos) es hasta
   *     dónde se puede ALEJAR: fija el zoom mínimo y el límite de paneo. Así,
   *     alejar un par de clics —con la rueda, ya habilitada— muestra el
   *     Distrito entero, Sumapaz incluida, sin que la vista de apertura pague
   *     ese precio.
   *
   * EL LIMITE DE PANEO SE ESTIRA HASTA CUBRIR LA VISTA INICIAL, y eso no es un
   * detalle: al zoom mínimo la vista sigue siendo MAS ANCHA que el propio
   * Distrito. Cuando eso pasa, Leaflet no puede meter la vista dentro de
   * `maxBounds` y la recoloca contra el borde — el resultado era la ciudad
   * pegada a un lado de la pantalla, con el encuadre recién calculado tirado a
   * la basura.
   */
  function encuadrar(datos, ajustar) {
    if (!datos.bbox || !datos.bboxDistrito) return;
    // Se suelta el límite anterior antes de medir: si no, lo que se mide es
    // una vista que el límite viejo ya movió, y el nuevo hereda el error.
    mapa.setMaxBounds(null);
    var suelo = mapa.getBoundsZoom(datos.bboxDistrito, false, [8, 8]);
    mapa.setMinZoom(suelo);
    if (ajustar) mapa.fitBounds(datos.bbox, { padding: [8, 8], animate: false });
    mapa.setMaxBounds(
      window.L.latLngBounds(datos.bboxDistrito).extend(mapa.getBounds()).pad(0.05)
    );
  }

  /**
   * Crea el mapa dentro de `nodo`. `alElegir(localidad, barrio)` se dispara al
   * tocar una zona; quien lo recibe (main.js) es el que sincroniza buscador,
   * eco y botón. `barrio` es null cuando el clic cae donde no hay sector
   * catastral —huecos, zona rural—, y entonces vale la localidad sola.
   * Devuelve false si Leaflet no cargó — sin red la librería no llega, y en ese
   * caso el quiz se sigue pudiendo completar con el buscador.
   */
  function montar(nodo, alElegir) {
    if (mapa || !nodo) return false;
    if (!window.L) return false;

    var datos = window.GDF_MAPA || { localidades: [], bbox: null };
    if (!datos.localidades.length) return false;

    mapa = window.L.map(nodo, {
      scrollWheelZoom: true,
      zoomControl: true,
      // Zoom en cuartos de nivel. Por defecto Leaflet solo admite niveles
      // enteros, así que `fitBounds` redondea HACIA ABAJO y la ciudad podía
      // abrir hasta el doble de lejos de lo que cabía: sobraba media
      // Cundinamarca alrededor. Con 0,25 el encuadre inicial se ajusta de
      // verdad al recuadro. La rueda y los botones siguen moviéndose de nivel
      // en nivel entero (`zoomDelta`, que se queda en 1).
      zoomSnap: 0.25,
      attributionControl: true,
      // El paneo rebota contra el límite en vez de dejar salir y volver solo.
      maxBoundsViscosity: 1.0,
      // Sin animaciones si el sistema las pidió apagadas (§15 del motion system).
      zoomAnimation: !quieto(),
      fadeAnimation: !quieto(),
    });

    window.L.tileLayer(TESELAS, {
      attribution: ATRIBUCION,
      maxZoom: 19,
    }).addTo(mapa);

    // Las localidades llegan de mayor a menor área, y en Leaflet lo último que
    // se agrega queda encima: así las pequeñas del centro (La Candelaria, Los
    // Mártires, Antonio Nariño) reciben el clic y no la que las rodea.
    var features = datos.localidades.map(function (loc) {
      return {
        type: 'Feature',
        properties: { id: loc.id, nombre: loc.nombre, centro: loc.centro },
        // Polygon, no MultiPolygon: el primer anillo es el contorno y los
        // demás son agujeros. Santa Fe es la única con dos, y el segundo es
        // La Candelaria, que es un enclave dentro suyo. Leaflet lo recorta
        // solo, así que La Candelaria queda clicable sin trucos.
        geometry: { type: 'Polygon', coordinates: loc.anillos },
      };
    });

    // Índice de barrios por localidad y clave, para que el buscador pueda
    // pedir un contorno por su nombre sin recorrer las 20 listas. Ver `porLoc`
    // arriba: va por localidad porque los nombres de sector se repiten entre
    // localidades y un índice global se los comía.
    porLoc = {};
    var geo = window.GDF_BARRIOS_GEO || {};
    Object.keys(geo).forEach(function (id) {
      var tabla = (porLoc[id] = {});
      geo[id].forEach(function (b, i) {
        // La posición dentro de su lista, para que el clic pueda mandar el
        // barrio EXACTO y no su nombre (ver `barrioPorIndice`). Se escribe en
        // el propio dato: es idempotente y `montar` es lo único que lo pone.
        b._i = i;
        // Con nombres repetidos dentro de una localidad se queda el primero:
        // este índice es solo el respaldo por nombre (ver `barrioPorNombre`);
        // ni el clic ni el buscador pasan por acá, los dos traen `bi`.
        if (!tabla[b.c]) tabla[b.c] = b;
      });
    });

    porNombre = {};
    idPorNombre = {};
    capa = window.L.geoJSON(
      { type: 'FeatureCollection', features: features },
      {
        // `noClip` ES LO QUE QUITA LOS RECUADROS NEGROS AL ARRASTRAR. Sin él,
        // Leaflet recorta cada polígono al rectángulo del área de dibujo
        // (la vista más un 10 %) y traza el contorno del polígono RECORTADO,
        // bordes rectos del recorte incluidos: Suba o Fontibón, que se salen
        // de la vista en cuanto se acerca el mapa, dibujaban una caja recta
        // que entraba en pantalla al arrastrar. Son 20 polígonos con ~3.000
        // vértices en total; dibujarlos enteros no cuesta nada.
        style: function (f) {
          return { className: claseDe(f.properties.nombre), weight: 1.5, noClip: true };
        },
        onEachFeature: function (f, capaLoc) {
          var nombre = f.properties.nombre;
          var id = f.properties.id;
          porNombre[nombre] = capaLoc;
          idPorNombre[nombre] = id;
          // ARRANCA INVISIBLE (`opacity: 0`) Y SIN TEXTO. Es lo que garantiza
          // que el nombre de la localidad no se asome NUNCA: Leaflet abre el
          // globo en cuanto el puntero entra al polígono, antes de que
          // `mousemove` haya podido averiguar qué barrio hay debajo, y con
          // cualquier contenido por defecto ese es el instante en que se vería.
          // `L.Tooltip.onAdd` reaplica `options.opacity` en cada apertura, así
          // que esto vuelve a valer cada vez que se entra a una localidad
          // nueva, no solo la primera.
          capaLoc.bindTooltip('', {
            sticky: true,
            className: 'gdf-zona-tip',
            opacity: 0,
          });
          // El globo y el resaltado nombran el BARRIO bajo el cursor: es lo que
          // avisa de qué va a elegir el clic. Se recalcula en cada movimiento,
          // así que va estrangulado — el ray casting es barato, pero no a
          // 120 Hz y para nada.
          // ENTRAR A UNA LOCALIDAD DEJA EL GLOBO EN BLANCO Y ESCONDIDO. Leaflet
          // lo abre en este mismo evento, un instante antes de que `mousemove`
          // sepa qué barrio hay debajo; sin esto, ese instante mostraría lo
          // último que se escribió en él.
          capaLoc.on('mouseover', function () {
            mostrarHover(capaLoc, null);
            // Y se reinicia el estrangulador: el primer `mousemove` dentro de
            // una localidad recién entrada tiene que resolver SIEMPRE, o el
            // rótulo se queda en blanco hasta 60ms después de cruzar la
            // frontera. Dentro de una misma localidad el estrangulado sigue
            // valiendo, que es donde de verdad ahorra.
            ultimoHover = 0;
          });
          capaLoc.on('mousemove', function (e) {
            var ahora = Date.now();
            if (ahora - ultimoHover < 60) return;
            ultimoHover = ahora;
            mostrarHover(capaLoc, barrioEn(e.latlng.lng, e.latlng.lat, id));
          });
          // Salir de la localidad borra el resaltado. Sin esto el contorno del
          // último barrio se queda encendido cuando el cursor se va al agua
          // entre polígonos o fuera del mapa.
          capaLoc.on('mouseout', limpiarHover);
          capaLoc.on('click', function (e) {
            // LA LOCALIDAD LA MANDA ESTA CAPA, no el barrio. Sus límites son
            // los oficiales y son los que el modelo entiende; el contorno del
            // barrio está simplificado y en el borde puede caer al otro lado.
            var b = barrioEn(e.latlng.lng, e.latlng.lat, id);
            // Se manda también la POSICION del barrio, no solo su nombre: es
            // lo único que identifica sin ambigüedad al que se acaba de tocar
            // (ver `barrioPorIndice`).
            if (alElegir) alElegir(nombre, b ? b.n : null, b ? b._i : null);
          });
        },
      }
    ).addTo(mapa);

    // El resaltado del barrio bajo el cursor. Se construye una sola vez y se
    // le cambian los vértices con `setLatLngs`, pero NO se agrega al mapa
    // todavía: sin vértices, agregarlo revienta (ver `mostrarHover`). Entra y
    // sale del mapa según haya o no barrio debajo.
    //
    // `interactive: false` por lo mismo que el polígono del sector elegido: si
    // recibiera el puntero taparía a la localidad de debajo y el propio
    // resaltado impediría hacer clic en lo que está resaltando.
    capaHover = window.L.polygon([], {
      className: 'gdf-barrio-hover',
      interactive: false,
      noClip: true,
      weight: 2,
    });

    // Encuadre provisional, antes de invalidateSize(): evita que se vea un
    // primer parpadeo con el mapa sin encuadrar mientras se mide el tamaño
    // real del contenedor. `encuadrar()`, un instante después, deja el
    // definitivo (y con él el zoom mínimo, que aquí todavía no se puede
    // calcular bien — ver el comentario de más abajo).
    if (datos.bbox) mapa.fitBounds(datos.bbox, { padding: [8, 8] });

    // OBLIGATORIO, no una precaución. `.gdf-scene` lleva `container-type:size`,
    // que implica `contain: size layout style`; dentro de ese contexto Leaflet
    // mide mal al crearse y pinta las teselas desplazadas o en una franja. Hay
    // que decirle que vuelva a medir cuando el nodo ya tiene su tamaño real.
    // Y el encuadre va DESPUES de remedir: `getBoundsZoom` sobre un contenedor
    // mal medido devuelve el zoom mínimo equivocado.
    setTimeout(function () {
      if (!mapa) return;
      mapa.invalidateSize();
      encuadrar(datos, true);
    }, 0);

    alRedimensionar = function () {
      clearTimeout(remedir);
      remedir = setTimeout(function () {
        if (!mapa) return;
        mapa.invalidateSize();
        // Se recalcula el suelo del zoom, pero NO se reencuadra: mover la
        // vista de alguien que está mirando su barrio porque giró el teléfono
        // sería peor que dejarle un encuadre un poco corto.
        encuadrar(datos, false);
      }, 150);
    };
    window.addEventListener('resize', alRedimensionar);

    return true;
  }

  /**
   * Mata el mapa. SIEMPRE antes de quitar el nodo del DOM: al revés, Leaflet
   * conserva sus listeners sobre un nodo que ya no existe y la vuelta a esta
   * pregunta falla con "Map container is already initialized".
   */
  function desmontar() {
    if (alRedimensionar) {
      window.removeEventListener('resize', alRedimensionar);
      alRedimensionar = null;
    }
    clearTimeout(remedir);
    remedir = null;
    if (mapa) {
      mapa.off();
      mapa.remove();
    }
    mapa = null;
    capa = null;
    capasBarrio = [];
    capaHover = null;
    hoverActual = null;
    porNombre = {};
    idPorNombre = {};
    porLoc = {};
    marcadas = [];
  }

  function montado() {
    return !!mapa;
  }

  window.GDF = window.GDF || {};
  window.GDF.mapa = {
    montar: montar,
    desmontar: desmontar,
    marcar: marcar,
    volarA: volarA,
    montado: montado,
    // Resolución de coordenada a zona. La usa el buscador de lugares para
    // ubicar lo que devuelve el geocodificador en vivo, que llega como
    // lat/lon sin barrio. No necesita el mapa montado.
    localidadEnPunto: localidadEnPunto,
    zonaEnPunto: zonaEnPunto,
    // El nombre de un sector por su posición, para los lugares del catálogo
    // local, que viajan con `loc`+`bi` pero sin el nombre del barrio.
    nombreDeBarrio: function (idLoc, bi) {
      var b = barrioPorIndice(idLoc, bi);
      return b ? b.n : null;
    },
  };
})();
