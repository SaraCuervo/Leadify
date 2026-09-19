import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { macheaOffer } from "../lib/offerConfig";
import { Reveal } from "./Reveal";

const faqs = [
  {
    q: "¿Necesito cambiar mi sitio web o mi CRM?",
    a: "No. Machea se acopla a lo que ya tienes — leemos tu catálogo actual y conectamos con tu CRM o WhatsApp, sin pedirte una migración ni un rediseño.",
  },
  {
    q: "¿Cuánto cuesta el piloto?",
    a: "Empieza con una auditoría gratuita: te mostramos, con tus propios datos, cuánto estás perdiendo por demora de respuesta. El costo del piloto se confirma según el volumen de leads de tu operación.",
  },
  {
    q: "¿Qué pasa si Manuela no funciona para mi inmobiliaria?",
    a: macheaOffer.guarantee.text,
  },
  {
    q: "¿Cómo empiezo?",
    a: 'Solicitas la auditoría gratis, en menos de 48 horas te mostramos los números reales de tu proceso actual, y decides si avanzas al piloto — sin compromiso desde el primer paso.',
  },
];

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section className="relative bg-white py-24">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mb-14 text-center">
          <p className="mb-4 text-sm font-bold uppercase tracking-[0.15em] text-coral">Antes de que preguntes</p>
          <h2 className="text-4xl font-extrabold text-navy md:text-5xl">Preguntas frecuentes</h2>
        </Reveal>

        <Reveal delay={0.1} className="space-y-3">
          {faqs.map((item, i) => {
            const isOpen = openIndex === i;
            return (
              <div key={item.q} className="overflow-hidden rounded-2xl border border-navy/10 bg-beige">
                <button
                  type="button"
                  onClick={() => setOpenIndex(isOpen ? null : i)}
                  className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
                >
                  <span className="font-bold text-navy">{item.q}</span>
                  <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.25 }} className="shrink-0 text-navy/50">
                    <ChevronDown size={20} />
                  </motion.span>
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                      className="overflow-hidden"
                    >
                      <p className="px-6 pb-5 text-navy/70">{item.a}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </Reveal>
      </div>
    </section>
  );
}
