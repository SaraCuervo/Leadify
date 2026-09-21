/* Ensambla el FloorPlan que consume el render, a partir de las respuestas.
   Es el puente entre la mitad "logica" (perfil + zonificacion + muros) y la
   mitad "geometria", y el unico sitio que conoce las dos. */
(function () {
  'use strict';

  // Acabado de piso por zona. Los banos van en ceramica aunque su zona sea
  // privada, que es como se resuelve en obra.
  function acabado(r) {
    if (r.zona === 'humeda') return 'tile';
    if (r.id.indexOf('bano') === 0) return 'tile';
    return 'wood';
  }

  /* Mobiliario por ambiente. Las posiciones son fracciones del rectangulo, no
     metros, para que un mismo ambiente amueble igual de bien en un VIS apretado
     que en un No VIS amplio. */
  /* Un mueble pegado a un muro tiene que elegir un muro SIN vano. El closet se
     ponia siempre al este y, cuando la puerta caia de ese lado, quedaba plantado
     en el paso. */
  function ladoLibre(preferidos, bloqueados) {
    var veto = bloqueados || [];
    for (var i = 0; i < preferidos.length; i++) {
      if (veto.indexOf(preferidos[i]) < 0) return preferidos[i];
    }
    return preferidos[0];
  }

  // Fraccion del rectangulo donde queda el centro de algo pegado a ese muro.
  var CONTRA = { o: [0.14, 0.5], e: [0.86, 0.5], n: [0.5, 0.14], s: [0.5, 0.86] };

  function amoblar(r, perfil, vetados) {
    var rect = r.rect, out = [];
    var x = rect.x, z = rect.z, w = rect.w, d = rect.d;
    // fx/fz: fraccion del ancho y del fondo -> metros absolutos
    var P = function (fx, fz) { return [x + w * fx, z + d * fz]; };
    var n = 0;
    var HOLGURA = 0.04;   // no pegar al muro: se ve como si lo atravesara

    /* Encaja la pieza dentro del ambiente en vez de confiar en la fraccion.
       Colocar por fracciones es comodo pero no comprueba nada: con un tamano
       fijo, en un ambiente chico la pieza se desborda y aparece atravesando el
       muro. Aqui se encoge lo que no quepa y se corre el centro lo justo. */
    var poner = function (kind, pos, size, rot) {
      var giro = ((rot || 0) % 180 + 180) % 180;
      // A 90 grados el ancho declarado pasa a medir en Z y el fondo en X.
      var ex = giro === 90 ? size[1] : size[0];
      var ez = giro === 90 ? size[0] : size[1];
      ex = Math.min(ex, w - HOLGURA * 2);
      ez = Math.min(ez, d - HOLGURA * 2);

      var cx = Math.min(Math.max(pos[0], x + ex / 2 + HOLGURA), x + w - ex / 2 - HOLGURA);
      var cz = Math.min(Math.max(pos[1], z + ez / 2 + HOLGURA), z + d - ez / 2 - HOLGURA);

      out.push({
        id: r.id + '-' + kind + (++n), kind: kind,
        position: [cx, cz],
        size: giro === 90 ? [ez, ex] : [ex, ez],
        rotation: rot || 0
      });
    };
    var horizontal = w >= d;

    switch (true) {
      case r.id === 'sala': {
        var areaSala = w * d;
        poner('rug', P(0.5, 0.5), [w * 0.6, d * 0.5]);
        poner('sofa', P(0.5, 0.18), [Math.min(2.1, w * 0.7), 0.85]);
        poner('table', P(0.5, 0.52), [Math.min(1.0, w * 0.35), 0.6]);

        /* La sala es el ambiente mas grande y con tres piezas quedaba medio
           vacia frente a las alcobas, que estan justas. Lo que se agrega depende
           del area, no de un numero fijo: en un VIS apretado sobrecargarla seria
           peor que dejarla sobria. */
        var ladoTV = ladoLibre(['s', 'n', 'e', 'o'], vetados);
        poner('console', P(CONTRA[ladoTV][0], CONTRA[ladoTV][1]),
          ladoTV === 'n' || ladoTV === 's'
            ? [Math.min(1.5, w * 0.4), 0.35]
            : [0.35, Math.min(1.5, d * 0.4)]);
        if (areaSala > 8.5) poner('chair', P(0.15, 0.68), [0.6, 0.6], -45);
        if (areaSala > 9.8) poner('plant', P(0.89, 0.13), [0.34, 0.34]);

        // Los extras salen del tramo de ingresos: es lo unico que esa pregunta
        // mueve en la escena.
        if (perfil.extrasSala.indexOf('mesaAuxiliar') >= 0) poner('table', P(0.12, 0.2), [0.45, 0.45]);
        if (perfil.extrasSala.indexOf('bar') >= 0) poner('counter', P(0.85, 0.75), [Math.min(1.3, w * 0.4), 0.5], 0);
        if (perfil.extrasSala.indexOf('piano') >= 0) poner('counter', P(0.2, 0.8), [1.4, 0.7], 0);
        break;
      }

      case r.id === 'comedor':
        // Un comedor amplio admite alfombra bajo la mesa; uno justo, no.
        if (w * d > 9) poner('rug', P(0.5, 0.5), [w * 0.75, d * 0.7]);
        poner('table', P(0.5, 0.5), [Math.min(1.5, w * 0.6), Math.min(0.95, d * 0.5)]);
        poner('chair', P(0.28, 0.5), [0.45, 0.45], 90);
        poner('chair', P(0.72, 0.5), [0.45, 0.45], -90);
        poner('chair', P(0.5, 0.22), [0.45, 0.45]);
        poner('chair', P(0.5, 0.78), [0.45, 0.45], 180);
        break;

      case r.id === 'flexible':
        if (perfil.esJoven) {
          poner('desk', P(0.5, 0.15), [Math.min(1.4, w * 0.7), 0.6]);
          poner('chair', P(0.5, 0.35), [0.45, 0.45], 180);
        } else {
          poner('sofa', P(0.5, 0.25), [Math.min(1.8, w * 0.7), 0.8]);
          poner('rug', P(0.5, 0.6), [w * 0.6, d * 0.4]);
        }
        break;

      case r.id === 'cocina': {
        // El meson va contra un muro sin vano: pegado al del paso, tapaba la
        // entrada a la cocina.
        var ladoC = ladoLibre(horizontal ? ['n', 's', 'o', 'e'] : ['o', 'e', 'n', 's'], vetados);
        var cc = CONTRA[ladoC];
        var horizC = ladoC === 'n' || ladoC === 's';
        poner('counter', P(cc[0], cc[1]), horizC ? [w * 0.8, 0.6] : [0.6, d * 0.8]);
        // La estufa comparte muro con el meson, corrida a un extremo.
        poner('stove', horizC ? P(0.22, cc[1]) : P(cc[0], 0.22), [0.6, 0.6]);
        // La nevera busca otro muro, y tampoco el del vano.
        var ladoN = ladoLibre(
          ['e', 'o', 's', 'n'].filter(function (k) { return k !== ladoC; }), vetados
        );
        poner('fridge', P(CONTRA[ladoN][0], CONTRA[ladoN][1]), [0.7, 0.7]);
        break;
      }

      case r.id === 'ropas': {
        var ladoR = ladoLibre(['n', 's', 'o', 'e'], vetados);
        poner('counter', P(CONTRA[ladoR][0], CONTRA[ladoR][1]),
          Math.min(1.1, w * 0.8) >= Math.min(0.6, d * 0.6)
            ? [Math.min(1.1, w * 0.7), Math.min(0.5, d * 0.5)]
            : [Math.min(0.5, w * 0.5), Math.min(1.1, d * 0.7)]);
        break;
      }

      case r.id.indexOf('bano') === 0:
        poner('toilet', P(0.25, 0.75), [0.45, 0.6], 0);
        poner('sink', P(0.25, 0.18), [0.6, 0.45]);
        poner('shower', P(0.75, 0.6), [Math.min(0.9, w * 0.45), Math.min(0.9, d * 0.45)]);
        break;

      case r.id.indexOf('alcoba') === 0:
        var principal = r.id === 'alcoba1';
        var camaW = principal ? 1.6 : 1.0;
        poner('bed', P(0.45, 0.45), [Math.min(camaW, w * 0.7), Math.min(2.0, d * 0.75)]);
        /* Sin rotar: `size` ya se da en [extension X, extension Z]. Rotarlo 90
           grados sin intercambiar las medidas metia el lado largo a traves del
           muro y el closet salia del edificio. */
        var lado = ladoLibre(['e', 'o', 'n', 's'], vetados);
        var contra = CONTRA[lado];
        var vertical = lado === 'e' || lado === 'o';
        poner('wardrobe', P(contra[0], contra[1]),
          vertical
            ? [Math.min(0.6, w * 0.22), Math.min(1.8, d * 0.6)]
            : [Math.min(1.8, w * 0.6), Math.min(0.6, d * 0.22)]);
        /* Una cama, un closet y (a veces) un tapete dejaban la alcoba principal
           —el ambiente mas grande del plano, hasta 12 m2— mas vacia que la sala.
           La mesa de noche va del lado de la cabecera que el closet no ocupo. */
        poner('table', P(vertical && lado === 'e' ? 0.17 : 0.83, 0.16), [0.4, 0.4]);
        var areaAlc = w * d;
        if (principal && areaAlc > 9) poner('table', P(vertical && lado === 'e' ? 0.83 : 0.17, 0.16), [0.4, 0.4]);
        if (areaAlc > 10.5) poner('plant', P(0.84, 0.86), [0.32, 0.32]);
        if (principal) poner('rug', P(0.45, 0.85), [w * 0.5, d * 0.18]);
        break;
    }
    return out;
  }


  /* Franja de paso frente a un vano: por ahi se entra, y ningun mueble puede
     ocuparla. */
  function pasoDe(muro, op) {
    var horiz = Math.abs(muro.end[1] - muro.start[1]) < 1e-6;
    var L = Math.hypot(muro.end[0] - muro.start[0], muro.end[1] - muro.start[1]);
    var t = op.offset * L;
    var cx = horiz ? Math.min(muro.start[0], muro.end[0]) + t : muro.start[0];
    var cz = horiz ? muro.start[1] : Math.min(muro.start[1], muro.end[1]) + t;
    var FONDO = 0.45;
    return horiz
      ? { x0: cx - op.width / 2, x1: cx + op.width / 2, z0: cz - FONDO, z1: cz + FONDO }
      : { x0: cx - FONDO, x1: cx + FONDO, z0: cz - op.width / 2, z1: cz + op.width / 2 };
  }

  function huella(f) {
    var giro = ((f.rotation || 0) % 180 + 180) % 180;
    var ex = giro === 90 ? f.size[1] : f.size[0];
    var ez = giro === 90 ? f.size[0] : f.size[1];
    return {
      x0: f.position[0] - ex / 2, x1: f.position[0] + ex / 2,
      z0: f.position[1] - ez / 2, z1: f.position[1] + ez / 2, ex: ex, ez: ez
    };
  }

  function choca(a, b) {
    return Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0) > 0.05 &&
      Math.min(a.z1, b.z1) - Math.max(a.z0, b.z0) > 0.05;
  }

  /* Corre los muebles que tapan un vano. Elegir el muro correcto al colocarlos
     resuelve la mayoria, pero no todo: en un bano de 1.6 m la franja de paso se
     come un tercio del ambiente y cualquier posicion fija choca tarde o
     temprano. Se prueban las posiciones espejadas dentro del mismo ambiente y
     se toma la primera que despeje. */
  function despejarVanos(plan) {
    var porAmbiente = {};
    plan.rooms.forEach(function (r) {
      var xs = r.polygon.map(function (q) { return q[0]; });
      var zs = r.polygon.map(function (q) { return q[1]; });
      porAmbiente[r.id] = {
        x0: Math.min.apply(null, xs), x1: Math.max.apply(null, xs),
        z0: Math.min.apply(null, zs), z1: Math.max.apply(null, zs)
      };
    });

    var pasos = [];
    plan.openings.forEach(function (op) {
      if (op.type !== 'door') return;
      var muro = null;
      for (var i = 0; i < plan.walls.length; i++) {
        if (plan.walls[i].id === op.wallId) { muro = plan.walls[i]; break; }
      }
      if (muro) pasos.push(pasoDe(muro, op));
    });

    (plan.furniture || []).forEach(function (f) {
      if (f.kind === 'rug') return;            // una alfombra no estorba el paso
      var cuarto = porAmbiente[f.id.split('-')[0]];
      if (!cuarto) return;
      var estorba = function () {
        var h = huella(f);
        for (var i = 0; i < pasos.length; i++) if (choca(h, pasos[i])) return true;
        return false;
      };
      if (!estorba()) return;

      var original = [f.position[0], f.position[1]];
      var tamOriginal = [f.size[0], f.size[1]];

      /* Se barren las posiciones utiles del ambiente —esquinas y centros de
         muro— y no solo los espejos: en un bano de 1.5 m el espejo cae en la
         misma franja de paso y no despeja nada. */
      function intentar() {
        var h = huella(f);
        var mx = h.ex / 2 + 0.04, mz = h.ez / 2 + 0.04;
        var xs = [cuarto.x0 + mx, (cuarto.x0 + cuarto.x1) / 2, cuarto.x1 - mx];
        var zs = [cuarto.z0 + mz, (cuarto.z0 + cuarto.z1) / 2, cuarto.z1 - mz];
        for (var a = 0; a < xs.length; a++) {
          for (var b = 0; b < zs.length; b++) {
            f.position = [
              Math.min(Math.max(xs[a], cuarto.x0 + mx), cuarto.x1 - mx),
              Math.min(Math.max(zs[b], cuarto.z0 + mz), cuarto.z1 - mz)
            ];
            if (!estorba()) return true;
          }
        }
        return false;
      }

      if (intentar()) return;
      // Si el ambiente es tan justo que ninguna posicion despeja, la pieza cede
      // tamano: mejor un mueble pequeno que uno plantado en la entrada.
      f.size = [tamOriginal[0] * 0.65, tamOriginal[1] * 0.65];
      if (intentar()) return;
      f.size = tamOriginal;
      f.position = original;
    });
  }

  function construirPlan(answers, paso, opts) {
    var perfil = window.GDF3D.perfilDesdeRespuestas(answers, paso);
    var zon = window.GDF3D.zonificar(perfil);
    var md = window.GDF3D.derivarMuros(zon, opts);
    var vetados = md.ladosBloqueados || {};

    var rooms = zon.rects.map(function (r) {
      var q = r.rect;
      return {
        id: r.id,
        name: r.nombre,
        zona: r.zona,
        floor: acabado(r),
        // En sentido horario: el generador de geometria triangula el poligono
        // tal cual, sin reordenarlo.
        polygon: [[q.x, q.z], [q.x + q.w, q.z], [q.x + q.w, q.z + q.d], [q.x, q.z + q.d]]
      };
    });

    var furniture = [];
    zon.rects.forEach(function (r) {
      if (r.zona === 'circulacion') return;
      furniture = furniture.concat(amoblar(r, perfil, vetados[r.id]));
    });

    var plan = {
      // La zonificacion ya trabaja en metros, asi que no hay conversion: el
      // `scale` existe para los planos que vienen de una imagen.
      scale: 1,
      walls: md.walls,
      openings: md.openings,
      rooms: rooms,
      furniture: furniture,
      // Util para la ficha y para depurar; el render lo ignora.
      meta: {
        ancho: zon.pl.w, fondo: zon.pl.d,
        area: zon.pl.w * zon.pl.d,
        alcobas: perfil.nAlcobas, banos: perfil.nBanos,
        vis: perfil.vis, paso: perfil.paso
      }
    };
    despejarVanos(plan);
    return plan;
  }

  window.GDF3D = window.GDF3D || {};
  window.GDF3D.construirPlan = construirPlan;
})();
