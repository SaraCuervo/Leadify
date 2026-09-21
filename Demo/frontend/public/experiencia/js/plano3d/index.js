/* Puente con la experiencia de Machea.
   Es el unico modulo que conoce a la anfitriona; el resto no sabe que existe.

   La anfitriona llama a `actualizar(state, derived)` desde `updatePlantaDOM`,
   que es por donde pasa el quiz: responder o volver atras NO dispara el
   `render()` completo, justamente para no destruir los nodos de la escena. */
(function () {
  'use strict';

  var G = window.GDF3D;
  var escena = null;
  var apagado = false;
  var ultimaClave = null;

  /* Se cae al plano 2D de recortes —que ya funciona— en vez de mostrar un
     hueco. El 3D es una mejora, no un requisito. */
  function soportado() {
    try {
      var c = document.createElement('canvas');
      if (!(c.getContext('webgl2') || c.getContext('webgl'))) return false;
    } catch (e) { return false; }
    var n = navigator;
    if (n.deviceMemory && n.deviceMemory <= 2) return false;
    if (n.hardwareConcurrency && n.hardwareConcurrency <= 2) return false;
    if (n.connection && n.connection.saveData) return false;
    return true;
  }

  function preset() {
    var angosto = window.matchMedia('(max-width: 900px)').matches;
    var quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    return {
      // En un panel de 250 px las sombras no se leen y cuestan un pase entero.
      sombras: !angosto,
      dprMax: angosto ? 1.5 : 2,
      mapaSombra: 1024,
      animar: !quieto
    };
  }

  function crear() {
    if (escena || apagado) return escena;
    if (!soportado()) { apagado = true; return null; }
    try {
      escena = G.crearEscena(preset());
    } catch (e) {
      // Crear el contexto puede fallar por razones que no detecta el sondeo.
      console.warn('[plano3d] sin 3D:', e);
      apagado = true;
    }
    return escena;
  }

  function actualizar(state, derived) {
    var esc = crear();
    if (!esc) return false;

    var host = document.querySelector('.gdf-scene');
    if (!host) return false;
    // Idempotente: `render()` desprende el lienzo del arbol sin destruir su
    // contexto, asi que basta re-adoptarlo.
    esc.montar(host);
    host.classList.add('con-plano3d');

    var answers = (state && state.answers) || {};
    // `qi` es el indice de la pregunta en curso, o sea cuantas van contestadas.
    var paso = Math.max(0, Number(state && state.qi) || 0);
    if (paso < 1) return true;   // todavia no hay nada que construir

    /* Reconstruir el plano en cada repintado seria tirar el CSG a la basura sin
       motivo: la anfitriona llama aqui tambien por cambios que no tocan las
       respuestas. */
    var clave = paso + '|' + JSON.stringify(answers);
    if (clave === ultimaClave) return true;
    ultimaClave = clave;

    esc.aplicarPlan(G.construirPlan(answers, paso));
    return true;
  }

  window.GDF3D.actualizar = actualizar;
  window.GDF3D.activo = function () { return !!escena && !apagado; };
  window.GDF3D.escena = function () { return escena; };
})();
