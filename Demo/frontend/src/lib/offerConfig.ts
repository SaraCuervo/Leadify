/**
 * ==========================================
 * CONFIGURACIÓN DE LA OFERTA — fácil de editar
 * Framework: Grand Slam Offer (Hormozi) — stack de valor + garantía + urgencia real.
 * Los campos marcados [CONFIRMAR CON EQUIPO] tienen cifras que el equipo
 * todavía tiene que afinar antes de GO FEST — no son inventadas.
 * ==========================================
 */
export const macheaOffer = {
  eyebrow: "Auditoría Gratuita + Piloto Machea",
  headline: "Antes de pedirte que cambies nada, te mostramos cuánto estás perdiendo hoy.",

  // El "stack" de valor: cada capa suma sobre la anterior — así se arma una Grand Slam Offer.
  stack: [
    {
      title: "Auditoría gratuita de tu proceso actual",
      text: "Con tus propios datos: te mostramos cuánto estás perdiendo por demora de respuesta — en menos de 48 horas.",
    },
    {
      title: "Piloto sin fricción",
      text: "Corremos Machea con tus primeros [NÚMERO DE LEADS — CONFIRMAR CON EQUIPO]. No tocamos tu sitio web actual ni tu CRM.",
    },
    {
      title: "Acompañamiento cercano",
      text: "Cupos limitados a [NÚMERO DE INMOBILIARIAS — CONFIRMAR CON EQUIPO] este trimestre, para darle seguimiento de cerca a cada implementación.",
    },
  ],

  guarantee: {
    title: "Garantía Machea",
    text: "Si Manuela no califica y agenda leads más rápido que tu proceso actual, no pagas el piloto.",
  },

  // Un solo texto de CTA, repetido igual en nav, hero y oferta — principio tomado de Chispa.
  ctaText: "Solicitar auditoría gratis",
  ctaNote: "Sin tarjeta, sin compromiso. Trato B2B directo.",
  contactEmail: "equipo@machea.co", // TODO: reemplazar por el correo comercial real antes de publicar
};
