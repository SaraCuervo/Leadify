import { AnimatePresence, motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { macheaOffer } from "../lib/offerConfig";
import { Logo } from "./Logo";

const links = [
  { href: "#como-funciona", label: "Cómo funciona" },
  { href: "#demos", label: "Beneficios" },
  { href: "#origen", label: "Por qué Machea" },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeHref, setActiveHref] = useState("#como-funciona");

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const sections = links
      .map((link) => document.querySelector(link.href))
      .filter((el): el is Element => el !== null);

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length > 0) {
          setActiveHref(`#${visible[0].target.id}`);
        }
      },
      { rootMargin: "-40% 0px -50% 0px" }
    );

    sections.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  const light = !scrolled; // sitting over the dark hero sky

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 border-b transition-colors duration-300 ${
        scrolled ? "border-navy/10 bg-white/90 shadow-sm backdrop-blur-md" : "border-white/10 bg-transparent"
      }`}
    >
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <a href="#inicio" className="cursor-pointer" aria-label="Machea, inicio">
          <Logo size={36} variant={light ? "mono" : "color"} />
        </a>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Navegación principal">
          {links.map((link) => {
            const isActive = activeHref === link.href;
            return (
              <a
                key={link.href}
                href={link.href}
                className={`relative pb-1 text-sm font-semibold transition-colors ${
                  isActive
                    ? light
                      ? "text-white"
                      : "text-coral"
                    : light
                      ? "text-white/70 hover:text-white"
                      : "text-navy/70 hover:text-coral"
                }`}
              >
                {link.label}
                {isActive && (
                  <motion.span
                    layoutId="nav-underline"
                    className={`absolute inset-x-0 -bottom-0.5 h-0.5 rounded-full ${light ? "bg-white" : "bg-coral"}`}
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
              </a>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <motion.a
            href="#oferta"
            className="hidden rounded-full bg-coral px-6 py-2.5 text-sm font-bold text-white shadow-coral sm:inline-block"
            whileHover={{ y: -2, boxShadow: "0 18px 34px -12px rgba(255,98,89,0.55)" }}
            whileTap={{ scale: 0.96 }}
            transition={{ type: "spring", stiffness: 400, damping: 20 }}
          >
            {macheaOffer.ctaText}
          </motion.a>
          <button
            type="button"
            className={`grid h-10 w-10 place-items-center rounded-full border md:hidden ${
              light ? "border-white/25 text-white" : "border-navy/10 text-navy"
            }`}
            aria-expanded={menuOpen}
            aria-label="Abrir menú"
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className={`overflow-hidden border-t md:hidden ${light ? "border-white/10 bg-navy" : "border-navy/10 bg-beige"}`}
          >
            <nav className="flex flex-col gap-1 px-4 py-4">
              {links.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className={`rounded-lg px-3 py-2.5 text-base font-semibold ${
                    light ? "text-white/90 hover:bg-white/10" : "text-navy/80 hover:bg-navy/5"
                  }`}
                >
                  {link.label}
                </a>
              ))}
              <a
                href="#oferta"
                onClick={() => setMenuOpen(false)}
                className="mt-2 rounded-full bg-coral px-6 py-3 text-center text-sm font-bold text-white shadow-coral"
              >
                {macheaOffer.ctaText}
              </a>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
