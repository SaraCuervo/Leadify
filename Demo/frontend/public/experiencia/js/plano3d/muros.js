/* Deriva muros y aberturas de los rectangulos que devuelve la zonificacion.
   Es el trabajo real del puerto: en la maqueta de agosto esta logica no existia
   como datos, estaba entretejida con la creacion de meshes (2268-2347).

   Coordenadas en metros, en el mismo sistema que la zonificacion: X a lo ancho
   de la planta, Z en profundidad. Coinciden con el par [x, y] del FloorPlan,
   cuya segunda componente el render mapea a Z.

   Tabiques y cascara pasan por la MISMA tuberia: cada ambiente propone tramos,
   se fusionan por linea y al final se cuelgan las aberturas del tramo que las
   contiene. Eso hace que la cascara CREZCA con los ambientes en vez de existir
   entera desde la primera respuesta — sus posiciones ya estan fijadas por el
   programa completo, asi que crece sin que nada se mueva de sitio. */
(function () {
  'use strict';

  var POR_DEFECTO = {
    /* Muros de casa de munecas, no de obra. A 2.2 m —la altura real— desde
       cualquier angulo util los muros tapan el interior y no se lee la planta,
       que es justo para lo que sirve este panel. Se sacrifica realismo
       arquitectonico a proposito; es la misma decision que tomo la maqueta de
       agosto, que usaba 1.1 m. Subirlo vuelve a cerrar la vista. */
    alturaMuro: 1.3,
    alturaCascara: 1.45,
    grosorCascara: 0.25,
    grosorTabique: 0.12,
    anchoPuerta: 0.9,
    // El vano nunca deja menos de esto de muro a cada lado.
    holguraPuerta: 0.85,
    anchoVentana: 1.4,
    // Proporcionados al muro bajo: con alfeizar de 0.85 no quedaria ventana.
    alfeizar: 0.45,
    altoVentana: 0.65
  };

  var EPS = 0.04;   // tolerancia de contacto entre bordes, en metros

  function cerca(a, b, tol) { return Math.abs(a - b) < (tol || EPS); }
  function n2(v) { return (Math.round(v * 100) / 100).toFixed(2); }

  // Los cuatro lados de un rectangulo, como segmentos.
  function lados(rect) {
    var x = rect.x, z = rect.z, w = rect.w, d = rect.d;
    return {
      n: { a: [x, z], b: [x + w, z], horiz: true },
      s: { a: [x, z + d], b: [x + w, z + d], horiz: true },
      o: { a: [x, z], b: [x, z + d], horiz: false },
      e: { a: [x + w, z], b: [x + w, z + d], horiz: false }
    };
  }

  function largo(seg) { return Math.hypot(seg.b[0] - seg.a[0], seg.b[1] - seg.a[1]); }

  function enPerimetro(seg, pl) {
    var hw = pl.w / 2, hd = pl.d / 2;
    if (seg.horiz) return cerca(seg.a[1], -hd, 0.01) || cerca(seg.a[1], hd, 0.01);
    return cerca(seg.a[0], -hw, 0.01) || cerca(seg.a[0], hw, 0.01);
  }

  /* Lado del ambiente que da a una zona de circulacion, para que la puerta abra
     ahi y no contra otra habitacion. Puerto de `ladoHaciaCirculacion` (2137). */
  function ladoHaciaCirculacion(rect, zonas, permitidos) {
    for (var i = 0; i < (zonas || []).length; i++) {
      var q = zonas[i].rect;
      var solX = Math.min(rect.x + rect.w, q.x + q.w) - Math.max(rect.x, q.x) > 0.5;
      var solZ = Math.min(rect.z + rect.d, q.z + q.d) - Math.max(rect.z, q.z) > 0.5;
      if (permitidos.indexOf('o') >= 0 && cerca(rect.x, q.x + q.w) && solZ) return 'o';
      if (permitidos.indexOf('e') >= 0 && cerca(rect.x + rect.w, q.x) && solZ) return 'e';
      if (permitidos.indexOf('n') >= 0 && cerca(rect.z, q.z + q.d) && solX) return 'n';
      if (permitidos.indexOf('s') >= 0 && cerca(rect.z + rect.d, q.z) && solX) return 's';
    }
    return null;
  }

  /* Hacia que lado del muro barre la hoja, para que no de contra el pasillo ni,
     peor, hacia fuera del edificio.

     El signo esta invertido respecto del producto cruz a proposito: el render
     gira la hoja con `rotation.y = anguloMuro + lado * APERTURA` sobre una
     bisagra fija, y con esa combinacion el sentido positivo barre hacia el lado
     NEGATIVO del cruz. Verificado en vista cenital, donde la posicion es
     inequivoca; en 3/4 la profundidad enganya. */
  function sentidoGiro(seg, centroAmbiente) {
    var dx = seg.b[0] - seg.a[0], dz = seg.b[1] - seg.a[1];
    var mx = (seg.a[0] + seg.b[0]) / 2, mz = (seg.a[1] + seg.b[1]) / 2;
    var cruz = dx * (centroAmbiente[1] - mz) - dz * (centroAmbiente[0] - mx);
    return cruz >= 0 ? -1 : 1;
  }

  function derivarMuros(zon, opts) {
    var o = Object.assign({}, POR_DEFECTO, opts || {});
    var pl = zon.pl, hw = pl.w / 2, hd = pl.d / 2;

    var candidatos = [], puertas = [], ventanas = [];
    var bloqueados = {};
    function bloquear(id, lado) { (bloqueados[id] = bloqueados[id] || []).push(lado); }

    function proponer(seg, grosor, altura) {
      var p0 = seg.horiz ? seg.a[0] : seg.a[1];
      var p1 = seg.horiz ? seg.b[0] : seg.b[1];
      candidatos.push({
        horiz: seg.horiz, fija: seg.horiz ? seg.a[1] : seg.a[0],
        a: Math.min(p0, p1), b: Math.max(p0, p1),
        grosor: grosor, altura: altura
      });
    }

    /* --- Cascara: solo los tramos que bordean ambientes ya construidos ---
       Emitirla entera desde la primera respuesta dejaba un rectangulo enorme de
       losa vacia durante media encuesta. */
    zon.rects.forEach(function (r) {
      var L = lados(r.rect);
      ['n', 's', 'o', 'e'].forEach(function (k) {
        var seg = L[k];
        if (!enPerimetro(seg, pl)) return;
        proponer(seg, o.grosorCascara, o.alturaCascara);

        /* Ventana por AMBIENTE, centrada en su tramo y no en el muro entero: un
           muro perimetral suele bordear varios, y una sola al medio dejaria
           habitaciones a oscuras. */
        if (r.zona === 'circulacion') return;
        var ancho = Math.min(o.anchoVentana, largo(seg) - 0.9);
        if (ancho < 0.7) return;
        ventanas.push({
          horiz: seg.horiz, fija: seg.horiz ? seg.a[1] : seg.a[0],
          centro: seg.horiz ? (seg.a[0] + seg.b[0]) / 2 : (seg.a[1] + seg.b[1]) / 2,
          ancho: ancho
        });
      });
    });

    /* --- Tabiques interiores ---
       Solo los proponen los ambientes cerrados. La zona social y la circulacion
       quedan delimitadas por los tabiques de sus vecinos y por la cascara; si
       tambien los propusieran, cada medianera se construiria dos veces. */
    zon.rects.forEach(function (r) {
      if (r.zona === 'social' || r.zona === 'circulacion') return;
      var rect = r.rect, L = lados(rect);
      var centro = [rect.x + rect.w / 2, rect.z + rect.d / 2];
      var libres = ['n', 's', 'o', 'e'].filter(function (k) { return !enPerimetro(L[k], pl); });
      if (!libres.length) return;

      // Un lado solo sirve de puerta si le queda muro a ambos costados del vano.
      var utiles = libres.filter(function (k) {
        return largo(L[k]) - o.holguraPuerta >= 0.7;
      });

      /* Preferencias de por donde se entra, filtradas por las que admiten vano:
         elegir el lado "correcto" y descubrir despues que mide 1.2 m deja el
         ambiente sin puerta, que es peor que entrar por un lado menos natural. */
      var ladoPuerta = null;
      if (r.id === 'banoPriv') {
        // El bano principal abre desde la alcoba principal, este donde este.
        var a1 = zon.completo.filter(function (q) { return q.id === 'alcoba1'; })[0];
        if (a1) ladoPuerta = ladoHaciaCirculacion(rect, [a1], utiles);
      }
      if (!ladoPuerta) ladoPuerta = ladoHaciaCirculacion(rect, zon.corredores, utiles);
      if (!ladoPuerta) ladoPuerta = ladoHaciaCirculacion(rect, zon.zonasAcceso, utiles);
      if (!ladoPuerta) {
        ladoPuerta = utiles.slice().sort(function (x, y) {
          return largo(L[y]) - largo(L[x]);
        })[0] || null;
      }

      libres.forEach(function (k) {
        var seg = L[k];
        proponer(seg, o.grosorTabique, o.alturaMuro);
        if (k !== ladoPuerta) return;
        bloquear(r.id, k);
        puertas.push({
          horiz: seg.horiz, fija: seg.horiz ? seg.a[1] : seg.a[0],
          centro: seg.horiz ? (seg.a[0] + seg.b[0]) / 2 : (seg.a[1] + seg.b[1]) / 2,
          ancho: Math.min(o.anchoPuerta, largo(seg) - o.holguraPuerta),
          /* Vano de altura completa: en un muro de 1.3 m no cabe dintel sobre
             una hoja de 2.05, y el paso se lee mejor abierto de arriba abajo. */
          alto: o.alturaMuro,
          swing: sentidoGiro(seg, centro), ambiente: r.id, hoja: false
        });
      });
    });

    /* --- Puerta de entrada ---
       Sobre el muro perimetral que toca la circulacion, para entrar al vestibulo
       y no directamente a una alcoba. */
    var acceso = zon.corredores.filter(function (c) { return c.id === 'vestibulo'; })[0] ||
      zon.corredores[0] ||
      zon.rects.filter(function (r) { return r.zona === 'social'; })[0];
    if (acceso && acceso.rect) {
      var ladoE = ladoHaciaCirculacion(
        { x: -hw, z: -hd, w: pl.w, d: pl.d }, [acceso], ['n', 's', 'o', 'e']
      ) || 's';
      var horizE = ladoE === 'n' || ladoE === 's';
      var fijaE = ladoE === 'n' ? -hd : ladoE === 's' ? hd : ladoE === 'o' ? -hw : hw;
      // El acceso marca ese lado para todo ambiente que de contra el.
      zon.rects.forEach(function (r) {
        if (enPerimetro(lados(r.rect)[ladoE], pl)) bloquear(r.id, ladoE);
      });
      puertas.push({
        horiz: horizE, fija: fijaE,
        centro: horizE
          ? acceso.rect.x + acceso.rect.w / 2
          : acceso.rect.z + acceso.rect.d / 2,
        ancho: o.anchoPuerta, alto: o.alturaCascara * 0.85,
        swing: sentidoGiro(
          horizE ? { a: [-hw, fijaE], b: [hw, fijaE] } : { a: [fijaE, -hd], b: [fijaE, hd] },
          [0, 0]
        ),
        ambiente: null, hoja: true
      });
    }

    /* --- Fusion por linea ---
       Se unen los tramos que se tocan o se solapan. Sin esto quedaban tabiques
       pisandose a medias: la banda humeda y la columna privada comparten plano
       pero sus ambientes no arrancan a la misma altura, asi que cada uno
       describia un tramo distinto de la misma medianera. Una clave canonica de
       arista solo caza el duplicado exacto. */
    var lineas = {};
    candidatos.forEach(function (c) {
      var clave = (c.horiz ? 'h' : 'v') + '@' + n2(c.fija) + '#' + n2(c.grosor);
      if (!lineas[clave]) {
        lineas[clave] = {
          horiz: c.horiz, fija: c.fija, grosor: c.grosor, altura: c.altura, tramos: []
        };
      }
      lineas[clave].tramos.push(c);
    });

    var walls = [], openings = [], nMuro = 0, nOp = 0;
    Object.keys(lineas).forEach(function (clave) {
      var linea = lineas[clave];
      var tramos = linea.tramos.slice().sort(function (p, q) { return p.a - q.a; });
      var fusion = [];
      tramos.forEach(function (t) {
        var ultimo = fusion[fusion.length - 1];
        if (ultimo && t.a <= ultimo.b + 0.01) ultimo.b = Math.max(ultimo.b, t.b);
        else fusion.push({ a: t.a, b: t.b });
      });
      fusion.forEach(function (f) {
        f.id = 'm' + (++nMuro);
        var a = linea.horiz ? [f.a, linea.fija] : [linea.fija, f.a];
        var b = linea.horiz ? [f.b, linea.fija] : [linea.fija, f.b];
        walls.push({
          id: f.id, start: a, end: b, thickness: linea.grosor, height: linea.altura
        });
      });
      linea.fusion = fusion;
    });

    /* --- Aberturas ---
       Cada una se cuelga del tramo fusionado que la contiene, recalculando su
       posicion relativa: el muro final es mas largo que el que la pidio. Si ese
       tramo todavia no existe —la cascara crece—, la abertura no se emite. */
    function colgar(item, tipo, grosor) {
      var linea = lineas[(item.horiz ? 'h' : 'v') + '@' + n2(item.fija) + '#' + n2(grosor)];
      if (!linea) return;
      var f = linea.fusion.filter(function (q) {
        return item.centro >= q.a - 0.01 && item.centro <= q.b + 0.01;
      })[0];
      if (!f) return;
      var L = f.b - f.a;
      if (L <= 0) return;

      var pos = item.centro - f.a;
      // Un vano mas ancho que su muro se sale por los extremos.
      if (pos - item.ancho / 2 < 0.12 || pos + item.ancho / 2 > L - 0.12) return;

      var op = {
        id: (tipo === 'door' ? 'd' : 'v') + (++nOp), wallId: f.id, type: tipo,
        offset: pos / L, width: item.ancho
      };
      if (tipo === 'door') {
        op.ambiente = item.ambiente;
        op.swing = item.swing;
        op.hoja = !!item.hoja;
        op.height = Math.min(item.alto, linea.altura);
      } else {
        op.sill = o.alfeizar;
        op.height = o.altoVentana;
      }
      openings.push(op);
    }

    puertas.forEach(function (p) {
      colgar(p, 'door', p.hoja ? o.grosorCascara : o.grosorTabique);
    });
    ventanas.forEach(function (v) { colgar(v, 'window', o.grosorCascara); });

    /* `ladosBloqueados` lo necesita el amoblado: un mueble pegado a un muro con
       vano queda plantado en el paso. Incluye la entrada, que va en el perimetro
       y afecta a cualquier ambiente que de contra ese muro. */
    return { walls: walls, openings: openings, ladosBloqueados: bloqueados };
  }

  window.GDF3D = window.GDF3D || {};
  window.GDF3D.derivarMuros = derivarMuros;
  window.GDF3D.MUROS_POR_DEFECTO = POR_DEFECTO;
})();
