# Reporte gerencial

**Fecha de corte:** 22 de septiembre de 2026
**Para:** seguimiento del proyecto — lectura sin contexto técnico previo

---

## Resumen ejecutivo

Leadify es un formulario de siete preguntas que recomienda proyectos de
vivienda (VIS y No VIS) en Bogotá D.C., a partir de un catálogo real de 96
proyectos de cuatro constructoras. No es un buscador con filtros: un modelo
de *machine learning* (Nearest Neighbors, colaborativo + contenido) calcula
qué tan bien encaja cada proyecto con el perfil de quien responde, ajustado
por si puede pagarlo, y por qué tan cerca queda de donde de verdad quiere
vivir — no solo de la localidad, sino del barrio, medido en kilómetros
reales.

Al final del formulario, la persona puede pedir que **Manuela**, una agente
de voz con IA, la llame para calificar su interés y agendar con un asesor.
Y si vuelve a llenar el formulario más adelante, el sistema la reconoce por
su cédula y teléfono y le muestra sus resultados de inmediato, sin repetir
las siete preguntas.

**Estado actual: el sistema completo está desplegado y funcionando en
producción**, no en ambiente de prueba:

- Formulario: <https://leadify-kappa.vercel.app>
- Motor de recomendación: desplegado en Render, verificado con datos reales
- Llamada automática (Dapta/Manuela): conectada y probada de punta a punta
- Base de datos de leads: Postgres en Supabase, en uso

---

## Avance frente a lo planeado

| Sprint | Historias de usuario | Cerradas | Vencía |
|---|---|---:|---|
| Sprint 1 | HU-001 a HU-003, HU-005 | 3 / 3 (100 %) | 29-ago-2026 |
| Sprint 2 | HU-006, HU-007 | 2 / 2 (100 %) | 05-sep-2026 |
| Sprint 3 | HU-008 a HU-011 | 3 / 4 (75 %) | 12-sep-2026 |
| **Total** | **11 historias** | **10 / 11 (91 %)** | |

La única historia abierta es **HU-010 — Pruebas de integración del flujo
completo**. En la práctica el flujo ya se probó de extremo a extremo varias
veces (formulario → modelo → llamada → base de datos), pero esa evidencia no
se ha consolidado todavía en la historia ni cerrado formalmente en el
tablero.

**Nota de transparencia:** las tres fechas de sprint ya vencieron y no se
actualizaron en el tablero. El trabajo siguió avanzando después de esas
fechas — lo que falta es reflejarlo en la planeación, no en el producto.

---

## Qué se puede medir hoy

Cifras verificadas contra el sistema en producción, no estimadas:

| Métrica | Valor |
|---|---|
| Proyectos en el catálogo | 96, de 4 constructoras |
| Proyectos recomendados por consulta | 18 |
| Sectores del grafo de cercanía (barrios) | 1.164, con distancia real en km |
| Tiempo de respuesta del modelo (servicio activo) | ~1 segundo |
| Tiempo de respuesta (servicio dormido, primera consulta del día) | 30–50 segundos |
| Tablas en la base de datos de leads | 3 (`leads`, `consultas`, `intereses`) |
| Verificaciones automáticas en cada cambio al código | 4 |

---

## Riesgos identificados y qué se hizo con cada uno

Ningún proyecto de este tamaño llega sin tropiezos. Estos son los que
tuvimos, cómo se resolvieron, y cuáles siguen abiertos:

### Resueltos

**Pérdida accidental de historial de código (dos veces).** Un
`force-push` de un integrante sobrescribió sin querer 81 commits del
repositorio compartido —incluida la verificación automática, la guía de
usuario, las capturas del formulario y parte del trabajo del modelo—.
Se recuperó **sin perder el trabajo de nadie**, combinando las dos historias
en vez de forzar una encima de la otra. No volvió a pasar desde entonces.

**El motor de recomendación no estaba conectado en producción.** El
formulario llevaba un tiempo calculando resultados con un motor de reglas
local, aproximado, en vez de con el modelo real. Se encontró la causa (el
archivo de despliegue estaba en la carpeta equivocada para que Render lo
leyera) y quedó corregido y verificado con datos reales.

**Créditos agotados en el servicio de llamadas (Dapta).** Durante las
pruebas se acabó el saldo gratuito. Se creó una cuenta y un flujo nuevos, se
reconectaron las credenciales, y se confirmó que la llamada se dispara
correctamente de extremo a extremo.

### Abiertos — requieren una decisión, no más trabajo técnico

**La protección de la rama principal está desactivada.** Tras el incidente
del `force-push` se activó una protección que lo habría evitado; luego se
desactivó a pedido del equipo. Hoy `main` puede volver a sobrescribirse sin
darse cuenta. **Recomendación:** reactivarla antes de la entrega final.

**El plan gratuito del servicio de recomendación se "duerme".** Tras 15
minutos sin uso, la primera consulta del día tarda 30–50 segundos en
responder — no es un error, es la condición del plan sin costo. El sistema
ya tiene una red de seguridad (cae a un motor local aproximado si el
servicio no responde a tiempo), pero para una demostración en vivo conviene
despertarlo un par de minutos antes.

**El desglose de lenguajes de GitHub no refleja el código real.** Es un
problema cosmético y conocido de GitHub tras reescrituras de historial — el
repositorio real tiene JavaScript, Python, CSS y SQL, pero la barra de
colores del repositorio no lo muestra bien. No afecta el funcionamiento de
nada; se reportó a soporte de GitHub y queda pendiente de que lo corrijan
del otro lado.

---

## Pendiente para la siguiente entrega

- Reactivar la protección de la rama `main`
- Cerrar formalmente HU-010 con la evidencia de las pruebas ya realizadas
- Actualizar las fechas de los tres sprints en el tablero
- Organigrama visual del equipo
- Seguimiento de la respuesta de soporte de GitHub sobre el desglose de lenguajes
