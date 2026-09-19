/**
 * Los iconos de las zonas comunes, dibujados aquí.
 *
 * POR QUÉ NO SE SCRAPEAN
 * ----------------------
 * El catálogo de Bogotá trae `zonas_comunes` como una LISTA DE TEXTO y nada
 * más: no hay ni una URL de icono en los 96 proyectos. Se podrían bajar de la
 * web de cada constructora —todas publican sus pictogramas— pero eso trae dos
 * problemas que no compensan:
 *
 *   1. Serían los iconos DE UNA MARCA dentro de la demo de otra. Es la misma
 *      mezcla que el resto del repo se dedica a evitar, y aquí encima se vería:
 *      los de Colsubsidio son azules y redondos, los de Bolívar son de línea.
 *   2. Cada web los publica de una forma distinta (sprites, CSS de fondo,
 *      SVG suelto) y con nombres que no cruzan con el vocabulario del contrato,
 *      así que habría que mapear 26 etiquetas a mano cuatro veces.
 *
 * Dibujados aquí son UNOS, coherentes entre sí, sin red y sin depender de que
 * nadie mantenga su CDN. Y como usan `currentColor`, toman el color de la marca
 * que lleve puesta la app.
 *
 * EL VOCABULARIO ES EL DEL CONTRATO, y esa es la clave de todo: las 26 llaves
 * de aquí son EXACTAMENTE los `label` de la pregunta `entorno_deseado` de
 * data.js — las 25 del contrato de Machea más "Cancha múltiple", que el
 * contrato no conoce. Si alguna se escribe distinto, esa zona se pinta con el
 * punto de siempre y no se entera nadie; por eso `icono()` busca sin tildes y
 * sin mayúsculas, que es la misma vuelta que da `machea.js`.
 *
 * Son de LÍNEA, no macizos: se pintan a 18-20 px dentro de una caja pequeña y
 * un pictograma relleno a ese tamaño se convierte en una mancha.
 */
(function () {
  'use strict';

  // Todos comparten caja y grosor para que la retícula no baile.
  var ABRE =
    '<svg class="gdf-icono" viewBox="0 0 24 24" fill="none" aria-hidden="true" ' +
    'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">';

  function svg(cuerpo) {
    return ABRE + cuerpo + '</svg>';
  }

  var TRAZOS = {
    // Campana de recepcion sobre el mostrador.
    'Lobby': '<path d="M8 12a4 4 0 0 1 8 0"/><path d="M6.5 12h11"/><path d="M12 8V6.6"/>' +
             '<circle cx="12" cy="5.6" r="1"/><path d="M4 20v-4h16v4"/><path d="M2.5 20h19"/>',
    // Agua en tres ondas y el borde del vaso.
    'Piscina': '<path d="M3 18c1.6 0 1.6-1.4 3.2-1.4S7.8 18 9.4 18s1.6-1.4 3.2-1.4S14.2 18 15.8 18' +
               's1.6-1.4 3.2-1.4S20.6 18 21 18"/>' +
               '<path d="M3 13c1.6 0 1.6-1.4 3.2-1.4S7.8 13 9.4 13s1.6-1.4 3.2-1.4S14.2 13 15.8 13' +
               's1.6-1.4 3.2-1.4S20.6 13 21 13"/><path d="M7 11V5a2 2 0 0 1 4 0v6"/>' +
               '<path d="M15 11V5a2 2 0 0 1 4 0v6"/>',
    'Zona de lavandería': '<rect x="4" y="3" width="16" height="18" rx="2"/>' +
                          '<circle cx="12" cy="14" r="4"/><path d="M7 7h2"/>',
    'Zona BBQ': '<path d="M5 8h14l-2 7a5 5 0 0 1-10 0Z"/><path d="M9 20l1.5-3M15 20l-1.5-3"/>' +
                '<path d="M9 5c0-1 1-1 1-2M13 5c0-1 1-1 1-2"/>',
    // Huella.
    'Zona pet': '<ellipse cx="12" cy="15" rx="4" ry="3.4"/><circle cx="6.5" cy="10" r="1.8"/>' +
                '<circle cx="17.5" cy="10" r="1.8"/><circle cx="9.5" cy="6" r="1.8"/>' +
                '<circle cx="14.5" cy="6" r="1.8"/>',
    // Tobogán.
    'Zona kids': '<path d="M4 20v-3a5 5 0 0 1 5-5h2"/><path d="M20 20l-6-9"/>' +
                 '<path d="M11 12h6"/><circle cx="16" cy="6" r="2"/><path d="M4 20h16"/>',
    'Locales comerciales': '<path d="M4 10v10h16V10"/><path d="M3 10l1.6-5h14.8L21 10Z"/>' +
                           '<path d="M10 20v-6h4v6"/>',
    // Mancuerna.
    'Zona fitness': '<path d="M4 9v6M7 7v10M17 7v10M20 9v6"/><path d="M7 12h10"/>',
    // Sofá.
    'Salón social': '<path d="M4 12V9a2 2 0 0 1 4 0v3M16 12V9a2 2 0 0 1 4 0v3"/>' +
                    '<rect x="3" y="12" width="18" height="6" rx="2"/><path d="M6 18v2M18 18v2"/>',
    'Spa mascotas': '<path d="M4 13h16v3a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4Z"/>' +
                    '<path d="M8 13V7a2 2 0 0 1 4 0"/><circle cx="16" cy="7" r="2.4"/>' +
                    '<path d="M14.6 5.2 15.6 4M17.4 5.2 16.4 4"/>',
    // Sombrilla y tumbona.
    'Zona cool': '<path d="M12 4a7 7 0 0 1 7 7H5a7 7 0 0 1 7-7Z"/><path d="M12 11v9"/>' +
                 '<path d="M9 20h6"/>',
    'Zona cine': '<rect x="3" y="6" width="14" height="12" rx="2"/>' +
                 '<path d="M17 10l4-2.5v9L17 14Z"/><path d="M7 6l2 4M12 6l2 4"/>',
    // Portátil.
    'Coworking': '<rect x="4" y="5" width="16" height="10" rx="1.5"/><path d="M2 19h20"/>' +
                 '<path d="M9 19l1-4h4l1 4"/>',
    'Sala VIP': '<path d="M4 8l3.5 3L12 5l4.5 6L20 8l-1.6 9H5.6Z"/><path d="M5.6 20h12.8"/>',
    'Zona café': '<path d="M4 8h13v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4Z"/>' +
                 '<path d="M17 9h2a2.5 2.5 0 0 1 0 5h-2"/><path d="M8 5c0-1 1-1 1-2M12 5c0-1 1-1 1-2"/>',
    // Cinta de correr.
    'Gimnasio': '<path d="M3 18h13l4-11"/><path d="M3 18v2M16 18v2"/>' +
                '<circle cx="8" cy="7" r="1.8"/><path d="M8 9v4l3 2"/><path d="M6 12l2-1"/>',
    'Parqueadero': '<rect x="3" y="3" width="18" height="18" rx="3"/>' +
                   '<path d="M10 17V7h3.2a3 3 0 0 1 0 6H10"/>',
    // Arbol de copa ancha. Antes era un circulo sobre un palo y se leia como
    // el simbolo de Venus.
    'Zona verde': '<path d="M12 21v-5.5"/>' +
                  '<path d="M7.6 15.5a4.2 4.2 0 0 1-1.4-8 5 5 0 0 1 9.6-1.2 4.4 4.4 0 0 1 1 8.7Z"/>' +
                  '<path d="M12 15.5 9.6 12.6M12 13.4l2.2-2.4"/><path d="M8.5 21h7"/>',
    // Un BANCO, no otro arbol: es lo que separa "parque" de "zona verde".
    'Parque': '<path d="M3 13h18"/><path d="M3 16.5h18"/><path d="M4.5 13v6M19.5 13v6"/>' +
              '<path d="M5 10h14"/><path d="M6 10V8.2M18 10V8.2"/><path d="M2 21h20"/>',
    // Dado.
    'Sala de juegos': '<rect x="3" y="3" width="18" height="18" rx="3"/>' +
                      '<circle cx="8.5" cy="8.5" r="1.1" fill="currentColor" stroke="none"/>' +
                      '<circle cx="15.5" cy="8.5" r="1.1" fill="currentColor" stroke="none"/>' +
                      '<circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none"/>' +
                      '<circle cx="8.5" cy="15.5" r="1.1" fill="currentColor" stroke="none"/>' +
                      '<circle cx="15.5" cy="15.5" r="1.1" fill="currentColor" stroke="none"/>',
    'Pista de trote': '<circle cx="15" cy="4.5" r="1.8"/>' +
                      '<path d="M13.6 8 10 10.5l1.8 3.2L9 20"/><path d="M11.8 13.7 16 15l1.4 4.6"/>' +
                      '<path d="M13.6 8l4 1.4 1.4 3"/><path d="M10 10.5 6 10"/>',
    'Voleibol playa': '<circle cx="12" cy="12" r="8"/><path d="M12 4c2.4 2.4 3.2 5.4 2.4 8.6"/>' +
                      '<path d="M4.6 9.4c3.2-.8 6.4 0 8.8 2.4"/><path d="M8 19.2c1.6-3 4-5 7.6-5.6"/>',
    'Cancha de pádel': '<ellipse cx="10" cy="8.5" rx="5" ry="5.5"/><path d="M10 14v6"/>' +
                       '<path d="M7.5 20h5"/><path d="M6.5 6.5h7M6.5 10.5h7M10 3.2v10.6"/>',
    'Taller de bicicletas': '<circle cx="6" cy="16" r="3.5"/><circle cx="18" cy="16" r="3.5"/>' +
                            '<path d="M6 16l3.5-7H14l4 7"/><path d="M9.5 9H8"/><path d="M12 16H6"/>',
    'Sauna': '<path d="M3 20h18"/><path d="M5 20v-7h14v7"/><path d="M5 13l7-4 7 4"/>' +
             '<path d="M9 7c0-1.2 1.2-1.2 1.2-2.4M13.8 7c0-1.2 1.2-1.2 1.2-2.4"/>',
    'Cancha múltiple': '<rect x="3" y="5" width="18" height="14" rx="1.5"/>' +
                       '<path d="M12 5v14"/><circle cx="12" cy="12" r="2.6"/>' +
                       '<path d="M3 9h2.6v6H3M21 9h-2.6v6H21"/>',
  };

  // Sin tildes y en minúsculas, igual que hace machea.js para cruzar el
  // vocabulario. Una tilde de menos no puede costar el icono.
  function normalizar(t) {
    return String(t || '')
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .toLowerCase().trim();
  }

  var POR_CLAVE = {};
  Object.keys(TRAZOS).forEach(function (label) {
    POR_CLAVE[normalizar(label)] = TRAZOS[label];
  });

  /**
   * El SVG de una zona común, o '' si no la conocemos.
   *
   * Devolver '' y no un icono genérico es a propósito: quien lea el código
   * tiene que poder ver de un vistazo cuáles faltan, y un comodín las
   * escondería. La que no cruza se pinta con el punto de siempre.
   */
  function icono(label) {
    var trazo = POR_CLAVE[normalizar(label)];
    return trazo ? svg(trazo) : '';
  }

  window.GDF = window.GDF || {};
  window.GDF.iconos = { icono: icono, TRAZOS: TRAZOS };
})();
