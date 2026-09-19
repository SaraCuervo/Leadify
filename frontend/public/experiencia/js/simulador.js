// Dinero: formato colombiano y elegibilidad de subsidio VIS. El nombre del
// archivo es historia — hasta hace poco vivía acá también un simulador de
// plan de pagos (overlay de dos pasos, tasas, amortización francesa) que se
// quitó de la tarjeta; lo que queda es justo lo que la tarjeta sigue usando
// para pintar el precio y el chip de subsidio, y no vale la pena mudarlo a
// otro archivo por dos funciones y una constante.
//
// `millones()` se llama ahora `pesos()` y ya no abrevia: ver su comentario.
(function () {
  'use strict';

  var SUPUESTOS = {
    // Salario mínimo 2026. Las pistas de la pregunta de ingresos en
    // js/data.js se calculan con este mismo valor, así que moverlo obliga a
    // revisarlas ("hasta 2 SMMLV ≈ $3,5M"). Actualizar cada año.
    smmlv: 1750905,

    // Techo del valor de una vivienda VIS, en SMMLV. Son 135 en general y
    // 150 en aglomeración urbana; la demo es solo de Bogotá, que va por los
    // 150. Confirmar si algún día se vuelve a incluir el resto del país.
    topeVisSmmlv: 150,

    // Subsidio a la cuota inicial para vivienda VIS, escalonado por ingresos
    // del hogar y expresado en SMMLV. Va SIN nombre de programa a propósito:
    // el esquema está en transición, así que la UI lo llama "subsidio
    // estimado, sujeto a verificación" y no promete un programa puntual.
    subsidioSmmlv: { '≤2 SMMLV': 30, '2–4 SMMLV': 20 },
  };

  // ¿Este proyecto puede recibir el subsidio a la cuota inicial? Dos
  // condiciones del INMUEBLE: estar marcado VIS y no pasarse del techo de
  // valor. El `vis` del catálogo no basta — hay proyectos marcados VIS cuyas
  // tipologías más grandes se salen del tope.
  function aptoParaSubsidio(vis, precio) {
    if (!vis || !precio) return false;
    return precio <= SUPUESTOS.topeVisSmmlv * SUPUESTOS.smmlv;
  }

  // Monto estimado del subsidio para un hogar, en pesos; 0 si sus ingresos
  // se pasan del tope (el escalón solo llega hasta 4 SMMLV).
  function subsidioEstimado(rangoIngresos) {
    return (SUPUESTOS.subsidioSmmlv[rangoIngresos] || 0) * SUPUESTOS.smmlv;
  }

  // El precio COMPLETO, con separador de miles colombiano: "$240.800.000".
  //
  // ANTES ABREVIABA A "$240,8M" Y SE CAMBIO A PROPOSITO. La abreviatura ahorra
  // seis caracteres en el sitio donde menos falta hacen: el precio es el dato
  // que la gente compara entre tarjetas, y "240,8M" obliga a traducir de
  // cabeza para compararlo con lo que tiene ahorrado o con lo que le presta el
  // banco. Ademas escondia la precision que si tenemos —el catalogo publica
  // 262.635.750, no "262,6M"—.
  //
  // El punto como separador de miles es el uso colombiano (y el que ya usa
  // `numeroEs` en templates.js para los decimales con coma). Se hace con la
  // regex y no con toLocaleString para que no dependa de la configuracion
  // regional del navegador de quien mire: en un equipo en ingles saldrian
  // comas y el numero se leeria como otro.
  function pesos(v) {
    if (!v) return '—';
    return '$' + Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  window.GDF = window.GDF || {};
  window.GDF.simulador = {
    aptoParaSubsidio: aptoParaSubsidio,
    subsidioEstimado: subsidioEstimado,
    pesos: pesos,
    SUPUESTOS: SUPUESTOS,
  };
})();
