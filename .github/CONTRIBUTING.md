# Cómo se trabaja en este repositorio

Cuatro personas tocando el mismo proyecto necesitan un acuerdo escrito, no uno
recordado. Esto es ese acuerdo.

## Las ramas

```
main ─────●──────────────●──────────────●────▶   estable: lo que se entrega
           \            /              /
develop ────●──────●───●──────●───────●─────▶    integración: lo que ya encaja
             \    /            \     /
feature/x     ●──●              ●───●            una rama por funcionalidad
```

| Rama | Qué es | Quién escribe en ella |
|---|---|---|
| `main` | Lo estable, lo que se entrega y lo que se despliega. | Nadie directamente: recibe merges desde `develop`. |
| `develop` | La rama de integración. Aquí se juntan las funcionalidades y aquí se ve si encajan entre sí. | Recibe merges desde las `feature/*`. |
| `feature/<funcionalidad>` | Una rama por funcionalidad, que sale de `develop` y vuelve a `develop`. | Quien esté desarrollando esa funcionalidad. |

**El nombre de la rama describe la funcionalidad, no la tarea ni la persona.**
`feature/verificacion-automatica`, no `feature/diego` ni `feature/arreglos`. En
minúsculas y con guiones.

### El ciclo completo

```bash
# 1. partir de develop al día
git checkout develop
git pull

# 2. abrir la rama de la funcionalidad
git checkout -b feature/calificacion-de-leads

# 3. trabajar y commitear (varios commits pequeños, no uno gigante)
git add <lo que cambió>
git commit

# 4. subirla
git push -u origin feature/calificacion-de-leads

# 5. abrir el Pull Request contra develop en GitHub
```

Cuando el PR se aprueba y la verificación automática pasa, se hace **merge sin
fast-forward** (`--no-ff`), para que la rama quede visible en la historia y se
pueda leer qué se hizo junto:

```bash
git checkout develop
git merge --no-ff feature/calificacion-de-leads
git push
```

`main` recibe lo que ya esté integrado y probado en `develop`, no funcionalidades
sueltas.

## Los mensajes de commit

Del acuerdo del Daily 5: **mensajes descriptivos**. En concreto:

- **La primera línea dice qué cambia**, en presente y sin punto final. No
  "cambios", no "update", no "arreglos varios".
- **El cuerpo dice por qué**, que es lo que no se puede deducir leyendo el
  diff. Un diff siempre muestra *qué* cambió; nunca muestra qué problema tenía
  el código anterior.
- Si el cambio toca una historia de usuario, se nombra: `HU-3`.

```
Verificacion automatica: prueba de humo, catalogo y enlaces

Hasta ahora todo se revisaba a mano, que es lo mismo que decir que se
revisaba cuando alguien se acordaba. Entra un workflow que corre en cada
push...
```

## Antes de subir

La verificación automática corre sola en cada push y en cada PR
(`.github/workflows/verificacion.yml`), pero enterarse antes ahorra una vuelta.
Las mismas tres comprobaciones, en local, **desde la raíz del repositorio**:

```bash
# 1. el motor responde y cumple el contrato (13 comprobaciones)
cd Demo/backend && python pruebas/prueba_humo.py

# 2. el catálogo versionado corresponde al código que lo genera
cd ../.. && python .github/scripts/verificar_catalogo.py

# 3. ningún enlace de la documentación está roto
python .github/scripts/verificar_enlaces.py
```

## Dónde va cada cosa

| Si estás tocando… | Va en… |
|---|---|
| El motor, la API, el scraper, el formulario | `Demo/` |
| Documentación del proyecto | `Docs/` |
| Los datos del motor | `Demo/backend/Model/data_projects/` (ver `Database/README.md`) |
| Scripts de análisis | `Demo/backend/` (ver `Script/README.md`) |
| Actas de los dailies | `Docs/Dailys/` |

Dos reglas que no son de estilo y conviene no romper:

- **`Model/catalogos.py` es la única fuente de los ids** de localidades y zonas
  comunes, y **`Model/rutas.py` la única fuente de las rutas.** Si un módulo
  define su propia copia, el desfase no falla: solo recomienda peor, en
  silencio.
- **La capa HTTP no toma decisiones de recomendación.** Cualquier regla nueva
  va en `Model/`, o queda invisible para la consola y para la evaluación.

El resto de invariantes está en la §9 de
[`Docs/GUIA_TECNICA.md`](../Docs/GUIA_TECNICA.md).
