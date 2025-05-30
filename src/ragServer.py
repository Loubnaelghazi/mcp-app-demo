from asyncio.log import logger
from mcp.server.fastmcp import FastMCP
import faiss
import numpy as np
import uvicorn
from sentence_transformers import SentenceTransformer
import PyPDF2

import logging

# this is the version 1 : simple model trnsofrmer implementation for the moment to test
mcp = FastMCP("rag-server", port=8001)
# Remplacer le modèle par un modèle multilingue performant
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')

PDF_INDEXES = {}

def extract_pdf_text(pdf_path):
    text = ""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text

def chunk_text(text, chunk_size=128):
    words = text.split()
    return [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]


@mcp.tool()
def index_pdf(file_path: str, session_id: str) -> str:
    print(f"[DEBUG] index_pdf session_id: {session_id}")
    text = extract_pdf_text(file_path)
    chunks = chunk_text(text)
    embeddings = model.encode(chunks)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings))
    PDF_INDEXES[session_id] = {"index": index, "chunks": chunks}
    return f"PDF indexé avec {len(chunks)} passages."

@mcp.tool()
def rag_query(question: str, session_id: str) -> str:
    print(f"[DEBUG] rag_query session_id: {session_id}")
    if session_id not in PDF_INDEXES:
        return "Aucun PDF indexé pour cette session."
    index = PDF_INDEXES[session_id]["index"]
    chunks = PDF_INDEXES[session_id]["chunks"]
    q_emb = model.encode([question])
    D, I = index.search(np.array(q_emb), k=1)
    idx = int(I[0][0])
    best_chunk = chunks[idx]
    # Post-traitement : extraire la phrase la plus proche de la question
    import re
    from sentence_transformers.util import cos_sim
    sentences = re.split(r'(?<=[.!?]) +', best_chunk)
    if len(sentences) == 1:
        best_sentence = best_chunk
    else:
        sent_embs = model.encode(sentences)
        q_emb_single = model.encode([question])[0]
        sims = [cos_sim(q_emb_single, s_emb)[0][0].item() for s_emb in sent_embs]
        best_idx = int(np.argmax(sims))
        best_sentence = sentences[best_idx]
    # Extraction intelligente si la question concerne l'auteur ou le présentateur
    if any(x in question.lower() for x in ["présenté", "présentateur", "auteur", "qui a fait", "qui a écrit", "qui a réalisé"]):
        # Cherche une structure du type "Présenté par ..." ou "Auteur ..."
        match = re.search(r'(présenté par|auteur|présentateur)\s*[:\-]?\s*([A-ZÉÈÀÂÎÔÛÇa-zéèàâêîôûç\'\- ]+)', best_sentence, re.IGNORECASE)
        if match:
            # Nettoie le nom
            nom = match.group(2).strip()
            nom = re.sub(r'[^A-Za-zÀ-ÖØ-öø-ÿ\'\- ]', '', nom)
            return nom
    return best_sentence



if __name__ == "__main__":
    logger.info("Demarrage du serveur MCP Web Scraper...")

    try:
     
       mcp.run(transport='sse')
        
    except KeyboardInterrupt:
        logger.info("Arret du serveur demandé par l'utilisateur")