# Configuración de Traducción por Lotes

## Cambios realizados para optimizar consultas

### Modificaciones en `agent_Service.py`

1. **Cambio a modelo superior (Gemini 3.1 Flash Lite)**:
   - Antes: gemini-3.6-flash (5 RPM, 20 RPD)
   - Ahora: gemini-3.1-flash-lite (15 RPM, 500 RPD)
   - Variable: `GEMINI_MODEL` (default: gemini-3.1-flash-lite)
   - **3x más consultas por minuto, 25x más consultas por día**

2. **Ajuste de CHUNK_SIZE para visibilidad de lotes**:
   - Antes: 500,000 caracteres (demasiado grande, un solo chunk)
   - Ahora: 80,000 caracteres (múltiples chunks visibles)
   - Variable: `TRANSLATION_CHUNK_SIZE` (default: 80000)

3. **Ajuste de tiempo entre consultas**:
   - Antes: 13 segundos (~4.6 consultas/minuto)
   - Ahora: 4 segundos (15 consultas/minuto exactas)
   - Variable: `MIN_SECONDS_BETWEEN_REQUESTS` (default: 4)

4. **Optimización del prompt**:
   - Instrucciones más específicas para traducir grandes volúmenes de texto
   - Enfoque en traducción completa vs resumen
   - Mantenimiento de formato y estructura detallados

5. **Logging de progreso en tiempo real**:
   - Muestra número de chunks a procesar
   - Indica tamaño total del texto
   - Calcula tiempo estimado de procesamiento
   - Progreso individual de cada chunk con emojis
   - Tiempos de espera entre consultas
   - Modo verbose activado en AgentExecutor
   - `print()` statements para visibilidad universal en cualquier entorno

## Variables de entorno recomendadas

Si necesitas ajustar estos valores, crea un archivo `.env` con:

```env
GEMINI_MODEL=gemini-3.1-flash-lite
TRANSLATION_CHUNK_SIZE=500000
MIN_SECONDS_BETWEEN_REQUESTS=4
```

## Impacto esperado

- **Archivos de 20-30 páginas**: Procesamiento en múltiples chunks visibles (~8-12 chunks por archivo)
- **Velocidad**: 3x más rápido (15 vs 5 consultas/minuto)
- **Capacidad diaria**: 25x más archivos por día (500 vs 20 RPD)
- **Tiempo total**: Mucho menor tiempo de procesamiento
- **Límite de API**: Mejor aprovechamiento de límites superiores
- **Calidad**: Traducción más coherente al procesar secciones más grandes
- **Visibilidad**: Logging detallado en tiempo real del progreso

## Uso

El sistema ahora procesará automáticamente más texto por chunk y utilizará el modelo superior con límites más generosos. No requiere cambios en Google Sheets ni en el flujo de trabajo.

## Ver progreso en tiempo real

Al ejecutar el servicio, verás logs como:
```
🔄 Iniciando traducción por lotes: 5 chunks a procesar
📊 Tamaño total del texto: 125,000 caracteres
⏱️  Tiempo estimado: ~0.3 minutos
📝 Procesando chunk 1/5 (25,000 caracteres)
✅ Chunk 1/5 completado
⏳ Esperando 4s antes de la siguiente consulta...
📝 Procesando chunk 2/5 (30,000 caracteres)
✅ Chunk 2/5 completado
...
🎉 Traducción completada: 5 chunks procesados
```
