/**
 * Cliente para la API del motor de recomendación (api.py, FastAPI).
 * En local corre `uvicorn api:app --port 8000` en paralelo al dev server.
 * En producción, apunta a donde esté desplegado api.py vía
 * VITE_API_BASE_URL (build-time env var de Vercel) — sin ella cae a
 * localhost, que solo funciona en dev.
 */
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type FormularioMachea = {
  tipo_vivienda: 0 | 1;
  salario: 1 | 2 | 3 | 4;
  personas_a_cargo: 1 | 2 | 3 | 4;
  edad: number;
  Localidad: number;
  numero_habitaciones: 1 | 2 | 3;
  afiliado?: 0 | 1;
  zonas_comunes?: string[];
  // Opcional (v0.4): nombre o código de sector catastral, tomado de
  // `getBarrios(localidad)`. No filtra: afina la distancia con la que el
  // motor mide la cercanía dentro de la localidad. Si contradice a
  // `Localidad`, la API responde 400 con el detalle.
  barrio?: string;
};

export type Apartamento = {
  posicion: number;
  compatibilidad: number;
  compatibilidad_texto: string;
  nombre_proyecto: string;
  tipo_vivienda: string;
  localidad: string;
  // Sector catastral del proyecto y, si el usuario dio barrio, a cuántos km
  // queda por el grafo de barrios. `distancia_km_estimada` avisa cuando el
  // proyecto no tiene barrio y el número es el típico de su salto de
  // localidad, no una medida. Opcionales: una API vieja no los manda.
  barrio?: string | null;
  distancia_km?: number | null;
  distancia_km_estimada?: boolean;
  direccion: string;
  precio_desde_cop: number;
  area_construida_m2: number | null;
  habitaciones: number | null;
  cumple_habitaciones: boolean;
  aplica_subsidio_caja: boolean;
  cuota_mensual_estimada_cop: number | null;
  zonas_comunes: string[];
  zonas_en_comun: string[];
  url_ficha: string;
  // Lo que aporta `Cota_minimaBG` (backend/Model/cota_minima.py): el esfuerzo
  // de pago de ESTA persona sobre ESTE proyecto. Opcionales porque una API
  // desplegada de una versión anterior no los manda, y el front no puede
  // romperse por eso.
  //   anos_de_pago === null  -> con su tramo de ingreso la cuota no alcanza a
  //                             cubrir ni los intereses. Es dato para mostrar,
  //                             no para esconder: `alcanzable` lo dice aparte.
  //   movido_por_cota > 0    -> la cota lo subió por ser más barato, aun a
  //                             costa de sacarlo de la localidad pedida.
  anos_de_pago?: number | null;
  alcanzable?: boolean;
  cuota_que_puede_pagar_cop?: number | null;
  cuota_del_proyecto_cop?: number | null;
  movido_por_cota?: number;
};

export type RespuestaRecomendador = {
  generado_en: string;
  motor: string;
  total_preseleccionados: number;
  usuario: {
    busqueda: {
      tipo_vivienda: string;
      localidad: string;
      barrio?: string | null;
      barrio_no_reconocido?: string | null;
      numero_habitaciones: number;
    };
  };
  apartamentos: Apartamento[];
};

export class MacheaApiError extends Error {}

export async function recomendar(payload: FormularioMachea): Promise<RespuestaRecomendador> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/recomendar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new MacheaApiError(
      "No pudimos conectar con el motor de recomendación. ¿Está corriendo `uvicorn api:app --port 8000`?"
    );
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Error desconocido del motor." }));
    throw new MacheaApiError(body.detail ?? "El formulario tiene datos inválidos.");
  }

  return res.json();
}

export type Localidad = { id: number; nombre: string };

export async function getCatalogos(): Promise<{ localidades: Localidad[]; zonas_comunes: string[] }> {
  const res = await fetch(`${API_BASE}/api/catalogos`);
  if (!res.ok) throw new MacheaApiError("No pudimos cargar el catálogo de localidades.");
  return res.json();
}

export type Barrio = { id: string; nombre: string };

/** Los barrios (sectores catastrales) de una localidad, para un desplegable
 *  dependiente. `disponible: false` = el backend corre sin grafo de barrios;
 *  el formulario puede omitir el campo y todo sigue funcionando. */
export async function getBarrios(
  localidad: number
): Promise<{ localidad: number; disponible: boolean; barrios: Barrio[] }> {
  const res = await fetch(`${API_BASE}/api/barrios?localidad=${localidad}`);
  if (!res.ok) throw new MacheaApiError("No pudimos cargar los barrios de esa localidad.");
  return res.json();
}

export type SolicitudLlamada = {
  nombre: string;
  telefono: string;
  afiliado: boolean;
  rango_ingreso: string;
  edad: number;
  personas_a_cargo: number;
  entorno_deseado: string;
  apartamento: Apartamento;
};

export type RespuestaLlamada = {
  status: "enviado" | "mock_enqueued";
  detalle?: string;
};

export async function llamar(payload: SolicitudLlamada): Promise<RespuestaLlamada> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/llamar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new MacheaApiError("No pudimos conectar con el motor para disparar la llamada.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Error desconocido al llamar." }));
    throw new MacheaApiError(body.detail ?? "No se pudo iniciar la llamada.");
  }
  return res.json();
}
