import {
  Bot,
  Building2,
  MessageCircleMore,
  Puzzle,
  ShieldCheck,
  Sparkles,
  House,
  type LucideIcon,
} from "lucide-react";

export type BeneficioMatch = {
  compatibilidad: string;
  proyecto: string;
  localidad: string;
  precioDesdeCop: number;
  zonasEnComun: string[];
  urlFicha: string;
};

export type Beneficio = {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  /** Solo el primer beneficio trae un ejemplo — salida real del motor de recomendación
   * (main.py · recomendar()) sobre el catálogo de 96 proyectos scrapeados. No es texto de ejemplo. */
  match?: BeneficioMatch;
};

// El formulario es UNO SOLO — el mismo que prueba cualquier visitante en "Pruébalo tú mismo".
// No son 5 demos distintas: son 5 beneficios del producto, válidos para cualquier inmobiliaria
// que hoy hace pauta digital, sin importar su catálogo o tamaño.
export const beneficios: Beneficio[] = [
  {
    id: "match-real",
    title: "Match real, no un formulario genérico",
    description:
      "El motor compara cada lead contra proyectos reales de tu catálogo y devuelve un % de compatibilidad — no una lista fija de preguntas sin salida.",
    icon: Sparkles,
    match: {
      compatibilidad: "97%",
      proyecto: "Florecer",
      localidad: "Bosa",
      precioDesdeCop: 207580000,
      zonasEnComun: ["Lobby", "Zona BBQ"],
      urlFicha: "https://www.colsubsidio.com/vivienda/proyectos/bogota/florecer",
    },
  },
  {
    id: "segundos",
    title: "Calificación en segundos, no en 24 horas",
    description: "Manuela llama y califica mientras el interés del lead sigue caliente, no al día siguiente.",
    icon: Bot,
  },
  {
    id: "solo-listos",
    title: "Solo los leads listos llegan a tu asesor",
    description:
      "Si no hay capacidad de compra hoy, el lead va a nutrición automática — no a la bandeja de tu equipo comercial.",
    icon: ShieldCheck,
  },
  {
    id: "sin-migrar",
    title: "Se acopla a lo que ya tienes",
    description:
      "Sin migrar tu CRM ni reconstruir tu sitio web — nos integramos a cualquier CRM para que los datos de tus leads lleguen directo a tu equipo comercial.",
    icon: Puzzle,
  },
  {
    id: "cualquier-inmobiliaria",
    title: "Funciona para cualquier inmobiliaria con pauta",
    description:
      "VIS, No VIS, un proyecto o cien: el motor se adapta a tu catálogo y a tu presupuesto de medios, con confidencialidad de datos garantizada por anonimización.",
    icon: Building2,
  },
];

export type Step = {
  number: string;
  title: string;
  description: string;
  tag: string;
  icon: LucideIcon;
};

export const steps: Step[] = [
  {
    number: "01",
    title: "Captura interactiva",
    description:
      'Leemos tu web y catálogo actual, y cambiamos el formulario genérico por una experiencia "arma tu vivienda ideal".',
    tag: "Tu web, sin reconstruirla",
    icon: House,
  },
  {
    number: "02",
    title: "Calificación con IA (Manuela)",
    description:
      "Nuestra agente de voz contacta al lead en segundos, mantiene una charla natural y evalúa capacidad de pago real.",
    tag: "Menos de 30 segundos",
    icon: Bot,
  },
  {
    number: "03",
    title: "Match comercial",
    description:
      "Solo si hay match real, el asesor recibe la ficha completa por WhatsApp o CRM para cerrar la conversación.",
    tag: "CRM o WhatsApp que ya usas",
    icon: MessageCircleMore,
  },
];
