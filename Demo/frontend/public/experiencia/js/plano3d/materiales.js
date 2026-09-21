/* Materiales y texturas procedurales. Puerto de `src/scene/{materials,textures}.ts`.

   Los materiales son singletons de modulo: compartir uno entre todas las mallas
   que lo usan evita que el renderer re-suba uniformes por objeto y evita
   asignar memoria dentro del bucle de dibujo. */
(function () {
  'use strict';

  var THREE = window.GDF3DLibs.THREE;

  /* Tamano fisico que cubre el lienzo, en metros. Las UV de los pisos vienen en
     metros (son ShapeGeometry, cuyas UV por defecto son la X/Y del vertice), asi
     que esto es lo que mantiene tablas y baldosas del mismo tamano real en
     habitaciones de cualquier forma. */
  var PARCHE = 2;
  var PX = 512;

  /* Variacion determinista por celda. Un PRNG de verdad romperia la continuidad
     del mosaico entre repeticiones: la funcion tiene que ser periodica. */
  function ruido(a, b) {
    var n = Math.sin(a * 127.1 + b * 311.7) * 43758.5453;
    return n - Math.floor(n);
  }

  function lienzo() {
    var el = document.createElement('canvas');
    el.width = PX; el.height = PX;
    return { el: el, ctx: el.getContext('2d') };
  }

  function terminar(el) {
    var t = new THREE.CanvasTexture(el);
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.colorSpace = THREE.SRGBColorSpace;
    /* Las juntas son lineas finas de alto contraste: vistas en escorzo alias an
       en moire que se arrastra, salvo que el muestreo tome varias muestras a lo
       largo del eje comprimido. */
    t.anisotropy = 16;
    t.generateMipmaps = true;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.repeat.set(1 / PARCHE, 1 / PARCHE);
    return t;
  }

  function texturaMadera() {
    var l = lienzo(), ctx = l.ctx;
    var filas = 10, altoFila = PX / filas, tabla = PX / 2;

    ctx.fillStyle = '#8a6740';
    ctx.fillRect(0, 0, PX, PX);

    for (var f = 0; f < filas; f++) {
      var off = ruido(f, 3) * tabla;
      for (var x = off - tabla; x < PX; x += tabla) {
        var s = ruido(f, Math.round(x)) * 26 - 13;
        ctx.fillStyle = 'rgb(' + (138 + s) + ',' + (103 + s * 0.8) + ',' + (64 + s * 0.6) + ')';
        ctx.fillRect(x, f * altoFila, tabla - 1.5, altoFila - 1.5);

        ctx.strokeStyle = 'rgba(90, 62, 36, 0.18)';
        ctx.lineWidth = 1;
        for (var g = 0; g < 3; g++) {
          var gy = f * altoFila + ruido(f + g, x) * altoFila;
          ctx.beginPath();
          ctx.moveTo(x, gy);
          ctx.lineTo(x + tabla, gy);
          ctx.stroke();
        }
      }
    }
    return terminar(l.el);
  }

  function texturaCeramica() {
    var l = lienzo(), ctx = l.ctx;
    var n = 5, lado = PX / n;

    ctx.fillStyle = '#a9a49b';
    ctx.fillRect(0, 0, PX, PX);

    for (var ty = 0; ty < n; ty++) {
      for (var tx = 0; tx < n; tx++) {
        var s = ruido(tx, ty) * 14 - 7;
        ctx.fillStyle = 'rgb(' + (216 + s) + ',' + (212 + s) + ',' + (204 + s) + ')';
        ctx.fillRect(tx * lado + 2, ty * lado + 2, lado - 4, lado - 4);
      }
    }
    return terminar(l.el);
  }

  function mat(color, rug, metal) {
    return new THREE.MeshStandardMaterial({ color: color, roughness: rug, metalness: metal || 0 });
  }

  var materiales = null;
  var pisos = null;

  /* Perezoso: las texturas necesitan `document.createElement`, y estos modulos
     se cargan antes de que exista la escena. */
  function init() {
    if (materiales) return;
    materiales = {
      /* Gris frio a proposito, pero CLARO. Los muros blancos se lavaban contra
         los pisos vistos desde arriba y las divisiones dejaban de leerse; un
         gris calido quedaba demasiado cerca en luminosidad de la madera. El
         frio separa por tono y por valor a la vez.
         Mas claro que en el prototipo de React porque aqui no hay HDRI: con
         solo luces directas el mismo hex renderiza bastante mas oscuro, y sobre
         el crema de la experiencia se leia pesado. */
      muro: mat('#bcc1c4', 0.9),
      // El lote, no asfalto: sobre fondo crema un gris oscuro pesa demasiado.
      base: mat('#b3b0a9', 0.95),
      // Losa de obra: el piso que existe antes de que el ambiente tenga acabado.
      obra: mat('#cdc8c0', 0.9),
      marco: mat('#8a6a4a', 0.6),
      tela: mat('#d8d3c8', 0.95),
      telaAcento: mat('#b9c6cc', 0.95),
      linoAzul: mat('#c3d3de', 0.95),
      linoBlanco: mat('#eceae4', 0.95),
      meson: mat('#e8e6e0', 0.4),
      electro: mat('#5c5f63', 0.35, 0.6),
      porcelana: mat('#f6f6f4', 0.25),
      vidrio: new THREE.MeshStandardMaterial({
        color: '#cfe0e6', roughness: 0.05, metalness: 0,
        transparent: true, opacity: 0.28
      }),
      tapete: mat('#c9c2b6', 1),
      follaje: mat('#5f7a54', 0.9),
      // Madera clara: una hoja casi blanca no se distingue del muro donde va.
      puerta: mat('#d9bd97', 0.65),
      // Mas claro que los muros, para que el marco se lea como pieza aparte.
      moldura: mat('#e9e6e0', 0.7)
    };
    pisos = {
      // Color base blanco: el mapa lleva el color, no lo tine el material.
      wood: new THREE.MeshStandardMaterial({ map: texturaMadera(), roughness: 0.75 }),
      tile: new THREE.MeshStandardMaterial({ map: texturaCeramica(), roughness: 0.4 }),
      stone: mat('#c8c4bc', 0.6)
    };
  }

  window.GDF3D = window.GDF3D || {};
  window.GDF3D.materiales = function () { init(); return materiales; };
  window.GDF3D.materialPiso = function (acabado) { init(); return pisos[acabado || 'wood']; };
})();
