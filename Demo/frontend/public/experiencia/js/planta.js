// Elige el apartamento que arma el quiz y calcula la geometría de sus piezas.
//
// QUÉ SE ARMA
// -----------
// El PLANO REAL de una tipología del catálogo: la imagen que publica la ficha
// de Colsubsidio, con muebles renderizados, texturas y muros gruesos. No un
// esquema dibujado a mano — eso se probó antes y se veía justamente como lo que
// era. Cada pieza que cae de la grúa es un recorte de esa imagen, y cuando
// están todas el conjunto es la imagen entera, sin costuras.
//
// Por dónde se corta lo calcula tools/analizar_planos.py y viene en
// js/planos.js: los cortes caen sobre los MUROS del plano, no sobre una rejilla
// ciega.
//
// EL APARTAMENTO ES ILUSTRATIVO
// -----------------------------
// Sirve para enseñar cómo se arma una vivienda, nada más: la recomendación de
// verdad la calcula matching.js con las respuestas y sale en la pantalla de
// resultados. Por eso en la escena no se dice de qué proyecto es.
//
// Se sortea uno provisional al empezar el quiz y queda fijado al contestar
// cuántas alcobas se quieren (la 6.ª pregunta): ahí se reemplaza por uno que
// de verdad las tenga, reacomodando las piezas ya puestas en vez de
// destruirlas. De ahí no vuelve a cambiar.
//
// NINGUNO DE LOS PLANOS DEL SORTEO LLEVA ROTULOS IMPRESOS (esos "Alcoba 2 ·
// 2.35 x 2.25" que estampan algunas constructoras sobre el plano). Los que los
// llevan están vetados en tools/analizar_planos.py: la gracia es que el
// apartamento se lea como un espacio que se arma, no que venga con las
// respuestas escritas encima, y al trocearlo los rótulos quedaban partidos por
// las costuras.
(function () {
  'use strict';

  // Sangría, en puntos porcentuales de la losa. Cada pieza se dibuja un pelo
  // más grande que su celda para que se solape con la vecina y no queden
  // costuras de subpíxel.
  //
  // Es gratis: como el `.lienzo` se dimensiona y se desplaza en función de W y
  // H de la propia pieza, las dos fórmulas se cancelan y el resultado es
  // idéntico con o sin sangría. Lo único que cambia es que la pieza enseña un
  // píxel de más del vecino, superpuesto. NO estira ni desalinea nada.
  var SANGRIA = 0.4;

  // Por debajo de esta densidad la celda es casi todo papel: no se dibuja ni
  // como pieza ni como hueco. TIENE QUE COINCIDIR con UMBRAL_CELDA de
  // tools/analizar_planos.py, que es quien decide el orden y el reparto: si
  // este fuera mas bajo, `vis[]` prometeria mas piezas de las que se dibujan.
  //
  // Esta en 55 y no en 30 porque es lo que permite que el sorteo del quiz sean
  // los 36 planos APTOS (16 proyectos) y no solo los rectangulares — o sea, lo
  // que permite que el plano de la escena persiga al proyecto #1. La celda que
  // cae por debajo no deja un agujero: deja un MORDISCO, y ese mordisco es la
  // forma real en L o en U del apartamento. Ver la nota larga en
  // analizar_planos.py.
  var UMBRAL_CELDA = 55;

  function redondear(n) {
    return Math.round(n * 1000) / 1000;
  }

  /**
   * FNV-1a de 32 bits. Se usa para que el mismo nombre saque siempre el mismo
   * apartamento (se lee como "este es tu plano") y dos personas seguidas en un
   * stand saquen planos distintos. Mismo criterio que la variante 3D del
   * proyecto, que hashea nombre+apellido para variar su planta.
   */
  function hashFnv(txt) {
    var h = 0x811c9dc5;
    var s = String(txt || '');
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
    }
    return h >>> 0;
  }

  // src del plano -> a qué proyecto y tipología pertenece. Se construye una vez
  // recorriendo el catálogo en vez de guardarlo en planos.js: una sola fuente
  // de verdad, y así regenerar uno de los dos archivos no desincroniza el otro.
  var _indice = null;
  function indicePlanos() {
    if (_indice) return _indice;
    _indice = {};
    var proyectos = (window.GDF.data && window.GDF.data.PROJECTS) || [];
    proyectos.forEach(function (p) {
      (p.tipologias || []).forEach(function (t) {
        (t.planos || []).forEach(function (pl) {
          if (pl.src && !_indice[pl.src]) _indice[pl.src] = { proyecto: p, tipologia: t };
        });
      });
    });
    return _indice;
  }

  /**
   * De los cortes que trae planos.js a las piezas con su CSS ya serializado.
   *
   * `datos` es la fila de GDF_PLANOS:
   *   [Wi, Hi, bx, by, bw, bh, cortesX‰, cortesY‰, densidades, orden, vis]
   */
  function geometriaCeldas(src, datos) {
    var Wi = datos[0], Hi = datos[1];
    var bx = datos[2], by = datos[3], bw = datos[4], bh = datos[5];
    var cortesX = datos[6], cortesY = datos[7], dens = datos[8], orden = datos[9];

    // Constantes del plano: hacen que el RECUADRO DE CONTENIDO llene una caja
    // del tamaño de la losa. Son iguales para las doce piezas.
    var bgW = redondear((100 * Wi) / bw);
    var bgH = redondear((100 * Hi) / bh);
    // Guarda: si la imagen no tiene margen blanco, la división es 0/0.
    var posX = Wi === bw ? 0 : redondear((100 * bx) / (Wi - bw));
    var posY = Hi === bh ? 0 : redondear((100 * by) / (Hi - bh));
    var fondo =
      "background-image:url('" + src + "');" +
      'background-size:' + bgW + '% ' + bgH + '%;' +
      'background-position:' + posX + '% ' + posY + '%;' +
      'background-repeat:no-repeat;';

    // Los cortes vienen en milésimas del recuadro; se redondean los CORTES y el
    // tamaño sale de la diferencia. Al revés (redondear posición y tamaño por
    // separado) el borde de una celda no coincide con el de la siguiente.
    var xs = [0];
    cortesX.forEach(function (v) { xs.push(v / 10); });
    xs.push(100);
    var ys = [0];
    cortesY.forEach(function (v) { ys.push(v / 10); });
    ys.push(100);

    var celdas = [];
    for (var a = 0; a < ys.length - 1; a++) {
      for (var b = 0; b < xs.length - 1; b++) {
        var i = celdas.length;
        var L = xs[b], T = ys[a];
        var W = redondear(xs[b + 1] - L + SANGRIA);
        var H = redondear(ys[a + 1] - T + SANGRIA);
        celdas.push({
          id: 'c' + i,
          dens: dens[i],
          L: L, T: T, W: W, H: H,
          styleText: 'left:' + L + '%;top:' + T + '%;width:' + W + '%;height:' + H + '%;',
          lienzoStyle:
            'left:' + redondear(-(L / W) * 100) + '%;' +
            'top:' + redondear(-(T / H) * 100) + '%;' +
            'width:' + redondear(10000 / W) + '%;' +
            'height:' + redondear(10000 / H) + '%;' +
            fondo,
        });
      }
    }

    // Las útiles, en el orden en que deben aparecer (lo decide el script de
    // Python por adyacencia, para que el plano a medias sea siempre una mancha
    // conexa y no piezas flotando en el aire).
    var enOrden = orden.map(function (i) { return celdas[i]; }).filter(Boolean);
    var huecos = celdas.filter(function (c) { return c.dens > UMBRAL_CELDA; });

    return { celdas: enOrden, huecos: huecos, ratio: redondear(bw / bh), wmax: bw };
  }

  // Cuántas alcobas tiene el apartamento de cada plano. Se calcula una vez
  // cruzando el índice con espacios.resumenTipologia.
  var _porHabitaciones = null;
  function poolDisponible() {
    // TODOS los planos aptos, no solo los rectangulares. Antes eran solo los
    // rectangulares —23 planos de 8 proyectos— por miedo a los mordiscos de la
    // silueta, y eso ponia un techo durisimo al match: el proyecto #1 del
    // ranking tenia plano el 40 % de las veces y nada mas.
    //
    // Se pudo abrir cuando se vio que el problema no era la FORMA sino la banda
    // intermedia de densidad: la silueta ya sigue la huella real de cada plano
    // (ver el filtro por UMBRAL_CELDA en construirPlanta), y con el umbral en
    // 55 las celdas medio vacias pasan a ser mordiscos en vez de piezas de
    // papel. Con eso el sorteo son 36 planos de 16 proyectos, 15 VIS y
    // cobertura 10/13/13 por alcobas.
    //
    // Los rectangulares quedan de respaldo por si al regenerar el catalogo la
    // lista de aptos se quedara vacia.
    var aptos = window.GDF_PLANOS_APTOS || [];
    return aptos.length ? aptos : window.GDF_PLANOS_RECTOS || [];
  }

  function habitacionesDe(src) {
    var ref = indicePlanos()[src];
    if (!ref) return null;
    return window.GDF.espacios.resumenTipologia(ref.tipologia, ref.proyecto).habitaciones;
  }

  function porHabitaciones() {
    if (_porHabitaciones) return _porHabitaciones;
    _porHabitaciones = {};
    poolDisponible().forEach(function (src) {
      var h = habitacionesDe(src);
      if (!h) return;
      if (!_porHabitaciones[h]) _porHabitaciones[h] = [];
      _porHabitaciones[h].push(src);
    });
    return _porHabitaciones;
  }

  /**
   * Arma el objeto `planta` a partir del src de un plano. Es la parte cara
   * (trocea la imagen en 12 celdas y serializa el CSS de cada una), asi que
   * solo se llama para el plano que se va a pintar, nunca para puntuar
   * candidatos.
   */
  function construirPlanta(src) {
    var datos = (window.GDF_PLANOS || {})[src];
    if (!datos) return null;

    var ref = indicePlanos()[src];
    var geo = geometriaCeldas(src, datos);
    var resumen = ref
      ? window.GDF.espacios.resumenTipologia(ref.tipologia, ref.proyecto)
      : null;

    return {
      sello: src,
      plano: src,
      proyecto: ref ? ref.proyecto.name : null,
      localidad: ref ? ref.proyecto.localidad : null,
      vis: ref ? !!ref.proyecto.vis : false,
      tipologia: ref ? ref.tipologia.nombre : null,
      area: ref ? ref.tipologia.area : null,
      areaPrivada: resumen ? resumen.areaPrivada : null,
      habitaciones: resumen ? resumen.habitaciones : null,
      precio: ref ? ref.tipologia.precio || null : null,
      amenidades: ref ? ref.proyecto.amenidades || [] : [],
      resumen: resumen,
      celdas: geo.celdas,
      huecos: geo.huecos,
      // Cuantas piezas se ven tras cada una de las 8 preguntas. Viene
      // precalculado por AREA de tinta, no por conteo: repartiendo por conteo
      // la primera pregunta se llevaba el 30 % de la superficie y las ultimas
      // solo anadian lascas.
      vis: datos[10],
      ratio: geo.ratio,
      wmax: geo.wmax,
    };
  }

  /**
   * El apartamento con el que ARRANCA el quiz.
   *
   * Determinista a partir del nombre, para que la misma persona vea siempre el
   * mismo y dos personas seguidas no. A partir de la primera respuesta manda
   * `mejorApartamento`.
   */
  function elegirApartamento(state, habitaciones) {
    var pool = poolDisponible();
    if (habitaciones) {
      var acotado = porHabitaciones()[habitaciones];
      // Si el catalogo no tiene ninguna planta rectangular con ese numero de
      // alcobas, mejor seguir con el pool entero que quedarse sin apartamento.
      if (acotado && acotado.length) pool = acotado;
    }
    if (!pool.length) return null;
    var semilla = String(state.nombre || '') + '|' + String(state.apellido || '');
    return construirPlanta(pool[hashFnv(semilla.toLowerCase().trim()) % pool.length]);
  }

  // -------------------------------------------------------------------------
  // El plano que mejor encaja con lo contestado HASTA AHORA
  // -------------------------------------------------------------------------
  // El plano se reelige en CADA respuesta, no solo en la de alcobas, y ahora SI
  // persigue al proyecto ganador de matching.js: el plano que se arma en la
  // escena es, siempre que se pueda, el del proyecto que va primero en el
  // ranking. Antes no lo hacia —convergia solo hacia lo que la persona habia
  // contestado— y coincidia con el #1 el 19,9 % de las veces.
  //
  // Lo hace `mejorApartamento` pasandole a `puntuarPlano` un mapa de BONOS por
  // puesto en el ranking. Medido sobre 3.000 quices al azar: el plano final es
  // el del #1 el 52,8 % de las veces y esta entre los 6 recomendados el 95,4 %.
  //
  // EL 52,8 % ES EL TECHO, NO UNA CHAPUZA. De los 31 proyectos del catalogo
  // solo 14 tienen plano usable: los otros 17 estan vetados por llevar rotulos
  // impresos, lineas de seccion o ser renders isometricos, y meterlos es un
  // retroceso documentado. Cuando el #1 no tiene plano se usa el del mejor
  // rankeado que si lo tenga, que es de donde sale el 95,4 %.
  //
  // Dentro de un mismo proyecto sigue mandando lo contestado: el bono es igual
  // para los 9 planos de Nuva Park o los 5 de La Arboleda, asi que quien elige
  // la tipologia es el resto de `puntuarPlano`.

  var _attrs = null;

  /** Atributos baratos de un plano, sin trocear la imagen. Se cachean. */
  function atributosDe(src) {
    if (!_attrs) _attrs = {};
    if (_attrs[src]) return _attrs[src];
    var ref = indicePlanos()[src];
    if (!ref) {
      _attrs[src] = {};
      return _attrs[src];
    }
    var resumen = window.GDF.espacios.resumenTipologia(ref.tipologia, ref.proyecto);
    _attrs[src] = {
      habitaciones: resumen ? resumen.habitaciones : null,
      area: ref.tipologia.area || null,
      precio: ref.tipologia.precio || null,
      vis: !!ref.proyecto.vis,
      localidad: ref.proyecto.localidad || null,
      amenidades: ref.proyecto.amenidades || [],
    };
    return _attrs[src];
  }

  /**
   * Que tan bien encaja ESTE plano con lo contestado hasta ahora.
   *
   * Las alcobas pesan mucho mas que el resto a proposito: ensenar un
   * apartaestudio a quien acaba de pedir tres alcobas es la incoherencia mas
   * visible que puede tener la escena, y ninguna suma de zonas comunes deberia
   * poder compensarla.
   */
  function puntuarPlano(src, a, rangos) {
    var x = atributosDe(src);
    if (!x.habitaciones) return 0;
    var s = 0;

    // EL PUESTO EN EL RANKING, si se lo pasan. `rangos` es
    // {nombre de proyecto: bono} y lo arma `mejorApartamento` una sola vez por
    // respuesta. Es el termino dominante a proposito: el resto de la funcion se
    // mueve en un rango de ~100 puntos, asi que con estos bonos el RANKING
    // decide entre proyectos y las respuestas siguen decidiendo DENTRO de cada
    // proyecto (que tipologia de las que tiene). Sin `rangos` la funcion se
    // comporta como siempre — asi la siguen pudiendo llamar los tests.
    if (rangos) {
      var ref = indicePlanos()[src];
      if (ref && rangos[ref.proyecto.name]) s += rangos[ref.proyecto.name];
    }

    // Las alcobas siguen mandando —ensenar un apartaestudio a quien pidio tres
    // es la incoherencia mas visible de la escena— pero no tanto como para que
    // nada mas pueda mover el plano dentro del mismo numero de alcobas.
    if (a.habitaciones !== undefined) {
      var pedidas = window.GDF.matching.habitacionesPedidas(a);
      if (x.habitaciones === pedidas) s += 34;
      else s -= 16 * Math.abs(x.habitaciones - pedidas);
    }

    if (a.tipo) s += x.vis === (a.tipo === 'VIS') ? 10 : -10;

    // LA LOCALIDAD USA LA VECINDAD, no solo la coincidencia exacta. Los 10
    // planos del sorteo salen de 7 localidades de las 13 que ofrece el quiz:
    // premiando solo el acierto exacto, mas de la mitad de las respuestas de
    // zona dejaban a los planos empatados a cero y el plano no se movia.
    // Con la vecindad oficial del Distrito (la misma que usa matching.js) cada
    // plano queda a una distancia distinta de CUALQUIER localidad que se elija,
    // asi que contestar siempre reordena.
    if (a.zona && x.localidad) {
      var vecinas = (window.GDF.data.VECINAS || {})[a.zona] || [];
      if (x.localidad === a.zona) s += 26;
      else if (vecinas.indexOf(x.localidad) > -1) s += 12;
      else s -= 9;
    }

    // El precio, graduado: antes era practicamente binario (cabe / no cabe) y
    // dos planos que cabian de sobra puntuaban igual, asi que mover el rango de
    // ingresos casi nunca reordenaba nada.
    //
    // `precio` viene en pesos y la banda en millones (ver matching.js). Ojo: un
    // plano del sorteo (Infinitum Zentral) NO publica precio; con `x.precio`
    // en 0 se colaba como el mas barato de todos y ganaba siempre esta parte.
    // Sin dato no puntua.
    if (a.ingresos && x.precio) {
      var band = window.GDF.matching.bandaDe(a) * 1e6;
      var rel = x.precio / band;
      if (rel <= 1) {
        // Cuanto mas holgado cabe, mejor, pero con rendimientos decrecientes:
        // un piso ridiculamente barato para el presupuesto tampoco es el ideal.
        s += Math.round(14 * Math.min(1, (1 - rel) / 0.45));
      } else {
        s -= Math.round(Math.min(22, (rel - 1) * 40));
      }
    }

    if (a.personas !== undefined && x.area) {
      var hogar = (a.personas === '4+' ? 4 : parseInt(a.personas, 10) || 0) + 1;
      var m2 = x.area / hogar;
      s += m2 >= 22 ? 10 : m2 >= 18 ? 5 : -Math.min(16, Math.round((18 - m2) / 1.2));
    }

    var pedidasAm = a.entorno_deseado;
    if (pedidasAm && pedidasAm.length && x.amenidades.length) {
      var claves = {};
      x.amenidades.forEach(function (am) {
        if (am && am.clave) claves[am.clave] = true;
      });
      var n = pedidasAm.filter(function (v) { return claves[v]; }).length;
      s += Math.min(12, n * 4);
    }
    return s;
  }

  // Cuanto tiene que ganar un candidato para desbancar al plano ya puesto. Es
  // la histeresis que impide que el plano salte de un lado a otro entre
  // preguntas contiguas por diferencias de un punto.
  //
  // MEDIDO sobre 800 quices con respuestas al azar. Con 2, el plano cambia 2,34
  // veces de media (maximo 5) y en el 26 % de los quices vuelve a un plano ya
  // visto. Bajarlo a 1 apenas gana reactividad (ingresos 63 % contra 60 %, zona
  // 46 % contra 45 %) y sube el vaiven; subirlo a 3 la pierde sin ganar
  // estabilidad apreciable.
  var MARGEN_CAMBIO = 2;

  /**
   * El mejor plano para lo contestado hasta ahora, o null si el que ya esta
   * puesto sigue siendo suficientemente bueno.
   *
   * El desempate sale del hash FNV del nombre — el mismo de
   * `elegirApartamento` — asi que se conserva la propiedad de siempre: la
   * misma persona ve siempre el mismo recorrido de planos, y dos personas
   * seguidas en un stand ven distintos.
   */
  // Cuanto suma un plano por el puesto que ocupa SU proyecto en el ranking de
  // matching.js. El salto entre el 1.o y el 2.o es el que manda: con 120 contra
  // 70 ningun encaje de respuestas puede colar al segundo por delante del
  // primero, y por debajo la escala se aplana para que entre el 4.o y el 6.o
  // vuelvan a pesar las respuestas.
  var BONO_RANGO = [120, 70, 45, 28, 16, 8];

  /** {nombre de proyecto: bono} para lo contestado hasta ahora. */
  function rangosDe(a) {
    var mapa = {};
    var top = window.GDF.matching.computeMatches(a, BONO_RANGO.length) || [];
    top.forEach(function (m, i) {
      mapa[m.name] = BONO_RANGO[i];
    });
    return mapa;
  }

  function mejorApartamento(state) {
    var pool = poolDisponible();
    if (!pool.length) return null;
    var a = state.answers || {};
    var semilla = hashFnv(
      (String(state.nombre || '') + '|' + String(state.apellido || '')).toLowerCase().trim()
    );

    // UNA sola vez por respuesta, no una por plano: `computeMatches` recorre los
    // 31 proyectos, y llamarlo dentro de `puntuarPlano` serian 37 pasadas.
    var rangos = rangosDe(a);

    var mejor = null;
    var mejorPuntos = -Infinity;
    pool.forEach(function (src, i) {
      // Ruido fijo por persona para desempatar: siempre el mismo para el mismo
      // nombre, asi que no introduce azar entre respuestas.
      var puntos = puntuarPlano(src, a, rangos) + ((semilla >>> (i % 16)) & 3) * 0.25;
      if (puntos > mejorPuntos) {
        mejorPuntos = puntos;
        mejor = src;
      }
    });
    if (!mejor) return null;

    var actual = state.planta;
    if (actual && actual.sello === mejor) return null;
    if (actual && puntuarPlano(actual.sello, a, rangos) + MARGEN_CAMBIO >= mejorPuntos) {
      return null;
    }
    return construirPlanta(mejor);
  }

  // -------------------------------------------------------------------------
  // Planos reales de la ficha
  // -------------------------------------------------------------------------

  /**
   * 'Plano del apartamento. Obra gris.' -> 'gris'
   *
   * El orden es JERÁRQUICO y no es negociable: la frase "Sugerencia de
   * distribución y acabados" es la etiqueta estándar del plano decorado, pero
   * también aparece en descripciones que terminan en "Se entrega en obra
   * gris". Si "acabados" se evalúa primero, 8 planos grises se clasifican como
   * decorados.
   *
   * DUPLICADO en tools/analizar_planos.py (clasificar_plano). Si cambia una,
   * cambia la otra: es el filtro que decide qué planos entran al sorteo.
   */
  function clasificarPlano(desc) {
    var t = String(desc || '').toLowerCase();
    if (!t) return 'otro';
    if (/axonometr/.test(t)) return 'axo';
    if (/obra gris|sin acabados/.test(t)) return 'gris';
    if (/acabados/.test(t)) return 'decorado';
    return 'otro';
  }

  /**
   * El plano que mejor representa una tipología: primero el decorado (se lee
   * como un hogar), luego el de obra gris, y la axonometría de última porque es
   * una vista 3D, no una planta. Lo usa la tarjeta de resultados.
   */
  function planoDeTipologia(tipologia) {
    var planos = (tipologia && tipologia.planos) || [];
    if (!planos.length) return null;
    var porTipo = { decorado: null, gris: null, otro: null, axo: null };
    planos.forEach(function (pl) {
      var tipo = clasificarPlano(pl.desc);
      if (!porTipo[tipo]) porTipo[tipo] = { src: pl.src, alt: pl.alt || pl.desc || 'Plano', tipo: tipo };
    });
    return porTipo.decorado || porTipo.gris || porTipo.otro || porTipo.axo;
  }

  window.GDF = window.GDF || {};
  window.GDF.planta = {
    elegirApartamento: elegirApartamento,
    mejorApartamento: mejorApartamento,
    puntuarPlano: puntuarPlano,
    porHabitaciones: porHabitaciones,
    geometriaCeldas: geometriaCeldas,
    indicePlanos: indicePlanos,
    hashFnv: hashFnv,
    planoDeTipologia: planoDeTipologia,
    clasificarPlano: clasificarPlano,
    SANGRIA: SANGRIA,
  };
})();
