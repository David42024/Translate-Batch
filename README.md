# Traductor por Lotes EN → ES

Aplicación de un solo módulo (Streamlit + LangChain + Gemini) para traducir
del inglés al español un artículo web (link) o un PDF, en lotes, con
revisión en vivo del avance.

## Instalación

```bash
pip install -r requirements-local.txt
```

## Obtener una API Key gratuita de Gemini

1. Ve a https://aistudio.google.com/apikey
2. Inicia sesión con tu cuenta de Google
3. Crea una API Key (el plan gratuito de Gemini tiene un límite de solicitudes por minuto, suficiente para uso personal)

## Ejecutar

```bash
streamlit run app.py
```

## Uso

1. Pega tu Gemini API Key en la barra lateral
2. Elige el modelo (`gemini-3.6-flash` es el predeterminado y el recomendado por la API)
3. Ajusta el tamaño de chunk y cuántos chunks se traducen por lote (concurrencia)
4. Elige "Pegar link" o "Subir PDF" y proporciona la fuente
5. Presiona "Traducir" — verás cada fragmento original y su traducción
   aparecer en vivo, lote por lote
6. Al terminar, descarga el resultado completo en `.txt` o `.docx`

## Notas técnicas

- **Extracción de texto**: `trafilatura` para URLs (limpia el contenido de
  menús/anuncios), `pypdf` para PDFs.
- **Chunking**: `RecursiveCharacterTextSplitter` de LangChain, respetando
  párrafos y oraciones para no cortar el contexto a la mitad.
- **Traducción**: un `AgentExecutor` de LangChain con la herramienta
  `translate_source_text`. El executor invoca la herramienta de forma
  explícita para evitar las llamadas de función incompatibles con la versión
  antigua del adaptador Gemini; la herramienta usa una chain
  (`prompt | llm | parser`) con llamadas secuenciales y una pausa configurable
  para respetar la cuota gratuita de Gemini.
- **Revisión en vivo**: Streamlit renderiza cada elemento a medida que el
  script se ejecuta, así que cada lote traducido aparece en pantalla en
  cuanto está listo, sin esperar a que termine todo el documento.

## Agente para Google Sheets y Google Docs

El archivo `agent_service.py` convierte el traductor en un servicio para la
hoja de cálculo. El archivo `google_sheets_agent.gs` funciona como disparador
de Google Sheets:

- Al escribir un enlace en `DOI / Enlace`, extrae y traduce el artículo,
  crea un Google Doc y escribe su URL en `Enlace con artículo traducido`.
- Al escribir un enlace de Google Docs en `Link del doc`, lee el contenido de
  ese documento, lo traduce, crea otro Google Doc y escribe su URL en
  `Enlace con artículo traducido`.
- Si el PDF está bloqueado para descargas automáticas, descárgalo con tu
  acceso, súbelo a Google Drive y coloca en `Link del doc` el enlace de Drive.
  Apps Script leerá el archivo de Drive y enviará su contenido al agente.
- Al escribir texto en `Fragmento tal y como está`, escribe su traducción en
  `Fragmento traducido` (también reconoce el encabezado escrito como
  `Fragemento traducido`).

### Ejecutar el servicio

Instala las dependencias y edita `.env`. Debes reemplazar los tres valores de
ejemplo: `GEMINI_API_KEY`, `AGENT_TOKEN` y, si quieres trazas en LangSmith,
`LANGCHAIN_API_KEY`.

```powershell
python -m pip install -r requirements.txt
uvicorn agent_service:app --host 0.0.0.0 --port 8000
```

`python-dotenv` carga `.env` automáticamente. No pegues esas claves en
`google_sheets_agent.gs` ni publiques el archivo `.env`.

El servicio debe estar publicado en una URL HTTPS accesible por Google Apps
Script. Para una prueba local:

```powershell
uvicorn agent_service:app --host 0.0.0.0 --port 8000
```

Para uso real, despliega este servicio en Cloud Run, Render, Railway u otro
servidor HTTPS. Define allí `GEMINI_API_KEY`, `AGENT_TOKEN` y opcionalmente
`GEMINI_MODEL`. El valor predeterminado es `gemini-3.6-flash`. Para reducir
solicitudes, `TRANSLATION_CHUNK_SIZE=100000` procesa hasta 100.000 caracteres por
llamada; `MIN_SECONDS_BETWEEN_REQUESTS=13` mantiene el límite de frecuencia.

### Conectar la hoja

1. Abre la hoja y entra en **Extensiones > Apps Script**.
2. Copia el contenido de `google_sheets_agent.gs`.
3. Sustituye `AGENT_URL` por la URL HTTPS de tu servicio y configura el mismo
   valor secreto en `AGENT_TOKEN`.
4. Ejecuta una vez `instalarAgente` y acepta los permisos de Sheets, Docs y
   solicitudes externas.
5. Regresa a la hoja y escribe un enlace o un fragmento en una fila de datos.

El disparador es instalable porque necesita llamar al servicio externo y crear
documentos. No pongas la clave de Gemini en Apps Script: solo debe existir en
el servidor Python.

### Desplegar en Vercel

El adaptador `api/index.py` publica este servicio como una función Python en
Vercel. Desde la raíz del proyecto:

```powershell
npm install -g vercel
vercel login
vercel
```

Cuando Vercel solicite las variables de entorno, configura:

```text
GEMINI_API_KEY
GEMINI_MODEL
AGENT_TOKEN
LANGCHAIN_TRACING_V2
LANGCHAIN_ENDPOINT
LANGCHAIN_API_KEY
LANGCHAIN_PROJECT
LANGSMITH_TRACING
LANGSMITH_API_KEY
LANGSMITH_PROJECT
TRANSLATION_CHUNK_SIZE
MIN_SECONDS_BETWEEN_REQUESTS
```

Después de desplegar, prueba:

```text
https://TU-PROYECTO.vercel.app/api/health
```

Y cambia en Apps Script únicamente:

```javascript
const AGENT_URL = 'https://TU-PROYECTO.vercel.app/api/process';
```

Vercel elimina la URL variable de ngrok. La función es adecuada para
fragmentos y documentos pequeños. Un PDF largo puede superar el tiempo máximo
de una función serverless, especialmente con `MIN_SECONDS_BETWEEN_REQUESTS`;
para artículos extensos se necesita una cola/worker persistente o procesarlos
en varios fragmentos.

### Desplegar en Render

Render es más adecuado para artículos largos porque ejecuta FastAPI como un
servicio persistente. Crea un **Web Service** conectado a este repositorio y
usa:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn agent_service:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

También puedes usar el archivo `render.yaml` con Render Blueprints. Configura
en el panel los valores secretos `GEMINI_API_KEY`, `AGENT_TOKEN` y las claves
de LangSmith. Cuando Render entregue una URL como
`https://traductor-batch.onrender.com`, usa en Apps Script:

```javascript
const AGENT_URL = 'https://traductor-batch.onrender.com/process';
```

### Configuración de LangChain

Las variables `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`,
`LANGCHAIN_API_KEY` y `LANGCHAIN_PROJECT` de `.env` activan el seguimiento de
las cadenas en LangSmith. El archivo `langchain_prompt.json` contiene el
prompt, la variable `texto`, el modelo y la temperatura para documentarlo o
recrear un prompt en LangSmith. En cada ejecución verás el `AgentExecutor`,
la llamada de la herramienta `translate_source_text` y las llamadas a Gemini.

Ese JSON no es un formato universal de importación de agentes de LangSmith:
LangChain no puede importar automáticamente un servicio FastAPI, sus secretos
y el disparador de Google Sheets desde un único JSON. En LangSmith puedes
crear un prompt con el contenido de `template` y la variable `texto`; el
servicio Python ya lo utiliza directamente. Además, `translate_with_agent`
está instrumentada explícitamente con `@traceable`, por lo que cada
traducción crea una traza principal aunque la detección automática de
callbacks no esté disponible.
