import { motion } from "framer-motion";
import { Bot, Check, Handshake, PhoneCall, UserRoundCheck } from "lucide-react";
import { useEffect, useState } from "react";

const nodes = [
  { label: "Captura", detail: "Web activa", icon: UserRoundCheck },
  { label: "Manuela", detail: "Calificando", icon: Bot },
  { label: "Asesor", detail: "Listo para recibir", icon: Handshake },
];

export function LeadMockup() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setActive((v) => (v + 1) % nodes.length), 1800);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="relative mx-auto w-full max-w-md">
      <motion.div
        aria-hidden="true"
        className="absolute -inset-6 -z-10 rounded-[40px] bg-coral/10 blur-3xl"
        animate={{ opacity: [0.5, 0.9, 0.5] }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        initial={{ opacity: 0, y: 30, rotate: -1.5 }}
        animate={{ opacity: 1, y: 0, rotate: -1.5 }}
        transition={{ duration: 0.8, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
        whileHover={{ rotate: 0, y: -4 }}
        className="relative rounded-[28px] border border-navy/10 bg-white p-6 shadow-soft"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.85, y: -8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ delay: 1.1, duration: 0.5, type: "spring", stiffness: 260, damping: 18 }}
          className="absolute -right-4 -top-4 flex items-center gap-2 rounded-2xl border border-navy/10 bg-white px-3.5 py-2.5 shadow-lg"
        >
          <motion.span
            animate={{ scale: [1, 1.15, 1] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
            className="grid h-6 w-6 place-items-center rounded-full bg-coral text-white"
          >
            <PhoneCall size={12} />
          </motion.span>
          <span className="text-xs font-bold text-navy">Manuela está calificando</span>
        </motion.div>

        <div className="flex items-start justify-between">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-navy/40">Lead activo</p>
            <p className="mt-1 text-base font-extrabold text-navy">Conversación lista para asesor</p>
          </div>
          <span className="flex items-center gap-1.5 rounded-full bg-emerald/15 px-2.5 py-1 text-[11px] font-bold text-emerald-700">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald" /> Match
          </span>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-2 border-t border-navy/8 pt-4 text-center">
          {[
            { k: "Tipo", v: "VIS" },
            { k: "Zona", v: "Norte" },
            { k: "Paso", v: "Llamar" },
          ].map((m) => (
            <div key={m.k}>
              <p className="text-[10px] font-bold uppercase tracking-wide text-navy/40">{m.k}</p>
              <p className="mt-0.5 text-sm font-extrabold text-navy">{m.v}</p>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-2xl bg-beige p-4">
          <p className="mb-3 text-[10px] font-extrabold uppercase tracking-[0.15em] text-navy/40">Ruta activa</p>
          <div className="flex items-center">
            {nodes.map((node, i) => {
              const Icon = node.icon;
              const isDone = i < active;
              const isActive = i === active;
              return (
                <div key={node.label} className="flex flex-1 items-center last:flex-none">
                  <div className="flex flex-col items-center gap-1.5">
                    <motion.span
                      animate={{
                        scale: isActive ? 1.15 : 1,
                        backgroundColor: isDone || isActive ? "var(--color-coral)" : "#ffffff",
                        color: isDone || isActive ? "#ffffff" : "var(--color-navy)",
                      }}
                      transition={{ duration: 0.4 }}
                      className="grid h-9 w-9 place-items-center rounded-full border border-navy/10 shadow-sm"
                    >
                      {isDone ? <Check size={15} /> : <Icon size={15} />}
                    </motion.span>
                    <div className="text-center">
                      <p className="text-[11px] font-bold text-navy">{node.label}</p>
                      <p className="text-[10px] text-navy/40">{node.detail}</p>
                    </div>
                  </div>
                  {i < nodes.length - 1 && (
                    <div className="mx-1 mb-5 h-px flex-1 bg-navy/10">
                      <motion.div
                        className="h-px bg-coral"
                        initial={{ width: "0%" }}
                        animate={{ width: i < active ? "100%" : "0%" }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
