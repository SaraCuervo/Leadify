import { Logo } from "./Logo";

export function Footer() {
  return (
    <footer className="border-t border-white/5 bg-navy pb-8 pt-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-col items-center justify-between gap-6 md:flex-row">
          <Logo size={28} variant="mono" />
          <p className="text-sm font-medium text-white/50">
            Hecho por el equipo de Machea
          </p>
        </div>
        <div className="text-center text-xs text-white/30">
          © 2026 Machea Proptech. Todos los derechos reservados.
        </div>
      </div>
    </footer>
  );
}
