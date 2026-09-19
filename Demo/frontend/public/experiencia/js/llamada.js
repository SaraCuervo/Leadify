// PASO 2 del contrato, de vuelta: la llamada de Manuela.
//
// Este archivo reemplaza al POST /leads que main.js documenta como
// eliminado ("AQUI SE ENVIABA EL LEAD"). No es el mismo contrato — no
// registra un lead_id, dispara una llamada real vía api.py -> Dapta — pero
// se engancha exactamente en el mismo punto: al entrar a 'confirmacion',
// una vez por partida, con el mismo patrón que cargarRecomendaciones() en
// main.js (cargando -> resuelto).
//
// POR QUÉ NO VA CONTRA MACHEA_BASE. Ese servicio (servicio_machea.py) solo
// sabe de recomendaciones y no conoce a Dapta ni tiene su API key. api.py sí
// la tiene, guardada en el servidor — nunca puede bajar al navegador — así
// que esta llamada va siempre contra DAPTA_LLAMADA_BASE (config.js),
// aunque SIN_BACKEND:true tenga las recomendaciones corriendo en local.
(function () {
  'use strict';

  function labelDe(qid, valor) {
    var q = (window.GDF.data.QUESTIONS || []).filter(function (x) { return x.id === qid; })[0];
    if (!q) return valor || '';
    var opt = (q.options || []).filter(function (o) { return o.v === valor; })[0];
    return opt ? opt.label : valor || '';
  }

  // entorno_deseado guarda un array de slugs ('piscina', 'zona kid'); Manuela
  // necesita texto legible, no el vocabulario interno del modelo.
  function entornoLegible(state) {
    var slugs = state.answers.entorno_deseado || [];
    var q = (window.GDF.data.QUESTIONS || []).filter(function (x) { return x.id === 'entorno_deseado'; })[0];
    var porSlug = {};
    (q ? q.options : []).forEach(function (o) { porSlug[o.v] = o.label; });
    return slugs.map(function (s) { return porSlug[s] || s; }).join(', ');
  }

  function personasNumero(state) {
    var v = state.answers.personas;
    if (v === '4+') return 4;
    var n = parseInt(v, 10);
    return isNaN(n) ? 0 : n;
  }

  function construirPayload(state) {
    var elegido = null;
    state.reco.items.forEach(function (vm) {
      if (vm.id === state.chosen) elegido = vm;
    });
    if (!elegido) return null;

    var apartamento = {
      nombre_proyecto: elegido.nombre,
      localidad: elegido.localidad || '',
      tipo_vivienda: elegido.vis ? 'VIS' : 'No VIS',
      precio_desde_cop: elegido.precioCop || 0,
      aplica_subsidio_caja: !!elegido.subsidio,
    };
    // Opcional en el contrato de api.py: el motor local (SIN_BACKEND) no lo
    // calcula, así que solo se manda cuando existe — nunca un 0 disfrazado.
    if (elegido.cuotaMensual) apartamento.cuota_mensual_estimada_cop = elegido.cuotaMensual;

    return {
      nombre: [state.nombre, state.apellido].filter(Boolean).join(' ').trim(),
      telefono: state.telefono.trim(),
      afiliado: state.afiliado === 'Sí',
      rango_ingreso: labelDe('ingresos', state.answers.ingresos),
      edad: parseInt(state.answers.edad, 10) || 0,
      personas_a_cargo: personasNumero(state),
      entorno_deseado: entornoLegible(state),
      apartamento: apartamento,
    };
  }

  /**
   * Dispara la llamada. `cb` recibe siempre { estado: 'lista' | 'error',
   * mensaje, real, telefono }, igual de forma que recommender.recomendar.
   * 'lista' cubre tanto un envío real (status "enviado") como el modo mock
   * del backend (status "mock_enqueued", cuando DAPTA_FLOW_WEBHOOK_URL no
   * está puesta en Render) — en los dos casos el POST llegó bien; lo que
   * cambia es `real`: solo con un envío real tiene sentido esperar un
   * resumen de verdad (ver verificarResultado más abajo).
   */
  function disparar(state, cb) {
    var base = (window.GDF_CONFIG || {}).DAPTA_LLAMADA_BASE;
    if (!base) {
      cb({ estado: 'error', mensaje: 'Falta window.GDF_CONFIG.DAPTA_LLAMADA_BASE (ver js/config.js).' });
      return;
    }

    var payload = construirPayload(state);
    if (!payload) {
      cb({ estado: 'error', mensaje: 'No se pudo armar la llamada: falta el proyecto elegido.' });
      return;
    }

    fetch(base.replace(/\/$/, '') + '/api/llamar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json().then(function (d) {
          if (!res.ok) {
            console.error('[GDF/llamada] /api/llamar respondió ' + res.status + ':', d);
            cb({ estado: 'error', mensaje: d.detail || 'No pudimos iniciar la llamada.' });
            return;
          }
          if (d.status === 'mock_enqueued') {
            console.warn('[GDF/llamada] modo mock — DAPTA_FLOW_WEBHOOK_URL no configurada en el backend.', d);
          }
          cb({
            estado: 'lista',
            real: d.status === 'enviado',
            telefono: d.telefono || null,
            mensaje: d.status === 'enviado'
              ? '¡Manuela te está llamando! Contesta en los próximos segundos.'
              : 'Simulado — el backend no tiene el webhook de Dapta configurado.',
          });
        });
      })
      .catch(function (err) {
        console.error('[GDF/llamada] fallo de red contra ' + base, err);
        cb({ estado: 'error', mensaje: 'No pudimos conectar con el servidor de llamadas.' });
      });
  }

  /**
   * Un solo chequeo de si ya llegó el resumen post-llamada (ver el receptor
   * del webhook en api.py, /webhooks/dapta/resultado). `cb` recibe el cuerpo
   * tal cual lo devuelve el backend: { listo: false } mientras no llega, o
   * { listo: true, temperatura_lead, resumen_llamada, recomendacion_asesor,
   * ... } una vez Dapta empuja el análisis. main.js decide el intervalo y
   * cuándo dejar de intentar — esta función solo hace UN chequeo.
   */
  function verificarResultado(telefono, cb) {
    var base = (window.GDF_CONFIG || {}).DAPTA_LLAMADA_BASE;
    if (!base || !telefono) {
      cb({ listo: false });
      return;
    }
    fetch(base.replace(/\/$/, '') + '/api/llamar/resultado?telefono=' + encodeURIComponent(telefono))
      .then(function (res) { return res.ok ? res.json() : { listo: false }; })
      .then(cb)
      .catch(function (err) {
        console.error('[GDF/llamada] fallo consultando el resultado', err);
        cb({ listo: false });
      });
  }

  window.GDF = window.GDF || {};
  window.GDF.llamada = { disparar: disparar, verificarResultado: verificarResultado };
})();
