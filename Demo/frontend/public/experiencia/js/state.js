// Estado central + valores derivados + acciones. Equivalente vanilla del
// estado de hooks + "renderVals()" del prototipo React original.
(function () {
  'use strict';

  function createInitial() {
    return {
      // escarapela | quiz | result | confirmacion
      // 'result' es la pantalla de SELECCIÓN de proyectos (ya sin la casa) y
      // 'confirmacion' es el cierre. Se conserva el nombre 'result' para no
      // renombrar acciones/CSS que ya funcionan.
      //
      // YA NO HAY 'splash'. Era la casita ilustrada con "Encuentra tu próximo
      // hogar" y un botón para empezar, y se fue con la landing que envolvía a
      // este quiz: ahí ya era una segunda puerta —por eso `?embed=1` la
      // saltaba— y ahora que la experiencia ES la página entera, es la única
      // puerta y sobra igual. Se entra directo a la escarapela.
      //
      // LA ESCARAPELA NO SE SALTA, aunque también sea una puerta: es donde se
      // piden nombre y teléfono, y sin ella la confirmación cierra con un lead
      // sin contacto y nada lo delata.
      //
      // Tampoco hay 'landing': esa era la portada clonada de Colsubsidio.
      screen: 'escarapela',
      // Sin pantalla de elegir personaje: 'x' (avatar neutro) por defecto.
      gender: 'x', // 'f' | 'm' | 'x'
      nombre: '',
      apellido: '',
      correo: '',
      telefono: '',
      // La cedula es la llave con la que se reconoce a alguien que vuelve. No
      // hay login: se pide junto con el telefono, y solo si los DOS coinciden
      // se devuelven sus resultados anteriores (ver js/datos.js).
      cedula: '',
      afiliado: null,
      consent: false,
      qi: 0,
      answers: {},
      // El barrio elegido en la pregunta de ubicacion. Vive FUERA de `answers`
      // a proposito (ver 'answerQuizZona' en main.js): dentro contaria como una
      // pregunta mas contestada en computeDerived y en las piezas que destapa
      // la escena. Pero tiene que estar declarado AQUI igualmente, porque
      // `restart` solo copia las claves de este objeto — si falta, reiniciar
      // arrastra el barrio de la partida anterior.
      zonaBarrio: null,
      // Los sectores elegidos, `[{localidad, barrio}, ...]`. Se pueden pedir
      // varios (ver `zonaSeleccion` en main.js). Vive fuera de `answers` por lo
      // mismo que `zonaBarrio`, y por lo mismo tiene que estar declarado AQUI:
      // `restart` solo copia las claves de este objeto, asi que sin esta linea
      // reiniciar arrastraria las zonas de la partida anterior.
      zonaSectores: [],
      matches: [],
      lead: null, // resultado de computeLeadQualification
      // Selección ÚNICA: guarda el `id` del view-model elegido (id_proyecto si
      // vino del backend). El contrato manda un solo `proyecto_elegido`, así
      // que marcar uno desmarca el anterior.
      chosen: null,
      // Pagina visible de la seleccion, 0..2. El modelo devuelve 18 proyectos
      // y la pantalla los reparte de seis en seis (ver `recoLista` en
      // templates.js). Vive aqui y no en el DOM para que marcar un proyecto
      // —que repinta la pantalla— no devuelva al usuario a la primera pagina.
      recoPagina: 0,

      // Paso 1 del contrato: POST /recomendaciones. Ver js/leads.js.
      // 'vacio' NO es un error: el backend respondió bien y no tiene proyectos
      // para esa zona; la pantalla lo dice distinto que un fallo de red.
      reco: {
        estado: 'idle', // idle | cargando | listo | vacio | error
        leadId: null,
        items: [],
        totalCatalogo: null,
        origenCatalogo: null,
        error: null,
        aproximado: false, // true = las tarjetas salen del motor local
      },

      // Paso 2 del contrato: la llamada de Manuela (ver js/llamada.js). Se
      // dispara al entrar a 'confirmacion', mismo patrón que 'reco' arriba.
      llamada: {
        estado: 'idle', // idle | cargando | lista | error
        mensaje: '',
      },

      // Paso 3: el resumen post-llamada (temperatura, resumen, recomendación
      // para el asesor). Solo arranca cuando 'llamada' resuelve con un envío
      // REAL — main.js hace polling corto contra /api/llamar/resultado hasta
      // que Dapta empuja el análisis, o hasta agotar los intentos.
      resumen: {
        estado: 'idle', // idle | esperando | listo | agotado
        datos: null,
      },

      // --- Desplegable de planos de cada tarjeta (ver detalleProyecto en
      // templates.js). Vive en el estado, y no solo en el DOM, porque marcar
      // un proyecto sí re-renderiza toda la lista: sin esto el desplegable se
      // cerraría y se perdería la tipología que el usuario estaba viendo.
      // Todos van indexados por NOMBRE de proyecto (no por posición, que
      // cambia si el clustering reordena la lista).
      detalleAbierto: {}, // nombre -> bool
      tipologiaActiva: {}, // nombre -> índice de la pestaña
      // El apartamento REAL que arma el quiz: qué plano oficial se está
      // montando y la geometría de sus piezas. Arranca con elegirApartamento
      // (sorteo estable por nombre) y se REELIGE con cada respuesta vía
      // ajustarPlanta -> planta.mejorApartamento.
      //
      // Converge hacia lo CONTESTADO, no hacia el proyecto ganador: sigue
      // siendo un ejemplo para enseñar cómo se construye una vivienda, no la
      // recomendación —esa la calcula matching.js al final y suele ser otro
      // proyecto, porque solo 8 de los 31 tienen plano utilizable.
      //
      // No es un valor derivado a propósito: el parcheo de DOM de main.js
      // necesita comparar lo que hay pintado contra lo que toca ahora.
      planta: null, // null | ver elegirApartamento() en js/planta.js
    };
  }

  // Ya no hay preguntas condicionales: al ser la demo solo de Bogotá se quitó
  // la de municipio, y con ella el "pregunta la zona solo si eligió Bogotá".
  // La función se conserva porque el resto del flujo (avance, atrás, contador)
  // razona sobre esta lista.
  function qListFor() {
    return window.GDF.data.QUESTIONS;
  }

  function computeDerived(state) {
    var scene = window.GDF.scene;
    var qList = qListFor(state.answers);
    var q = qList[state.qi];

    var answeredQs = qList.filter(function (x) {
      return state.answers[x.id] !== undefined;
    });
    var answered = answeredQs.length;
    // Ya no es un número fijo con excepciones: las siete preguntas se hacen
    // siempre (zona, tipo, ingresos, personas, habitaciones, entorno_deseado,
    // edad), así que el total es la lista misma. Ese orden lo fija data.js y no
    // es arbitrario: la última tiene que ser la que menos mueva la
    // recomendación, porque al contestarla se salta a resultados. El porqué
    // completo, incluido por qué `zona` va primera, está en la cabecera de
    // data.js.
    var stepTotal = qList.length;

    var nHab = state.answers.habitaciones === '3+' ? 3 : parseInt(state.answers.habitaciones || '2', 10);
    var nPers = state.answers.personas === '4+' ? 4 : parseInt(state.answers.personas || '0', 10);
    // El encaje con el catalogo, EN VIVO y de verdad: sale del mismo motor
    // que decide las recomendaciones (ver compatDe en matching.js). Antes
    // era `42 + (answered/stepTotal)*55`, o sea el progreso del quiz
    // disfrazado de match: subia igual contestaras lo que contestaras.
    var compat = window.GDF.matching.compatDe(state.answers);

    // El plano REAL que se está armando (ver js/planta.js); aquí solo se
    // decide cuántas de sus piezas se ven ya. La silueta y la losa existen
    // desde antes de la primera respuesta.
    var planta = state.planta;
    var showLote = !planta;
    var losaRevealed = !!planta;
    var visibles = scene.celdasVisibles(state.answers, qList, planta);
    var rooms = scene.buildRooms(planta, visibles);
    var huecos = scene.buildHuecos(planta);

    var a = state.answers;
    var perfilChips = [];
    if (a.tipo) perfilChips.push({ text: a.tipo, hi: true });
    if (a.ingresos) perfilChips.push({ text: a.ingresos, hi: false });
    if (a.habitaciones) perfilChips.push({ text: a.habitaciones + ' hab', hi: false });
    // UN CHIP POR ZONA, no solo la primera. `a.zona` es unicamente la inicial;
    // en el mapa se pueden marcar varios sectores y el resumen mostraba una
    // sola, dando a entender que se recomendo sobre ella nada mas. No es asi:
    // los dos motores puntuan contra la lista entera (matching.js y el
    // `Localidad` multiple del contrato), y el resumen tiene que decirlo.
    // Por encima de tres se resume, para no romper la linea de chips.
    var zonasChip = (a.zonas && a.zonas.length) ? a.zonas : (a.zona ? [a.zona] : []);
    zonasChip.slice(0, 3).forEach(function (z) {
      perfilChips.push({ text: z, hi: false });
    });
    if (zonasChip.length > 3) {
      perfilChips.push({ text: '+' + (zonasChip.length - 3) + ' zonas', hi: false });
    }
    if (a.afiliado === 'Sí') perfilChips.push({ text: 'Afiliado ✓', hi: true });

    return {
      qList: qList,
      q: q,
      answered: answered,
      stepTotal: stepTotal,
      showLote: showLote,
      losaRevealed: losaRevealed,
      rooms: rooms,
      huecos: huecos,
      // El apartamento que se está armando: de aquí salen el rótulo y la
      // relación de aspecto de la losa.
      planta: planta,
      nHab: nHab,
      nPers: nPers,
      compat: compat,
      perfilChips: perfilChips,
    };
  }

  /**
   * Reelige el plano segun TODO lo contestado hasta ahora.
   *
   * Se llama en CADA respuesta, no solo en la de alcobas. `mejorApartamento`
   * (planta.js) devuelve null cuando el que ya esta puesto sigue siendo el
   * mejor, o cuando el candidato no gana por el margen minimo — asi el plano
   * no salta de un lado a otro entre preguntas contiguas.
   *
   * `ajustada` queda en true SIEMPRE que se conteste, cambie el plano o no, y
   * main.js lo lee para animar. Es a proposito: si la misma accion unas veces
   * mueve el plano y otras no hace nada, se lee como que la app se colgo. Lo
   * que la animacion comunica es "tu plano quedo ajustado a lo que pediste", y
   * eso es cierto en los dos casos.
   *
   * EL SUELO DE PIEZAS (`minimo`/`minimoDesde`) es lo que impide que el
   * apartamento ENCOJA al cambiar de plano. Cada plano trae su propio reparto
   * `vis[]`, monotono dentro de si mismo pero no entre planos distintos: pasar
   * de uno de 12 celdas a uno de 9 restaba piezas y el usuario veia MENOS
   * apartamento despues de contestar. Con el suelo, la bola reordena y nunca
   * resta. Se guarda desde que pregunta aplica para que `goBack` siga restando
   * como siempre.
   */
  function ajustarPlanta(state, respondidas, visiblesAntes) {
    var actual = state.planta;
    var nueva = window.GDF.planta.mejorApartamento(state);
    if (!nueva) {
      // El que esta puesto sigue siendo el mejor: no hay nada que cambiar,
      // pero la respuesta igual tiene que producir una reaccion.
      if (actual) actual.ajustada = true;
      return;
    }
    nueva.ajustada = true;
    if (actual) {
      nueva.minimo = visiblesAntes;
      nueva.minimoDesde = respondidas;
    }
    state.planta = nueva;
  }

  function applyAction(state, action, ds) {
    switch (action) {
      // AQUI VIVIA 'goSplash'. Se borro con la pantalla a la que llevaba (ver
      // createInitial): una accion que apunta a una pantalla que ya no existe
      // no se ve rota, se ve como una bienvenida que aparece a destiempo.
      // Cualquier accion desconocida cae en el `default` de mas abajo, que
      // devuelve false y no toca el estado.

      case 'goEscarapela':
        state.screen = 'escarapela';
        break;

      case 'setAfiliado':
        state.afiliado = ds.value;
        break;

      case 'toggleConsent':
        state.consent = !state.consent;
        break;

      case 'startQuiz': {
        var isValidEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(state.correo.trim());
        var canStart = !!(
          state.nombre.trim() &&
          state.apellido.trim() &&
          state.correo.trim() &&
          isValidEmail &&
          state.telefono.trim() &&
          state.cedula.trim() &&
          state.consent
        );
        if (!canStart) return false;
        state.answers = { afiliado: state.afiliado };
        state.qi = 0;
        state.screen = 'quiz';
        // El apartamento se elige AQUÍ y ya no cambia. Sale del nombre y el
        // apellido que se acaban de escribir, así que la misma persona ve
        // siempre el mismo plano y dos personas seguidas en un stand ven
        // planos distintos.
        state.planta = window.GDF.planta.elegirApartamento(state);
        break;
      }

      /* Alguien que YA paso por aqui y vuelve: se le devuelven sus resultados
         sin volver a preguntarle nada (ver js/datos.js y el intercepto de
         'startQuiz' en main.js). `ds.respuestas` son las respuestas que dio
         aquella vez.

         Aqui NO se pinta la lista: eso lo hace 'recoResuelta' justo despues,
         con los resultados guardados tal cual se guardaron. Reusarla es lo que
         garantiza que la pantalla restaurada sea identica a la original — si
         se armara aparte, serian dos caminos que pueden divergir. */
      case 'restaurarConsulta': {
        state.answers = ds.respuestas || {};
        state.qi = 0;
        state.screen = 'result';
        state.chosen = null;
        // La calificacion del lead se recalcula, no se guarda: depende de las
        // respuestas, que si estan guardadas, y asi un cambio en las reglas de
        // negocio aplica tambien a quien vuelve.
        var mejorGuardado = window.GDF.matching.computeMatches(state.answers, 1);
        state.lead = window.GDF.qualification.computeLeadQualification(
          state.answers,
          mejorGuardado[0] ? mejorGuardado[0].score : 0
        );
        break;
      }

      case 'selectOption': {
        var qid = ds.qid;
        var value = ds.value;
        var nextAnswers = Object.assign({}, state.answers);
        nextAnswers[qid] = value;
        var list = qListFor(nextAnswers);
        var ni = state.qi + 1;
        state.answers = nextAnswers;
        if (ni >= list.length) {
          // Terminó el quiz -> pantalla de selección de proyectos, en estado
          // 'cargando'. Las recomendaciones ya NO se calculan aquí: las pide
          // main.js al backend (paso 1 del contrato). Ver js/recommender.js.
          state.screen = 'result';
          state.reco = {
            estado: 'cargando', leadId: null, items: [], totalCatalogo: null,
            origenCatalogo: null, error: null, aproximado: false,
          };
          state.chosen = null;
          // La calificación del lead SÍ se calcula ya: es lógica de negocio y
          // no debe depender de una llamada de red. Se apoya en el motor local
          // solo para saber qué tan bien calza el mejor proyecto disponible.
          var mejores = window.GDF.matching.computeMatches(nextAnswers, 1);
          state.lead = window.GDF.qualification.computeLeadQualification(
            nextAnswers,
            mejores[0] ? mejores[0].score : 0
          );
        } else {
          state.qi = ni;
        }
        // El plano se reajusta con CADA respuesta, no solo con la de alcobas:
        // es lo que hace que la escena reaccione a todo lo que se contesta.
        //
        // El cambio es barato de ver porque todas las plantas del sorteo son
        // rectangulares y se trocean igual (12 celdas, c0..c11): las piezas ya
        // puestas no mueren, se reacomodan y cambian de imagen.
        //
        // Se mide cuantas piezas habia ANTES de cambiar para pasarselas como
        // suelo al plano nuevo; si no, cambiar de plano podia restar piezas.
        ajustarPlanta(
          state,
          list.filter(function (x) { return nextAnswers[x.id] !== undefined; }).length,
          window.GDF.scene.celdasVisibles(state.answers, list, state.planta)
        );
        break;
      }

      // Resultado del paso 1 (POST /recomendaciones). Lo despacha main.js
      // cuando resuelve la promesa; `ds` ES el objeto que arma recommender.js.
      case 'recoResuelta':
        state.reco = {
          estado: ds.estado,
          leadId: ds.leadId || null,
          items: ds.items || [],
          totalCatalogo: ds.totalCatalogo || null,
          origenCatalogo: ds.origenCatalogo || null,
          error: ds.error || null,
          aproximado: !!ds.aproximado,
        };
        // Si la lista cambió, la selección anterior puede ya no existir.
        if (state.chosen && !state.reco.items.some(function (x) { return x.id === state.chosen; })) {
          state.chosen = null;
        }
        break;

      case 'recoCargando':
        state.reco.estado = 'cargando';
        state.reco.error = null;
        break;

      // Paso 2: resultado de POST /api/llamar (ver js/llamada.js). `ds` es
      // el objeto que arma llamada.js: { estado, mensaje }.
      case 'llamadaCargando':
        state.llamada = { estado: 'cargando', mensaje: '' };
        break;

      case 'llamadaResuelta':
        state.llamada = { estado: ds.estado, mensaje: ds.mensaje || '' };
        break;

      // Botón "Reintentar" de la pantalla de cierre tras un error. main.js
      // detecta esta acción y vuelve a llamar a llamada.disparar().
      case 'reintentarLlamada':
        state.llamada = { estado: 'cargando', mensaje: '' };
        state.resumen = { estado: 'idle', datos: null };
        break;

      // Paso 3: ciclo de polling de /api/llamar/resultado (ver js/llamada.js
      // y main.js). `ds` en 'resumenListo' es el cuerpo que devolvió el
      // backend cuando `listo: true`.
      case 'resumenEsperando':
        state.resumen = { estado: 'esperando', datos: null };
        break;

      case 'resumenListo':
        state.resumen = { estado: 'listo', datos: ds };
        break;

      case 'resumenAgotado':
        state.resumen = { estado: 'agotado', datos: null };
        break;

      // Botón "Buscar resumen" tras agotar los intentos automáticos. Vuelve
      // a 'esperando' para que main.js relance el ciclo de polling.
      case 'reintentarResumen':
        state.resumen = { estado: 'esperando', datos: null };
        break;

      case 'goBack': {
        // En la primera pregunta no hay a dónde retroceder dentro del quiz:
        // regresa a escarapela (el paso anterior en el flujo completo).
        if (state.qi === 0) {
          state.screen = 'escarapela';
          break;
        }
        var qList = qListFor(state.answers);
        var prev = qList[state.qi - 1];
        var nextAnswers2 = Object.assign({}, state.answers);
        delete nextAnswers2[prev.id];
        state.qi = state.qi - 1;
        state.answers = nextAnswers2;
        // El barrio vive fuera de `answers` (ver 'answerQuizZona' en main.js),
        // así que el delete de arriba no lo alcanza: si no se borra aquí,
        // al volver sobre la pregunta de ubicación seguiría anunciando el
        // barrio de la respuesta que se acaba de deshacer.
        //
        // `zonas` SI vive dentro de `answers` —es lo que leen matching.js y
        // leadify.js— pero el delete de arriba solo quita la llave de la
        // pregunta (`zona`), así que hay que quitarla a mano o la respuesta
        // quedaría medio deshecha: sin `zona` pero con las localidades.
        //
        // `zonaSectores` NO se borra a propósito: es lo que se acaba de
        // elegir, y al volver aquí se recupera para poder corregirlo (ver
        // attachInputListeners). Deshacer la respuesta no es tirar el trabajo.
        if (prev.id === 'zona') {
          state.zonaBarrio = null;
          delete state.answers.zonas;
        }
        // El apartamento NO se pierde al retroceder, ni siquiera hasta la
        // primera pregunta: se queda sin piezas y en pantalla sigue la silueta.
        // Eso es lo que evita tener que reconstruir la escena por innerHTML.
        if (state.planta) state.planta.ajustada = false;
        break;
      }

      // Tocar "Llamar" en una tarjeta ES elegir el proyecto: el contrato manda
      // un solo `proyecto_elegido`, y aquí queda fijado en el mismo gesto que
      // lleva al cierre. Ya no hay un paso previo de marcar la tarjeta.
      case 'llamarProyecto':
        if (!ds.value) return false;
        state.chosen = ds.value;
        state.screen = 'confirmacion';
        break;

      // Las 3 acciones del desplegable de planos solo guardan la preferencia:
      // el repintado lo hace main.js por DOM directo (ver dispatch), porque
      // re-renderizar aquí cerraría el <details> y recargaría los planos.
      case 'setDetalleAbierto':
        state.detalleAbierto[ds.proyecto] = ds.valor === '1';
        break;

      case 'verTipologia':
        state.tipologiaActiva[ds.proyecto] = parseInt(ds.idx, 10) || 0;
        break;

      case 'goSeleccion':
        state.screen = 'result';
        break;

      case 'irAPagina': {
        // El destino llega como texto desde `data-pagina`. Se acota contra el
        // numero real de proyectos —no contra un 3 fijo— porque una tanda con
        // menos de 18 tiene menos paginas, y las flechas de los extremos van
        // deshabilitadas pero un teclado puede llegar igual.
        var porPag = window.GDF.recommender.POR_PAGINA || 6;
        var cuantas = Math.max(1, Math.ceil(((state.reco.items || []).length) / porPag));
        var destino = Number(ds && ds.pagina);
        if (isNaN(destino)) return false;
        destino = Math.min(Math.max(destino, 0), cuantas - 1);
        if (destino === state.recoPagina) return false;
        state.recoPagina = destino;
        break;
      }

      case 'restart': {
        var fresh = createInitial();
        Object.keys(fresh).forEach(function (k) {
          state[k] = fresh[k];
        });
        // "Empezar de nuevo" vuelve a la entrada, y cual es la entrada lo
        // decide `createInitial()` — hoy la escarapela. Aqui NO se fija a
        // mano: el nombre de la pantalla escrito en dos sitios es lo que deja
        // un 'splash' colgado cuando la entrada cambia.
        state.screen = fresh.screen;
        break;
      }

      default:
        return false;
    }
    return true;
  }

  window.GDF = window.GDF || {};
  window.GDF.state = {
    createInitial: createInitial,
    computeDerived: computeDerived,
    applyAction: applyAction,
  };
})();
