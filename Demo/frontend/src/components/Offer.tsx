import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Lock, ShieldCheck } from "lucide-react";
import { useState } from "react";
import logoGlow from "../assets/img/logo.png";
import { macheaOffer } from "../lib/offerConfig";
import { Reveal, StaggerGroup, StaggerItem } from "./Reveal";

export function Offer() {
  const [nombre, setNombre] = useState("");
  const [correo, setCorreo] = useState("");
  const [sitioWeb, setSitioWeb] = useState("");
  const [enviado, setEnviado] = useState(false);

  const listo = nombre.trim() !== "" && correo.trim() !== "";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!listo) return;
    const asunto = encodeURIComponent(`Solicitud de auditoría gratis — ${nombre}`);
    const cuerpo = encodeURIComponent(
      `Nombre: ${nombre}\nCorreo: ${correo}\nSitio de la inmobiliaria: ${sitioWeb || "(no indicado)"}\n`
    );
    setEnviado(true);
    window.setTimeout(() => {
      window.location.href = `mailto:${macheaOffer.contactEmail}?subject=${asunto}&body=${cuerpo}`;
    }, 400);
  };

  return (
    <section id="oferta" className="relative overflow-hidden bg-navy py-24">
      <motion.img
        src={logoGlow}
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute -right-40 -top-40 w-[720px] max-w-none opacity-60 mix-blend-screen"
        animate={{ x: [0, -20, 0], y: [0, 16, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-0 left-0 h-96 w-96 rounded-full bg-emerald mix-blend-screen opacity-10 blur-[150px]"
        animate={{ scale: [1, 1.15, 1] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="relative z-10 mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
        <Reveal className="rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur-lg md:p-12">
          <p className="mb-4 text-sm font-bold uppercase tracking-[0.15em] text-coral">{macheaOffer.eyebrow}</p>
          <h2 className="mb-10 text-4xl font-extrabold text-white md:text-5xl">{macheaOffer.headline}</h2>

          <StaggerGroup className="mx-auto max-w-2xl space-y-3 text-left">
            {macheaOffer.stack.map((item, i) => (
              <StaggerItem key={item.title}>
                <div className="flex gap-4 rounded-2xl border border-white/10 bg-white/5 p-4">
                  <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-coral/20 text-xs font-extrabold text-coral">
                    {i + 1}
                  </span>
                  <div>
                    <h4 className="text-base font-bold text-white">{item.title}</h4>
                    <p className="mt-1 text-sm text-white/70">{item.text}</p>
                  </div>
                </div>
              </StaggerItem>
            ))}
          </StaggerGroup>

          <Reveal delay={0.25} className="mx-auto mt-6 max-w-2xl">
            <motion.div
              animate={{ boxShadow: ["0 0 0px rgba(45,212,167,0)", "0 0 26px rgba(45,212,167,0.35)", "0 0 0px rgba(45,212,167,0)"] }}
              transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
              className="flex items-start gap-4 rounded-2xl border border-emerald/30 bg-emerald/10 p-5 text-left"
            >
              <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-emerald text-navy">
                <ShieldCheck size={18} />
              </span>
              <div>
                <h4 className="text-base font-extrabold text-white">{macheaOffer.guarantee.title}</h4>
                <p className="mt-1 text-sm text-white/80">{macheaOffer.guarantee.text}</p>
              </div>
            </motion.div>
          </Reveal>

          <Reveal delay={0.3} className="mx-auto mt-10 max-w-2xl">
            <AnimatePresence mode="wait">
              {enviado ? (
                <motion.div
                  key="enviado"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center gap-3 rounded-2xl border border-emerald/30 bg-emerald/10 p-8 text-center"
                >
                  <CheckCircle2 size={32} className="text-emerald" />
                  <p className="font-bold text-white">¡Listo! Abrimos tu correo con la solicitud lista para enviar.</p>
                </motion.div>
              ) : (
                <motion.form
                  key="form"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  onSubmit={handleSubmit}
                  className="space-y-3 text-left"
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      type="text"
                      required
                      value={nombre}
                      onChange={(e) => setNombre(e.target.value)}
                      placeholder="Tu nombre"
                      className="w-full rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-sm font-medium text-white placeholder:text-white/40 focus:border-coral focus:outline-none"
                    />
                    <input
                      type="email"
                      required
                      value={correo}
                      onChange={(e) => setCorreo(e.target.value)}
                      placeholder="Tu correo"
                      className="w-full rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-sm font-medium text-white placeholder:text-white/40 focus:border-coral focus:outline-none"
                    />
                  </div>
                  <input
                    type="url"
                    value={sitioWeb}
                    onChange={(e) => setSitioWeb(e.target.value)}
                    placeholder="Link del sitio web de tu inmobiliaria (opcional, pero lo hace mejor)"
                    className="w-full rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-sm font-medium text-white placeholder:text-white/40 focus:border-coral focus:outline-none"
                  />

                  <motion.button
                    type="submit"
                    disabled={!listo}
                    whileHover={listo ? { scale: 1.03, boxShadow: "0 0 40px rgba(45,212,167,0.5)" } : {}}
                    whileTap={listo ? { scale: 0.97 } : {}}
                    transition={{ type: "spring", stiffness: 350, damping: 20 }}
                    className="w-full rounded-full bg-emerald px-10 py-5 text-lg font-extrabold text-navy disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
                  >
                    {macheaOffer.ctaText}
                  </motion.button>
                </motion.form>
              )}
            </AnimatePresence>
            <p className="mt-4 flex items-center justify-center gap-1.5 text-sm font-medium text-white/40">
              <Lock size={12} /> {macheaOffer.ctaNote}
            </p>
          </Reveal>
        </Reveal>
      </div>
    </section>
  );
}
