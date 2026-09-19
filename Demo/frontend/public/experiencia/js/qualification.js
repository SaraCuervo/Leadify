// Calificación/priorización de leads — el resultado CENTRAL del reto de
// Colsubsidio: no basta con recomendar vivienda, hay que decidir si el lead
// pasa directo al asesor o entra a un flujo de nutrición/maduración.
//
// Reglas ligadas al brief del hackathon "Reto Vivienda" (Colsubsidio × 30X):
// - Regla 90/10: Colsubsidio debe vender 90% a afiliados, 10% a no afiliados.
// - Validar capacidad de compra (ingreso, ahorro) antes de pasar al asesor.
// - VIS + primera vivienda habilita el subsidio a la cuota inicial (cierre
//   concreto).
// - Los leads que no califican HOY no son "innecesarios": se nutren, nunca
//   se descartan ni se les oculta el catálogo recomendado.
(function () {
  'use strict';

  var READY_THRESHOLD = 60; // único punto de ajuste del umbral ready/nurture

  function computeLeadQualification(answers, bestMatchScore) {
    var s = 40; // punto de partida neutral
    var notes = [];

    // 1. Cupo 90/10: un afiliado avanza casi directo; un no afiliado sigue
    //    siendo un lead válido (cabe en el 10% o puede afiliarse) — nunca
    //    descalifica por sí solo.
    if (answers.afiliado === 'Sí') {
      s += 22;
      notes.push('Afiliado Colsubsidio');
    } else {
      s += 6;
      notes.push('No afiliado — cupo 10% / posible afiliación');
    }

    // 2. Capacidad financiera real (ahorro/cesantías) — la señal más directa
    //    de "puede comprar ya", antes de ocupar tiempo del asesor.
    //    El quiz ya no pregunta por el ahorro, así que normalmente no llega
    //    dato: en ese caso el factor no suma ni resta. Solo se penaliza si el
    //    lead declara explícitamente que aún no tiene ahorro — no saberlo no
    //    es lo mismo que no tenerlo.
    if (answers.ahorro === 'Sí, completo') {
      s += 18;
      notes.push('Cuota inicial lista');
    } else if (answers.ahorro === 'Algo') {
      s += 6;
      notes.push('Ahorro parcial');
    } else if (answers.ahorro === 'Aún no') {
      s -= 10;
      notes.push('Aún sin ahorro');
    }

    // 3. Rango de ingresos: define el universo de proyectos financiables.
    s += ({ '≤2 SMMLV': -4, '2–4 SMMLV': 4, '4–8 SMMLV': 10, '8+ SMMLV': 10 })[answers.ingresos] || 0;

    // 4. VIS + primera vivienda = elegible al subsidio a la cuota inicial:
    //    combinación concreta y accionable de inmediato para un asesor. Sin
    //    nombre de programa a propósito — el esquema está en transición y no
    //    prometemos uno puntual (mismo criterio que el simulador).
    //    Hoy queda inactivo: el quiz ya no pregunta si es la primera vivienda,
    //    así que `answers.primera` no llega. Se conserva la regla porque el
    //    dato puede volver a capturarse (p. ej. ya en la conversación con el
    //    asesor) sin tener que reescribir la calificación.
    if (answers.tipo === 'VIS' && answers.primera === 'Sí') {
      s += 10;
      notes.push('Elegible a subsidio de cuota inicial');
    }

    // 5. Ingreso bajo pidiendo No VIS: suele indicar que el lead aún no
    //    conoce sus opciones reales — mejor nutrir/educar que enviarlo así,
    //    sin preparación, a una conversación de cierre.
    if (answers.tipo === 'No VIS' && answers.ingresos === '≤2 SMMLV') {
      s -= 14;
      notes.push('Ingreso y tipo de vivienda aún no calzan');
    }

    // 6. Qué tan bien calza con el inventario disponible ahora mismo (score
    //    de computeMatches). Si ni el mejor proyecto calza, un asesor no
    //    tiene todavía nada concreto que ofrecer.
    if (bestMatchScore >= 80) {
      s += 10;
      notes.push('Excelente match de proyectos');
    } else if (bestMatchScore >= 65) {
      s += 4;
    } else {
      s -= 8;
      notes.push('Match de proyectos aún débil');
    }

    s = Math.max(5, Math.min(98, Math.round(s)));
    var ready = s >= READY_THRESHOLD;

    return {
      score: s,
      status: ready ? 'ready' : 'nurture',
      label: ready ? 'Listo para asesor' : 'En maduración',
      icon: ready ? '✅' : '🌱',
      notes: notes,
    };
  }

  window.GDF = window.GDF || {};
  window.GDF.qualification = {
    computeLeadQualification: computeLeadQualification,
    READY_THRESHOLD: READY_THRESHOLD,
  };
})();
