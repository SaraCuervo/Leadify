// Espejo de catalogos.py — única fuente de verdad de los ids en el repo del modelo.
// Duplicado aquí a propósito: el form necesita las etiquetas sin depender de red.

export const LOCALIDADES: { id: number; nombre: string }[] = [
  "Usaquén", "Chapinero", "Santa Fe", "San Cristóbal", "Usme", "Tunjuelito", "Bosa",
  "Kennedy", "Fontibón", "Engativá", "Suba", "Barrios Unidos", "Teusaquillo",
  "Los Mártires", "Antonio Nariño", "Puente Aranda", "La Candelaria",
  "Rafael Uribe Uribe", "Ciudad Bolívar", "Sumapaz",
].map((nombre, i) => ({ id: i + 1, nombre }));

// Subconjunto curado de las 25 zonas comunes del modelo — las más pedidas, para
// que el form quepa en una pantalla de stand sin volverse una lista de 25 checks.
export const ZONAS_COMUNES_POPULARES = [
  "Lobby", "Piscina", "Gimnasio", "Zona BBQ", "Zona kids", "Parque",
  "Salón social", "Coworking", "Parqueadero", "Zona verde",
];

export const SALARIO_OPCIONES = [
  { value: 1, label: "Hasta 2 SMMLV" },
  { value: 2, label: "2 a 4 SMMLV" },
  { value: 3, label: "4 a 8 SMMLV" },
  { value: 4, label: "Más de 8 SMMLV" },
] as const;
