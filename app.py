"""
Traductor por Lotes EN → ES
Módulo único: Streamlit + LangChain + Gemini
Acepta un link o un PDF, extrae el texto, lo divide en lotes (chunks),
traduce cada lote con Gemini vía LangChain y muestra la revisión en vivo
mientras avanza el proceso.
"""

import io
import requests
import streamlit as st
import trafilatura
from pypdf import PdfReader
from docx import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI


# ----------------------------------------------------------------------
# Extracción de texto
# ----------------------------------------------------------------------

def extract_text_from_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    partes = []
    for page in reader.pages:
        texto = page.extract_text() or ""
        if texto.strip():
            partes.append(texto)
    return "\n\n".join(partes)


def extract_text_from_url(url: str) -> str:
    descargado = trafilatura.fetch_url(url)
    if not descargado:
        # Fallback manual si trafilatura no logra descargar directo
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        descargado = resp.text

    texto = trafilatura.extract(descargado, include_comments=False, include_tables=True)
    if not texto:
        raise ValueError("No se pudo extraer contenido legible de esa URL.")
    return texto


# ----------------------------------------------------------------------
# Chunking (división en lotes)
# ----------------------------------------------------------------------

def split_into_chunks(texto: str, chunk_size: int = 1200, overlap: int = 100) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(texto)


def group_chunks(chunks: list[str], batch_size: int) -> list[list[str]]:
    return [chunks[i:i + batch_size] for i in range(0, len(chunks), batch_size)]


# ----------------------------------------------------------------------
# Cadena de traducción (LangChain + Gemini)
# ----------------------------------------------------------------------

def build_translation_chain(api_key: str, model_name: str):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.2,
    )
    prompt = ChatPromptTemplate.from_template(
        "Traduce el siguiente texto del inglés al español. "
        "Conserva el formato, los saltos de párrafo y el tono original. "
        "Responde SOLO con la traducción, sin comentarios adicionales.\n\n"
        "Texto:\n{texto}"
    )
    return prompt | llm | StrOutputParser()


# ----------------------------------------------------------------------
# Exportación
# ----------------------------------------------------------------------

def build_docx_bytes(texto: str) -> bytes:
    doc = Document()
    doc.add_heading("Traducción", level=1)
    for parrafo in texto.split("\n\n"):
        if parrafo.strip():
            doc.add_paragraph(parrafo.strip())
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ----------------------------------------------------------------------
# UI - Streamlit
# ----------------------------------------------------------------------

st.set_page_config(page_title="Traductor por Lotes EN→ES", page_icon="🌐", layout="wide")
st.title("🌐 Traductor por Lotes (Inglés → Español)")
st.caption("Pega un link o sube un PDF. La traducción se procesa en lotes y se revisa en vivo.")

with st.sidebar:
    st.header("Configuración")
    api_key = st.text_input("Gemini API Key", type="password", help="Consíguela gratis en aistudio.google.com/apikey")
    model_name = st.selectbox(
        "Modelo",
        ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
    )
    chunk_size = st.slider("Tamaño de chunk (caracteres)", 500, 3000, 1200, step=100)
    batch_size = st.slider("Chunks por lote (concurrentes)", 1, 10, 4)

modo = st.radio("Fuente del contenido", ["Pegar link", "Subir PDF"], horizontal=True)

texto_fuente = None
url_input = None
pdf_input = None

if modo == "Pegar link":
    url_input = st.text_input("URL del artículo o documento")
else:
    pdf_input = st.file_uploader("Sube un archivo PDF", type=["pdf"])

iniciar = st.button("Traducir", type="primary")

if iniciar:
    if not api_key:
        st.error("Ingresa tu Gemini API Key en la barra lateral.")
        st.stop()
    if modo == "Pegar link" and not url_input:
        st.error("Ingresa una URL.")
        st.stop()
    if modo == "Subir PDF" and not pdf_input:
        st.error("Sube un archivo PDF.")
        st.stop()

    # --- Extracción ---
    with st.spinner("Extrayendo texto..."):
        try:
            if modo == "Pegar link":
                texto_fuente = extract_text_from_url(url_input)
            else:
                texto_fuente = extract_text_from_pdf(pdf_input)
        except Exception as e:
            st.error(f"No se pudo extraer el texto: {e}")
            st.stop()

    if not texto_fuente or not texto_fuente.strip():
        st.error("No se encontró texto para traducir.")
        st.stop()

    st.success(f"Texto extraído: {len(texto_fuente):,} caracteres.")

    # --- Chunking ---
    chunks = split_into_chunks(texto_fuente, chunk_size=chunk_size)
    lotes = group_chunks(chunks, batch_size=batch_size)
    st.info(f"{len(chunks)} fragmentos divididos en {len(lotes)} lotes.")

    # --- Cadena de traducción ---
    try:
        chain = build_translation_chain(api_key, model_name)
    except Exception as e:
        st.error(f"No se pudo inicializar el modelo: {e}")
        st.stop()

    st.subheader("Revisión en vivo")
    progreso = st.progress(0.0)
    traducciones = []

    for i, lote in enumerate(lotes):
        try:
            resultados = chain.batch([{"texto": c} for c in lote])
        except Exception as e:
            st.error(f"Error traduciendo el lote {i + 1}: {e}")
            st.stop()

        for original, traducido in zip(lote, resultados):
            traducciones.append(traducido)
            with st.container(border=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Original**")
                    st.write(original)
                with col2:
                    st.markdown("**Traducción**")
                    st.write(traducido)

        progreso.progress((i + 1) / len(lotes))

    st.success("Traducción completa.")

    texto_final = "\n\n".join(traducciones)

    st.subheader("Descargar resultado")
    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "Descargar como .txt",
            data=texto_final.encode("utf-8"),
            file_name="traduccion.txt",
            mime="text/plain",
            on_click="ignore",
        )
    with col_b:
        st.download_button(
            "Descargar como .docx",
            data=build_docx_bytes(texto_final),
            file_name="traduccion.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            on_click="ignore",
        )
