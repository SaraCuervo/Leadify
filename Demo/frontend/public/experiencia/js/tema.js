// Aplica la identidad visual de la marca activa a las custom properties de CSS.
//
// POR QUE EXISTE
// --------------
// styles.css tenia 117 hex de marca escritos a mano. Para que la misma app
// pueda vestirse de cualquier constructora, esos valores viven ahora en el
// `:root` de styles.css como TOKENS POR ROL (--marca, --acento, --tinta y sus
// derivados), y este archivo los reescribe segun el `window.GDF_MARCA` del
// tenant que se haya cargado.
//
// EL DEFAULT ES COLSUBSIDIO, Y ESO NO ES CASUAL: el `:root` de styles.css trae
// los valores exactos de hoy. Si este archivo no corre, o si la marca no
// declara paleta, la app se ve EXACTAMENTE igual que antes del refactor. Es lo
// que permite verificar el cambio con capturas idénticas en vez de "parecidas".
//
// UNA MARCA APORTA TRES COLORES, NO VEINTE
// ----------------------------------------
// De `primario`, `acento` y `tinta` se derivan los demas mezclando con blanco o
// negro. Una constructora nueva entrega tres hex de su manual de marca y la app
// sale coherente. Si algun derivado no le sirve, puede fijarlo a mano en
// `paleta.tokens` y ese gana — que es justo lo que hace Colsubsidio, porque sus
// diez tonos estan curados y el refactor no puede mover un pixel.
//
// LA ESCENA SE QUEDA FUERA A PROPOSITO. Las piezas del plano van en
// `mix-blend-mode: multiply`, asi que el blanco del papel deja pasar el fondo:
// si `.gdf-scene` tomara un tinte de marca, el apartamento entero saldria
// tenido de ese color. Su gris es neutro y tiene que seguir siendolo.
(function () {
  'use strict';

  // Los tres colores de Colsubsidio, que son tambien el default del `:root`.
  var BASE = { primario: '#0067b1', acento: '#ffd000', tinta: '#33322f' };

  /**
   * LA PALETA ESTANDAR: negro y naranja, igual para las cuatro constructoras.
   *
   * La app se vestia del color de cada una — verde Bolivar, azul Colsubsidio,
   * rojo Amarilo, turquesa Cusezar — y eso se para aqui: el formulario tiene
   * ahora UNA identidad y la marca se reconoce por su logo, su nombre y su
   * cabecera, no por repintar la aplicacion entera.
   *
   * EL DATO DE MARCA NO SE BORRA. `paleta` sigue en tenants/<slug>/marca.js
   * con los colores reales de cada una (los de Bolivar costaron bajarse su
   * logo para descubrir que eran verde y amarillo, no azul y rojo). Lo unico
   * que hace este bloque es no usarlos. Para volver a la app multi-color basta
   * poner ESTANDAR en null.
   */
  var ESTANDAR = { primario: '#ff7a18', acento: '#ff9d3f', tinta: '#33322f' };

  /**
   * SUPERFICIE CLARA DE MACHEA, y solo de Machea.
   *
   * Todo lo demas en este archivo asume la consola en negro (`--fondo:
   * #0a0b0d` de styles.css) — es la identidad de las cuatro constructoras
   * revendidas y no se toca. Pero Machea no es una constructora revendida:
   * es la marca del propio stand, y el resto de su sitio (la landing en
   * React) es clara — blanco y beige, nunca negro. Un fondo casi negro aqui
   * dentro, en medio de esa landing, se ve como una app distinta pegada con
   * cinta, no como parte del mismo producto.
   *
   * SE PROBO EN NAVY OSCURO Y SE VOLVIO A CLARO, a peticion. Queda anotado
   * para no repetir el viaje: el ADN del Machea Motion System pide dark navy
   * con el coral como color de señal, y en pantalla la app se separaba de su
   * propia landing.
   *
   * `fondo`/`papel`/`papel2`/`borde` se fijan ANTES de derivar() para que
   * haciaFondo() (mezcla contra --fondo) mezcle contra ESTE fondo y no
   * contra el negro de styles.css — así los tintes y velos de marca salen
   * pasteles claros, no manchas oscuras. `tinta*` no se puede derivar de la
   * misma manera: viene fija en derivar() como gris claro para consola
   * negra, así que se reemplaza aparte, a mano, con la escala de texto
   * oscuro que ya usa el resto del sitio de Machea (--color-navy).
   */
  var SUPERFICIE_MACHEA = {
    fondo: '#fdf6f0',
    papel: '#ffffff',
    papel2: '#f5efe9',
    borde: '#dedad8',
    tinta: '#2d3b4e',
    tintaMedia: '#676f7b',
    tintaSuave: '#95999f',
    tintaTenue: '#b6b6b9',
    // El verde del badge de subsidio. El `:root` trae el aclarado para la
    // consola negra (#4fd6bf); sobre blanco ese mismo verde da 2,5 de
    // contraste, así que aquí va la versión oscura.
    exito: '#0f6f64',
  };

  function aRgb(hex) {
    var h = String(hex || '').trim().replace('#', '');
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    if (!/^[0-9a-fA-F]{6}$/.test(h)) return null;
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }

  function aHex(rgb) {
    return (
      '#' +
      rgb
        .map(function (v) {
          var n = Math.max(0, Math.min(255, Math.round(v)));
          return (n < 16 ? '0' : '') + n.toString(16);
        })
        .join('')
    );
  }

  /**
   * Mezcla `hex` con blanco (p > 0) o con negro (p < 0). `p` es cuanto del OTRO
   * color entra, de 0 a 1.
   *
   * Se mezcla en RGB y no en un espacio perceptual a proposito: es lo mismo que
   * hace `color-mix(in srgb)`, no necesita libreria, y para aclarar/oscurecer un
   * color de marca el resultado es indistinguible del que da OKLab a estas
   * distancias. Lo que si importa es que sea DETERMINISTA y revisable.
   */
  function mezclar(hex, p) {
    var rgb = aRgb(hex);
    if (!rgb) return hex;
    var hacia = p >= 0 ? 255 : 0;
    var k = Math.abs(p);
    return aHex(
      rgb.map(function (v) {
        return v + (hacia - v) * k;
      })
    );
  }

  /**
   * El FONDO de la app, para mezclar contra él.
   *
   * `mezclar(color, +p)` aclara hacia el blanco, y con eso se derivaban los
   * tintes y los velos: superficies casi blancas para chips y avisos. La app
   * va ahora en NEGRO, y ahí un tinte casi blanco no es un velo, es un foco.
   *
   * Así que esos tokens se mezclan contra el fondo real. Se lee del CSS en vez
   * de escribirlo aquí para que no haya dos verdades: si un día la app vuelve
   * a fondo claro, basta cambiar `--fondo` en styles.css y esto la sigue.
   */
  function fondo() {
    var v = getComputedStyle(document.documentElement)
      .getPropertyValue('--fondo').trim();
    return /^#[0-9a-f]{6}$/i.test(v) ? v : '#0a0b0d';
  }

  /** Como `mezclar` pero hacia el fondo de la app, no hacia el blanco. */
  function haciaFondo(hex, k) {
    var a = aRgb(hex);
    var b = aRgb(fondo());
    if (!a || !b) return hex;
    return aHex(a.map(function (v, i) { return v + (b[i] - v) * k; }));
  }

  /**
   * Los tokens derivados de los tres colores base.
   *
   * LOS PORCENTAJES ESTAN CALIBRADOS, no puestos a ojo: se buscó, para cada
   * tono curado de Colsubsidio, la mezcla que mejor lo reproduce. Doce de los
   * quince caen a una distancia RGB menor que 2 sobre 255, o sea que son el
   * mismo color. Así una marca nueva no obtiene tonos al azar: obtiene una
   * familia con las MISMAS relaciones internas que la que un diseñador armó a
   * mano para Colsubsidio.
   *
   * Los tres que NO se pueden derivar son sus azules claros (`--marca-viva`,
   * `--marca-suave`, `--marca-borde`): no son el primario aclarado sino un azul
   * más saturado, y ninguna mezcla con blanco llega ahí (el error se dispara a
   * 22-25). Para Colsubsidio se fijan explícitos en `paleta.tokens`; para una
   * marca nueva la versión mezclada es perfectamente coherente, que es lo que
   * importa cuando no hay un manual de marca que consultar.
   */
  function derivar(p) {
    return {
      '--marca': p.primario,
      '--marca-fuerte': mezclar(p.primario, -0.39),
      '--marca-viva': mezclar(p.primario, 0.05),
      '--marca-medio': mezclar(p.primario, 0.3),
      '--marca-suave': mezclar(p.primario, 0.53),
      // Estos tres son SUPERFICIE, no color de marca: van mezclados contra el
      // fondo oscuro. Con la mezcla hacia blanco cada chip salia como un foco.
      '--marca-borde': haciaFondo(p.primario, 0.68),
      '--marca-tinte': haciaFondo(p.primario, 0.86),
      '--marca-tinte-2': haciaFondo(p.primario, 0.90),

      // El texto de marca sobre fondo oscuro tiene que ACLARARSE, no apagarse.
      '--marca-texto': mezclar(p.primario, 0.42),

      '--acento': p.acento,
      '--acento-oscuro': mezclar(p.acento, -0.1),
      '--acento-tinte': haciaFondo(p.acento, 0.86),
      '--acento-tinte-2': haciaFondo(p.acento, 0.91),
      // El texto sobre amarillo no puede ser el amarillo oscurecido a secas: a
      // ese nivel de luminosidad pierde contraste. Oscurecerlo un 47% da
      // #876e00, que es el #8a6d00 que ya usaba Colsubsidio.
      '--sobre-acento': mezclar(p.acento, -0.47),

      // LA TINTA NO SALE DE LA MARCA. Su `tinta` es un gris oscuro pensado
      // para papel blanco; sobre negro seria invisible. Los textos van con la
      // escala de la consola, igual para las cuatro marcas — el color de marca
      // ya se ve en la cabecera, los botones y los acentos.
      '--tinta': '#e7ebf0',
      '--tinta-media': '#b3bcc7',
      '--tinta-suave': '#8d97a5',
      '--tinta-tenue': '#7c8695',

      // Los velos: los tintes casi blancos de chips, avisos y degradados.
      '--marca-velo-fuerte': haciaFondo(p.primario, 0.78),
      '--marca-velo': haciaFondo(p.primario, 0.86),
      '--marca-velo-claro': haciaFondo(p.primario, 0.90),
      '--marca-borde-suave': haciaFondo(p.primario, 0.72),
      '--acento-velo': haciaFondo(p.acento, 0.92),
    };
  }

  /**
   * Luminancia relativa (WCAG). Se usa para decidir si sobre el primario va
   * texto blanco o texto oscuro: una marca con un primario claro (un amarillo,
   * un verde lima) dejaria el texto blanco de la cabecera ilegible.
   */
  function luminancia(hex) {
    var rgb = aRgb(hex);
    if (!rgb) return 0;
    var c = rgb.map(function (v) {
      var s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }

  function contraste(a, b) {
    var la = luminancia(a);
    var lb = luminancia(b);
    var hi = Math.max(la, lb);
    var lo = Math.min(la, lb);
    return (hi + 0.05) / (lo + 0.05);
  }

  function aplicar() {
    var M = window.GDF_MARCA || {};
    var esMachea = M.slug === 'machea';
    // Machea es la propia marca del stand, no una constructora revendida:
    // aqui el estandar naranja no aplica y manda la paleta de tenants/machea.
    var usaEstandar = ESTANDAR && !esMachea;
    var paleta = usaEstandar ? {} : (M.paleta || {});
    var base = {
      primario: paleta.primario || (usaEstandar ? ESTANDAR.primario : BASE.primario),
      acento: paleta.acento || (usaEstandar ? ESTANDAR.acento : BASE.acento),
      tinta: paleta.tinta || (usaEstandar ? ESTANDAR.tinta : BASE.tinta),
    };

    var raiz = document.documentElement;

    // La superficie clara de Machea se fija AQUI, antes de derivar(): esa
    // función lee --fondo del DOM (vía haciaFondo/fondo()) para mezclar los
    // tintes y velos, así que tiene que ver el fondo nuevo, no el negro que
    // trae styles.css por defecto. Las cuatro constructoras no pasan por
    // aquí y se quedan con la consola negra de siempre.
    if (esMachea) {
      raiz.style.setProperty('--fondo', SUPERFICIE_MACHEA.fondo);
      raiz.style.setProperty('--papel', SUPERFICIE_MACHEA.papel);
      raiz.style.setProperty('--papel-2', SUPERFICIE_MACHEA.papel2);
      raiz.style.setProperty('--borde', SUPERFICIE_MACHEA.borde);
      raiz.style.colorScheme = 'light';
    } else {
      raiz.style.colorScheme = 'dark';
    }

    var tokens = derivar(base);

    // La tinta (texto) no se puede derivar del fondo con la misma cuenta que
    // los tintes de marca — en derivar() viene fija como gris claro para
    // consola negra. Para Machea se reemplaza por la escala de texto oscuro
    // de --color-navy, ANTES de que --texto-cta (más abajo) la use para
    // calcular contraste, o calcularía contra el gris claro equivocado.
    if (esMachea) {
      tokens['--tinta'] = SUPERFICIE_MACHEA.tinta;
      tokens['--tinta-media'] = SUPERFICIE_MACHEA.tintaMedia;
      tokens['--tinta-suave'] = SUPERFICIE_MACHEA.tintaSuave;
      tokens['--tinta-tenue'] = SUPERFICIE_MACHEA.tintaTenue;
      tokens['--exito'] = SUPERFICIE_MACHEA.exito;
    }

    // Los tokens FIJADOS a mano por la marca ganan sobre los derivados. Es lo
    // que hace que Colsubsidio quede identico: sus diez tonos curados se
    // declaran explicitos y la derivacion no los toca.
    var fijos = paleta.tokens || {};
    Object.keys(fijos).forEach(function (k) {
      tokens[k] = fijos[k];
    });

    // Texto sobre el primario: blanco salvo que no contraste.
    //
    // EL RESPALDO NO PUEDE SER `--tinta`. Lo era, y funcionaba mientras la
    // tinta era un gris oscuro para papel blanco; desde que la app va en negro
    // la tinta es CLARA, asi que sobre un primario vivo —el naranja estandar—
    // caia en claro sobre claro. Se fija un oscuro de verdad.
    tokens['--sobre-marca'] = contraste(base.primario, '#ffffff') >= 4.5 ? '#ffffff' : '#1b1c1f';

    // TEXTO DEL CTA PRINCIPAL, que va sobre el acento.
    //
    // Se decide POR CONTRASTE y no por gusto. Colsubsidio pone ahi un gris
    // neutro, que funciona porque su amarillo es clarisimo; con el verde de
    // otra marca ese mismo gris queda ilegible. Se prueba el gris de la marca
    // y, si no llega a 4.5:1, se cambia a blanco o negro — el que gane.
    //
    // Para Colsubsidio el gris da 5.0:1 y se elige, o sea que el CTA conserva
    // exactamente el color de hoy.
    var grisTexto = tokens['--tinta-media'];
    if (contraste(grisTexto, base.acento) >= 4.5) {
      tokens['--texto-cta'] = grisTexto;
    } else {
      tokens['--texto-cta'] =
        contraste('#ffffff', base.acento) >= contraste(tokens['--tinta'], base.acento)
          ? '#ffffff'
          : tokens['--tinta'];
    }

    Object.keys(tokens).forEach(function (k) {
      raiz.style.setProperty(k, tokens[k]);
    });

    if (M.identidad && M.identidad.nombre) {
      document.title = 'Grúa del Futuro | ' + M.identidad.nombre;
    }

    return tokens;
  }

  var aplicados = aplicar();

  window.GDF = window.GDF || {};
  window.GDF.tema = {
    aplicar: aplicar,
    derivar: derivar,
    mezclar: mezclar,
    contraste: contraste,
    tokens: aplicados,
  };
})();
