// Normaliza el campo `espacios[]` de las tipologías del catálogo scrapeado a
// un vocabulario cerrado de piezas dibujables, para que js/planta.js pueda
// generar la planta de un apartamento REAL.
//
// Es el equivalente en JS de lo que `clave_de_amenidad` hace en
// tools/scrape_proyectos.py: una tabla de reglas ORDENADAS, gana la primera
// que casa, y `null` si no encaja — nunca se fuerza una etiqueta a una
// categoría que no le corresponde.
//
// POR QUÉ HACE FALTA
// ------------------
// El sitio publica los espacios como texto libre y cada constructora escribe a
// su manera: 534 items en 81 tipologías con ~64 etiquetas distintas. Conviven
// 'Salacomedor' (42 veces, pegado), 'Sala comedor' (21) y 'Sala' (11); las
// habitaciones vienen unas veces ENUMERADAS ('Habitación 2') y otras AGREGADAS
// ('3 habitaciones', 'Tres habitaciones'); y hay erratas reales del CMS
// ('Baño y viester', 'Walkingcloset').
(function () {
  'use strict';

  // Mismo criterio que en recommender.js: se construye con new RegExp para que
  // el archivo no lleve caracteres combinantes sueltos, invisibles en el editor.
  var RE_DIACRITICOS = new RegExp('[\u0300-\u036f]', 'g');

  function sinTildes(s) {
    return String(s || '').normalize('NFD').replace(RE_DIACRITICOS, '');
  }

  function normalizarTexto(s) {
    return sinTildes(s).toLowerCase().replace(/\s+/g, ' ').trim();
  }

  // 'Tres habitaciones' -> 3. El sitio alterna dígito y palabra.
  var NUMEROS = { un: 1, una: 1, uno: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5 };

  // OJO: el número solo cuenta si va al PRINCIPIO de la etiqueta.
  // '3 habitaciones' es un agregado (3 piezas), pero 'Habitación 2' es un
  // ORDINAL (1 pieza). Aceptar el dígito en cualquier posición hace que Acanto
  // salga con 6 alcobas — verificado.
  function numeroLider(texto) {
    var m = texto.match(/^(\d+|un|una|uno|dos|tres|cuatro|cinco)\b/);
    if (!m) return 1;
    var n = NUMEROS[m[1]] || parseInt(m[1], 10);
    return n > 0 && n < 10 ? n : 1;
  }

  // El ORDEN de esta tabla es el diseño, no un detalle de implementación.
  // Dos trampas comprobadas contra las 81 tipologías reales:
  //
  //   1. `opcional` va PRIMERO. 'Disponible para futuro baño o vestier' es una
  //      posibilidad que ofrece la constructora, no una pieza que exista.
  //   2. 'Habitación principal con baño' tiene que casar ANTES que la regla
  //      genérica de baño, porque contiene la palabra "baño". Con el orden mal
  //      se pierde la alcoba principal y las discrepancias con p.hab suben de
  //      25 a 30. Por lo mismo 'Baño alcobas' casa como baño, no como alcoba.
  var REGLAS = [
    // 1 — opcionales/futuros: se registran aparte, no cuentan como pieza firme
    { re: /^(1 )?disponible|^proyeccion|^espacio para|^disponible para|^area de estudio o habitacion|con opcion de/, opcional: true },

    // 2-5 — húmedos (van antes que las alcobas, ver nota de arriba)
    { re: /(habitacion|alcoba) principal con bano/, da: ['habitacion_principal', 'bano_privado'] },
    { re: /bano (y|con) (vestier|viester|closet)/, da: ['bano_privado', 'vestier'] },
    { re: /bano principal|bano alcoba principal/, da: ['bano_privado'] },
    { re: /bano/, da: ['bano'], cuenta: true },

    // 6-8 — privados
    { re: /(habitacion|alcoba) principal/, da: ['habitacion_principal'] },
    { re: /habitacion|alcoba/, da: ['habitacion'], cuenta: true },
    { re: /walking ?closet|vestier|viester/, da: ['vestier'] },

    // 9-13 — sociales y servicio
    { re: /cocina/, da: ['cocina'] },
    { re: /sala ?comedor|sala y comedor|zona social|area social/, da: ['sala_comedor'] },
    { re: /^sala$/, da: ['sala'] },
    { re: /^comedor$/, da: ['comedor'] },
    // 'Zona de descanso' aparece en Lúmina 77 (Tipo A y E, de 31-33 m²) junto a
    // 'Sala' y 'Alcoba principal': es un rincón de estar, no una alcoba más.
    { re: /estudio|sala de tareas|estar de tv|sala tv|sala de tv|zona de descanso/, da: ['estudio'] },
    { re: /ropa|lavanderia/, da: ['ropas'] },

    // 14-17 — extras
    { re: /balcon|terraza/, da: ['balcon'] },
    { re: /deposito/, da: ['deposito'] },
    { re: /parqueadero/, da: ['parqueadero'] },
  ];

  /**
   * 'Habitación principal con baño' -> [{clave:'habitacion_principal', ...},
   *                                     {clave:'bano_privado', ...}]
   * Devuelve null si la etiqueta no es una pieza del apartamento. Eso pasa de
   * verdad: en algunas fichas se colaron amenidades dentro de `espacios[]`
   * ('Cuarto de basuras', 'Administración', 'Salón juvenil', 'Zona de arte').
   * null es la respuesta correcta para esas, no una categoría inventada.
   */
  function clavesDeEspacio(label) {
    var texto = normalizarTexto(label);
    if (!texto) return null;

    for (var i = 0; i < REGLAS.length; i++) {
      var r = REGLAS[i];
      if (!r.re.test(texto)) continue;

      // La regla de opcionales no dice QUÉ pieza es, solo que es hipotética:
      // se reintenta contra el resto de la tabla para averiguar la clave.
      if (r.opcional) {
        var interna = claveIgnorandoOpcionales(texto);
        return interna ? [{ clave: interna, cantidad: 1, opcional: true }] : null;
      }

      var cantidad = r.cuenta ? numeroLider(texto) : 1;
      return r.da.map(function (clave, idx) {
        // 'Habitación principal con baño' con cantidad>1 no existe; el
        // multiplicador solo aplica a la primera clave de la regla.
        return { clave: clave, cantidad: idx === 0 ? cantidad : 1, opcional: false };
      });
    }
    return null;
  }

  function claveIgnorandoOpcionales(texto) {
    for (var i = 1; i < REGLAS.length; i++) {
      if (REGLAS[i].re.test(texto)) return REGLAS[i].da[0];
    }
    return null;
  }

  /**
   * Recorre los `espacios[]` de una tipología y devuelve cuántas piezas de cada
   * clave hay, las que son solo posibles, y las etiquetas que no clasificó
   * (útil al regenerar proyectos.js: si aparece una etiqueta nueva se ve aquí).
   */
  function normalizar(espacios) {
    var conteo = {};
    var opcionales = {};
    var sinClasificar = [];

    (espacios || []).forEach(function (e) {
      var label = e && e.label;
      var claves = clavesDeEspacio(label);
      if (!claves) {
        if (label) sinClasificar.push(label);
        return;
      }
      claves.forEach(function (c) {
        var destino = c.opcional ? opcionales : conteo;
        destino[c.clave] = (destino[c.clave] || 0) + c.cantidad;
      });
    });

    return { conteo: conteo, opcionales: opcionales, sinClasificar: sinClasificar };
  }

  // m² de referencia por pieza. Se usan aquí solo para la red de seguridad
  // (¿el programa leído justifica el área de la ficha?); el reparto real de
  // superficie lo hace js/planta.js con su propia tabla.
  var M2_REFERENCIA = {
    sala_comedor: 16, sala: 10, comedor: 8, cocina: 7, ropas: 2,
    bano: 3.2, bano_privado: 3.6, habitacion_principal: 11, habitacion: 8,
    vestier: 2.4, estudio: 6, balcon: 3.5, deposito: 2,
  };

  function m2Programa(conteo) {
    var total = 0;
    Object.keys(conteo).forEach(function (clave) {
      total += (M2_REFERENCIA[clave] || 0) * conteo[clave];
    });
    return total;
  }

  /**
   * El resumen que consume js/planta.js: qué piezas tiene esta tipología.
   *
   * MANDA `espacios[]`, NO `p.hab`/`p.banos`. Es deliberado y está medido:
   * 25 de las 81 tipologías discrepan del dato de proyecto, y los casos son
   * inequívocos a favor de los espacios. Infinitum Zentral Tipo H son 31,9 m²
   * con una sola alcoba listada, y `p.hab` dice 2; lo mismo Eskala Tipo A
   * (34,4 m²), Lúmina 77 Tipo E (31,4 m²) y Ciudad Jardín Tipo A (33,6 m²).
   * La razón de fondo es que `hab` es dato de PROYECTO y la planta es de
   * TIPOLOGÍA: dentro de un mismo proyecto las tipologías varían.
   *
   * `p.hab`/`p.banos` quedan como red de seguridad para los dos casos en que
   * los espacios no alcanzan, y entonces `fuenteHab` lo deja anotado.
   */
  function resumenTipologia(tipologia, proyecto) {
    var t = tipologia || {};
    var p = proyecto || {};
    var n = normalizar(t.espacios);
    var c = n.conteo;

    var areaPrivada = t.areaPrivada || t.area || p.area || 45;
    var habitaciones = (c.habitacion || 0) + (c.habitacion_principal ? 1 : 0);
    var banos = (c.bano || 0) + (c.bano_privado || 0);
    var fuenteHab = 'espacios';

    // Red de seguridad 1: la ficha no listó ninguna alcoba.
    if (habitaciones === 0 && p.hab > 0) {
      habitaciones = p.hab;
      fuenteHab = 'proyecto';
    }
    // Red de seguridad 2: el programa leído no justifica el área publicada
    // (pasa cuando la ficha lista los espacios a medias). Si el proyecto dice
    // que hay más alcobas, se le cree a él.
    var programa = m2Programa(c);
    if (programa > 0 && areaPrivada / programa > 1.6 && p.hab > habitaciones) {
      habitaciones = p.hab;
      fuenteHab = 'proyecto';
    }
    if (banos === 0) {
      banos = p.banos > 0 ? p.banos : 1;
    }

    return {
      habitaciones: Math.max(1, Math.min(4, habitaciones)),
      principal: !!c.habitacion_principal || habitaciones > 0,
      banos: Math.max(1, Math.min(3, banos)),
      banoPrivado: !!c.bano_privado,
      vestier: !!c.vestier,
      estudio: !!c.estudio,
      balcon: !!c.balcon,
      ropas: !!c.ropas,
      deposito: !!c.deposito,
      // Siempre hay cocina, la liste la ficha o no: un apartamento sin cocina
      // dibujada se lee como un error del generador, no como un dato fiel.
      cocina: true,
      salaComedor: !c.sala || !!c.sala_comedor,
      opcionales: n.opcionales,
      areaPrivada: areaPrivada,
      area: t.area || areaPrivada,
      fuenteHab: fuenteHab,
      sinClasificar: n.sinClasificar,
    };
  }

  /**
   * Auditoría de las 81 tipologías del catálogo. No se llama sola: es para
   * ejecutarla a mano desde la consola del navegador
   * (`GDF.espacios.auditar()`) al regenerar proyectos.js, y ver de un vistazo
   * si aparecieron etiquetas que ninguna regla clasifica.
   */
  function auditar() {
    var proyectos = window.GDF_PROYECTOS || [];
    var filas = [];
    var sinClasificar = {};
    var problemas = [];

    proyectos.forEach(function (p) {
      (p.tipologias || []).forEach(function (t) {
        var r = resumenTipologia(t, p);
        filas.push({
          proyecto: p.name, tipologia: t.nombre,
          hab: r.habitaciones, 'p.hab': p.hab, banos: r.banos,
          m2: r.areaPrivada, fuente: r.fuenteHab,
        });
        r.sinClasificar.forEach(function (l) {
          sinClasificar[l] = (sinClasificar[l] || 0) + 1;
        });
        if (!r.areaPrivada) problemas.push(p.name + ' ' + t.nombre + ': sin área');
      });
    });

    var discrepan = filas.filter(function (f) { return f.hab !== f['p.hab']; });
    console.log('tipologías: %d | discrepan de p.hab: %d | por proyecto: %d',
      filas.length, discrepan.length,
      filas.filter(function (f) { return f.fuente === 'proyecto'; }).length);
    console.table(filas);
    console.log('etiquetas sin clasificar:', sinClasificar);
    if (problemas.length) console.warn('problemas:', problemas);
    return { filas: filas, discrepan: discrepan, sinClasificar: sinClasificar };
  }

  window.GDF = window.GDF || {};
  window.GDF.espacios = {
    clavesDeEspacio: clavesDeEspacio,
    normalizar: normalizar,
    resumenTipologia: resumenTipologia,
    auditar: auditar,
    REGLAS: REGLAS,
  };
})();
