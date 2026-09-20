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
   * SUPERFICIE CLARA DE Leadify, y solo de Leadify.
   *
   * Todo lo demas en este archivo asume la consola en negro (`--fondo:
   * #0a0b0d` de styles.css) — es la identidad de las cuatro constructoras
   * revendidas y no se toca. Pero Leadify no es una constructora revendida:
   * es la marca del propio stand, y el resto de su sitio (la landing en
   * React) es clara — blanco y beige, nunca negro. Un fondo casi negro aqui
   * dentro, en medio de esa landing, se ve como una app distinta pegada con
   * cinta, no como parte del mismo producto.
   *
   * SE PROBO EN NAVY OSCURO Y SE VOLVIO A CLARO, a peticion. Queda anotado
   * para no repetir el viaje: el ADN del Leadify Motion System pide dark navy
   * con el coral como color de señal, y en pantalla la app se separaba de su
   * propia landing.
   *
   * `fondo`/`papel`/`papel2`/`borde` se fijan ANTES de derivar() para que
   * haciaFondo() (mezcla contra --fondo) mezcle contra ESTE fondo y no
   * contra el negro de styles.css — así los tintes y velos de marca salen
   * pasteles claros, no manchas oscuras. `tinta*` no se puede derivar de la
   * misma manera: viene fija en derivar() como gris claro para consola
   * negra, así que se reemplaza aparte, a mano, con la escala de texto
   * oscuro que ya usa el resto del sitio de Leadify (--color-navy).
   */
  var SUPERFICIE_Leadify = {
    fondo: '#fdf6f0',
    papel: '#ffffff',
    papel2: '#f5efe9',
    // El `border-navy/10` con el que la landing dibuja cada tarjeta. Era un
    // gris cálido (#dedad8) y sobre el beige tiraba a sepia; el navy
    // translúcido es el mismo tono del texto, más apagado, que es lo que
    // hace que el borde desaparezca de la lectura en vez de competir.
    borde: 'rgba(45, 59, 78, 0.12)',
    tinta: '#2d3b4e',
    tintaMedia: '#676f7b',
    tintaSuave: '#95999f',
    tintaTenue: '#b6b6b9',
    // El verde del badge de subsidio. El `:root` trae el aclarado para la
    // consola negra (#4fd6bf); sobre blanco ese mismo verde da 2,5 de
    // contraste, así que aquí va la versión oscura.
    exito: '#0f6f64',
  };

  /**
   * EL SISTEMA DE LA LANDING, y solo para Leadify.
   *
   * SUPERFICIE_Leadify aclaró el fondo; esto alinea lo que quedaba: la
   * tipografía de los titulares y la geometría. Son los mismos valores que
   * declara el `@theme` de frontend/src/index.css, escritos aquí a mano.
   *
   * SE DUPLICAN A PROPÓSITO, igual que la paleta de tenants/leadify/marca.js.
   * Este bundle no compila con el proyecto de Vite —es estático, vive en
   * public/ y se sirve tal cual— así que no hay forma de importar los tokens
   * de Tailwind. Lo que sí hay es un sitio donde desincronizarse se ve solo:
   * el quiz se abre DENTRO de la landing, en un iframe (ver LiveDemo.tsx), y
   * las dos superficies quedan una al lado de la otra en la misma pantalla.
   *
   * LO QUE CAMBIA, Y POR QUÉ:
   *   - SORA en los titulares. Era la única diferencia tipográfica que
   *     quedaba con la landing; Manrope ya era el cuerpo en las dos.
   *   - RADIOS MÁS GRANDES. La landing redondea a 24-32px lo que la consola
   *     redondea a 12-16. Es lo que más separa las dos superficies a primera
   *     vista, por encima del color.
   *   - EL CTA EN PASTILLA Y EN CORAL. En la landing el botón de acción es
   *     `rounded-full bg-coral`. El verde de aquí es el color de que algo
   *     encaja —compatibilidad, match, llamada— y gastarlo en 'Continuar' le
   *     quitaba ese significado justo donde hace falta, en los resultados.
   *   - SOMBRAS CON OFFSET NEGATIVO. Las de la consola son sombras duras
   *     pensadas para fondo negro; las de la landing (--shadow-soft,
   *     --shadow-coral) se abren hacia afuera y tiñen de navy, no de negro.
   */
  var SISTEMA_Leadify = {
    '--fuente-titulos': "'Sora', 'Poppins', sans-serif",
    '--radio-campo': '16px',
    '--radio-boton': '18px',
    '--radio-cta': '999px',
    '--radio-tarjeta': '24px',
    '--radio-panel': '28px',
    // El CTA toma el primario (coral), no el acento (verde).
    '--cta-fondo': 'var(--marca)',
    // --shadow-soft de index.css, literal.
    '--sombra-tarjeta': '0 10px 40px -10px rgba(45, 59, 78, 0.1)',
    // El desplegable FLOTA sobre el panel y tiene que despegarse más que una
    // tarjeta apoyada: la misma familia, con más profundidad.
    '--sombra-flotante': '0 18px 44px -14px rgba(45, 59, 78, 0.22)',
    // --shadow-coral de index.css, literal.
    '--sombra-cta': '0 14px 34px -12px rgba(255, 98, 89, 0.55)',
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
    var esLeadify = M.slug === 'leadify';
    // Leadify es la propia marca del stand, no una constructora revendida:
    // aqui el estandar naranja no aplica y manda la paleta de tenants/leadify.
    var usaEstandar = ESTANDAR && !esLeadify;
    var paleta = usaEstandar ? {} : (M.paleta || {});
    var base = {
      primario: paleta.primario || (usaEstandar ? ESTANDAR.primario : BASE.primario),
      acento: paleta.acento || (usaEstandar ? ESTANDAR.acento : BASE.acento),
      tinta: paleta.tinta || (usaEstandar ? ESTANDAR.tinta : BASE.tinta),
    };

    var raiz = document.documentElement;

    // La superficie clara de Leadify se fija AQUI, antes de derivar(): esa
    // función lee --fondo del DOM (vía haciaFondo/fondo()) para mezclar los
    // tintes y velos, así que tiene que ver el fondo nuevo, no el negro que
    // trae styles.css por defecto. Las cuatro constructoras no pasan por
    // aquí y se quedan con la consola negra de siempre.
    // EL SLUG, EN EL <html>. Casi todo lo que distingue a una marca se puede
    // decir con un token, y por eso esta línea no existía. Lo que no se puede
    // son las decisiones tipográficas que no son un color ni una medida —una
    // versalita, un interletrado— y que el sistema de la landing sí trae. Van
    // en `[data-marca='leadify']` al final de styles.css, que es el único sitio
    // del archivo donde una regla mira de qué marca se trata.
    raiz.setAttribute('data-marca', M.slug || '');

    if (esLeadify) {
      raiz.style.setProperty('--fondo', SUPERFICIE_Leadify.fondo);
      raiz.style.setProperty('--papel', SUPERFICIE_Leadify.papel);
      raiz.style.setProperty('--papel-2', SUPERFICIE_Leadify.papel2);
      raiz.style.setProperty('--borde', SUPERFICIE_Leadify.borde);
      raiz.style.colorScheme = 'light';
      // La geometría y los titulares se fijan aquí, al lado de la superficie:
      // no se derivan de ningún color, así que derivar() no tiene nada que
      // decir sobre ellos. Las cuatro constructoras no pasan por aquí y se
      // quedan con los valores de consola del `:root`.
      Object.keys(SISTEMA_Leadify).forEach(function (k) {
        raiz.style.setProperty(k, SISTEMA_Leadify[k]);
      });
    } else {
      raiz.style.colorScheme = 'dark';
    }

    var tokens = derivar(base);

    // La tinta (texto) no se puede derivar del fondo con la misma cuenta que
    // los tintes de marca — en derivar() viene fija como gris claro para
    // consola negra. Para Leadify se reemplaza por la escala de texto oscuro
    // de --color-navy, ANTES de que --texto-cta (más abajo) la use para
    // calcular contraste, o calcularía contra el gris claro equivocado.
    if (esLeadify) {
      tokens['--tinta'] = SUPERFICIE_Leadify.tinta;
      tokens['--tinta-media'] = SUPERFICIE_Leadify.tintaMedia;
      tokens['--tinta-suave'] = SUPERFICIE_Leadify.tintaSuave;
      tokens['--tinta-tenue'] = SUPERFICIE_Leadify.tintaTenue;
      tokens['--exito'] = SUPERFICIE_Leadify.exito;
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

    // TEXTO DEL CTA PRINCIPAL.
    //
    // SE MIDE CONTRA EL FONDO QUE EL BOTON VA A TENER, no contra el acento a
    // secas. Eran lo mismo mientras `--cta-fondo` valia `var(--acento)` para
    // todos; desde que Leadify lo pone en coral, calcular contra el verde daria
    // un color elegido para un fondo que ese boton no tiene. Es el tipo de
    // desfase que no falla: solo deja un texto peor contrastado de lo que la
    // cuenta creia.
    var fondoCta = esLeadify ? base.primario : base.acento;

    // Se decide POR CONTRASTE y no por gusto. Colsubsidio pone ahi un gris
    // neutro, que funciona porque su amarillo es clarisimo; con el verde de
    // otra marca ese mismo gris queda ilegible. Se prueba el gris de la marca
    // y, si no llega a 4.5:1, se cambia a blanco o al oscuro de la tinta — el
    // que gane.
    //
    // Para Colsubsidio el gris da 5.0:1 y se elige, o sea que el CTA conserva
    // exactamente el color de hoy. Sobre el coral de Leadify el gris no llega,
    // y entre los dos candidatos gana el navy (3,9:1 contra 2,9:1 del blanco).
    // Es UNA DIFERENCIA DELIBERADA CON LA LANDING, que pone texto blanco sobre
    // coral: ahi son 2,9:1, justo por debajo del 3,0 que pide AA para texto
    // grande. El boton se lee mejor asi, y el navy es el color de texto del
    // resto de la marca de todos modos.
    var grisTexto = tokens['--tinta-media'];
    if (contraste(grisTexto, fondoCta) >= 4.5) {
      tokens['--texto-cta'] = grisTexto;
    } else {
      tokens['--texto-cta'] =
        contraste('#ffffff', fondoCta) >= contraste(tokens['--tinta'], fondoCta)
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
