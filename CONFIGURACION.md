# Configuración de Traducción por Lotes

## Cambios realizados para optimizar consultas

### Modificaciones en `agent_Service.py`

1. **Aumento de CHUNK_SIZE**: 
   - Antes: 100,000 caracteres
   - Ahora: 500,000 caracteres (5x más texto por consulta)
   - Variable: `TRANSLATION_CHUNK_SIZE` (default: 500000)

2. **Ajuste de tiempo entre consultas**:
   - Antes: 13 segundos (~4.6 consultas/minuto)
   - Ahora: 12 segundos (5 consultas/minuto exactas)
   - Variable: `MIN_SECONDS_BETWEEN_REQUESTS` (default: 12)

3. **Optimización del prompt**:
   - Instrucciones más específicas para traducir grandes volúmenes de texto
   - Enfoque en traducción completa vs resumen
   - Mantenimiento de formato y estructura detallados

4. **Logging de progreso en tiempo real**:
   - Muestra número de chunks a procesar
   - Indica tamaño total del texto
   - Calcula tiempo estimado de procesamiento
   - Progreso individual de cada chunk con emojis
   - Tiempos de espera entre consultas
   - Modo verbose activado en AgentExecutor

## Variables de entorno recomendadas

Si necesitas ajustar estos valores, crea un archivo `.env` con:

```env
TRANSLATION_CHUNK_SIZE=500000
MIN_SECONDS_BETWEEN_REQUESTS=12
```

## Impacto esperado

- **Archivos de 20-30 páginas**: Reducción de ~20 consultas a ~4-6 consultas por archivo
- **Tiempo total**: Mayor tiempo por consulta pero menos consultas totales
- **Límite de API**: Mejor aprovechamiento del límite de 5 consultas/minuto
- **Calidad**: Traducción más coherente al procesar secciones más grandes
- **Visibilidad**: Logging detallado en tiempo real del progreso

## Uso

El sistema ahora procesará automáticamente más texto por chunk y respetará el límite de 5 consultas por minuto. No requiere cambios en Google Sheets ni en el flujo de trabajo.

## Ver progreso en tiempo real

Al ejecutar el servicio, verás logs como:
```
🔄 Iniciando traducción por lotes: 5 chunks a procesar
📊 Tamaño total del texto: 125,000 caracteres
⏱️  Tiempo estimado: ~1.0 minutos
📝 Procesando chunk 1/5 (25,000 caracteres)
✅ Chunk 1/5 completado
⏳ Esperando 12s antes de la siguiente consulta...
📝 Procesando chunk 2/5 (30,000 caracteres)
✅ Chunk 2/5 completado
...
🎉 Traducción completada: 5 chunks procesados
```
