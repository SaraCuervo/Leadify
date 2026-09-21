/* La escena, en imperativo. Reemplaza la capa de componentes de React del
   prototipo: misma geometria y mismos materiales, sin framework.

   Dibuja BAJO DEMANDA. Entre respuesta y respuesta no se renderiza nada: en un
   formulario la escena esta quieta la mayor parte del tiempo, y un bucle
   continuo gastaria bateria por nada.

   Y no reconstruye: DIFERENCIA. Cada pieza lleva una clave derivada de su
   geometria, asi que al cambiar de plano solo entra lo nuevo y solo sale lo que
   se fue. Reconstruir entero haria que responder una pregunta volviera a armar
   el apartamento desde cero, que se lee como un parpadeo y no como algo que
   crece. */
(function () {
  'use strict';

  var THREE = window.GDF3DLibs.THREE;
  var G = window.GDF3D;

  // Se queda alto a proposito: con muros de 2.2 m un angulo bajo tapa el
  // interior y el apartamento se lee como una caja cerrada.
  var ELEVACION_DEF = 58, AZIMUT_DEF = 45;
  var MARGEN = 1.22;
  var GROSOR_BASE = 0.25;
  var HUNDIR_BASE = 0.02;   // la base y los pisos no pueden compartir y=0

  var ENTRADA = 0.7;        // lo que tarda una pieza en llegar a su sitio
  var SALIDA = 0.3;         // igual que `retirarPieza` de la anfitriona
  var DESFASE = 0.9;        // reparto total del escalonado entre las piezas
  var SEPARACION = 1.1;     // desde que distancia entra, en metros
  var ELEVA = 0.8;

  function suave(t) { return 1 - Math.pow(1 - t, 3); }
  function n2(v) { return (Math.round(v * 100) / 100).toFixed(2); }

  function crearEscena(opciones) {
    var o = opciones || {};
    var ELEVACION = THREE.MathUtils.degToRad(o.elevacion || ELEVACION_DEF);
    var AZIMUT = THREE.MathUtils.degToRad(o.azimut === undefined ? AZIMUT_DEF : o.azimut);
    var animar = o.animar !== false;

    var renderer = new THREE.WebGLRenderer({ antialias: o.antialias !== false, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, o.dprMax || 2));
    if (o.sombras !== false) {
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFShadowMap;
    }
    renderer.toneMappingExposure = 1.08;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);

    /* El modelo se orbita libre, asi que tiene que aguantar desde todos los
       lados. Hemisferica y no ambiental plana: el prototipo en React se apoyaba
       en un HDRI de drei que aqui seria una descarga de red, y sin el las
       superficies quedan planas. La hemisferica da cielo arriba y rebote de
       suelo abajo, que es justo la variacion que se pierde. */
    scene.add(new THREE.HemisphereLight(0xf2f6f8, 0x8d8579, 1.35));
    var sol = new THREE.DirectionalLight(0xffffff, 1.1);
    sol.position.set(7, 14, 5);
    if (o.sombras !== false) {
      sol.castShadow = true;
      sol.shadow.mapSize.set(o.mapaSombra || 1024, o.mapaSombra || 1024);
      // Sin esto, la moldura delgada se auto-sombrea en rayas que se arrastran.
      sol.shadow.normalBias = 0.02;
      sol.shadow.bias = -0.0004;
      var cs = sol.shadow.camera;
      cs.left = -12; cs.right = 12; cs.top = 12; cs.bottom = -12;
    }
    scene.add(sol);
    var relleno = new THREE.DirectionalLight(0xffffff, 0.45);
    relleno.position.set(-8, 10, -6);
    scene.add(relleno);

    var raiz = new THREE.Group();
    scene.add(raiz);

    var lienzo = renderer.domElement;
    lienzo.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block';

    var contenedor = null, ro = null, pendiente = false, vivo = true;
    var planActual = null, caja = null, esquinasCaja = null, edad = 1, ultimo = 0;
    var nodos = {};          // clave -> {grupo, anim}
    var baseNodo = null;

    /* ---------- bucle ---------- */

    function pedirCuadro() {
      if (pendiente || !vivo) return;
      pendiente = true;
      requestAnimationFrame(cuadro);
    }

    function cuadro(t) {
      pendiente = false;
      if (!vivo) return;
      var dt = ultimo ? Math.min((t - ultimo) / 1000, 0.05) : 0.016;
      ultimo = t;
      var sigue = false;

      /* Se sigue reencuadrando un rato tras montar: el contenedor suele medir
         cero o un tamano provisional en el primer cuadro, y un ajuste unico
         calculado contra eso deja la vivienda descentrada y recortada. */
      if (edad < 0.6) { edad += dt; encuadrar(); sigue = true; }
      if (avanzar(dt)) sigue = true;

      renderer.render(scene, camera);
      if (sigue) pedirCuadro();
    }

    function avanzar(dt) {
      var activo = false;
      Object.keys(nodos).forEach(function (clave) {
        var n = nodos[clave], a = n.anim;
        if (!a) return;
        a.t += dt;
        var p = Math.min(1, Math.max(0, (a.t - a.retraso) / a.dur));
        if (a.t < a.retraso) { activo = true; return; }

        var k = a.saliendo ? 1 - suave(p) : suave(p);
        var resto = 1 - k;
        n.grupo.position.set(a.dx * SEPARACION * resto, ELEVA * resto, a.dz * SEPARACION * resto);
        n.grupo.visible = true;

        if (p >= 1) {
          n.anim = null;
          if (a.saliendo) { soltar(n.grupo); delete nodos[clave]; }
        } else activo = true;
      });
      return activo;
    }

    /* ---------- limpieza ---------- */

    function soltar(nodo) {
      nodo.traverse(function (n) {
        if (!n.isMesh || !n.geometry) return;
        /* Los materiales son singletons compartidos: liberarlos romperia el
           resto de la escena. Y la geometria de muro esta CACHEADA por forma,
           asi que tampoco es propia: soltarla dejaria el cache apuntando a
           geometria muerta y el siguiente acierto dibujaria nada. */
        if (n.geometry.userData && n.geometry.userData.cacheado) return;
        n.geometry.dispose();
      });
      raiz.remove(nodo);
    }

    /* ---------- encuadre ---------- */

    var objetivo = new THREE.Vector3(), dir = new THREE.Vector3();
    var frente = new THREE.Vector3(), derecha = new THREE.Vector3(), arriba = new THREE.Vector3();
    var esquina = new THREE.Vector3();
    var ARRIBA = new THREE.Vector3(0, 1, 0);

    /* Distancia que mantiene las 8 esquinas de la caja dentro del frustum en
       esta orientacion. Interpolar entre dos distancias correctas en los
       extremos no sirve: a mitad de camino la inclinacion mete la altura de los
       muros en pantalla y la vivienda se sale del cuadro. */
    function encuadrar() {
      if (!caja) return;
      objetivo.set(caja.center[0], caja.center[1], caja.center[2]);
      dir.set(
        Math.cos(ELEVACION) * Math.sin(AZIMUT),
        Math.sin(ELEVACION),
        Math.cos(ELEVACION) * Math.cos(AZIMUT)
      );
      frente.copy(dir).negate();
      derecha.crossVectors(frente, ARRIBA).normalize();
      arriba.crossVectors(derecha, frente);

      var tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
      var tanH = tanV * camera.aspect;
      var dist = 0;
      for (var i = 0; i < esquinasCaja.length; i++) {
        esquina.set(esquinasCaja[i][0], esquinasCaja[i][1], esquinasCaja[i][2]);
        var a = esquina.dot(dir);
        var h = Math.abs(esquina.dot(derecha)) / tanH;
        var v = Math.abs(esquina.dot(arriba)) / tanV;
        dist = Math.max(dist, a + Math.max(h, v) * MARGEN);
      }
      camera.position.copy(objetivo).addScaledVector(dir, dist);
      camera.lookAt(objetivo);
    }

    function medir() {
      if (!contenedor) return;
      var r = contenedor.getBoundingClientRect();
      var w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      edad = 0;                 // un cambio de tamano reabre la ventana de ajuste
      pedirCuadro();
    }

    /* ---------- construccion de piezas ----------
       Cada pieza lleva una clave derivada de SU GEOMETRIA, no de su id: los
       identificadores de muro y abertura se renumeran en cada plano, asi que
       usarlos haria salir y volver a entrar piezas que no cambiaron. */

    function piezasDe(plan) {
      var M = G.materiales();
      var out = [];

      // Pisos. La Y va negada porque la rotacion de -90 en X mapea la Y de la
      // forma a Z invertida, y los muros ponen la Y del plano en +Z.
      plan.rooms.forEach(function (r) {
        var forma = new THREE.Shape(r.polygon.map(function (p) {
          return new THREE.Vector2(p[0] * plan.scale, -p[1] * plan.scale);
        }));
        var m = new THREE.Mesh(new THREE.ShapeGeometry(forma), G.materialPiso(r.floor));
        m.receiveShadow = true;
        var g = new THREE.Group();
        g.rotation.x = -Math.PI / 2;
        g.add(m);
        var xs = r.polygon.map(function (p) { return p[0]; });
        var zs = r.polygon.map(function (p) { return p[1]; });
        out.push({
          clave: 'piso|' + r.id + '|' + r.polygon.map(function (p) { return n2(p[0]) + ',' + n2(p[1]); }).join(';'),
          grupo: g, ambiente: r.id,
          centro: [(Math.min.apply(null, xs) + Math.max.apply(null, xs)) / 2,
                   (Math.min.apply(null, zs) + Math.max.apply(null, zs)) / 2]
        });
      });

      // Muros. La clave incluye sus aberturas: el corte CSG cambia la geometria.
      var porMuro = {};
      plan.openings.forEach(function (op) {
        (porMuro[op.wallId] = porMuro[op.wallId] || []).push(
          op.type + n2(op.offset) + n2(op.width) + n2(op.sill || 0)
        );
      });
      G.construirMuros(plan).forEach(function (w, i) {
        var muro = plan.walls[i];
        var m = new THREE.Mesh(w.geometry, M.muro);
        m.castShadow = true; m.receiveShadow = true;
        var g = new THREE.Group();
        g.add(m);
        m.position.set(w.position[0], w.position[1], w.position[2]);
        m.rotation.y = w.rotationY;
        out.push({
          clave: 'muro|' + n2(muro.start[0]) + ',' + n2(muro.start[1]) + '|' +
            n2(muro.end[0]) + ',' + n2(muro.end[1]) + '|' + n2(muro.thickness) + '|' +
            n2(muro.height) + '|' + (porMuro[muro.id] || []).sort().join('+'),
          grupo: g, ambiente: null,
          centro: [w.position[0], w.position[2]]
        });
      });

      // Marcos y vidrios de ventana. Las puertas no llevan marco: sus jambas
      // bajaban hasta el piso y dejaban una franja clara en cada umbral.
      var JAMBA = 0.06, SALIENTE = 0.03, SOLAPE = 0.012;
      G.ubicarAberturas(plan, 'window').forEach(function (p) {
        var g = new THREE.Group();
        g.add(marcoVentana(p, M, JAMBA, SALIENTE, SOLAPE));
        out.push({
          clave: 'ventana|' + n2(p.center[0]) + ',' + n2(p.center[2]) + '|' +
            n2(p.width) + '|' + n2(p.sill) + '|' + n2(p.wallAngle),
          grupo: g, ambiente: null, centro: [p.center[0], p.center[2]]
        });
      });

      var ABRE = THREE.MathUtils.degToRad(72);
      G.ubicarAberturas(plan, 'door').forEach(function (p) {
        // Los vanos interiores quedan abiertos: solo la entrada lleva hoja.
        if (!p.opening.hoja) return;
        var g = new THREE.Group();
        g.add(hojaPuerta(p, M, ABRE));
        out.push({
          clave: 'puerta|' + n2(p.center[0]) + ',' + n2(p.center[2]) + '|' +
            n2(p.width) + '|' + n2(p.wallAngle) + '|' + (p.opening.swing || 1),
          grupo: g, ambiente: p.opening.ambiente || null,
          centro: [p.center[0], p.center[2]]
        });
      });

      // Mobiliario.
      /* El tope para los muebles altos sale del muro mas bajo: un closet que
         asoma por encima de la pared se lee como si atravesara el techo. */
      var techo = Math.min.apply(null, plan.walls.map(function (w) { return w.height; })) * 0.92;
      (plan.furniture || []).forEach(function (item) {
        var g = G.mueble(item, plan.scale, techo);
        if (!g) return;
        var cont = new THREE.Group();
        cont.add(g);
        out.push({
          clave: 'mueble|' + item.kind + '|' + n2(item.position[0]) + ',' + n2(item.position[1]) +
            '|' + n2(item.size[0]) + ',' + n2(item.size[1]) + '|' + (item.rotation || 0),
          grupo: cont, ambiente: item.id.split('-')[0],
          centro: [item.position[0], item.position[1]]
        });
      });

      return out;
    }

    function marcoVentana(p, M, JAMBA, SALIENTE, SOLAPE) {
      var g = new THREE.Group();
      g.position.set(p.center[0], p.center[1], p.center[2]);
      g.rotation.y = p.wallAngle;
      var fondo = p.thickness + SALIENTE * 2;
      var alto = p.sill + p.height;

      /* Los marcos se solapan hacia dentro del hueco. Al ras, la cara interna de
         la jamba queda coplanar con la del corte CSG y ambas miran en la misma
         direccion: z-fighting que se arrastra al mover la camara. */
      [-1, 1].forEach(function (s) {
        var j = new THREE.Mesh(new THREE.BoxGeometry(JAMBA + SOLAPE, p.height, fondo), M.moldura);
        j.position.set(s * ((p.width + JAMBA) / 2 - SOLAPE / 2), p.sill + p.height / 2, 0);
        j.castShadow = true;
        g.add(j);
      });
      [alto + JAMBA / 2 - SOLAPE / 2, p.sill - JAMBA / 2 + SOLAPE / 2].forEach(function (y) {
        var h = new THREE.Mesh(
          new THREE.BoxGeometry(p.width + JAMBA * 2, JAMBA + SOLAPE, fondo), M.moldura
        );
        h.position.set(0, y, 0);
        h.castShadow = true;
        g.add(h);
      });
      // Embutido: los bordes del vidrio no deben apoyar en la cara del corte.
      var v = new THREE.Mesh(new THREE.BoxGeometry(p.width - 0.03, p.height - 0.03, 0.02), M.vidrio);
      v.position.set(0, p.sill + p.height / 2, 0);
      g.add(v);
      return g;
    }

    function hojaPuerta(p, M, ABRE) {
      /* `swing` dice hacia QUE LADO del muro barre la hoja, y la bisagra se queda
         siempre en el mismo canto. Mover las dos cosas con el mismo signo deja
         la hoja del mismo lado, solo espejada: no hay forma de elegir el lado. */
      var lado = p.opening.swing || 1;
      var off = -p.width / 2;
      var g = new THREE.Group();
      g.position.set(
        p.center[0] + Math.cos(p.wallAngle) * off, 0,
        p.center[2] - Math.sin(p.wallAngle) * off
      );
      g.rotation.y = p.wallAngle + lado * ABRE;
      var hoja = new THREE.Mesh(new THREE.BoxGeometry(p.width, p.height, 0.04), M.puerta);
      // Desplazada media hoja: la bisagra es el canto, no el centro.
      hoja.position.set(p.width / 2, p.height / 2, 0);
      hoja.castShadow = true;
      g.add(hoja);
      return g;
    }

    /* ---------- aplicar un plano ---------- */

    function aplicarPlan(plan, opts) {
      var conAnim = animar && !(opts && opts.animar === false);
      planActual = plan;
      var M = G.materiales();

      caja = G.cajaDelPlano(plan);
      esquinasCaja = G.esquinas(caja);

      // La losa no se anima: es el lote, existe antes que la vivienda.
      if (baseNodo) { soltar(baseNodo); baseNodo = null; }

      /* Un plano VACIO no lleva losa. Pasa en el paso de ubicacion, que no
         construye nada, y al volver atras hasta el: sin este corte la losa se
         dimensionaria contra una caja de tamano cero y quedaria un cuadrado
         gris de 1 m flotando solo, que se lee peor que no mostrar nada. El
         resto de la funcion ya deja la escena vacia por si misma, porque el
         diff no encuentra ninguna pieza y retira las que hubiera. */
      if (plan.walls.length) {
        baseNodo = new THREE.Mesh(
          new THREE.BoxGeometry(
            (caja.halfExtents[0] + 0.5) * 2, GROSOR_BASE, (caja.halfExtents[2] + 0.5) * 2
          ), M.base
        );
        baseNodo.position.set(caja.center[0], -GROSOR_BASE / 2 - HUNDIR_BASE, caja.center[2]);
        baseNodo.receiveShadow = true;
        raiz.add(baseNodo);

        /* Losa de obra sobre TODA la huella. El cascaron se dimensiona para el
           programa completo desde la primera respuesta, pero los ambientes
           aparecen de a poco: sin esto queda un vacio gris enorme dentro de los
           muros y se lee como que el piso no cargo. Va apenas debajo del nivel
           de los pisos de ambiente, que se van montando encima. */
        var obra = new THREE.Mesh(
          new THREE.BoxGeometry(caja.halfExtents[0] * 2, 0.02, caja.halfExtents[2] * 2), M.obra
        );
        // Hija de la losa del lote, asi que se va con ella al cambiar de plano.
        // Su Y es relativa: queda justo debajo del nivel de los pisos de
        // ambiente.
        obra.position.set(0, GROSOR_BASE / 2 + HUNDIR_BASE - 0.015, 0);
        obra.receiveShadow = true;
        baseNodo.add(obra);
      }

      var nuevas = piezasDe(plan);
      var vistas = {};
      var entrantes = [];

      nuevas.forEach(function (pieza) {
        vistas[pieza.clave] = true;
        var previo = nodos[pieza.clave];
        if (previo) {
          /* Ya estaba: se deja quieta y se descarta la copia nueva. Pero si
             estaba SALIENDO hay que cancelar esa salida — al terminar se
             eliminaria a si misma, y la pieza acabaria de volver. Pasa al ir y
             venir rapido por el formulario: sin esto la escena se vacia. */
          if (previo.anim && previo.anim.saliendo) {
            if (conAnim) {
              var dv = direccion(previo.centro);
              previo.anim = {
                t: 0, retraso: 0, dur: ENTRADA, saliendo: false, dx: dv[0], dz: dv[1]
              };
            } else {
              previo.anim = null;
              previo.grupo.position.set(0, 0, 0);
            }
          }
          soltar(pieza.grupo);
          return;
        }
        raiz.add(pieza.grupo);
        nodos[pieza.clave] = { grupo: pieza.grupo, anim: null, centro: pieza.centro };
        entrantes.push(pieza);
      });

      // Lo que ya no esta en el plano se retira. Salir es la mitad que faltaba:
      // sin esto, volver atras en el formulario dejaba el apartamento intacto.
      Object.keys(nodos).forEach(function (clave) {
        if (vistas[clave] || (nodos[clave].anim && nodos[clave].anim.saliendo)) return;
        var n = nodos[clave];
        if (!conAnim) { soltar(n.grupo); delete nodos[clave]; return; }
        n.anim = {
          t: 0, retraso: 0, dur: SALIDA, saliendo: true,
          dx: direccion(n.centro)[0], dz: direccion(n.centro)[1]
        };
      });

      if (conAnim && entrantes.length) {
        // Escalonado repartido, no fijo por pieza: un plano grande se comeria el
        // reloj y las ultimas piezas se quedarian a medio camino para siempre.
        var paso = DESFASE / entrantes.length;
        var porAmbiente = {}, orden = 0;
        entrantes.forEach(function (pieza) {
          var k = pieza.ambiente || '_';
          if (porAmbiente[k] === undefined) porAmbiente[k] = orden++;
        });
        entrantes.forEach(function (pieza) {
          var d = direccion(pieza.centro);
          var n = nodos[pieza.clave];
          n.anim = {
            t: 0, retraso: porAmbiente[pieza.ambiente || '_'] * paso, dur: ENTRADA,
            saliendo: false, dx: d[0], dz: d[1]
          };
          pieza.grupo.position.set(d[0] * SEPARACION, ELEVA, d[1] * SEPARACION);
        });
      }

      edad = 0;
      encuadrar();
      pedirCuadro();
    }

    // Direccion desde el centro del plano hacia la pieza: es por donde entra y
    // por donde se va.
    function direccion(centro) {
      if (!centro || !caja) return [0, 0];
      var dx = centro[0] - caja.center[0], dz = centro[1] - caja.center[2];
      var l = Math.hypot(dx, dz) || 1;
      return [dx / l, dz / l];
    }

    /* ---------- montaje ---------- */

    function montar(el) {
      if (!el) return false;
      if (lienzo.parentNode !== el) {
        el.appendChild(lienzo);
        contenedor = el;
        if (ro) ro.disconnect();
        ro = new ResizeObserver(medir);
        ro.observe(el);
        medir();
      }
      pedirCuadro();
      return true;
    }

    function dispose() {
      vivo = false;
      if (ro) ro.disconnect();
      Object.keys(nodos).forEach(function (c) { soltar(nodos[c].grupo); delete nodos[c]; });
      if (baseNodo) soltar(baseNodo);
      renderer.dispose();
      if (lienzo.parentNode) lienzo.parentNode.removeChild(lienzo);
    }

    return {
      montar: montar, aplicarPlan: aplicarPlan, encuadrar: encuadrar,
      pedirCuadro: pedirCuadro, dispose: dispose,
      canvas: lienzo, renderer: renderer, scene: scene, camera: camera,
      plan: function () { return planActual; },
      piezas: function () { return Object.keys(nodos).length; }
    };
  }

  window.GDF3D = window.GDF3D || {};
  window.GDF3D.crearEscena = crearEscena;
})();
