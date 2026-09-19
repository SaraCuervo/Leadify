// Algoritmo de scoring de proyectos. Mismo punto de partida 38, mismo clamp
// [51,96], y cada proyecto sale con `factores`: qué sumó y qué restó. Eso es lo
// que alimenta el panel de depuración (#debug) y permite comparar este motor
// contra el clustering cuando el compañero lo conecte.
//
// EL PUNTAJE SE MUESTRA EN VIVO DURANTE EL QUIZ (la barra "encaje con el
// catálogo", ver computeDerived en state.js), así que importa que TODAS las
// preguntas lo muevan: si una no suma ni resta, contestarla no produce ninguna
// reacción y la escena se lee como colgada.
//
// De las 8 preguntas puntúan 7:
//   tipo · ingresos · zona · habitaciones   — los pesos de siempre
//   personas · entorno_deseado              — cruzan con datos REALES del catálogo
//   edad                                    — vía el plazo de crédito (ver FACTOR_EDAD)
//   piso_preferido                          — NO puntúa, y no es un olvido:
//     ni los 31 proyectos ni las 81 tipologías guardan en qué piso está nada.
//     Cualquier peso sería inventado y el panel #debug lo delataría. Esa
//     pregunta sigue teniendo su efecto de escena (el `data-piso` cambia el
//     fondo y la sombra). Para que puntúe hay que sacar el dato en el scraper
//     primero.
(function () {
  'use strict';

  // Techo de precio (en millones) por rango de ingresos. Vive acá porque es
  // parte de la fórmula, pero se exporta: recommender.js lo necesita para
  // redactar la razón de cada recomendación y duplicarlo sería la típica tabla
  // que se desincroniza a la primera.
  var BANDA_INGRESOS = { '≤2 SMMLV': 110, '2–4 SMMLV': 170, '4–8 SMMLV': 320, '8+ SMMLV': 600 };

  // A menor edad, más plazo de crédito cabe antes del tope de edad del banco, y
  // con más plazo la misma cuota alcanza un precio mayor. Es el ÚNICO vínculo
  // defendible entre la edad y el catálogo: no hay dato de edad en ningún
  // proyecto.
  //
  // SUPUESTO, NO VERIFICADO con el área hipotecaria — igual que las tasas
  // pendientes de js/simulador.js. Los factores son deliberadamente suaves
  // (±8 %) para que la edad module y no decida. Si alguna vez llega la tabla
  // real de plazo por edad, se sustituye aquí y en ningún otro sitio.
  var FACTOR_EDAD = [
    { hasta: 30, factor: 1.08, motivo: 'a tu edad cabe el plazo más largo' },
    { hasta: 45, factor: 1.0, motivo: null },
    { hasta: 55, factor: 0.95, motivo: 'el plazo se acorta y baja el monto financiable' },
    { hasta: 999, factor: 0.92, motivo: 'el plazo se acorta bastante y baja el monto financiable' },
  ];

  function factorEdad(a) {
    var edad = parseInt(a.edad, 10);
    if (!edad || isNaN(edad)) return FACTOR_EDAD[1]; // sin dato, ni premia ni castiga
    for (var i = 0; i < FACTOR_EDAD.length; i++) {
      if (edad <= FACTOR_EDAD[i].hasta) return FACTOR_EDAD[i];
    }
    return FACTOR_EDAD[FACTOR_EDAD.length - 1];
  }

  function bandaDe(a) {
    var base = BANDA_INGRESOS[a.ingresos] || 200;
    return Math.round(base * factorEdad(a).factor);
  }

  function habitacionesPedidas(a) {
    return a.habitaciones === '3+' ? 3 : parseInt(a.habitaciones || '1', 10);
  }

  function computeMatches(a, limite) {
    var PROJECTS = window.GDF.data.PROJECTS;
    var VECINAS = window.GDF.data.VECINAS;

    var wantVis = a.tipo === 'VIS';
    var need = habitacionesPedidas(a);
    // La demo es solo de Bogotá: la ubicación que se pide es la LOCALIDAD, no
    // el municipio (esa pregunta ya no existe). `zona` conserva el id viejo
    // para no renombrar la respuesta en todo el flujo.
    //
    // Y SON VARIAS. Se pueden pedir varios sectores del mapa, así que `zonas`
    // trae todas las localidades pedidas y `zona` la primera. Un proyecto se
    // puntúa contra la MEJOR de ellas —la que le dé más puntos—, que es lo
    // mismo que hace el modelo de verdad midiendo la distancia a la más
    // cercana del conjunto (ver el BFS multi-origen de catalogos.py). Con una
    // sola zona la fórmula es idéntica a la de antes.
    var locs = (a.zonas && a.zonas.length) ? a.zonas : (a.zona ? [a.zona] : []);
    var band = bandaDe(a);

    return PROJECTS.map(function (p) {
      var s = 38;
      var factores = [];
      function suma(puntos, motivo) {
        s += puntos;
        if (puntos) factores.push({ puntos: puntos, motivo: motivo });
      }

      // Mientras la pregunta de zona no se haya contestado NO se penaliza a
      // nadie. Antes caía un -16 a los 31 proyectos, y como el puntaje se
      // muestra en vivo eso hundía la barra al piso del clamp: contestabas y el
      // número no se movía. Además el motivo se escribía 'queda lejos de
      // undefined' en el panel #debug.
      //
      // Esta rama casi no se usa ya: desde que `zona` es la PRIMERA pregunta
      // (ver la cabecera de data.js), `loc` está definida durante todo el resto
      // del quiz. Se conserva porque sigue cubriendo el primer pintado, cuando
      // aún no hay ninguna respuesta.
      //
      // Y el reverso de moverla: este es el factor más brusco de la fórmula
      // (+29 / +11 / −16), así que ahora es la primera respuesta la que más
      // mueve el número. Por eso la barra de encaje no se muestra hasta la
      // segunda (ver quizPanel en templates.js).
      if (!locs.length) {
        // sin factor: aún no sabemos dónde quiere vivir
      } else {
        // La mejor de las pedidas: estar EN una de ellas gana a colindar con
        // otra, y colindar gana a quedar lejos de todas.
        var mejor = null;
        for (var z = 0; z < locs.length; z++) {
          var loc = locs[z];
          var cand;
          if (p.localidad === loc) {
            cand = { puntos: 29, motivo: 'Está en ' + loc };
          } else if ((VECINAS[loc] || []).indexOf(p.localidad) > -1) {
            // Colindante según los límites oficiales del Distrito.
            cand = { puntos: 11, motivo: p.localidad + ' colinda con ' + loc };
          } else {
            cand = { puntos: -16, motivo: p.localidad + ' queda lejos de ' + loc };
          }
          if (!mejor || cand.puntos > mejor.puntos) mejor = cand;
        }
        suma(mejor.puntos, mejor.motivo);
      }

      suma(p.vis === wantVis ? 11 : -13, p.vis === wantVis ? 'Coincide ' + (p.vis ? 'VIS' : 'No VIS') : 'No coincide con ' + (wantVis ? 'VIS' : 'No VIS'));

      if (p.hab === need) suma(7, need + ' habitaciones, justo lo pedido');
      else if (p.hab > need) suma(4, 'Tiene ' + p.hab + ' hab (pediste ' + need + ')');
      else suma(-7, 'Solo ' + p.hab + ' hab (pediste ' + need + ')');

      if (p.vis && a.afiliado === 'Sí') suma(4, 'VIS + afiliado a Colsubsidio');
      if (p.vis && a.primera === 'Sí') suma(3, 'VIS + primera vivienda');
      if (a.ahorro && a.ahorro !== 'Aún no') suma(2, 'Ya tiene ahorro');

      // `band` va en MILLONES y `price` del catalogo viene en PESOS, asi que
      // hay que bajarlo antes de compararlos. Sin esto, 262635750 se medía
      // contra un techo de ~250 y NINGUN proyecto cabia en el presupuesto:
      // las seis tarjetas salian con "se pasa de tu presupuesto", incluida la
      // del 96 %. Solo se veia con el motor local (SIN_BACKEND / 'local'),
      // porque por el camino del backend el precio llega ya resuelto.
      var precioM = (p.price || 0) / 1e6;
      if (precioM <= band) {
        suma(Math.min(6, Math.round((band - precioM) / (band * 0.06))), 'Precio ($' + Math.round(precioM) + 'M) cabe en tu presupuesto');
      } else {
        suma(-Math.min(11, Math.round((precioM - band) / 8)), 'Precio ($' + Math.round(precioM) + 'M) por encima de tu rango');
      }

      // La edad ya movió `band` arriba; el factor se explica aquí para que el
      // panel #debug muestre POR QUÉ el techo de precio no es el de la tabla.
      var fe = factorEdad(a);
      if (fe.motivo) factores.push({ puntos: 0, motivo: 'Techo de precio $' + band + 'M: ' + fe.motivo });

      // --- personas a cargo: hacinamiento y holgura -------------------------
      // `personas` es cuántas personas MÁS del titular ('0'..'4+'), así que el
      // hogar son personas + 1. Se cruza contra las habitaciones y los m² del
      // proyecto, que son datos oficiales de la ficha.
      if (a.personas !== undefined && a.personas !== null && a.personas !== '') {
        var hogar = (a.personas === '4+' ? 4 : parseInt(a.personas, 10) || 0) + 1;
        var porHab = hogar / Math.max(1, p.hab);
        if (porHab > 2) suma(-9, hogar + ' personas en ' + p.hab + ' habitación' + (p.hab > 1 ? 'es' : '') + ': queda apretado');
        else if (porHab > 1.5) suma(-3, hogar + ' personas para ' + p.hab + ' habitaciones: justo');
        else suma(4, 'Las ' + p.hab + ' habitaciones alcanzan para ' + hogar + (hogar > 1 ? ' personas' : ' persona'));

        // ~18 m² por persona es el umbral por debajo del cual la vivienda se
        // siente pequeña para ese hogar. Es una regla de dedo, no una norma.
        // El castigo es PROPORCIONAL a lo lejos que queda del umbral: con un
        // -4 plano se anulaba exacto con el +4 de arriba y `personas` acababa
        // sumando cero justo en los proyectos que encajan por habitaciones.
        var m2 = (p.area || 0) / hogar;
        if (p.area && m2 < 18) suma(-Math.min(10, Math.round((18 - m2) / 1.5)), Math.round(p.area) + ' m² entre ' + hogar + ' son ' + Math.round(m2) + ' m² por persona');
      }

      // --- entorno deseado: las zonas comunes que pidió ---------------------
      // Cruce directo: `entorno_deseado` trae las etiquetas exactas del
      // backend y `amenidades[].clave` ya viene normalizada por el scraper al
      // mismo vocabulario de 26. Es el mismo cruce que usan el halo de la
      // escena (templates.js) y la razón de cada tarjeta (recommender.js).
      var pedidas = a.entorno_deseado;
      if (pedidas && pedidas.length && (p.amenidades || []).length) {
        var claves = {};
        p.amenidades.forEach(function (am) {
          if (am && am.clave) claves[am.clave] = am.label || am.clave;
        });
        var acierta = pedidas.filter(function (v) { return claves[v]; });
        if (acierta.length) {
          var nombres = acierta.slice(0, 3).map(function (v) { return claves[v]; });
          // Tope a +9: tres coincidencias ya dicen "este sitio es lo que
          // buscabas"; más allá solo aplastaría al factor de localidad.
          suma(Math.min(9, acierta.length * 3), 'Tiene ' + nombres.join(', ') + (acierta.length > 3 ? ' y más de lo que pediste' : ''));
        } else {
          suma(-4, 'No tiene ninguna de las zonas comunes que pediste');
        }
      }

      var bruto = s;
      s = Math.max(51, Math.min(96, Math.round(s)));

      var out = {};
      Object.keys(p).forEach(function (k) {
        out[k] = p[k];
      });
      out.score = s;
      out.factores = factores;
      out.scoreBruto = bruto;
      return out;
    })
      .sort(function (x, y) {
        // Se ordena por el puntaje SIN recortar. El `score` que se muestra está
        // acotado a [51,96] para que ninguna tarjeta se vea humillada, pero eso
        // empata a todos los que caen por debajo de 51 — y ahí se perdía la
        // señal de localidad: pidiendo Usaquén, el único proyecto de Usaquén
        // quedaba fuera del top 6 porque otros ganaban el desempate por
        // transacciones. Ordenar por el bruto conserva el orden real.
        // Entre iguales, primero el que más gente ha comprado (transacciones
        // reales del Excel); los que no tienen el dato no se penalizan.
        return y.scoreBruto - x.scoreBruto || (y.transacciones || 0) - (x.transacciones || 0);
      })
      .slice(0, limite || 3);
  }

  /**
   * El porcentaje que se ve EN VIVO durante el quiz ("Encaje con el catálogo").
   *
   * Dos decisiones, las dos medidas y no a ojo:
   *
   * 1. Sale del puntaje SIN RECORTAR (`scoreBruto`), no del `score`. El clamp
   *    [51,96] existe para que ninguna tarjeta de resultados se vea humillada,
   *    y para una barra en vivo es justo lo que sobra: aplastaba el número
   *    contra el 51 en los perfiles difíciles y contra el 96 en los fáciles, y
   *    entonces contestar dejaba de mover nada.
   *
   * 2. Es el PROMEDIO DEL TOP 6, no el del líder. Mirando solo al primero, una
   *    respuesta que reordena el catálogo entero pero no cambia al puntero
   *    dejaba la barra quieta. El promedio de los seis que además son los que
   *    se van a recomendar se mueve en más preguntas y da saltos menos bruscos.
   *
   * La escala está medida sobre el recorrido real de ese promedio (35,8 a
   * 89,3): el mapa lineal 36 -> 45 % y 89 -> 97 % lo reparte sin tocar los
   * topes salvo en los extremos de verdad.
   *
   * OJO: no todas las preguntas lo mueven siempre, y no es un fallo.
   * `piso_preferido` NUNCA lo mueve (no hay dato de piso en el catálogo) y
   * `edad` solo lo mueve fuera de la banda 31-45, que es neutra a propósito.
   * Que contestar siempre produzca una reacción lo garantiza la ESCENA (la
   * bola y las piezas que caen), no este número.
   */
  function compatDe(a) {
    var top = computeMatches(a, 6);
    if (!top.length) return 45;
    var media = top.reduce(function (s, x) { return s + x.scoreBruto; }, 0) / top.length;
    return Math.max(40, Math.min(97, Math.round(45 + (media - 36) * 0.98)));
  }

  window.GDF = window.GDF || {};
  window.GDF.matching = {
    computeMatches: computeMatches,
    compatDe: compatDe,
    BANDA_INGRESOS: BANDA_INGRESOS,
    bandaDe: bandaDe,
    habitacionesPedidas: habitacionesPedidas,
  };
})();
