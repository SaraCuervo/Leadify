/* La base de datos del formulario: Postgres gestionado (Supabase).
 *
 * QUE SE GUARDA
 * -------------
 * Quien es la persona (cedula, nombre, correo, telefono), que respondio y que
 * se le recomendo, que proyecto le intereso, y si en la llamada acabo
 * agendando cita con un asesor.
 *
 * COMO SE ENTRA
 * -------------
 * NO se leen las tablas. La clave que viaja en este archivo es publica —
 * cualquiera la ve con ver-codigo-fuente— asi que las tablas estan cerradas a
 * cal y canto y solo se exponen cuatro funciones del lado del servidor. La de
 * lectura exige cedula Y telefono: sin los dos no devuelve nada, ni siquiera
 * confirma que la cedula exista. Eso es lo que evita que alguien con una
 * cedula ajena vea el nombre, el correo y las recomendaciones de esa persona,
 * porque aqui no hay login que lo impida.
 *
 * NADA DE ESTO PUEDE ROMPER EL FORMULARIO. Si la base no responde, cada
 * funcion llama a su callback con el error y el quiz sigue su camino normal:
 * guardar es un efecto secundario, no un requisito. Por eso ningun callback
 * recibe solo el dato — siempre es (dato, error), y quien llama decide.
 */
(function () {
  'use strict';

  window.GDF = window.GDF || {};

  function cfg() {
    return window.GDF_CONFIG || {};
  }

  // Sin credenciales configuradas la app funciona igual, solo que no persiste.
  // Es el mismo criterio que SIN_BACKEND: la falta de un servicio opcional no
  // es un fallo que haya que "arreglar" a la fuerza.
  function activo() {
    return !!(cfg().SUPABASE_URL && cfg().SUPABASE_KEY);
  }

  function rpc(fn, cuerpo, cb) {
    cb = cb || function () {};
    if (!activo()) {
      cb(null, 'sin base de datos configurada');
      return;
    }
    var c = cfg();
    fetch(c.SUPABASE_URL.replace(/\/$/, '') + '/rest/v1/rpc/' + fn, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: c.SUPABASE_KEY,
        Authorization: 'Bearer ' + c.SUPABASE_KEY,
      },
      body: JSON.stringify(cuerpo),
    })
      .then(function (res) {
        return res.json().then(function (d) {
          if (!res.ok) throw new Error((d && (d.message || d.hint)) || 'HTTP ' + res.status);
          return d;
        });
      })
      .then(function (d) {
        cb(d, null);
      })
      .catch(function (err) {
        console.warn('[GDF/datos] ' + fn + ' fallo:', err);
        cb(null, (err && err.message) || 'error de red');
      });
  }

  /**
   * Busca la ultima consulta de alguien que ya paso por aqui.
   * `cb(registro, error)` — `registro` es null si no hay nada (o si la pareja
   * cedula/telefono no coincide, que desde fuera es indistinguible a proposito).
   */
  function buscar(cedula, telefono, cb) {
    if (!cedula || !telefono) {
      cb(null, 'faltan cedula o telefono');
      return;
    }
    rpc('buscar_resultados', { p_cedula: cedula, p_telefono: telefono }, function (d, err) {
      if (err) {
        cb(null, err);
        return;
      }
      // La funcion devuelve una tabla: viene lista, vacia si no hubo match.
      cb(d && d.length ? d[0] : null, null);
    });
  }

  /**
   * Guarda lo que la persona respondio y lo que se le recomendo.
   * `resultado` se guarda TAL CUAL lo devuelve js/recommender.js, para que
   * restaurarlo sea volver a pasarselo a la misma accion que lo pinto la
   * primera vez (ver 'recoResuelta' en state.js). Si se guardara masticado,
   * habria dos formas distintas de construir la misma pantalla.
   */
  function guardar(state, resultado, cb) {
    rpc(
      'guardar_consulta',
      {
        p_cedula: state.cedula,
        p_nombre: state.nombre,
        p_apellido: state.apellido,
        p_correo: state.correo,
        p_telefono: state.telefono,
        p_respuestas: state.answers || {},
        p_resultados: resultado || {},
      },
      cb
    );
  }

  /** Anota que proyecto le intereso. */
  function marcarInteres(state, proyecto, consultaId, cb) {
    rpc(
      'marcar_interes',
      {
        p_cedula: state.cedula,
        p_telefono: state.telefono,
        p_proyecto: proyecto,
        p_consulta_id: consultaId || null,
      },
      cb
    );
  }

  /**
   * Cierra el ciclo: hubo intencion de compra si en la llamada quedo una cita
   * puesta. La senal es `fecha_de_seguimiento`, que Dapta devuelve en el
   * analisis post-llamada (ver el webhook en api/app.py). Si viene vacia, la
   * funcion del servidor deja `intencion_compra` en false — la decision de que
   * cuenta como intencion vive alla, no aqui.
   */
  function marcarIntencion(state, proyecto, fechaSeguimiento, temperatura, cb) {
    rpc(
      'marcar_intencion',
      {
        p_cedula: state.cedula,
        p_telefono: state.telefono,
        p_proyecto: proyecto,
        p_fecha_seguimiento: fechaSeguimiento || null,
        p_temperatura: temperatura || null,
      },
      cb
    );
  }

  window.GDF.datos = {
    activo: activo,
    buscar: buscar,
    guardar: guardar,
    marcarInteres: marcarInteres,
    marcarIntencion: marcarIntencion,
  };
})();
