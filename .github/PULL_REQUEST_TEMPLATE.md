<!--
  Este PR va contra `develop`, salvo que sea una entrega de develop a main.
  El flujo completo está en CONTRIBUTING.md.
-->

## Qué cambia

<!-- Una o dos frases. Qué hace el sistema ahora que antes no hacía. -->

## Por qué

<!-- El problema que tenía el código anterior. Esto es lo que el diff no
     muestra y lo que el revisor necesita para saber si la solución encaja. -->

## Historia de usuario

<!-- HU-N, o "ninguna" si es documentación, configuración o mantenimiento. -->

## Cómo se probó

<!-- Qué se corrió y qué salió. Si es del front, en qué navegador se abrió y
     hasta dónde se llegó en el recorrido. -->

- [ ] `cd Demo/backend && python pruebas/prueba_humo.py`
- [ ] `python .github/scripts/verificar_catalogo.py`
- [ ] `python .github/scripts/verificar_enlaces.py`
- [ ] Probado a mano en el navegador (si toca el formulario)

## Revisión

- [ ] La rama sale de `develop` y su nombre describe la funcionalidad
- [ ] Los mensajes de commit dicen qué cambia y por qué
- [ ] Si cambió el etiquetado del catálogo, se regeneró `proyectos_model.json`
- [ ] Si cambió la documentación, los enlaces resuelven
- [ ] No se subieron credenciales, llaves ni URLs de webhooks
