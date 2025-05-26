import os
import tempfile
import streamlit as st
import requests
import json
import time
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

# Configuration MCP
MCP_SERVER_URL = "http://localhost:8000/sse"

async def call_mcp_tool(tool_name: str, params: dict):
    """Appelle un outil MCP via SSE et retourne la réponse."""
    try:
        async with sse_client(MCP_SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=params)
                return result
    except Exception as e:
        st.error(f"Erreur lors de l'appel MCP: {str(e)}")
        return None

def run_async_tool(tool_name: str, params: dict):
  
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(call_mcp_tool(tool_name, params))
        loop.close()
        return result
    except Exception as e:
        st.error(f"Erreur lors de l'exécution asynchrone: {str(e)}")
        return None

def main():
    st.set_page_config(
        page_title="MCP Web Scraper App",
        page_icon="🕷️",
        layout="wide"
    )
    
    st.title("🕷️ MCP Web Scraper Application")
    st.markdown("Interface pour scraper et analyser des pages web avec MCP")
    
    # Sidebar
    st.sidebar.header("À propos")
    st.sidebar.info(
        "Cette application utilise MCP (Model Context Protocol) pour scraper "
        "et analyser des pages web. Vous pouvez extraire du contenu, "
        "des métadonnées et des liens."
    )
    if 'scrape_result' not in st.session_state:
        st.session_state['scrape_result'] = '' 

    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📄 RAG PDF Chatbot", "🕷️ Web Scraper", "📊 Résultats"])
    
    # TAB 1 - RAG PDF 
    with tab1:
        st.header("📄 Upload de documents")
        uploaded_file = st.file_uploader("Choisir un fichier", type=['pdf', 'docx'])
        
        if uploaded_file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                file_path = tmp_file.name
            
            st.session_state['file_path'] = file_path
            st.session_state['file_name'] = uploaded_file.name
            
            if st.button("Traiter le document"):
                with st.spinner("Traitement du document..."):
                    result = run_async_tool("parse_file", {"file_path": file_path})
                    if result is None:
                        st.error("Erreur lors du traitement du document! Vérifiez la connexion au serveur")
                    elif isinstance(result, str):
                        st.session_state['document_text'] = result
                        st.success("Document traité avec succès!")
                        st.info(f"Le document contient {len(result.split())} mots.")
                        with st.expander("Aperçu du document"):
                            st.text(result[:1000] + ("..." if len(result) > 1000 else ""))
                    else:
                        st.session_state["document_text"] = str(result)
                        st.success("Document traité!")
                        with st.expander("Aperçu du document"):
                            st.json(result)
    
    # TAB 2 - Web Scraper
    with tab2:
        st.header("🕷️ Web Scraper MCP")
        
  
        col1, col2 = st.columns([2, 1])
        
        with col1:
            url = st.text_input("🌐 URL à scraper", placeholder="https://example.com")
        
        with col2:
            format_output = st.selectbox(
                "📝 Format de sortie",
                ["markdown", "text", "html", "json"],
                index=0
            )
        
  
        with st.expander("⚙️ Options avancées"):
            col3, col4 = st.columns(2)
            with col3:
                include_links = st.checkbox("Inclure les liens", value=False)
                include_images = st.checkbox("Inclure les images", value=False)
            with col4:
                max_length = st.number_input("Longueur max (0 = illimité)", min_value=0, value=0)
                max_length = None if max_length == 0 else max_length
        
      
        col5, col6, col7 = st.columns(3)
        
        with col5:
            if st.button("🕷️ Scraper la page", type="primary"):
                if url:
                    with st.spinner("Scraping en cours..."):
                        params = {
                            "url": url,
                            "format": format_output,
                            "include_links": include_links,
                            "include_images": include_images
                        }
                        if max_length:
                            params["max_length"] = max_length
                        
                        result = run_async_tool("scrape_webpage", params)
                        
                        if result:
                            st.session_state['scrape_result'] = result
                            st.session_state['scrape_url'] = url
                            st.success("✅ Scraping terminé!")
                        else:
                            st.error("❌ Erreur lors du scraping")
                else:
                    st.warning("⚠️ Veuillez entrer une URL")
        
        with col6:
            if st.button("🔗 Extraire les liens"):
                if url:
                    with st.spinner("Extraction des liens..."):
                        result = run_async_tool("extract_links", {
                            "url": url,
                            "filter_domain": False,
                            "link_type": "all"
                        })
                        
                        if result:
                            st.session_state['links_result'] = result
                            st.success("✅ Liens extraits!")
                        else:
                            st.error("❌ Erreur lors de l'extraction")
                else:
                    st.warning("⚠️ Veuillez entrer une URL")
        
        with col7:
            if st.button("ℹ️ Infos de la page"):
                if url:
                    with st.spinner("Récupération des informations..."):
                        result = run_async_tool("get_page_info", {"url": url})
                        
                        if result:
                            st.session_state['page_info'] = result
                            st.success("✅ Informations récupérées!")
                        else:
                            st.error("❌ Erreur lors de la récupération")
                else:
                    st.warning("⚠️ Veuillez entrer une URL")
        
        # Scraping multiple
        st.divider()
        st.subheader("📚 Scraping multiple")
        
        urls_text = st.text_area(
            "URLs (une par ligne)",
            placeholder="https://example1.com\nhttps://example2.com\nhttps://example3.com"
        )
        
        col8, col9 = st.columns(2)
        with col8:
            delay = st.slider("Délai entre requêtes (sec)", 0.5, 5.0, 1.0, 0.5)
        with col9:
            max_pages = st.number_input("Nombre max de pages", 1, 20, 5)
        
        if st.button("🚀 Scraper plusieurs pages"):
            if urls_text.strip():
                urls_list = [url.strip() for url in urls_text.strip().split('\n') if url.strip()]
                if urls_list:
                    with st.spinner(f"Scraping de {len(urls_list)} pages..."):
                        result = run_async_tool("scrape_multiple_pages", {
                            "urls": urls_list,
                            "format": format_output,
                            "delay": delay,
                            "max_pages": max_pages
                        })
                        
                        if result:
                            st.session_state['multiple_scrape_result'] = result
                            st.success(f"✅ {len(urls_list)} pages traitées!")
                        else:
                            st.error("❌ Erreur lors du scraping multiple")
                else:
                    st.warning("⚠️ Aucune URL valide trouvée")
            else:
                st.warning("⚠️ Veuillez entrer au moins une URL")
    
    # TAB 3 
    with tab3:
        st.header("📊 Résultats")

        result = st.session_state.get('scrape_result')

        if result:
            st.subheader(f"🕷️ Contenu scraped de: {st.session_state.get('scrape_url', '')}")

            
            if format_output == "json":
                try:
                    json_data = json.loads(result)
                    st.json(json_data)
                except:
                    st.text_area("Contenu JSON brut", result, height=400)
            else:
                st.text_area("Contenu", result, height=400)

            # 
            col10, col11 = st.columns(2)
            with col10:
                try:
                    if isinstance(result, str):
                        data = result
                    elif hasattr(result, 'content'):
                        data = str(result.content)
                    elif hasattr(result, '__dict__'):
                        data = json.dumps(result.__dict__, indent=2, ensure_ascii=False)
                    else:
                        data = str(result)
                except Exception as e:
                    st.error(f"Erreur lors de la conversion du résultat: {e}")
                    data = "Erreur lors de la conversion."

                st.download_button(
                    label="💾 Télécharger le contenu",
                    data=data.encode("utf-8"),
                    file_name=f"scraped_content_{int(time.time())}.txt",
                    mime="text/plain"
                )

            with col11:
                if st.button("🗑️ Effacer le résultat"):
                    st.session_state.pop('scrape_result', None)
                    st.session_state.pop('scrape_url', None)
                    st.experimental_rerun()
        else:
            st.info("Aucun résultat à afficher. Veuillez effectuer le scraping d'abord.")


       
    
        if 'links_result' in st.session_state:
            st.subheader("🔗 Liens extraits")
            try:
                links_data = json.loads(st.session_state['links_result'])
                st.metric("Nombre total de liens", links_data.get('total_links', 0))
                
                if links_data.get('links'):
                    for i, link in enumerate(links_data['links'][:20]):  
                        with st.expander(f"Lien {i+1}: {link.get('text', 'Sans titre')[:50]}..."):
                            st.write(f"**Texte:** {link.get('text', 'N/A')}")
                            st.write(f"**URL:** {link.get('url', 'N/A')}")
                            st.write(f"**Type:** {link.get('type', 'N/A')}")
                
                st.download_button(
                    label="💾 Télécharger les liens (JSON)",
                    data=st.session_state['links_result'],
                    file_name=f"extracted_links_{int(time.time())}.json",
                    mime="application/json"
                )
            except:
                st.text(st.session_state['links_result'])
        

        if 'page_info' in st.session_state:
            st.subheader("ℹ️ Informations de la page")
            try:
                page_data = json.loads(st.session_state['page_info'])
                
                if 'metadata' in page_data:
                    st.write("**📋 Métadonnées:**")
                    metadata = page_data['metadata']
                    col12, col13 = st.columns(2)
                    with col12:
                        st.write(f"**Titre:** {metadata.get('title', 'N/A')}")
                        st.write(f"**Description:** {metadata.get('description', 'N/A')}")
                        st.write(f"**Auteur:** {metadata.get('author', 'N/A')}")
                    with col13:
                        st.write(f"**Langue:** {metadata.get('language', 'N/A')}")
                        st.write(f"**Mots-clés:** {metadata.get('keywords', 'N/A')}")
                
                if 'statistics' in page_data:
                    st.write("**📊 Statistiques:**")
                    stats = page_data['statistics']
                    col14, col15, col16 = st.columns(3)
                    with col14:
                        st.metric("Temps de réponse", f"{stats.get('response_time', 0):.2f}s")
                        st.metric("Taille du contenu", f"{stats.get('content_length', 0):,} chars")
                    with col15:
                        st.metric("Nombre de liens", stats.get('links_count', 0))
                        st.metric("Nombre d'images", stats.get('images_count', 0))
                    with col16:
                        st.metric("Scripts", stats.get('scripts_count', 0))
                        st.metric("Feuilles de style", stats.get('stylesheets_count', 0))
                
                st.download_button(
                    label="💾 Télécharger les infos (JSON)",
                    data=st.session_state['page_info'],
                    file_name=f"page_info_{int(time.time())}.json",
                    mime="application/json"
                )
            except:
                st.text(st.session_state['page_info'])
        
        # Résultat du scraping multiple
        if 'multiple_scrape_result' in st.session_state:
            st.subheader("📚 Résultats du scraping multiple")
            st.text_area("Contenu multiple", st.session_state['multiple_scrape_result'], height=400)
            
            st.download_button(
                label="💾 Télécharger le contenu multiple",
                data=st.session_state['multiple_scrape_result'],
                file_name=f"multiple_scraped_{int(time.time())}.txt",
                mime="text/plain"
            )

if __name__ == "__main__":
    main()