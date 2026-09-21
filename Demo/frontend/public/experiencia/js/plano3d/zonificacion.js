/* Distribucion de la planta: bandas verticales reales —social junto al balcon,
   nucleo humedo, circulacion, alcobas—, no repartos arbitrarios.

   Puerto de la maqueta de agosto (casa-vivienda-3d.html, 1289-1557). Aquel
   leia dos globales, `respuestas` y `paso`; aqui todo entra por `perfil`.

   Devuelve DATOS PUROS: rectangulos en metros por ambiente. No hay muros ni
   puertas — eso lo deriva `muros.js` a partir de estos rectangulos. */
(function () {
  'use strict';

  /* Programa de areas objetivo en m2. La planta se dimensiona a partir de esto,
     no al reves: si entran mas alcobas, el apartamento crece. */
  var PROGRAMA = {
    sala: 11, comedor: 7.5, flexible: 6.5, cocina: 6, ropas: 2.6,
    bano: 3, banoPriv: 2.8, alcoba1: 10, alcobaN: 7.5
  };
  var MIN = { soc: 2.6, hum: 1.95, priUna: 2.65, corr: 1.05 };
  var PROPORCION = 1.55;   // la planta tiende a ser ancha y no profunda
  var FACTOR_VIS = 0.78;   // el VIS aprieta el programa un 22 %

  // Lista de ambientes desbloqueados a una altura dada del formulario.
  function programa(perfil, hasta) {
    var E = perfil.etapas, n = perfil.nAlcobas;
    var f = perfil.vis ? FACTOR_VIS : 1;
    var A = function (x) { return x * f; };
    var soc = [], hum = [], pri = [];

    if (hasta >= E.sala) soc.push({ id: 'sala', nombre: 'Sala', area: A(PROGRAMA.sala), zona: 'social' });
    if (hasta >= E.comedor) soc.push({ id: 'comedor', nombre: 'Comedor', area: A(PROGRAMA.comedor), zona: 'social' });
    /* Con 3 alcobas ya no queda programa para un cuarto flexible: los
       catalogos VIS de 3 alcobas dan 40-56 m2, y agregarlo aqui siempre
       (sin mirar cuantas alcobas hay) inflaba esos planos a 65-76 m2. Con 1
       o 2 alcobas el area libre lo admite bien.

       Ojo: se mira `nAlcobasResuelto`, no solo `n < 3`. Antes de responder
       `habitaciones`, `n` es una ESTIMA (`sugeridaAlcobas`) que para hogares
       de 4+ personas ya vale 3 desde el paso 3. Condicionar solo en `n`
       aplicaba este recorte tambien ahi, encogia el ancho social de golpe y
       el mueble de ropas quedaba tapando su puerta en 90 de 1008 corridas —
       ningun usuario alcanzo a responder nada nuevo para que el plano se
       hubiera movido asi. */
    if (hasta >= E.flexible && !(n >= 3 && perfil.nAlcobasResuelto)) {
      soc.push({
        id: 'flexible',
        nombre: perfil.esJoven ? 'Estudio' : 'Sala de estar',
        area: A(PROGRAMA.flexible), zona: 'social'
      });
    }
    if (hasta >= E.cocina) hum.push({ id: 'cocina', nombre: 'Cocina', area: A(PROGRAMA.cocina), zona: 'humeda' });
    if (hasta >= E.ropas) hum.push({ id: 'ropas', nombre: 'Zona de ropa', area: A(PROGRAMA.ropas), zona: 'humeda' });

    // Una sola alcoba: su bano es el unico, no hay bano social aparte.
    var soloUno = hasta >= E.alcobas && n === 1;
    if (hasta >= E.bano && !soloUno) {
      hum.push({ id: 'bano', nombre: 'Bano social', area: A(PROGRAMA.bano), zona: 'humeda' });
    }
    if (hasta >= E.alcoba1) {
      pri.push({ id: 'alcoba1', nombre: 'Alcoba principal', area: A(PROGRAMA.alcoba1), zona: 'privada' });
    }
    if (hasta >= E.alcobas) {
      pri.push({ id: 'banoPriv', nombre: 'Bano principal', area: A(PROGRAMA.banoPriv), zona: 'privada' });
      for (var i = 2; i <= n; i++) {
        pri.push({ id: 'alcoba' + i, nombre: 'Alcoba ' + i, area: A(PROGRAMA.alcobaN), zona: 'privada' });
      }
    }
    return { soc: soc, hum: hum, pri: pri, n: n };
  }

  // Fondo minimo habitable, en metros, segun el tipo de ambiente.
  function fondoMin(r) {
    if (r.id.indexOf('alcoba') === 0) return 2.30;
    if (r.id.indexOf('bano') === 0) return 1.55;
    if (r.id === 'cocina') return 2.00;
    if (r.id === 'ropas') return 1.45;
    return 1.90;
  }
  // Fondo maximo, como proporcion del ancho de su banda: evita ambientes tubo.
  function fondoMax(r, w) {
    if (r.id.indexOf('alcoba') === 0) return w * 1.9;
    if (r.id.indexOf('bano') === 0) return w * 2.1;
    if (r.id === 'cocina') return w * 2.2;
    if (r.id === 'ropas') return w * 2.0;
    if (r.zona === 'social') return w * 2.3;
    return 99;
  }

  function suma(a) { return a.reduce(function (s, r) { return s + r.area; }, 0); }
  function sumaFondoMin(a) { return a.reduce(function (s, r) { return s + fondoMin(r); }, 0); }

  // Reparte las alcobas en dos columnas. La principal y su bano van juntas.
  function partirPrivada(pri) {
    var A = [], B = [];
    var peso = function (g) { return g.reduce(function (s, r) { return s + r.area; }, 0); };
    pri.forEach(function (r, i) {
      if (i < 2) A.push(r);
      else (peso(A) <= peso(B) ? A : B).push(r);
    });
    return { A: A, B: B, peso: peso };
  }

  /* Busca el fondo que da la mejor proporcion respetando los anchos minimos de
     cada banda. Si una banda no cabe en su minimo, la planta crece. */
  function dimensiones(prog) {
    var As = suma(prog.soc), Ah = suma(prog.hum), Ap = suma(prog.pri);
    var cols = prog.n >= 3 ? 2 : 1;
    var wCorr = prog.pri.length ? MIN.corr : 0;
    var minPri = cols === 2 ? (prog.n >= 4 ? 5.5 : 5.0) : MIN.priUna;

    var dMinPri = 0;
    if (prog.pri.length) {
      if (cols === 1) dMinPri = sumaFondoMin(prog.pri);
      else {
        var p = partirPrivada(prog.pri);
        dMinPri = Math.max(sumaFondoMin(p.A), sumaFondoMin(p.B));
      }
    }
    /* La humeda (y, con dos columnas, la columna A de privada) NO reciben el
       fondo D completo: `zonificar` les resta `ramal` para el vestibulo antes
       de apilarlas (`D - ramal`, mas abajo). Sin sumarlo aqui, `dMin` se queda
       corto y `apilarMin` fija cada cuarto a su minimo pero el `D` que le
       toca ya no alcanza para todos: el rescale final (linea ~155) los
       encoge a todos por igual por debajo de su propio minimo. Asi fue como
       `ropas` termino en 1.10 m de fondo con `fondoMin` en 1.45 — el mueble
       ya no tenia donde no tapar la puerta. */
    var ramal0 = wCorr > 0 ? Math.min(1.25, wCorr + 0.2) : 0;
    var dMin = Math.max(
      4.4, sumaFondoMin(prog.soc), sumaFondoMin(prog.hum) + ramal0, dMinPri + ramal0
    );

    var mejor = null;
    for (var D = dMin; D <= 15; D += 0.05) {
      var wS = As > 0 ? Math.max(As / D, MIN.soc) : 0;
      var wH = Ah > 0 ? Math.max(Ah / D, MIN.hum) : 0;
      var wP = Ap > 0 ? Math.max(Ap / D, minPri) : 0;
      var W = wS + wH + wP + wCorr;
      if (W <= 0) continue;
      /* El error mezcla forma y metros sobrantes a proposito. Buscando solo la
         proporcion 1.55, cuando una banda toca su ancho minimo, estirar el
         fondo para cuadrar la forma infla metros que nadie pidio: un VIS de
         tres alcobas terminaba en 75 m2 con un programa que suma 56. */
      var util = As + Ah + Ap + wCorr * D;
      var sobra = (W * D - util) / util;
      var err = Math.abs(W / D - PROPORCION) * 0.25 + sobra;
      if (!mejor || err < mejor.err) {
        mejor = { err: err, D: D, W: W, wS: wS, wH: wH, wP: wP, wCorr: wCorr, cols: cols };
      }
    }
    return mejor || { D: 6, W: 7, wS: 7, wH: 0, wP: 0, wCorr: 0, cols: 1 };
  }

  /* Apila los ambientes de una banda a lo largo de Z, repartiendo el fondo en
     proporcion al area pero respetando minimos y maximos de cada uno. */
  function apilarMin(rooms, x, w, D) {
    if (!rooms.length) return [];
    var min = rooms.map(fondoMin);
    var max = rooms.map(function (r) { return fondoMax(r, w); });
    var fijo = rooms.map(function () { return false; });
    var tope = rooms.map(function () { return false; });
    var d = rooms.map(function () { return 0; });

    for (var it = 0; it <= rooms.length * 2; it++) {
      var resto = D, area = 0;
      rooms.forEach(function (r, i) { if (fijo[i]) resto -= d[i]; else area += r.area; });
      var nuevo = false;
      rooms.forEach(function (r, i) {
        if (fijo[i]) return;
        d[i] = area > 0 ? resto * r.area / area : resto / rooms.length;
        if (d[i] < min[i]) { d[i] = min[i]; fijo[i] = true; nuevo = true; }
        else if (d[i] > max[i]) { d[i] = max[i]; fijo[i] = true; tope[i] = true; nuevo = true; }
      });
      if (!nuevo) break;
    }

    // El sobrante va a los que aun pueden crecer, nunca a los que ya tocaron su
    // proporcion maxima. Asi la alcoba no se estira hasta quedar un pasillo.
    var sobra = D - d.reduce(function (a, b) { return a + b; }, 0);
    if (sobra > 1e-6) {
      var libres = rooms.map(function (r, i) { return i; }).filter(function (i) { return !tope[i]; });
      var areaL = libres.reduce(function (t, i) { return t + rooms[i].area; }, 0);
      if (libres.length && areaL > 0) {
        libres.forEach(function (i) { d[i] += sobra * rooms[i].area / areaL; });
      }
    }

    var f = D / d.reduce(function (a, b) { return a + b; }, 0);
    var z = -D / 2, out = [];
    rooms.forEach(function (r, i) {
      var dd = d[i] * f;
      out.push(Object.assign({}, r, { rect: { x: x, z: z, w: w, d: dd } }));
      z += dd;
    });
    return out;
  }

  /* La planta no sale siempre igual: se espeja y se invierte el orden de los
     ambientes segun un hash del tipo y el nombre. Determinista, asi que no
     cambia mientras se responde. */
  function varianteLayout(semilla) {
    var txt = String(semilla || ''), h = 2166136261;
    for (var i = 0; i < txt.length; i++) {
      h ^= txt.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    h = Math.abs(h);
    return { mx: !!(h & 1), mz: !!(h & 2), invSoc: !!(h & 4), invPri: !!(h & 8) };
  }

  function zonificar(perfil) {
    var E = perfil.etapas;
    // El dimensionado usa SIEMPRE el programa completo, no el desbloqueado:
    // asi los muros no bailan a medida que se contesta.
    var full = programa(perfil, 999);
    var dim = dimensiones(full);
    var D = dim.D, W = dim.W, x0 = -W / 2, xHum = x0 + dim.wS;
    var todos = [], corredores = [];

    if (!full.pri.length || dim.wCorr <= 0) {
      todos = apilarMin(full.soc, x0, dim.wS, D).concat(apilarMin(full.hum, xHum, dim.wH, D));
      return {
        pl: { w: W, d: D }, rects: todos, corredores: [], zonasAcceso: [],
        corredor: null, dim: dim, completo: todos
      };
    }

    /* Circulacion en L: un pasillo vertical junto a la zona privada y un
       vestibulo horizontal que lo conecta con la social. Asi se llega a
       cualquier alcoba o bano sin cruzar otra habitacion. */
    var v = varianteLayout(perfil.semilla);
    var soc = v.invSoc ? full.soc.slice().reverse() : full.soc;
    var ramal = Math.min(1.25, dim.wCorr + 0.2);
    var corrido = function (r) {
      return Object.assign({}, r, { rect: Object.assign({}, r.rect, { z: r.rect.z - ramal / 2 }) });
    };

    if (dim.cols === 2) {
      var p = partirPrivada(full.pri);
      var colA = v.invPri ? p.A.slice().reverse() : p.A;
      var colB = v.invPri ? p.B.slice().reverse() : p.B;
      var wA = dim.wP * p.peso(colA) / (p.peso(colA) + p.peso(colB) || 1);
      wA = Math.max(2.6, Math.min(dim.wP - 2.6, wA));
      var wB = dim.wP - wA;
      var xColA = xHum + dim.wH, xCorrDos = xColA + wA, xColB = xCorrDos + dim.wCorr;
      todos = apilarMin(soc, x0, dim.wS, D)
        .concat(apilarMin(full.hum, xHum, dim.wH, D - ramal).map(corrido))
        .concat(apilarMin(colA, xColA, wA, D - ramal).map(corrido))
        .concat(apilarMin(colB, xColB, wB, D));
      corredores = [
        {
          id: 'corredor', nombre: 'Circulacion', zona: 'circulacion',
          rect: { x: xCorrDos, z: -D / 2, w: dim.wCorr, d: D }
        },
        {
          id: 'vestibulo', nombre: 'Vestibulo', zona: 'circulacion',
          rect: { x: xHum, z: D / 2 - ramal, w: dim.wH + wA, d: ramal }
        }
      ];
    } else {
      var xCorr = xHum + dim.wH, xPri = xCorr + dim.wCorr;
      var pri = v.invPri ? full.pri.slice().reverse() : full.pri;
      todos = apilarMin(soc, x0, dim.wS, D)
        .concat(apilarMin(full.hum, xHum, dim.wH, D - ramal).map(corrido))
        .concat(apilarMin(pri, xPri, dim.wP, D));
      corredores = [
        {
          id: 'corredor', nombre: 'Circulacion', zona: 'circulacion',
          rect: { x: xCorr, z: -D / 2, w: dim.wCorr, d: D }
        },
        {
          id: 'vestibulo', nombre: 'Vestibulo', zona: 'circulacion',
          rect: { x: xHum, z: D / 2 - ramal, w: dim.wH, d: ramal }
        }
      ];
    }

    /* El espejado conserva exactamente las adyacencias —el acceso no puede
       romperse— pero cambia por completo donde queda cada zona. */
    var espejo = function (r) {
      var x = r.rect.x, z = r.rect.z, w = r.rect.w, d = r.rect.d;
      if (v.mx) x = -(x + w);
      if (v.mz) z = -(z + d);
      return Object.assign({}, r, { rect: { x: x, z: z, w: w, d: d } });
    };
    if (v.mx || v.mz) {
      todos = todos.map(espejo);
      corredores = corredores.map(espejo);
    }

    var ahora = programa(perfil, perfil.paso);
    var vivos = {};
    ahora.soc.concat(ahora.hum, ahora.pri).forEach(function (r) { vivos[r.id] = true; });
    var rects = todos.filter(function (r) { return vivos[r.id]; });

    /* La circulacion existe desde que hay ambientes cerrados —la cocina—, no
       desde que aparecen las alcobas: si no, cocina y ropas quedan sin acceso
       durante varios pasos. */
    var corrs = perfil.paso >= E.cocina ? corredores : [];

    /* El corredor se dibuja RECORTADO a la huella ya construida. A tamano final
       desde el paso 3 sirve alcobas que aun no existen, y el piso sobrante se
       lee como un vacio gris tan grande como la vivienda. Recortarlo no mueve
       nada: el tramo que ya estaba sigue donde estaba y el resto se suma
       despues. Lo que NO se recorta es `corredores`: de ahi salen los lados de
       puerta, que tienen que decidirse contra el plano completo. */
    if (corrs.length && rects.length) {
      var hx0 = Infinity, hx1 = -Infinity, hz0 = Infinity, hz1 = -Infinity;
      rects.forEach(function (r) {
        hx0 = Math.min(hx0, r.rect.x); hx1 = Math.max(hx1, r.rect.x + r.rect.w);
        hz0 = Math.min(hz0, r.rect.z); hz1 = Math.max(hz1, r.rect.z + r.rect.d);
      });
      corrs.forEach(function (c) {
        var q = c.rect;
        var x0 = Math.max(q.x, hx0), x1 = Math.min(q.x + q.w, hx1);
        var z0 = Math.max(q.z, hz0), z1 = Math.min(q.z + q.d, hz1);
        if (x1 - x0 < 0.3 || z1 - z0 < 0.3) return;   // no queda tramo util
        rects.push({
          id: c.id, nombre: c.nombre, zona: c.zona,
          rect: { x: x0, z: z0, w: x1 - x0, d: z1 - z0 }
        });
      });
    }

    /* Las puertas se deciden contra el plano COMPLETO, no contra lo revelado:
       si no, se moverian a medida que el apartamento se llena. */
    var zonas = corredores.concat(todos.filter(function (r) { return r.zona === 'social'; }));

    return {
      pl: { w: W, d: D }, rects: rects, corredores: corrs, zonasAcceso: zonas,
      corredor: corrs.filter(function (c) { return c.id === 'corredor'; })[0] || null,
      dim: dim, completo: todos
    };
  }

  window.GDF3D = window.GDF3D || {};
  window.GDF3D.zonificar = zonificar;
  window.GDF3D.PROGRAMA = PROGRAMA;
})();
