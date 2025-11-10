"""
URL Handler Service

Handles URL transformations, validations, and domain operations for WebNexus.
Provides URL normalization, validation, and domain extraction utilities.
"""

import re
import logging
from urllib.parse import urlparse, urljoin, urlunparse
from typing import Optional, List, Set, Dict, Any

logger = logging.getLogger(__name__)


class URLHandler:
    """Service for URL operations and validations."""
    
    def __init__(self):
        """Initialize URL handler with common patterns."""
        # File extensions to skip
        self.skip_extensions = {
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', 
            '.mp4', '.mov', '.avi', '.zip', '.tar', '.gz', '.css', '.js'
        }
        
        # Common paths to skip
        self.skip_paths = {
            '/admin', '/login', '/api', '/assets', '/static', '/images',
            '/css', '/js', '/fonts', '/_next', '/__next'
        }
    
    def is_valid_url(self, url: str) -> bool:
        """
        Check if URL is valid and crawlable.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid and crawlable
        """
        if not url or not isinstance(url, str):
            return False
            
        try:
            parsed = urlparse(url)
            
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Must be http or https
            if parsed.scheme not in ('http', 'https'):
                return False
                
            # Check for skip extensions
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in self.skip_extensions):
                return False
                
            # Check for skip paths
            if any(skip_path in path_lower for skip_path in self.skip_paths):
                return False
                
            return True
            
        except Exception as e:
            logger.warning(f"Error validating URL {url}: {e}")
            return False
    
    def is_sitemap(self, url: str) -> bool:
        """
        Check if a URL is a sitemap.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is a sitemap
        """
        try:
            return (
                url.endswith('sitemap.xml') or 
                'sitemap' in urlparse(url).path.lower() or
                url.endswith('robots.txt')
            )
        except Exception as e:
            logger.warning(f"Error checking if URL is sitemap: {e}")
            return False
    
    def is_text_file(self, url: str) -> bool:
        """
        Check if a URL is a text file.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is a text file
        """
        try:
            text_extensions = {'.txt', '.md', '.rst', '.csv', '.json', '.xml'}
            parsed = urlparse(url)
            return any(parsed.path.lower().endswith(ext) for ext in text_extensions)
        except Exception as e:
            logger.warning(f"Error checking if URL is text file: {e}")
            return False
    
    def normalize_url(self, url: str, base_url: Optional[str] = None) -> str:
        """
        Normalize URL by resolving relative URLs and cleaning up.
        
        Args:
            url: URL to normalize
            base_url: Base URL for resolving relative URLs
            
        Returns:
            Normalized absolute URL
        """
        try:
            if base_url and not url.startswith(('http://', 'https://')):
                url = urljoin(base_url, url)
            
            parsed = urlparse(url)
            
            # Remove fragment
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),  # Lowercase domain
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            
            # Remove trailing slash except for root
            if normalized.endswith('/') and parsed.path != '/':
                normalized = normalized.rstrip('/')
                
            return normalized
            
        except Exception as e:
            logger.warning(f"Error normalizing URL {url}: {e}")
            return url
    
    def get_domain(self, url: str) -> str:
        """
        Extract domain from URL.
        
        Args:
            url: URL to extract domain from
            
        Returns:
            Domain name
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception as e:
            logger.warning(f"Error extracting domain from {url}: {e}")
            return ""
    
    def get_base_url(self, url: str) -> str:
        """
        Get base URL (scheme + netloc) from full URL.
        
        Args:
            url: Full URL
            
        Returns:
            Base URL
        """
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception as e:
            logger.warning(f"Error getting base URL from {url}: {e}")
            return url
    
    def is_same_domain(self, url1: str, url2: str) -> bool:
        """
        Check if two URLs are from the same domain.
        
        Args:
            url1: First URL
            url2: Second URL
            
        Returns:
            True if same domain
        """
        try:
            domain1 = self.get_domain(url1)
            domain2 = self.get_domain(url2)
            return domain1 == domain2 and domain1 != ""
        except Exception as e:
            logger.warning(f"Error comparing domains for {url1} and {url2}: {e}")
            return False
    
    def extract_links(self, content: str, base_url: str) -> List[str]:
        """
        Extract and normalize links from HTML content.
        
        Args:
            content: HTML content
            base_url: Base URL for resolving relative links
            
        Returns:
            List of normalized URLs
        """
        links = []
        
        try:
            # Simple regex to find href attributes
            # Note: This is a basic implementation - for production, use a proper HTML parser
            href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
            
            for match in href_pattern.finditer(content):
                href = match.group(1)
                
                # Skip javascript, mailto, tel, etc.
                if any(href.startswith(prefix) for prefix in ('javascript:', 'mailto:', 'tel:', '#')):
                    continue
                
                normalized = self.normalize_url(href, base_url)
                
                if self.is_valid_url(normalized):
                    links.append(normalized)
                    
        except Exception as e:
            logger.warning(f"Error extracting links from content: {e}")
        
        return list(set(links))  # Remove duplicates
    
    def filter_urls_by_domain(self, urls: List[str], allowed_domains: Set[str]) -> List[str]:
        """
        Filter URLs to only include those from allowed domains.
        
        Args:
            urls: List of URLs to filter
            allowed_domains: Set of allowed domains
            
        Returns:
            Filtered list of URLs
        """
        filtered = []
        
        for url in urls:
            try:
                domain = self.get_domain(url)
                if domain in allowed_domains:
                    filtered.append(url)
            except Exception as e:
                logger.warning(f"Error filtering URL {url}: {e}")
                continue
        
        return filtered
    
    def get_robots_txt_url(self, base_url: str) -> str:
        """
        Get robots.txt URL for a domain.
        
        Args:
            base_url: Base URL of the site
            
        Returns:
            robots.txt URL
        """
        try:
            base = self.get_base_url(base_url)
            return f"{base}/robots.txt"
        except Exception as e:
            logger.warning(f"Error getting robots.txt URL for {base_url}: {e}")
            return ""
    
    def get_sitemap_urls(self, base_url: str) -> List[str]:
        """
        Get common sitemap URLs for a domain.
        
        Args:
            base_url: Base URL of the site
            
        Returns:
            List of potential sitemap URLs
        """
        try:
            base = self.get_base_url(base_url)
            return [
                f"{base}/sitemap.xml",
                f"{base}/sitemap_index.xml",
                f"{base}/sitemaps/sitemap.xml",
                f"{base}/sitemap/sitemap.xml"
            ]
        except Exception as e:
            logger.warning(f"Error getting sitemap URLs for {base_url}: {e}")
            return []


# Global URL handler instance
url_handler = URLHandler()