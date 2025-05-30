import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from html2text import html2text
from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INTERNAL_ERROR, INVALID_PARAMS
from urllib.parse import urljoin, urlparse
import time
import json
from typing import List, Dict, Any, Optional
import re
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("web-scraper")


DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def is_valid_url(url: str) -> bool:
    try:
        if not url or not isinstance(url, str):
            return False
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    
    except Exception:

        return False

def clean_text(text: str) -> str:

    if not text:
        return ""
    

    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)

    return text.strip()

def safe_request(url: str, timeout: int = 15, **kwargs) -> requests.Response:

    try:
        logger.info(f"Request to : {url}")
        
       
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        
      
        request_kwargs = {
            'timeout': timeout,
            'allow_redirects': True,
            'verify': True,  # Verfy SSL
            **kwargs
        }
        
        response = session.get(url, **request_kwargs)
        response.raise_for_status() 
        if 'charset' not in response.headers.get('content-type', ''):
            response.encoding = response.apparent_encoding  
        
        logger.info(f"Réponse reçue: {response.status_code}, taille: {len(response.content)} bytes")
        return response
        
    except requests.exceptions.Timeout:
        raise McpError(ErrorData(INTERNAL_ERROR, f"Timeout lors de la requête vers {url}"))
    
    except requests.exceptions.ConnectionError:
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur de connexion vers {url}"))
    
    except requests.exceptions.HTTPError as e:
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur HTTP {e.response.status_code}: {str(e)}"))
    
    except requests.exceptions.RequestException as e:
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur de requête: {str(e)}"))
    
    except Exception as e:
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur inattendue lors de la requête: {str(e)}"))

def get_page_metadata(soup: BeautifulSoup, url: str) -> Dict[str, Any]:

    metadata = {
        'url': url,
        'title': '',
        'description': '',
        'keywords': '',
        'author': '',
        'language': '',
        'canonical_url': '',
        'og_title': '',
        'og_description': '',
        'og_image': ''}
    
    try:
       
        title_tag = soup.find('title')
        if title_tag and title_tag.get_text():
            metadata['title'] = clean_text(title_tag.get_text())
        
       
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            metadata['description'] = clean_text(desc_tag.get('content'))
    
        keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_tag and keywords_tag.get('content'):
            metadata['keywords'] = clean_text(keywords_tag.get('content'))
        
    
        author_tag = soup.find('meta', attrs={'name': 'author'})
        if author_tag and author_tag.get('content'):
            metadata['author'] = clean_text(author_tag.get('content'))
        

        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
  
        canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
        if canonical_tag and canonical_tag.get('href'):
            metadata['canonical_url'] = canonical_tag.get('href')

        # Open Graph
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title and og_title.get('content'):
            metadata['og_title'] = clean_text(og_title.get('content'))
        
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content'):
            metadata['og_description'] = clean_text(og_desc.get('content'))
        
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image and og_image.get('content'):
            metadata['og_image'] = og_image.get('content')
        
    except Exception as e:
        logger.warning(f"Erreur lors de l'extraction des métadonnées: {str(e)}")
    
    return metadata

@mcp.tool()
def scrape_webpage(url: str, format: str = "markdown", include_links: bool = False, 
                   include_images: bool = False, max_length: Optional[int] = None) -> str:
    """
    Scrape une page web et retourne son contenu dans le format spécifié.
    
    Args:
        url: URL de la page à scraper
        format: Format de sortie - "markdown", "text", "html", ou "json"
        include_links: Inclure les liens dans l'extraction
        include_images: Inclure les images dans l'extraction
        max_length: Longueur maximale du contenu (None = pas de limite)
    
    Returns:
        Contenu de la page dans le format demandé
    """
    try:
     
        if not is_valid_url(url):
            raise ValueError("URL invalide. Doit commencer par http:// ou https://")
        
        valid_formats = ["markdown", "text", "html", "json"]
        if format.lower() not in valid_formats:
            raise ValueError(f"Format non supporté: {format}. Formats valides: {', '.join(valid_formats)}")
        
        logger.info(f"Scraping de {url} en format {format}")
   
        response = safe_request(url)
  
        soup = BeautifulSoup(response.text, "html.parser")
        metadata = get_page_metadata(soup, url)
        
      
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            element.decompose()
        
     
        main_content = None

        content_selectors = [
            'main', 'article', '[role="main"]', 
            '.content', '#content', '.main-content', 
            '.post-content', '.entry-content', '.article-content',
            'div[itemprop="articleBody"]',  
            '.story__content',  
            '#story',  
            '#main-content'  
        ]
        
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content and main_content.get_text().strip():
                break
        
        if not main_content:

           
            main_content = soup.find('body')
            if not main_content:
                main_content = soup
        

        if format.lower() == "markdown":
            try:
                h = html2text.HTML2Text()
                h.ignore_links = not include_links
                h.ignore_images = not include_images
                h.body_width = 0  #no limits
                content = h.handle(str(main_content))
                content = clean_text(content)
            except Exception as e:
                logger.warning(f"Erreur conversion Markdown: {str(e)}")
                content = clean_text(main_content.get_text())
                    
        elif format.lower() == "text":
            content = main_content.get_text()
            content = clean_text(content)
            
        elif format.lower() == "html":
            content = str(main_content)
            
        elif format.lower() == "json":
            links = []
            images = []
            
            if include_links:
                try:
                    for link in main_content.find_all('a', href=True):
                        href = link.get('href', '').strip()
                        if href:
                            absolute_url = urljoin(url, href)
                            link_text = clean_text(link.get_text())
                            if link_text or absolute_url:
                                links.append({
                                    'text': link_text[:200],  # exp of text limits (for performance)
                                    'url': absolute_url})
                except Exception as e:
                    logger.warning(f"Erreur lors de l'extraction des liens: {str(e)}")
            
            if include_images:
                try:
                    for img in main_content.find_all('img', src=True):
                        src = img.get('src', '').strip()
                        if src:
                            absolute_url = urljoin(url, src)
                            images.append({
                                'alt': clean_text(img.get('alt', ''))[:200],
                                'src': absolute_url
                            })
                except Exception as e:
                    logger.warning(f"Erreur lors de l'extraction des images: {str(e)}")
            
            result = {
                'metadata': metadata,
                'content': clean_text(main_content.get_text()),
                'links': links,
                'images': images,
                'extracted_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            return json.dumps(result, ensure_ascii=False, indent=2)
        
       
        if max_length and isinstance(max_length, int) and max_length > 0:
            if len(content) > max_length:
                content = content[:max_length] + "..."
       
        if format.lower() in ["markdown", "text"] and metadata.get('title'):
            header_parts = []
            if metadata['title']:
                header_parts.append(f"# {metadata['title']}")
            if metadata['description']:
                header_parts.append(f"**Description:** {metadata['description']}")
            if metadata['url']:
                header_parts.append(f"**Source:** {metadata['url']}")
            
            if header_parts:
                header = "\n\n".join(header_parts) + "\n\n---\n\n"
                content = header + content
        
        logger.info(f"Scraping terminé avec succès pour {url}")
        return content
        
    except ValueError as e:
        logger.error(f"Erreur de validation: {str(e)}")
        raise McpError(ErrorData(INVALID_PARAMS, str(e))) from e
    except McpError:
     
        raise
    except Exception as e:
        logger.error(f"Erreur inattendue lors du scraping de {url}: {str(e)}")
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur inattendue: {str(e)}")) from e

@mcp.tool()
def scrape_multiple_pages(urls: List[str], format: str = "markdown", 
                         delay: float = 1.0, max_pages: int = 10) -> str:
    """
    Scrape plusieurs pages web avec un delai entre les requetes.
    
    Args:
        urls: Liste des URLs à scraper
        format: Format de sortie
        delay: Délai en secondes entre les requeetes
        max_pages: Nombre maximum de pages a traiter
    
    Returns:
        Contenu de toutes les pages concaténé
    """
    try:
        if not urls or not isinstance(urls, list):
            raise ValueError("La liste d'URLs ne peut pas être vide")
        
        if len(urls) > max_pages:
            raise ValueError(f"Trop d'URLs. Maximum autorisé: {max_pages}, reçu: {len(urls)}")
        
        if delay < 0.1:
            delay = 0.1 
        
        logger.info(f"Scraping de {len(urls)} pages avec un délai de {delay}s")
        
        results = []
        successful_scrapes = 0
        
        for i, url in enumerate(urls):
            try:
                if not is_valid_url(url):
                    results.append(f"=== ERREUR PAGE {i+1}: {url} ===\n\nErreur: URL invalide\n\n")
                    continue
                
                logger.info(f"Scraping de la page {i+1}/{len(urls)}: {url}")
                content = scrape_webpage(url, format=format)
                results.append(f"=== PAGE {i+1}: {url} ===\n\n{content}\n\n")
                successful_scrapes += 1
                
             
                if i < len(urls) - 1:
                    time.sleep(delay)
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Erreur lors du scraping de {url}: {error_msg}")
                results.append(f"=== ERREUR PAGE {i+1}: {url} ===\n\nErreur: {error_msg}\n\n")
        
        final_result = "\n".join(results)
        
       
        summary = f"=== RÉSUMÉ ===\n\nPages traitées: {len(urls)}\nPages réussies: {successful_scrapes}\nPages échouées: {len(urls) - successful_scrapes}\n\n"
        final_result = summary + final_result
        
        logger.info(f"Scraping multiple terminé: {successful_scrapes}/{len(urls)} pages réussies")
        return final_result
        
    except ValueError as e:
        logger.error(f"Erreur de validation: {str(e)}")
        raise McpError(ErrorData(INVALID_PARAMS, str(e))) from e
    except Exception as e:
        logger.error(f"Erreur inattendue lors du scraping multiple: {str(e)}")
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur inattendue: {str(e)}")) from e

@mcp.tool()
def extract_links(url: str, filter_domain: bool = False, 
                 link_type: str = "all") -> str:
    """
    Extrait tous les liens d'une page web.
    
    Args:
        url: URL de la page
        filter_domain: Ne garder que les liens du même domaine
        link_type: Type de liens - "all", "internal", "external"
    
    Returns:
        JSON contenant tous les liens extraits
    """
    try:
        # Validation des paramètres
        if not is_valid_url(url):
            raise ValueError("URL invalide")
        
        valid_link_types = ["all", "internal", "external"]
        if link_type not in valid_link_types:
            raise ValueError(f"Type de lien invalide: {link_type}. Types valides: {', '.join(valid_link_types)}")
        
        logger.info(f"Extraction des liens de {url} (type: {link_type})")
        
        # Effectuer la requête
        response = safe_request(url)
        
    
        soup = BeautifulSoup(response.text, "html.parser")
        base_domain = urlparse(url).netloc
        links = []

  
        for link in soup.find_all('a', href=True):
            try:
                href = link.get('href', '').strip()
                if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('tel:'):
                    continue
                
                absolute_url = urljoin(url, href)
                
                # Vérifier si c'est une URL valide
                if not is_valid_url(absolute_url):
                    continue
                
                link_domain = urlparse(absolute_url).netloc
                is_internal = link_domain == base_domain
                
          
                if link_type == "internal" and not is_internal:
                    continue
                elif link_type == "external" and is_internal:
                    continue
                
        
                if filter_domain and not is_internal:
                    continue
                
                link_text = clean_text(link.get_text())
                
                links.append({
                    'text': link_text[:200] if link_text else 'Lien sans texte',
                    'url': absolute_url,
                    'type': 'internal' if is_internal else 'external'
                })
                
            except Exception as e:
                logger.warning(f"Erreur lors du traitement d'un lien: {str(e)}")
                continue
        
      
        unique_links = []
        seen_urls = set()
        for link in links:
            if link['url'] not in seen_urls:
                unique_links.append(link)
                seen_urls.add(link['url'])
        
        # Statistiques
        internal_count = len([l for l in unique_links if l['type'] == 'internal'])
        external_count = len([l for l in unique_links if l['type'] == 'external'])
        
        result = {
            'source_url': url,
            'total_links': len(unique_links),
            'internal_links': internal_count,
            'external_links': external_count,
            'links': unique_links,
            'extracted_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"Extraction terminée: {len(unique_links)} liens trouvés")
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except ValueError as e:
        logger.error(f"Erreur de validation: {str(e)}")
        raise McpError(ErrorData(INVALID_PARAMS, str(e))) from e
    except McpError:
        raise
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'extraction des liens: {str(e)}")
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur inattendue: {str(e)}")) from e

@mcp.tool()
def get_page_info(url: str) -> str:
    """
    Récupère les informations générales d'une page web (métadonnées, statistiques).
    
    Args:
        url: URL de la page
    
    Returns:
        JSON contenant toutes les informations de la page
    """
    try:
        # Validation de l'URL
        if not is_valid_url(url):
            raise ValueError("URL invalide")
        
        logger.info(f"Récupération des informations de {url}")
        

        start_time = time.time()
        response = safe_request(url)
        response_time = time.time() - start_time
        
        
        soup = BeautifulSoup(response.text, "html.parser")
        metadata = get_page_metadata(soup, url)
        
        
        stats = {
            'response_time': round(response_time, 3),
            'content_length': len(response.text),
            'status_code': response.status_code,
            'content_type': response.headers.get('content-type', ''),
            'encoding': response.encoding or 'unknown',
            'links_count': len(soup.find_all('a', href=True)),
            'images_count': len(soup.find_all('img', src=True)),
            'forms_count': len(soup.find_all('form')),
            'scripts_count': len(soup.find_all('script')),
            'stylesheets_count': len(soup.find_all('link', rel='stylesheet')),
            'headings_count': {
                'h1': len(soup.find_all('h1')),
                'h2': len(soup.find_all('h2')),
                'h3': len(soup.find_all('h3')),
                'h4': len(soup.find_all('h4')),
                'h5': len(soup.find_all('h5')),
                'h6': len(soup.find_all('h6'))
            }
        }
        
        # Informations sur les headers HTTP
        headers_info = {
            'server': response.headers.get('server', ''),
            'last_modified': response.headers.get('last-modified', ''),
            'cache_control': response.headers.get('cache-control', ''),
            'expires': response.headers.get('expires', ''),
            'etag': response.headers.get('etag', '')
        }
        
        result = {
            'url': url,
            'metadata': metadata,
            'statistics': stats,
            'headers': headers_info,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info(f"Informations récupérées avec succès pour {url}")
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except ValueError as e:
        logger.error(f"Erreur de validation: {str(e)}")
        raise McpError(ErrorData(INVALID_PARAMS, str(e))) from e
    except McpError:
        raise
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la récupération des informations: {str(e)}")
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur inattendue: {str(e)}")) from e


@mcp.tool()
def health_check() -> str:

    try:
        health_info = {
            'status': 'healthy',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'server': 'web-scraper MCP',
            'version': '1.0.0'
        }
        return json.dumps(health_info, ensure_ascii=False, indent=2)
    except Exception as e:
        raise McpError(ErrorData(INTERNAL_ERROR, f"Erreur lors du health check: {str(e)}"))



if __name__ == "__main__":
  
    logger.info("Demarrage du serveur MCP Web Scraper...")

    try:
     
        mcp.run(transport='sse')
        
    except KeyboardInterrupt:
        logger.info("Arret du serveur demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur fatale lors du demarrage du serveur: {str(e)}")
        raise