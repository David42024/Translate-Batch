"""Servicio HTTP del agente que conecta Google Sheets con LangChain y Gemini."""

import io
import logging
import os
import time
import base64
from typing import Any

import requests
import trafilatura
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from langchain.agents import AgentExecutor
from langchain_core.output_parsers import StrOutputParser
from langchain_core.agents import AgentFinish
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable
from pypdf import PdfReader
from pydantic import BaseModel


load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="Agente traductor de artículos")


class ProcessRequest(BaseModel):
    source_url: str | None = None
    source_text: str | None = None
    pdf_base64: str | None = None
    fragment: str | None = None


def build_translation_chain():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY.")

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.2,
    )
    prompt = ChatPromptTemplate.from_template(
        "Traduce del inglés al español el siguiente texto técnico. "
        "Instrucciones importantes:\n"
        "- Traduce grandes secciones de texto completo, no resumas\n"
        "- Conserva exactamente el formato, estructura de párrafos, enumeraciones y tablas\n"
        "- Mantiene terminología técnica y especializada precisa\n"
        "- Traduce todos los detalles, cifras, nombres propios y referencias\n"
        "- Responde ÚNICAMENTE con la traducción completa sin comentarios adicionales\n\n"
        "Texto a traducir:\n{texto}"
    )
    return prompt | llm | StrOutputParser()


def extract_article(url: str) -> str:
    if url.startswith("10."):
        url = f"https://doi.org/{url}"
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    is_pdf = "application/pdf" in content_type or url.lower().split("?")[0].endswith(".pdf")
    if is_pdf:
        reader = PdfReader(io.BytesIO(response.content))
        article = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not article:
            raise ValueError("No se pudo extraer texto del PDF.")
        return article

    downloaded = response.text

    article = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
    )
    if not article:
        raise ValueError("No se pudo extraer texto legible del enlace.")
    validate_extracted_article(article)
    return article


def extract_pdf_bytes(pdf_base64: str) -> str:
    reader = PdfReader(io.BytesIO(base64.b64decode(pdf_base64)))
    article = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not article:
        raise ValueError("No se pudo extraer texto del PDF guardado en Drive.")
    validate_extracted_article(article)
    return article


def validate_extracted_article(article: str) -> None:
    normalized = " ".join(article.lower().split())
    access_markers = [
        "cargando", "acceder", "sign in", "log in", "login", "institutional access",
    ]
    if len(normalized) < 300 or sum(marker in normalized for marker in access_markers) >= 2:
        raise ValueError(
            "El enlace devolvió una página de acceso o muy poco texto. "
            "Descarga el PDF con tu acceso y súbelo a Google Drive."
        )


def translate_text(text: str) -> str:
    chain = build_translation_chain()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=int(os.environ.get("TRANSLATION_CHUNK_SIZE", "500000")),
        chunk_overlap=0,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    total_chunks = len(chunks)
    pause_seconds = float(os.environ.get("MIN_SECONDS_BETWEEN_REQUESTS", "4"))
    
    print(f"🔄 Iniciando traducción por lotes: {total_chunks} chunks a procesar")
    print(f"📊 Tamaño total del texto: {len(text):,} caracteres")
    print(f"⏱️  Tiempo estimado: ~{total_chunks * pause_seconds / 60:.1f} minutos")
    logger.info(f"🔄 Iniciando traducción por lotes: {total_chunks} chunks a procesar")
    logger.info(f"📊 Tamaño total del texto: {len(text):,} caracteres")
    logger.info(f"⏱️  Tiempo estimado: ~{total_chunks * pause_seconds / 60:.1f} minutos")
    
    translations = []
    for index, chunk in enumerate(chunks):
        chunk_num = index + 1
        print(f"📝 Procesando chunk {chunk_num}/{total_chunks} ({len(chunk):,} caracteres)")
        logger.info(f"📝 Procesando chunk {chunk_num}/{total_chunks} ({len(chunk):,} caracteres)")
        
        if index:
            print(f"⏳ Esperando {pause_seconds}s antes de la siguiente consulta...")
            logger.info(f"⏳ Esperando {pause_seconds}s antes de la siguiente consulta...")
            time.sleep(pause_seconds)
        
        try:
            translated = chain.invoke({"texto": chunk})
            translations.append(translated)
            print(f"✅ Chunk {chunk_num}/{total_chunks} completado")
            logger.info(f"✅ Chunk {chunk_num}/{total_chunks} completado")
        except Exception as e:
            print(f"❌ Error en chunk {chunk_num}/{total_chunks}: {e}")
            logger.error(f"❌ Error en chunk {chunk_num}/{total_chunks}: {e}")
            raise
    
    print(f"🎉 Traducción completada: {total_chunks} chunks procesados")
    logger.info(f"🎉 Traducción completada: {total_chunks} chunks procesados")
    return "\n\n".join(translations)


def build_translation_agent() -> AgentExecutor:
    @tool
    def translate_source_text(text: str) -> str:
        """Traduce al español un artículo o fragmento técnico escrito en inglés."""
        return translate_text(text)

    def run_translation_tool(inputs: dict[str, Any]) -> AgentFinish:
        translated = translate_source_text.invoke(inputs["input"])
        return AgentFinish(
            return_values={"output": translated},
            log="La herramienta de traducción procesó la entrada.",
        )

    agent = RunnableLambda(run_translation_tool)
    return AgentExecutor(
        agent=agent,
        tools=[translate_source_text],
        verbose=True,
        max_iterations=3,
    )


@traceable(name="traductor-agent", run_type="chain")
def translate_with_agent(text: str) -> str:
    result = build_translation_agent().invoke({
        "input": "Traduce el siguiente texto conservando formato y terminología técnica:\n\n"
        + text,
    })
    return result["output"]


def check_token(authorization: str | None) -> None:
    expected = os.environ.get("AGENT_TOKEN")
    if not expected:
        raise RuntimeError("Falta la variable de entorno AGENT_TOKEN.")
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Token no válido.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process")
def process(
    request: ProcessRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    check_token(authorization)
    if not request.source_url and not request.source_text and not request.pdf_base64 and not request.fragment:
        raise HTTPException(status_code=400, detail="No hay enlace ni fragmento.")

    try:
        if request.source_text:
            validate_extracted_article(request.source_text)
        translated_article = (
                translate_with_agent(
                request.source_text
                if request.source_text
                else (
                    extract_pdf_bytes(request.pdf_base64)
                    if request.pdf_base64
                    else extract_article(request.source_url)
                )
            )
            if request.source_url or request.source_text or request.pdf_base64
            else None
        )
        translated_fragment = (
            translate_with_agent(request.fragment)
            if request.fragment and request.fragment.strip()
            else None
        )
        return {
            "translated_article": translated_article,
            "translated_fragment": translated_fragment,
        }
    except Exception as error:
        logger.exception("Error procesando solicitud del agente")
        raise HTTPException(status_code=502, detail=str(error)) from error