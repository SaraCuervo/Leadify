# Contrato del formulario · Leadify v0.1

Qué tiene que llenar el usuario, qué JSON se le manda al modelo y qué JSON
devuelve.

---

## 1. El formulario mínimo

**Seis preguntas.** Con eso el modelo ya calcula el score y devuelve el Top 18.
Todo lo demás es opcional.

| # | Pregunta al usuario | Campo | Valor que se envía |
|---|---|---|---|
| 1 | ¿Qué tipo de vivienda buscas? | `tipo_vivienda` | `0` No VIS · `1` VIS |
| 2 | ¿Cuánto ganas al mes? | `salario` | `1` hasta 2 SMMLV · `2` de 2 a 4 · `3` de 4 a 8 · `4` más de 8 |
| 3 | ¿Cuántas personas viven contigo? | `personas_a_cargo` | `1` a `4`, donde `4` es "4 o más" |
| 4 | ¿Cuántos años tienes? | `edad` | entero entre `18` y `125` |
| 5 | ¿En qué localidad quieres vivir? | `Localidad` | `1` a `20` (tabla en §4) |
| 6 | ¿Cuántas habitaciones necesitas? | `numero_habitaciones` | `1` a `3`, donde `3` es "3 o más" |

> `Localidad` va con **L mayúscula** y **sin ceros a la izquierda**: `9`, no `09`.
> (También se acepta `localidad` en minúscula, por compatibilidad.)

Con solo esos seis campos:

```json
{
  "tipo_vivienda": 1,
  "salario": 2,
  "personas_a_cargo": 3,
  "edad": 34,
  "Localidad": 9,
  "numero_habitaciones": 3
}
```

## 2. Los campos opcionales (y qué gana el usuario con cada uno)

Ninguno es obligatorio, pero **tres de ellos cambian el resultado**:

| Campo | Valores | Qué cambia si se llena |
|---|---|---|
| `zonas_comunes` | lista de strings del vocabulario de 25 (§5) | **Mucho.** Es el 20 % del score y además parte del filtro: sin esto, todas las amenidades cuentan igual y el ranking pierde precisión. |
| `barrio` | nombre o código de sector catastral, de `GET /api/barrios?localidad=N` | **La cercanía deja de ser "misma localidad o no".** El motor mide en kilómetros, por el grafo de barrios, cuánto le queda cada proyecto y lo cuenta en el score. Sin este dato, dos proyectos de Suba a 8 km uno del otro le quedan "igual de cerca". Si contradice a `Localidad`, la respuesta es un error 400. Ver §4.1. |
| `afiliado` | `0` no · `1` sí | **Bastante, si busca VIS.** Un afiliado a caja accede al subsidio, así que el ingreso que le exige cada proyecto baja y se le abren opciones que sin subsidio no podría pagar. |
| `piso` | `0` bajo · `1` medio · `3` alto · `4` sin preferencia | **Nada, hoy.** Se guarda y viaja a la respuesta, pero ninguna constructora publica el piso por unidad, así que no filtra. Si no viene, se asume `4`. |
| `nombres`, `apellidos` | string | Solo para saludar y para el lead. |
| `correo` | string | Solo para el lead. |
| `telefono` | entero | Solo para el lead. |

**Recomendación:** pedir las 6 obligatorias + `zonas_comunes` + `afiliado` +
`barrio`. Son 9 preguntas y con eso el modelo trabaja al máximo de lo que hoy
sabe hacer. El barrio se pide como un desplegable **dependiente** de la
localidad, llenado con `GET /api/barrios?localidad=N`.
Los datos de contacto pueden ir en un segundo paso, después de mostrar los
resultados.

## 3. El JSON que se le manda al modelo

Formulario completo, las 15 llaves:

```json
{
  "nombres": "Ana",
  "apellidos": "Torres Ruiz",
  "correo": "ana.torres@correo.com",
  "telefono": 3009998877,
  "afiliado": 1,

  "tipo_vivienda": 1,
  "salario": 2,
  "personas_a_cargo": 3,
  "edad": 34,
  "Localidad": 9,
  "barrio": "Modelia",
  "numero_habitaciones": 3,
  "piso": 1,
  "zonas_comunes": ["Lobby", "Piscina", "Zona BBQ", "Zona kids", "Coworking", "Gimnasio"]
}
```

`id_proyecto` y `link_proyecto` también existen en el contrato, pero son del
lado del **proyecto**: el formulario los manda en `null` o los omite.

### Cómo se invoca

```python
from main import recomendar, respuesta_json

resultado = recomendar(payload, ruta_salida=None, verbose=False)
return respuesta_json(resultado, ruta_salida=None)
```

`recomendar()` acepta un **dict**, un string JSON o una ruta a archivo. Desde
una API se le pasa el dict directamente: no hace falta escribir nada en disco.

### Errores

Si el formulario viene mal, `recomendar()` levanta `ValueError` con **todos**
los errores juntos, no solo el primero, para que el front los marque de una vez:

```
JSON de usuario inválido:
  - salario debe estar entre 1 y 4 (recibido: 9)
  - personas_a_cargo debe estar entre 1 y 4 (recibido: None)
  - edad debe estar entre 18 y 125 (recibido: 5)
  - tipo_vivienda debe ser 0 (No VIS) o 1 (VIS) (recibido: None)
  - Localidad debe estar entre 1 y 20 (recibido: 44)
  - numero_habitaciones debe estar entre 1 y 3, donde 3 es '3 o más' (recibido: None)
```

Una zona común que no esté en el vocabulario **no rompe nada**: se ignora para
el cálculo y se reporta aparte, así que el front puede avisar sin bloquear. Lo
mismo un `barrio` que no exista en el grafo: viaja en
`usuario.busqueda.barrio_no_reconocido` y el score usa solo la localidad. Lo
que **sí** es error es un barrio que existe pero queda en otra localidad:

```
  - barrio 'Cedritos' (Cedritos) queda en Usaquén, no en Suba (Localidad=11)
```

## 4. Localidades (`Localidad`)

| id | Localidad | id | Localidad | id | Localidad | id | Localidad |
|---:|---|---:|---|---:|---|---:|---|
| 1 | Usaquén | 6 | Tunjuelito | 11 | Suba | 16 | Puente Aranda |
| 2 | Chapinero | 7 | Bosa | 12 | Barrios Unidos | 17 | La Candelaria |
| 3 | Santa Fe | 8 | Kennedy | 13 | Teusaquillo | 18 | Rafael Uribe Uribe |
| 4 | San Cristóbal | 9 | Fontibón | 14 | Los Mártires | 19 | Ciudad Bolívar |
| 5 | Usme | 10 | Engativá | 15 | Antonio Nariño | 20 | Sumapaz |

**Se pueden ofrecer las 20**, aunque hoy solo 14 tienen proyectos. Si el
usuario pide una sin oferta, el modelo expande la búsqueda a las localidades
vecinas siguiendo un grafo de colindancia y le devuelve resultados igual, con
la distancia descontada del score. Nunca devuelve una lista vacía.

### 4.1 Barrio (`barrio`, opcional)

```
GET /api/barrios?localidad=11
-> {"localidad": 11, "disponible": true,
    "barrios": [{"id": "009218", "nombre": "Almirante Colon"}, ...]}
```

Son los **sectores catastrales** oficiales de la localidad (1.164 en toda la
ciudad; Suba tiene 128). Se manda el `id` o el `nombre`, da igual. Con él el
motor calcula a cuántos kilómetros queda cada proyecto —por el grafo de
vecindad de barrios, no en línea recta— y cada apartamento de la respuesta
trae `distancia_km`. Si `disponible` viene en `false`, el backend corre sin
grafo de barrios: se omite el campo y todo sigue funcionando.

## 5. Zonas comunes (`zonas_comunes`)

Lista de strings. **Tienen que escribirse exactamente así** (con tildes):

```
Lobby                Locales comerciales   Coworking          Parque
Piscina              Zona fitness          Sala VIP           Sala de juegos
Zona de lavandería   Salón social          Zona café          Pista de trote
Zona BBQ             Spa mascotas          Gimnasio           Voleibol playa
Zona pet             Zona cool             Parqueadero        Cancha de pádel
Zona kids            Zona cine             Zona verde         Taller de bicicletas
                                                              Sauna
```

También se acepta un solo string con los nombres separados por comas
(`"Lobby, Piscina, Gimnasio"`), que es como lo manda un formulario HTML simple.

## 6. El JSON que devuelve

```json
{
  "generado_en": "2026-08-26T03:20:54+00:00",
  "motor": "colaborativo+contenido",
  "total_preseleccionados": 10,

  "usuario": {
    "nombre_completo": "Ana Torres Ruiz",
    "correo": "ana.torres@correo.com",
    "telefono": 3009998877,
    "afiliado": true,
    "perfil": { "salario": 2, "personas_a_cargo": 3, "edad": 34 },
    "busqueda": {
      "tipo_vivienda": "VIS",
      "localidad": "Fontibón",
      "numero_habitaciones": 3,
      "piso": "medio",
      "zonas_comunes": ["Lobby", "Piscina", "Zona BBQ", "Zona kids", "Coworking", "Gimnasio"]
    }
  },

  "apartamentos": [
    {
      "posicion": 1,
      "compatibilidad": 86,
      "compatibilidad_texto": "86%",

      "id_proyecto": 89,
      "nombre_proyecto": "La Unión I de la Marlene",
      "tipo_vivienda": "VIS",
      "localidad": "Bosa",
      "barrio": "Campo Verde",
      "distancia_km": 4.3,
      "distancia_km_estimada": false,
      "direccion": "Bosa, Bogotá. Cra. 95 A #90-42 Sur",
      "precio_desde_cop": 231700000.0,
      "area_construida_m2": 48.0,
      "habitaciones": 3,
      "cumple_habitaciones": true,

      "aplica_subsidio_caja": true,
      "cuota_mensual_estimada_cop": 1785852,
      "ingreso_requerido_smmlv": 2.98,

      "zonas_comunes": ["Zona de lavandería", "Zona BBQ", "Salón social", "Gimnasio", "..."],
      "zonas_en_comun": ["Zona BBQ", "Gimnasio"],

      "url_ficha": "https://cusezar.com/proyectos/con-subsidio/la-union-i/",
      "fichas_alternas": [],
      "constructoras": [],
      "datos_no_publicados": [],

      "score": 0.7577
    }
  ]
}
```

### Qué pintar y qué no

| Campo | Para la vista |
|---|---|
| `compatibilidad_texto` | **Esto es lo que se muestra** ("86%"). El primero nunca baja de 85 %; el resto cae libre según su score. **Nunca se repite dos veces en la misma respuesta**: si dos coinciden, el más barato se queda con el porcentaje alto. |
| `score` | El valor crudo del modelo (0–1). Para depurar, **no para mostrar**. |
| `zonas_en_comun` | Las amenidades que el usuario pidió Y el proyecto tiene. Ideal para resaltarlas. |
| `cumple_habitaciones` | Si es `false`, el proyecto entró relajando el requisito: conviene avisarlo. |
| `barrio`, `distancia_km` | El sector catastral del proyecto (`null` si no se pudo ubicar) y, **solo si el usuario dio `barrio`**, a cuántos km le queda ("a 4,3 km de tu barrio"). Si `distancia_km_estimada` es `true` el proyecto no tiene barrio y el número es el típico de su salto de localidad: mostrar "aprox." o no mostrarlo. Sin barrio del usuario, `distancia_km` viene en `null`. |
| `fichas_alternas` | Si trae URLs, la misma obra la publican dos constructoras con **precios distintos**. Vale la pena ofrecer las dos. |
| `datos_no_publicados` | Lista como `["habitaciones"]`. La constructora no publica ese dato: mostrar "no informado", **no un cero**. |
| `motor` | `contenido` o `colaborativo+contenido`. Diagnóstico interno. |

Las imágenes no van en la respuesta: están en `imagenes_proyectos/<id_proyecto>/`,
numeradas `01`, `02`, … La `01` es siempre la de portada.

---

## 7. Ejemplo mínimo de extremo a extremo

```python
from main import recomendar, respuesta_json

payload = {
    "tipo_vivienda": 1, "salario": 2, "personas_a_cargo": 3,
    "edad": 34, "Localidad": 9, "numero_habitaciones": 3,
}

try:
    resultado = recomendar(payload, ruta_salida=None, verbose=False)
    respuesta = respuesta_json(resultado, ruta_salida=None)
except ValueError as e:
    return {"error": str(e)}, 400

return respuesta, 200
```

## 8. Antes de levantar el servicio

El repo trae ya generados `proyectos_model.json` y `historial_simulado.json`,
así que `recomendar()` funciona recién clonado. Solo hay que regenerarlos
cuando cambie el catálogo:

```bash
python scraper_projects.py            # vuelve a scrapear las 4 constructoras
python prep.py                        # recalcula el perfil objetivo
python simulacion/generar_clientes.py --semilla 42
python generar_historial.py --semilla 42
python simulacion/evaluar.py          # comprobar que el historial sigue aportando
```

Si `evaluar.py` reporta una mejora negativa, el historial quedó desactualizado
respecto al catálogo y hay que regenerarlo.
