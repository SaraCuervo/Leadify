import { motion } from "framer-motion";
import {
  Bot,
  CalendarCheck,
  ChevronDown,
  ClipboardList,
  ListFilter,
  MessageCircle,
  Sparkles,
  TrendingUp,
  UserRoundCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { CountUp } from "./CountUp";
import { Reveal } from "./Reveal";

const W = 1200;
const H = 460;

type Node = {
  id: string;
  x: number;
  y: number;
  icon: LucideIcon;
  title: string;
  subtitle: string;
  accent: "coral" | "slate" | "emerald" | "whatsapp";
};

const nodes: Node[] = [
  { id: "form", x: 90, y: 230, icon: ClipboardList, title: "Formulario inteligente", subtitle: "Toma de datos", accent: "slate" },
  { id: "match", x: 305, y: 230, icon: Sparkles, title: "Clustering · Match", subtitle: "Como Tinder", accent: "coral" },
  { id: "call", x: 520, y: 230, icon: Bot, title: "Llamada IA — Manuela", subtitle: "Instantánea", accent: "coral" },
  { id: "answers", x: 735, y: 110, icon: CalendarCheck, title: "Contesta", subtitle: "Sigue en línea", accent: "emerald" },
  { id: "whatsapp", x: 735, y: 350, icon: MessageCircle, title: "No contesta", subtitle: "Sigue por WhatsApp", accent: "whatsapp" },
  { id: "classify", x: 950, y: 230, icon: ListFilter, title: "Clasifica", subtitle: "Motor de calificación", accent: "slate" },
  { id: "qualified", x: 1150, y: 230, icon: UserRoundCheck, title: "Lead calificado y agendado", subtitle: "Listo para el asesor", accent: "emerald" },
];

const edges: { id: string; d: string; color: string; delay: number }[] = [
  { id: "e1", d: `M90,230 L305,230`, color: "#FF6259", delay: 0 },
  { id: "e2", d: `M305,230 L520,230`, color: "#FF6259", delay: 0.5 },
  { id: "e3", d: `M520,230 C610,230 645,110 735,110`, color: "#2DD4A7", delay: 1 },
  { id: "e4", d: `M520,230 C610,230 645,350 735,350`, color: "#25D366", delay: 1 },
  { id: "e5", d: `M735,110 C840,110 850,230 950,230`, color: "#2DD4A7", delay: 1.6 },
  { id: "e6", d: `M735,350 C840,350 850,230 950,230`, color: "#25D366", delay: 1.6 },
  { id: "e7", d: `M950,230 L1150,230`, color: "#2DD4A7", delay: 2.2 },
];

const accentClasses: Record<Node["accent"], string> = {
  coral: "border-coral/40 bg-coral/10 text-white",
  slate: "border-white/15 bg-white/[0.06] text-white",
  emerald: "border-emerald/40 bg-emerald/10 text-white",
  whatsapp: "border-[#25D366]/40 bg-[#25D366]/10 text-white",
};

const iconBg: Record<Node["accent"], string> = {
  coral: "bg-coral text-white",
  slate: "bg-white/15 text-white",
  emerald: "bg-emerald text-navy",
  whatsapp: "bg-[#25D366] text-white",
};

export function FlowDiagram() {
  return (
    <section className="relative overflow-hidden bg-navy py-24">
      <div className="star-field pointer-events-none absolute inset-0 -z-10 opacity-50" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_rgba(255,255,255,0.06)_0%,_transparent_60%)]" aria-hidden="true" />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 top-16 -z-10 h-96 w-96 rounded-full bg-coral/20 blur-3xl"
        animate={{ x: [0, 26, 0], y: [0, -18, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 bottom-0 -z-10 h-[28rem] w-[28rem] rounded-full bg-emerald/15 blur-3xl"
        animate={{ x: [0, -22, 0], y: [0, 16, 0] }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-4 text-sm font-bold uppercase tracking-[0.15em] text-coral">De principio a fin</p>
          <h2 className="text-4xl font-extrabold text-white md:text-5xl">Así fluye cada lead.</h2>
          <p className="mt-4 text-lg text-white/70">
            Un solo flujo, sin intervención manual: del formulario al asesor, con la ruta correcta según cada
            respuesta — y una tasa de cierre muy por encima del proceso tradicional.
          </p>
        </Reveal>

        <Reveal delay={0.1} className="overflow-x-auto">
          <div className="relative mx-auto min-w-[1000px] max-w-6xl" style={{ aspectRatio: `${W} / ${H}` }}>
            <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full" fill="none">
              {edges.map((e) => (
                <g key={e.id}>
                  <path d={e.d} stroke={e.color} strokeOpacity={0.3} strokeWidth={2.5} />
                  <circle r={5} fill={e.color}>
                    <animateMotion dur="2.6s" begin={`${e.delay}s`} repeatCount="indefinite" path={e.d} />
                  </circle>
                </g>
              ))}
            </svg>

            {nodes.map((n, i) => {
              const Icon = n.icon;
              return (
                <motion.div
                  key={n.id}
                  initial={{ opacity: 0, scale: 0.7 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true, margin: "-80px" }}
                  transition={{ delay: i * 0.12, type: "spring", stiffness: 260, damping: 18 }}
                  className="absolute -translate-x-1/2 -translate-y-1/2"
                  style={{ left: `${(n.x / W) * 100}%`, top: `${(n.y / H) * 100}%` }}
                >
                  <div
                    className={`flex w-[168px] flex-col items-center gap-2 rounded-2xl border-2 px-3 py-4 text-center backdrop-blur-sm ${accentClasses[n.accent]}`}
                  >
                    <span className={`grid h-10 w-10 place-items-center rounded-xl ${iconBg[n.accent]}`}>
                      <Icon size={19} />
                    </span>
                    <div>
                      <p className="text-sm font-extrabold leading-tight text-white">{n.title}</p>
                      {n.subtitle && <p className="mt-0.5 text-[11px] font-medium text-white/50">{n.subtitle}</p>}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </Reveal>

        <Reveal delay={0.15} className="mx-auto mt-2 max-w-2xl text-center text-sm text-white/40">
          Desliza para ver el flujo completo en pantallas pequeñas.
        </Reveal>

        <Reveal delay={0.3} className="mx-auto mt-8 flex max-w-md flex-col items-center">
          <motion.div
            animate={{ y: [0, 6, 0] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
            className="mb-2 text-emerald"
            aria-hidden="true"
          >
            <ChevronDown size={22} />
          </motion.div>
          <motion.div
            whileHover={{ y: -4 }}
            transition={{ type: "spring", stiffness: 300, damping: 22 }}
            className="relative w-full overflow-hidden rounded-3xl border border-emerald/30 bg-gradient-to-br from-white/[0.07] to-white/[0.02] p-8 text-center shadow-[0_20px_60px_-20px_rgba(45,212,167,0.35)]"
          >
            <motion.div
              aria-hidden="true"
              className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-emerald/25 blur-3xl"
              animate={{ scale: [1, 1.15, 1] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            />
            <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-emerald text-navy shadow-coral">
              <TrendingUp size={26} />
            </span>
            <p className="mt-5 flex items-center justify-center gap-1 text-5xl font-extrabold text-white">
              <CountUp to={21} suffix="x" />
            </p>
            <p className="mt-2 text-sm font-bold uppercase tracking-[0.15em] text-emerald">Mejor tasa de cierre</p>
            <p className="mt-3 text-sm text-white/60">
              Contra un lead que espera 24 horas en un formulario genérico — porque Manuela llama, califica y agenda
              mientras el interés sigue caliente.
            </p>
          </motion.div>
        </Reveal>
      </div>
    </section>
  );
}
