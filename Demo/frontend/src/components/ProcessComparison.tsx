import { AnimatePresence, motion } from "framer-motion";
import { Bot, Check, ClipboardList, Frown, Loader2, UserRoundCheck, Zap } from "lucide-react";
import { useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Izquierda: el formulario genérico de siempre — a propósito feo, a propósito
// lento. Un guion de "fotogramas" avanza solo, en loop.
// ---------------------------------------------------------------------------
const FRAMES = [
  { nombre: "", telefono: "", mensaje: "", checked: false, phase: "idle", hold: 900 },
  { nombre: "Andrea Gómez", telefono: "", mensaje: "", checked: false, phase: "idle", hold: 700 },
  { nombre: "Andrea Gómez", telefono: "300 456 7890", mensaje: "", checked: false, phase: "idle", hold: 700 },
  { nombre: "Andrea Gómez", telefono: "300 456 7890", mensaje: "Info del proyecto, por favor", checked: false, phase: "idle", hold: 800 },
  { nombre: "Andrea Gómez", telefono: "300 456 7890", mensaje: "Info del proyecto, por favor", checked: true, phase: "idle", hold: 600 },
  { nombre: "Andrea Gómez", telefono: "300 456 7890", mensaje: "Info del proyecto, por favor", checked: true, phase: "sending", hold: 2200 },
  { nombre: "Andrea Gómez", telefono: "300 456 7890", mensaje: "Info del proyecto, por favor", checked: true, phase: "sent", hold: 2400 },
] as const;

function TypedField({ value }: { value: string }) {
  return (
    <span className="inline-block overflow-hidden whitespace-nowrap align-bottom">
      <motion.span
        className="inline-block"
        initial={false}
        animate={{ width: value ? `${value.length}ch` : "0ch" }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        style={{ display: "inline-block", overflow: "hidden" }}
      >
        {value}
      </motion.span>
    </span>
  );
}

function SketchyForm() {
  const [i, setI] = useState(0);
  const frame = FRAMES[i];

  useEffect(() => {
    const t = window.setTimeout(() => setI((v) => (v + 1) % FRAMES.length), frame.hold);
    return () => window.clearTimeout(t);
  }, [i, frame.hold]);

  return (
    <div className="rounded-2xl border-2 border-dashed border-navy/25 bg-[#ece6d8] p-5" style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>
      <div className="mb-3 flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
        <span className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
        <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
        <span className="ml-2 text-[10px] text-navy/40">inmobiliaria-generica.com/contacto</span>
      </div>

      <p className="mb-3 text-center text-lg font-bold text-navy underline decoration-2 underline-offset-4">
        CONTÁCTENOS
      </p>

      <div className="space-y-2.5 text-[13px] text-navy/80">
        <div>
          <label className="mb-0.5 block text-[11px] text-navy/60">Nombre completo:</label>
          <div className="h-7 w-full border-2 border-navy/30 bg-white px-2 py-1">
            <TypedField value={frame.nombre} />
          </div>
        </div>
        <div>
          <label className="mb-0.5 block text-[11px] text-navy/60">Teléfono:</label>
          <div className="h-7 w-full border-2 border-navy/30 bg-white px-2 py-1">
            <TypedField value={frame.telefono} />
          </div>
        </div>
        <div>
          <label className="mb-0.5 block text-[11px] text-navy/60">¿En qué podemos ayudarle?</label>
          <div className="h-12 w-full border-2 border-navy/30 bg-white px-2 py-1">
            <TypedField value={frame.mensaje} />
          </div>
        </div>
        <div className="flex items-center gap-1.5 border border-navy/20 bg-white px-2 py-1.5 text-[10px] text-navy/50">
          <span
            className={`grid h-3.5 w-3.5 place-items-center border border-navy/40 ${frame.checked ? "bg-navy/70" : "bg-white"}`}
          >
            {frame.checked && <Check size={9} className="text-white" />}
          </span>
          No soy un robot
        </div>
        <button
          type="button"
          disabled
          className="rounded-sm bg-blue-700 px-4 py-1.5 text-xs font-bold text-white opacity-90"
        >
          ENVIAR →
        </button>

        <div className="h-6 pt-1">
          <AnimatePresence mode="wait">
            {frame.phase === "sending" && (
              <motion.p
                key="sending"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1.5 text-[11px] text-navy/50"
              >
                <Loader2 size={12} className="animate-spin" /> Enviando…
              </motion.p>
            )}
            {frame.phase === "sent" && (
              <motion.p
                key="sent"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1.5 text-[11px] text-navy/50"
              >
                <Frown size={12} /> Un asesor le contactará en 24–48 horas.
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Derecha: el mismo momento, contado con Machea — formulario, llamada, lead
// calificado y cierre, en loop.
// ---------------------------------------------------------------------------
const MACHEA_STEPS = [
  { icon: ClipboardList, title: "Formulario", detail: "Datos capturados" },
  { icon: Bot, title: "Llamada IA", detail: "Manuela califica en vivo" },
  { icon: Zap, title: "Lead calificado", detail: "Capacidad de pago validada" },
  { icon: UserRoundCheck, title: "Asesor de cierre", detail: "Ficha completa, listo para cerrar" },
];

function MacheaFlow() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const t = window.setInterval(() => setActive((v) => (v + 1) % (MACHEA_STEPS.length + 1)), 1300);
    return () => window.clearInterval(t);
  }, []);

  return (
    <div className="rounded-2xl border border-emerald/20 bg-navy p-6 text-white">
      <p className="mb-5 text-center text-sm font-bold text-white/60">Con Machea, en segundos</p>
      <div className="space-y-0">
        {MACHEA_STEPS.map((step, i) => {
          const Icon = step.icon;
          const done = i < active;
          const isActive = i === active;
          const isLast = i === MACHEA_STEPS.length - 1;
          return (
            <div key={step.title} className="flex gap-3">
              <div className="flex flex-col items-center">
                <motion.span
                  animate={{
                    scale: isActive ? 1.12 : 1,
                    backgroundColor: done || isActive ? "#2DD4A7" : "rgba(255,255,255,0.08)",
                    color: done || isActive ? "#2D3B4E" : "rgba(255,255,255,0.5)",
                  }}
                  transition={{ duration: 0.35 }}
                  className="grid h-10 w-10 shrink-0 place-items-center rounded-full"
                >
                  {done ? <Check size={17} /> : <Icon size={17} />}
                </motion.span>
                {!isLast && (
                  <div className="my-1 h-8 w-0.5 bg-white/10">
                    <motion.div
                      className="w-0.5 bg-emerald"
                      initial={{ height: 0 }}
                      animate={{ height: i < active ? "100%" : "0%" }}
                      transition={{ duration: 0.35 }}
                    />
                  </div>
                )}
              </div>
              <div className="pb-6">
                <p className={`text-sm font-bold ${done || isActive ? "text-white" : "text-white/40"}`}>{step.title}</p>
                <p className={`text-xs ${done || isActive ? "text-white/60" : "text-white/25"}`}>{step.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ProcessComparison() {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <span className="mb-3 inline-block rounded-full bg-red-100 px-3 py-1 text-xs font-bold text-red-600">
          Proceso tradicional
        </span>
        <SketchyForm />
      </div>
      <div>
        <span className="mb-3 inline-block rounded-full bg-emerald/20 px-3 py-1 text-xs font-bold text-emerald-700">
          Con Machea
        </span>
        <MacheaFlow />
      </div>
    </div>
  );
}
