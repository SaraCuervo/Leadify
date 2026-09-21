/* Geometria del plano: muros extruidos con sus aberturas recortadas, ubicacion
   de puertas y ventanas, y la caja envolvente que usa el encuadre.

   Puerto directo del prototipo en React (`src/geometry/`). Es codigo agnostico
   del framework —solo Three.js—, asi que lo unico que cambia es de donde sale
   `THREE` y que ya no hay tipos. */
(function () {
  'use strict';

  var Libs = window.GDF3DLibs;
  var THREE = Libs.THREE;

  var ALTO_PUERTA = 2.05;
  var ALTO_VENTANA = 1.2;

  /* Un solo evaluador para todo: crear uno por muro desperdicia su cache de BVH.
     `useGroups` en false porque renderizamos con un material unico; en true la
     geometria sale con grupos multi-material que aqui no sirven de nada. */
  var evaluador = new Libs.Evaluator();
  evaluador.useGroups = false;

  function altoAbertura(op) {
    if (op.height !== undefined) return op.height;
    return op.type === 'door' ? ALTO_PUERTA : ALTO_VENTANA;
  }

  /* La cortadora se ubica en el espacio LOCAL del muro: la caja esta centrada en
     el origen y corre a lo largo de X, asi que X va de -largo/2 a largo/2 y la Y
     de -alto/2 a alto/2.

     Las medidas horizontales vienen del plano y se escalan; las verticales
     (alto, alfeizar) ya estan en metros, porque ninguna imagen de planta las
     contiene. Escalar las verticales es un bug silencioso hasta que scale != 1. */
  function cortadora(op, muro, largo, grosor, scale) {
    var alto = altoAbertura(op);
    var base = op.type === 'door' ? 0 : (op.sill || 0);

    // Sobresale del grosor a proposito: al ras, la cara de la cortadora queda
    // coplanar con la del corte y deja artefactos.
    var c = new Libs.Brush(new THREE.BoxGeometry(op.width * scale, alto, grosor * 2));
    c.position.set(
      op.offset * largo - largo / 2,
      base + alto / 2 - muro.height / 2,
      0
    );
    c.updateMatrixWorld();
    return c;
  }

  function geometriaMuro(muro, aberturas, largo, grosor, scale) {
    var solido = new THREE.BoxGeometry(largo, muro.height, grosor);
    if (!aberturas.length) return solido;

    var res = new Libs.Brush(solido);
    res.updateMatrixWorld();

    for (var i = 0; i < aberturas.length; i++) {
      var c = cortadora(aberturas[i], muro, largo, grosor, scale);
      var previo = res;
      res = evaluador.evaluate(previo, c, Libs.SUBTRACTION);
      // Cada evaluate devuelve un Brush nuevo: el anterior queda huerfano.
      previo.geometry.dispose();
      c.geometry.dispose();
    }
    return res.geometry;
  }

  /* Cache de geometria por muro. Recortar un vano es caro, y la escena pide el
     plano entero en cada respuesta aunque casi todos los muros sigan igual: sin
     cache se recalcula el CSG para tirarlo acto seguido. Ir y venir por el
     formulario deja de costar nada.

     Las geometrias cacheadas se marcan para que la limpieza de la escena NO las
     libere: estan compartidas, y soltarlas dejaria el cache apuntando a
     geometria muerta. */
  var cache = {};
  var ordenCache = [];
  var TOPE_CACHE = 300;

  function cachear(clave, hacer) {
    if (cache[clave]) return cache[clave];
    var g = hacer();
    g.userData.cacheado = true;
    cache[clave] = g;
    ordenCache.push(clave);
    if (ordenCache.length > TOPE_CACHE) {
      var viejo = ordenCache.shift();
      if (cache[viejo]) { cache[viejo].dispose(); delete cache[viejo]; }
    }
    return g;
  }

  function n2(v) { return (Math.round(v * 100) / 100).toFixed(2); }

  /* Convierte los segmentos de muro del plano en mallas en espacio de escena
     (plano XZ, Y hacia arriba), con las aberturas ya recortadas. */
  function construirMuros(plan) {
    return plan.walls.map(function (muro) {
      var sx = muro.start[0], sy = muro.start[1];
      var ex = muro.end[0], ey = muro.end[1];
      var largo = Math.hypot(ex - sx, ey - sy) * plan.scale;
      var grosor = muro.thickness * plan.scale;
      var aberturas = plan.openings.filter(function (o) { return o.wallId === muro.id; });

      /* La clave describe la FORMA, no el muro: los identificadores se renumeran
         en cada plano, asi que usarlos haria fallar el cache siempre. */
      var clave = [n2(largo), n2(grosor), n2(muro.height)].concat(
        aberturas.map(function (o) {
          return o.type + n2(o.offset) + n2(o.width) + n2(o.sill || 0) + n2(o.height || 0);
        }).sort()
      ).join('|');

      var g = cachear(clave, function () {
        var geo = geometriaMuro(muro, aberturas, largo, grosor, plan.scale);
        /* El traslado va DENTRO de la fabrica: fuera, cada acierto de cache
           volveria a desplazar la misma geometria y los muros treparian medio
           alto por respuesta. Deja la base en y=0 local, para que el muro pueda
           crecer con scale.y desde el piso. */
        geo.translate(0, muro.height / 2, 0);
        return geo;
      });

      return {
        id: muro.id,
        geometry: g,
        position: [((sx + ex) / 2) * plan.scale, 0, ((sy + ey) / 2) * plan.scale],
        rotationY: -Math.atan2(ey - sy, ex - sx),
        thickness: grosor
      };
    });
  }

  /* Ubicacion de aberturas. Compartida por puertas y ventanas para que la
     trigonometria del muro viva en un solo sitio. */
  function ubicarAberturas(plan, tipo) {
    var out = [];
    plan.openings.forEach(function (op) {
      if (op.type !== tipo) return;
      var muro = null;
      for (var i = 0; i < plan.walls.length; i++) {
        if (plan.walls[i].id === op.wallId) { muro = plan.walls[i]; break; }
      }
      if (!muro) return;

      var sx = muro.start[0], sy = muro.start[1];
      var ex = muro.end[0], ey = muro.end[1];
      var largo = Math.hypot(ex - sx, ey - sy) * plan.scale;
      var angulo = -Math.atan2(ey - sy, ex - sx);
      var a = op.offset * largo - largo / 2;
      var mx = ((sx + ex) / 2) * plan.scale;
      var mz = ((sy + ey) / 2) * plan.scale;

      out.push({
        opening: op,
        width: op.width * plan.scale,
        height: altoAbertura(op),
        sill: op.type === 'door' ? 0 : (op.sill || 0),
        thickness: muro.thickness * plan.scale,
        center: [mx + Math.cos(angulo) * a, 0, mz - Math.sin(angulo) * a],
        wallAngle: angulo
      });
    });
    return out;
  }

  /* Caja alineada a los ejes de la vivienda construida: huella en XZ y Y desde
     el piso hasta el muro mas alto. */
  function cajaDelPlano(plan) {
    /* Sin muros no hay caja, y hay que decirlo con numeros finitos: sobre una
       lista vacia `Math.min.apply` devuelve Infinity y `Math.max` -Infinity, y
       de ahi salen un centro NaN y un tamano -Infinity que acaban en las
       posiciones de la geometria. No falla nada visible —three solo avisa de
       que el radio es NaN al calcular la esfera envolvente— y por eso conviene
       cortarlo aqui: el plano esta vacio mientras se contesta la pregunta de
       ubicacion, que no construye nada (ver ETAPAS en perfil.js). */
    if (!plan.walls.length) {
      return { center: [0, 0, 0], halfExtents: [0, 0, 0] };
    }

    var xs = [], zs = [];
    plan.walls.forEach(function (w) {
      xs.push(w.start[0] * plan.scale, w.end[0] * plan.scale);
      zs.push(w.start[1] * plan.scale, w.end[1] * plan.scale);
    });
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
    var minZ = Math.min.apply(null, zs), maxZ = Math.max.apply(null, zs);
    var alto = Math.max.apply(null, plan.walls.map(function (w) { return w.height; }));

    return {
      center: [(minX + maxX) / 2, alto / 2, (minZ + maxZ) / 2],
      halfExtents: [(maxX - minX) / 2, alto / 2, (maxZ - minZ) / 2]
    };
  }

  // Las 8 esquinas de la caja, como desplazamientos desde su centro.
  function esquinas(caja) {
    var hx = caja.halfExtents[0], hy = caja.halfExtents[1], hz = caja.halfExtents[2];
    var out = [];
    [-hx, hx].forEach(function (x) {
      [-hy, hy].forEach(function (y) {
        [-hz, hz].forEach(function (z) { out.push([x, y, z]); });
      });
    });
    return out;
  }

  window.GDF3D = window.GDF3D || {};
  window.GDF3D.construirMuros = construirMuros;
  window.GDF3D.ubicarAberturas = ubicarAberturas;
  window.GDF3D.cajaDelPlano = cajaDelPlano;
  window.GDF3D.esquinas = esquinas;
  window.GDF3D.ALTO_PUERTA = ALTO_PUERTA;
})();
