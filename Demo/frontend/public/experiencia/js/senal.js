// EL FONDO "AI SIGNAL" del Leadify Motion System (§6). Tres capas:
//
//   1. Atmosphere — dos gradientes radiales muy suaves. Van en CSS
//      (.gdf-senal-atmosfera), no aquí: son estáticos y pintarlos en canvas
//      sería gastar un frame en algo que no se mueve.
//   2. Network     — esta capa. Una red pequeña de nodos que derivan lento.
//   3. Signal      — un pulso coral que recorre UNA conexión de vez en cuando.
//
// POR QUE VIVE FUERA DE #root, y esto es lo que lo hace funcionar. `render()`
// en main.js reconstruye `root.innerHTML` ENTERO en cada cambio de pantalla.
// Un canvas ahí dentro se destruiría y volvería a nacer al pasar de la
// escarapela al quiz: la red daría un salto y el efecto se leería como dos
// pantallas distintas pegadas. Colgado del <body> sobrevive a los re-renders,
// y esa continuidad es precisamente lo que dice §3 — el formulario es el
// primer nodo de UN sistema, no una pantalla suelta.
//
// SOLO PARA Leadify. Las cuatro constructoras revendidas tienen su identidad
// en negro y naranja y no se les impone la del stand; misma línea que sigue
// `SUPERFICIE_Leadify` en tema.js.
(function () {
  'use strict';

  // Densidad BAJA a propósito (§6): "evita partículas numerosas, estrellas,
  // ruido excesivo". Con 18 nodos la red se lee como una estructura; con 60
  // se lee como un protector de pantalla.
  var NODOS = 18;
  var DIST_CONEXION = 190; // px a los que dos nodos se consideran vecinos
  var DERIVA = 0.055; // px por frame: lento, casi imperceptible

  // Cada cuánto sale un pulso, y cuánto tarda en recorrer su conexión.
  var PAUSA_MIN = 2600;
  var PAUSA_MAX = 6200;
  var VIAJE_MS = 1500;

  var lienzo = null;
  var ctx = null;
  var nodos = [];
  var pulso = null; // { a, b, t0 } mientras viaja
  var proximoPulso = 0;
  var lazo = 0;
  var quieto = false; // prefers-reduced-motion

  function color(nombre, respaldo) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(nombre);
    return (v && v.trim()) || respaldo;
  }

  function aleatorio(a, b) {
    return a + Math.random() * (b - a);
  }

  function medir() {
    if (!lienzo) return;
    // El devicePixelRatio se topa en 2: por encima se pintan cuatro veces más
    // píxeles sin que se note, y esto es un fondo, no el contenido.
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var an = lienzo.clientWidth;
    var al = lienzo.clientHeight;
    lienzo.width = Math.round(an * dpr);
    lienzo.height = Math.round(al * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function sembrar() {
    var an = lienzo.clientWidth || 1;
    var al = lienzo.clientHeight || 1;
    nodos = [];
    for (var i = 0; i < NODOS; i++) {
      nodos.push({
        x: aleatorio(0, an),
        y: aleatorio(0, al),
        // Direcciones desiguales a propósito: §6 pide que las conexiones NO
        // salgan perfectamente uniformes.
        vx: aleatorio(-DERIVA, DERIVA),
        vy: aleatorio(-DERIVA, DERIVA),
        r: aleatorio(1.1, 2.2),
      });
    }
  }

  // Las parejas de nodos que hoy están lo bastante cerca para tener línea.
  function vecinos() {
    var pares = [];
    for (var i = 0; i < nodos.length; i++) {
      for (var j = i + 1; j < nodos.length; j++) {
        var dx = nodos[i].x - nodos[j].x;
        var dy = nodos[i].y - nodos[j].y;
        var d = Math.sqrt(dx * dx + dy * dy);
        if (d < DIST_CONEXION) pares.push({ a: nodos[i], b: nodos[j], d: d });
      }
    }
    return pares;
  }

  function pintar(ahora) {
    var an = lienzo.clientWidth;
    var al = lienzo.clientHeight;
    ctx.clearRect(0, 0, an, al);

    var tintaRgb = '143, 154, 170'; // --leadify-muted, en rgb para el alpha
    var coral = color('--marca', '#FF6259');

    var pares = vecinos();

    // --- Capa 2: la red ---
    for (var p = 0; p < pares.length; p++) {
      var par = pares[p];
      // Cuanto más lejos, más tenue: da profundidad sin subir la opacidad
      // general, que es lo que convertiría esto en ruido.
      var alfa = (1 - par.d / DIST_CONEXION) * 0.26;
      ctx.strokeStyle = 'rgba(' + tintaRgb + ',' + alfa.toFixed(3) + ')';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(par.a.x, par.a.y);
      ctx.lineTo(par.b.x, par.b.y);
      ctx.stroke();
    }
    for (var n = 0; n < nodos.length; n++) {
      ctx.fillStyle = 'rgba(' + tintaRgb + ',0.52)';
      ctx.beginPath();
      ctx.arc(nodos[n].x, nodos[n].y, nodos[n].r, 0, Math.PI * 2);
      ctx.fill();
    }

    // --- Capa 3: la señal ---
    // El coral aparece SOLO aquí (§2: "es un color de señal, no debe llenar
    // toda la interfaz"). Un pulso cada vez, no una lluvia de puntos.
    if (!pulso && ahora > proximoPulso && pares.length) {
      pulso = { par: pares[(Math.random() * pares.length) | 0], t0: ahora };
    }
    if (pulso) {
      var t = (ahora - pulso.t0) / VIAJE_MS;
      if (t >= 1) {
        pulso = null;
        proximoPulso = ahora + aleatorio(PAUSA_MIN, PAUSA_MAX);
      } else {
        // easeInOutSine: sale y entra suave, sin arrancar de golpe. §21 pide
        // `sine.inOut` justo para los loops ambientales.
        var e = 0.5 - Math.cos(Math.PI * t) / 2;
        var x = pulso.par.a.x + (pulso.par.b.x - pulso.par.a.x) * e;
        var y = pulso.par.a.y + (pulso.par.b.y - pulso.par.a.y) * e;
        // Se desvanece por los dos extremos para que no aparezca ni muera de
        // golpe sobre el nodo.
        var vida = Math.sin(Math.PI * t);
        ctx.fillStyle = coral;
        ctx.globalAlpha = 0.9 * vida;
        ctx.beginPath();
        ctx.arc(x, y, 2.6, 0, Math.PI * 2);
        ctx.fill();
        // Un halo muy tenue, del mismo coral. Es lo único que "brilla".
        ctx.globalAlpha = 0.16 * vida;
        ctx.beginPath();
        ctx.arc(x, y, 9, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    }
  }

  function mover() {
    var an = lienzo.clientWidth;
    var al = lienzo.clientHeight;
    for (var i = 0; i < nodos.length; i++) {
      var n = nodos[i];
      n.x += n.vx;
      n.y += n.vy;
      // Rebote en los bordes: reaparecer por el lado contrario haría saltar
      // las líneas que ese nodo sostiene.
      if (n.x < 0 || n.x > an) n.vx *= -1;
      if (n.y < 0 || n.y > al) n.vy *= -1;
    }
  }

  function marco(ahora) {
    mover();
    pintar(ahora);
    lazo = requestAnimationFrame(marco);
  }

  function arrancar() {
    if (lazo || quieto) return;
    proximoPulso = performance.now() + 1200;
    lazo = requestAnimationFrame(marco);
  }

  function parar() {
    if (lazo) cancelAnimationFrame(lazo);
    lazo = 0;
  }

  // MOTIVOS PARA ESTAR PARADO, Y NO UN BOOLEANO. Hay dos que pueden coincidir
  // —la pestaña de fondo (§16) y un scroll en curso (ver
  // `engancharScrollResultados` en main.js)— y con una sola bandera el que
  // termina primero reanima la red aunque el otro siga pidiendo que esté
  // quieta: minimizar la ventana mientras se scrollea dejaba el canvas
  // corriendo de fondo. Se arranca solo cuando el conjunto está vacío.
  var frenos = {};

  function frenar(motivo, si) {
    if (si) frenos[motivo] = true;
    else delete frenos[motivo];
    if (Object.keys(frenos).length) parar();
    else arrancar();
  }

  function montar() {
    // Solo la marca del stand. Ver la nota de arriba.
    var marca = window.GDF_MARCA || {};
    if (marca.slug !== 'leadify') return;

    lienzo = document.createElement('canvas');
    lienzo.className = 'gdf-senal';
    lienzo.setAttribute('aria-hidden', 'true');
    var atmosfera = document.createElement('div');
    atmosfera.className = 'gdf-senal-atmosfera';
    atmosfera.setAttribute('aria-hidden', 'true');
    document.body.appendChild(atmosfera);
    document.body.appendChild(lienzo);
    // La marca en el <html> es lo que deja al CSS volver translúcidos el
    // panel y la escarapela SOLO donde hay señal detrás. Sin ella habría que
    // repetir el `slug === 'leadify'` en cada regla, y las otras cuatro marcas
    // —que no montan esto— se quedarían con paneles transparentes sobre nada.
    document.documentElement.classList.add('gdf-con-senal');

    ctx = lienzo.getContext('2d');
    medir();
    sembrar();

    // §15: quien pide menos movimiento se queda con la red QUIETA, no sin
    // red. Borrar el fondo entero cambiaría la composición; congelarlo
    // conserva la profundidad y quita el movimiento, que es lo que molesta.
    var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    quieto = mq.matches;
    if (quieto) pintar(performance.now());
    else arrancar();
    if (mq.addEventListener) {
      mq.addEventListener('change', function (e) {
        quieto = e.matches;
        if (quieto) { parar(); pintar(performance.now()); } else arrancar();
      });
    }

    var remedir;
    window.addEventListener('resize', function () {
      clearTimeout(remedir);
      remedir = setTimeout(function () {
        medir();
        sembrar();
        if (quieto) pintar(performance.now());
      }, 150);
    });

    // §16: nada de gastar frames con la pestaña de fondo.
    document.addEventListener('visibilitychange', function () {
      frenar('pestana', document.hidden);
    });
  }

  // Congela la red mientras dura un scroll. Es un no-op si esta marca no monta
  // la señal (las cuatro constructoras revendidas), así que main.js puede
  // llamarlo sin preguntar.
  function pausar() {
    if (lienzo) frenar('scroll', true);
  }

  function reanudar() {
    if (lienzo) frenar('scroll', false);
  }

  window.GDF = window.GDF || {};
  window.GDF.senal = { montar: montar, pausar: pausar, reanudar: reanudar };
})();
