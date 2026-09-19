import { motion } from "framer-motion";

const items = [
  "21x más cierres respondiendo rápido",
  "Manuela califica en menos de 30s",
  "Funciona con cualquier inmobiliaria que hace pauta",
  "Sin migrar tu CRM ni tu sitio",
  "Match verificado, no solo un contacto",
];

function Track() {
  return (
    <div className="flex shrink-0 items-center gap-10 pr-10">
      {items.map((item) => (
        <span key={item} className="flex items-center gap-10 text-sm font-bold uppercase tracking-wide text-navy/60">
          {item}
          <span className="text-coral">✦</span>
        </span>
      ))}
    </div>
  );
}

export function Marquee() {
  return (
    <div className="overflow-hidden border-y border-navy/8 bg-white py-5">
      <motion.div
        className="flex w-max"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: 22, ease: "linear", repeat: Infinity }}
      >
        <Track />
        <Track />
      </motion.div>
    </div>
  );
}
