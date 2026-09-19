import { motion, useMotionTemplate, useScroll, useSpring, useTransform } from "framer-motion";
import { Heart, Play } from "lucide-react";
import { useRef } from "react";
import { macheaOffer } from "../lib/offerConfig";
import { AnimatedWords } from "./AnimatedWords";
import { CountUp } from "./CountUp";
import { LeadMockup } from "./LeadMockup";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: (delay: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] as const },
  }),
};

export function Hero() {
  const sectionRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: sectionRef, offset: ["start start", "end start"] });
  const mockupY = useTransform(scrollYProgress, [0, 1], [0, 70]);
  const skyY = useTransform(scrollYProgress, [0, 1], [0, -80]);

  const tiltX = useSpring(0, { stiffness: 200, damping: 20 });
  const tiltY = useSpring(0, { stiffness: 200, damping: 20 });
  const tiltTransform = useMotionTemplate`perspective(900px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;

  const handleMockupMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    tiltX.set(py * -10);
    tiltY.set(px * 10);
  };
  const resetTilt = () => {
    tiltX.set(0);
    tiltY.set(0);
  };

  return (
    <section id="inicio" ref={sectionRef} className="dawn-sky relative overflow-hidden pb-24 pt-36 lg:pb-32 lg:pt-44">
      <motion.div style={{ y: skyY }} className="star-field pointer-events-none absolute inset-0 -z-10 opacity-90" aria-hidden="true" />
      <div className="signal-streak pointer-events-none -z-10" style={{ left: "8%", top: "0%", animationDelay: "0s" }} aria-hidden="true" />
      <div className="signal-streak pointer-events-none -z-10" style={{ left: "55%", top: "-10%", animationDelay: "4.5s" }} aria-hidden="true" />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 top-24 -z-10 h-72 w-72 rounded-full bg-emerald/20 blur-3xl"
        animate={{ x: [0, 30, 0], y: [0, 20, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 top-52 -z-10 h-80 w-80 rounded-full bg-white/10 blur-3xl"
        animate={{ x: [0, -24, 0], y: [0, -16, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_0.95fr] lg:gap-10">
          <div className="text-center lg:text-left">
            <motion.div
              initial="hidden"
              animate="show"
              custom={0}
              variants={fadeUp}
              className="mb-6 flex flex-wrap items-center justify-center gap-2.5 lg:justify-start"
            >
              <span className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-4 py-2 backdrop-blur-sm">
                <span className="flex h-2 w-2 rounded-full bg-coral-light">
                  <span className="h-2 w-2 animate-ping rounded-full bg-coral-light" />
                </span>
                <span className="text-sm font-bold uppercase tracking-wide text-white">Presentes en GO FEST 2026</span>
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-4 py-2 text-sm font-bold text-navy">
                <Heart size={13} fill="currentColor" className="text-coral" />
                El Tinder de las inmobiliarias
              </span>
            </motion.div>

            <h1 className="mx-auto max-w-2xl text-5xl font-extrabold leading-[1.05] tracking-tight text-white md:text-6xl lg:mx-0 xl:text-7xl">
              <AnimatedWords text="Contactar un lead en 5 minutos multiplica por" startDelay={0.1} />{" "}
              <motion.span
                className="inline-block text-emerald"
                initial={{ opacity: 0, scale: 0.6, rotate: -8 }}
                animate={{ opacity: 1, scale: 1, rotate: 0 }}
                transition={{ delay: 0.75, duration: 0.6, type: "spring", stiffness: 200, damping: 14 }}
              >
                <CountUp to={21} suffix="x" duration={1.2} />
              </motion.span>{" "}
              <AnimatedWords text="el cierre." startDelay={0.95} />
            </h1>

            <motion.p
              initial="hidden"
              animate="show"
              custom={1.15}
              variants={fadeUp}
              className="mx-auto mb-10 mt-6 max-w-xl text-xl font-medium text-white/80 lg:mx-0 md:text-2xl"
            >
              ¿Cuánto de tu pauta digital se está perdiendo en la demora? Machea perfila, contacta con IA en
              segundos y entrega leads listos para comprar a tus asesores.
            </motion.p>

            <motion.div
              initial="hidden"
              animate="show"
              custom={1.3}
              variants={fadeUp}
              className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center lg:justify-start"
            >
              <motion.a
                href="#demos"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-8 py-4 text-lg font-bold text-navy shadow-[0_14px_34px_-12px_rgba(0,0,0,0.4)]"
                whileHover={{ y: -3, boxShadow: "0 20px 40px -12px rgba(0,0,0,0.5)" }}
                whileTap={{ scale: 0.96 }}
                transition={{ type: "spring", stiffness: 400, damping: 20 }}
              >
                <motion.span
                  animate={{ x: [0, 3, 0] }}
                  transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                  className="flex items-center gap-2"
                >
                  <Play size={16} fill="currentColor" className="text-coral" /> Ver por qué funciona
                </motion.span>
              </motion.a>
              <a href="#oferta" className="text-sm font-medium text-white/70 underline decoration-white/40 underline-offset-4 hover:text-white">
                {macheaOffer.ctaText} — sin compromiso.
              </a>
            </motion.div>
          </div>

          <motion.div
            style={{ y: mockupY }}
            onMouseMove={handleMockupMove}
            onMouseLeave={resetTilt}
            className="[perspective:900px]"
          >
            <motion.div style={{ transform: tiltTransform }}>
              <LeadMockup />
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
