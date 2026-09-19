// Cuánto del plano se ve según lo que ya se contestó, y cómo se traduce a los
// <div> que pinta templates.js.
//
// Antes esto era un mapa "pregunta -> qué ambiente se destapa". Ya no puede
// serlo: las piezas son recortes de una imagen y no sabemos qué ambiente cae en
// cada una (los nombres van impresos en el plano, y no hacemos OCR). El orden
// lo decide la geometría — tools/analizar_planos.py lo precalcula por
// ADYACENCIA desde el centro del plano hacia afuera, que es lo que garantiza
// que lo revelado sea siempre una mancha conexa y no piezas sueltas flotando.
(function () {
  'use strict';

  /**
   * Cuántas piezas se ven ya.
   *
   * Cuenta RESPUESTAS PRESENTES, no `state.qi`: es lo que hace que retroceder
   * funcione solo, sin lógica aparte. `vis` viene precalculado por plano, así
   * que aquí no queda aritmética.
   */
  function celdasVisibles(answers, qList, planta) {
    if (!planta || !planta.vis) return 0;
    var respondidas = 0;
    (qList || []).forEach(function (q) {
      if (answers && answers[q.id] !== undefined) respondidas++;
    });
    if (respondidas <= 0) return 0;
    var i = Math.min(respondidas, planta.vis.length) - 1;
    var n = planta.vis[i] || 0;

    // SUELO DE PIEZAS. Cada plano trae su propio reparto `vis[]`, monótono
    // dentro de sí mismo pero NO entre planos distintos: al cambiar de uno de
    // 12 celdas a uno de 9, el conteo bajaba y el usuario veía menos
    // apartamento después de contestar. `minimo` lo guarda state.js al
    // cambiar de plano (ver ajustarPlanta) y aquí impide que baje.
    //
    // `minimoDesde` es la pregunta en la que se puso ese suelo: por debajo de
    // ella no aplica, y por eso `goBack` sigue restando piezas como siempre.
    if (planta.minimo && respondidas >= (planta.minimoDesde || 0)) {
      n = Math.max(n, Math.min(planta.minimo, (planta.celdas || []).length));
    }
    return n;
  }

  /** Las piezas reveladas, en orden. */
  function buildRooms(planta, n) {
    if (!planta || !planta.celdas) return [];
    return planta.celdas.slice(0, n).map(function (c) {
      return {
        id: c.id,
        // `animated` sale siempre en false: cuál cae de la grúa lo decide el
        // parcheo de DOM de main.js comparando contra lo que YA está pintado,
        // que es la única fuente de verdad de "esto es nuevo".
        animated: false,
        styleText: c.styleText,
        lienzoStyle: c.lienzoStyle,
      };
    });
  }

  /**
   * La silueta: un hueco gris por cada celda con contenido. Se pinta una vez y
   * no se toca.
   *
   * Su unión ES la forma real del apartamento (una L, una T, lo que sea), sin
   * líneas internas porque son todos del mismo gris y teselan exacto. Sirve
   * para que las piezas caigan DENTRO de algo en vez de aparecer flotando, y
   * para que al retroceder quede el hueco a la vista.
   */
  function buildHuecos(planta) {
    if (!planta || !planta.huecos) return [];
    return planta.huecos.map(function (c) {
      return { id: c.id, styleText: c.styleText };
    });
  }

  window.GDF = window.GDF || {};
  window.GDF.scene = {
    celdasVisibles: celdasVisibles,
    buildRooms: buildRooms,
    buildHuecos: buildHuecos,
  };
})();
