# Changelog

Todos los cambios notables de este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto se adhiere a un [Versionado Semántico](https://semver.org/).

## [1.2.0] - 2026-02-22

### ✨ Añadido (Added)
- **Tema Visual "Dark Corporate":** Nueva hoja de estilos QSS global integrada en `ui/theme.py`. Reemplaza los grises nativos por una paleta neo-brutalista oscura, optimizando márgenes, inputs y bordes de la UI del asistente gráfico.
- **Micro-Animaciones UI:** Inyección de `QPropertyAnimation` con `QGraphicsOpacityEffect` en `WizardDialog`. Permite transiciones fluidas de opacidad (*fade-in*) al cambiar y validar pasos de configuración en el asistente.
- **Degradación Elegante (Graceful Degradation):** Introducción de un *timeout ping* (1.5s) ultra-rápido usando `urllib.request` antes de inyectar las capas de Mapas Base XYZ (Google, CartoDB, OSM). Si el servidor está bloqueado/caído, evita el cuelgue infinito de QGIS y renderiza automáticamente el mapa usando un fondo fallback (`map_bg`).
- **Circuit Breaker:** Mecanismo integrado en `wizard_controller.py` que detiene instáneamente la iteración asíncrona (*generation batch*) si ocurren 3 fallos *consecutivos* de renderizado, reportando la anomalía sin crashear el loop principal.

### ♻️ Cambiado (Changed - Refactorización)
- **Arquitectura MVC (Separation of Concerns):** El componente masivo `WizardDialog` (UI) fue despojado de la lógica de iteración, validación global y construcción del motor. Toda esa capa de orquestación fue movida al nuevo controlador `WizardController`.
- **Mejora Editorial Infográfica:** Refinamiento estético completo del `_DEFAULT_TEMPLATE` en `report_composer.py`. 
  - Nuevas paletas predeterminadas de alto contraste (*Slate & Cyan*).
  - Tipografía general modernizada a *Segoe UI*.
  - Aumento en las métricas y jerarquías (`font_weight`, sizes) del título y subtítulo para darle un look corporativo tipo revista/infografía y abandonar la estética de "mapa por defecto".
- **Validaciones Estrictas (Type Coverage):** Fortalecido `ReportConfig` (`models.py`) con la validación de formato RGB/HEX nativa de Python mediante Expresiones Regulares (`re.match`) directamente durante el hook de `__post_init__`.

### 🪲 Solucionado (Fixed)
- Solucionada vulnerabilidad de bloqueo de UI Thread durante peticiones a servidores XYZ muertos o lentos en la previsualización y exportación masiva.
