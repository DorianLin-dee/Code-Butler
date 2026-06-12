#!/usr/bin/env python3
"""
论文搜索工具 - 搜索学术论文并寻找免费PDF链接
"""

import argparse
import requests
import re
import urllib.parse
from typing import List, Dict, Optional

class PaperSearcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search_arxiv(self, query: str) -> List[Dict]:
        """在arXiv上搜索论文"""
        results = []
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results=5"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                entries = re.findall(r'<entry>(.*?)</entry>', content, re.DOTALL)
                
                for entry in entries:
                    title = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                    authors = re.findall(r'<name>(.*?)</name>', entry)
                    pdf_link = re.search(r'<link.*?title="pdf".*?href="(.*?)"', entry)
                    summary = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
                    
                    if title:
                        results.append({
                            'title': title.group(1).strip(),
                            'authors': authors,
                            'pdf_url': pdf_link.group(1) if pdf_link else None,
                            'summary': summary.group(1).strip() if summary else '',
                            'source': 'arXiv'
                        })
        except Exception as e:
            print(f"arXiv搜索出错: {e}")
        return results

    def search_google_scholar(self, query: str) -> List[Dict]:
        """在Google Scholar上搜索（基本实现）"""
        results = []
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://scholar.google.com/scholar?q={encoded_query}"
            print(f"Google Scholar搜索链接: {url}")
            print("提示: 请手动访问上述链接查找论文")
        except Exception as e:
            print(f"Google Scholar搜索出错: {e}")
        return results

    def find_scihub_links(self, doi: Optional[str] = None, title: Optional[str] = None) -> List[str]:
        """查找Sci-Hub链接"""
        links = []
        scihub_domains = [
            'sci-hub.se',
            'sci-hub.ru',
            'sci-hub.tw',
            'sci-hub.st'
        ]
        
        for domain in scihub_domains:
            if doi:
                links.append(f"https://{domain}/{doi}")
            elif title:
                links.append(f"https://{domain}/?query={urllib.parse.quote(title)}")
        return links

    def find_libgen_links(self, query: str) -> List[str]:
        """查找Library Genesis链接"""
        links = []
        libgen_domains = [
            'libgen.is',
            'libgen.rs',
            'libgen.st'
        ]
        
        for domain in libgen_domains:
            links.append(f"http://{domain}/search.php?req={urllib.parse.quote(query)}")
        return links

    def extract_doi(self, text: str) -> Optional[str]:
        """从文本中提取DOI"""
        doi_pattern = r'10\.\d{4,9}/[-._;()/:A-Z0-9]+'
        match = re.search(doi_pattern, text, re.IGNORECASE)
        return match.group(0) if match else None

    def search(self, query: str) -> Dict:
        """综合搜索论文"""
        print(f"🔍 正在搜索: {query}\n")
        
        results = {
            'query': query,
            'arxiv_results': [],
            'other_links': [],
            'doi': None
        }
        
        # 提取DOI
        doi = self.extract_doi(query)
        if doi:
            results['doi'] = doi
            print(f"📌 检测到DOI: {doi}\n")

        # 搜索arXiv
        print("📡 正在搜索arXiv...")
        arxiv_results = self.search_arxiv(query)
        results['arxiv_results'] = arxiv_results
        
        if arxiv_results:
            print(f"✅ 在arXiv上找到 {len(arxiv_results)} 篇相关论文\n")
        else:
            print("❌ arXiv上未找到\n")

        # 查找其他链接
        print("🔗 正在查找其他可用链接...")
        
        if doi or arxiv_results:
            scihub_links = self.find_scihub_links(doi, arxiv_results[0]['title'] if arxiv_results else query)
            results['other_links'].extend([{'source': 'Sci-Hub', 'url': link} for link in scihub_links])
        
        libgen_links = self.find_libgen_links(query)
        results['other_links'].extend([{'source': 'Library Genesis', 'url': link} for link in libgen_links])

        return results

    def display_results(self, results: Dict):
        """显示搜索结果"""
        print("=" * 80)
        print("📊 搜索结果")
        print("=" * 80)
        
        # arXiv结果
        if results['arxiv_results']:
            for i, paper in enumerate(results['arxiv_results'], 1):
                print(f"\n📄 {i}. {paper['title']}")
                print(f"   作者: {', '.join(paper['authors'][:3])}")
                print(f"   来源: {paper['source']}")
                if paper['pdf_url']:
                    print(f"   📥 PDF: {paper['pdf_url']}")
                print("   " + "-" * 60)
                print(f"   {paper['summary'][:200]}...")
        
        # 其他链接
        if results['other_links']:
            print("\n" + "=" * 80)
            print("🔗 其他可用链接")
            print("=" * 80)
            for link in results['other_links']:
                print(f"\n{link['source']}:")
                print(f"   {link['url']}")

        print("\n" + "=" * 80)

def main():
    parser = argparse.ArgumentParser(description='论文搜索工具')
    parser.add_argument('query', help='搜索关键词、论文标题或DOI')
    args = parser.parse_args()

    searcher = PaperSearcher()
    results = searcher.search(args.query)
    searcher.display_results(results)

if __name__ == '__main__':
    main()
