import { motion } from "framer-motion";
import { steps } from "../lib/content";
import { Reveal, StaggerGroup, StaggerItem } from "./Reveal";

export function Credibility() {
  return (
    <section id="origen" className="relative overflow-hidden border-t border-navy/5 bg-beige py-24">
      <div className="dot-field-a pointer-events-none absolute inset-0 -z-10 opacity-50" aria-hidden="true" />
      <div className="dot-field-c pointer-events-none absolute inset-0 -z-10 opacity-70" aria-hidden="true" />
      <div className="signal-streak pointer-events-none -z-10" style={{ right: "10%", top: "0%", animationDelay: "2.2s" }} aria-hidden="true" />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/3 -z-10 h-[32rem] w-[32rem] -translate-x-1/2 rounded-full bg-navy/[0.05] blur-3xl"
        animate={{ scale: [1, 1.1, 1] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto mb-16 max-w-3xl text-center">
          <h2 className="mb-6 text-4xl font-extrabold text-navy md:text-5xl">
            Un sistema end-to-end, nacido de un caso real en Colombia.
          </h2>
          <p className="text-xl text-navy/70">
            Así convertimos tu tráfico en ventas — sin que tú o tu equipo técnico muevan un dedo.
          </p>
        </Reveal>

        <div className="relative mx-auto max-w-5xl">
          <motion.div
            className="absolute left-0 top-1/2 hidden h-1 w-full origin-left -translate-y-1/2 bg-navy/10 md:block"
            initial={{ scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          />
          <StaggerGroup className="relative z-10 grid grid-cols-1 gap-8 md:grid-cols-3">
            {steps.map((step, i) => {
              const isMiddle = i === 1;
              return (
                <StaggerItem key={step.number}>
                  <motion.div
                    whileHover={{ y: -6 }}
                    transition={{ type: "spring", stiffness: 300, damping: 22 }}
                    className={`relative h-full rounded-3xl border bg-white p-8 text-center shadow-soft ${
                      isMiddle ? "border-coral/30 ring-4 ring-coral/10" : "border-navy/5"
                    }`}
                  >
                    <div
                      className={`absolute -top-6 left-1/2 grid h-12 w-12 -translate-x-1/2 place-items-center rounded-full border-4 border-beige text-xl font-bold text-white ${
                        isMiddle ? "bg-coral" : i === 2 ? "bg-emerald" : "bg-navy"
                      }`}
                    >
                      {step.number}
                    </div>
                    <motion.div
                      className="mb-6 mt-4 flex justify-center"
                      whileHover={{ scale: 1.15, rotate: isMiddle ? 0 : 8 }}
                      transition={{ type: "spring", stiffness: 300, damping: 15 }}
                    >
                      <step.icon
                        size={36}
                        className={isMiddle ? "text-coral" : i === 2 ? "text-emerald/60" : "text-navy/30"}
                      />
                    </motion.div>
                    <h4 className="mb-3 text-xl font-bold text-navy">{step.title}</h4>
                    <p className="text-sm text-navy/70">{step.description}</p>
                    <span className="mt-4 inline-block rounded-full bg-navy/5 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-navy/50">
                      {step.tag}
                    </span>
                  </motion.div>
                </StaggerItem>
              );
            })}
          </StaggerGroup>
        </div>

        <Reveal delay={0.2} className="mx-auto mt-16 max-w-2xl text-center text-sm font-medium text-navy/50">
          No pedimos que migres de CRM ni que reconstruyas tu sitio — Machea se acopla a lo que ya tienes,
          con resultados verificables desde el primer piloto.
        </Reveal>
      </div>
    </section>
  );
}
