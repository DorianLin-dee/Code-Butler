#!/usr/bin/env python3
"""
Related Work 分析工具 v3.0 - 简洁可泛化版本
自动从 PDF 论文中提取 Related Work，分析引用论文，搜索免费链接，生成研究脉络报告
"""

import re
import sys
import json
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class PaperReference:
    """论文引用信息"""
    authors: str
    year: str
    raw_citation: str
    title: str = ""
    venue: str = ""
    doi: str = ""
    url: str = ""
    
    def get_url(self) -> str:
        """获取可访问的链接"""
        if self.url:
            return self.url
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return ""


class RelatedWorkAnalyzer:
    """Related Work 分析器"""
    
    def __init__(self, pdf_path: str = None):
        self.pdf_path = pdf_path
        self.pdf_text = ""
        self.related_work_text = ""
        self.references: List[PaperReference] = []
        self.sections: Dict[str, str] = {}
        
    def extract_pdf_text(self) -> bool:
        """从 PDF 提取文本"""
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            print(f"❌ 文件不存在: {self.pdf_path}")
            return False
            
        try:
            from pypdf import PdfReader
            reader = PdfReader(self.pdf_path)
            self.pdf_text = "\n".join([
                page.extract_text() or "" 
                for page in reader.pages
            ])
            return bool(self.pdf_text)
        except ImportError:
            print("📦 安装依赖 pypdf...")
            os.system("pip install pypdf -q")
            try:
                from pypdf import PdfReader
                reader = PdfReader(self.pdf_path)
                self.pdf_text = "\n".join([
                    page.extract_text() or "" 
                    for page in reader.pages
                ])
                return bool(self.pdf_text)
            except Exception as e:
                print(f"❌ PDF 提取失败: {e}")
                return False
        except Exception as e:
            print(f"❌ PDF 提取失败: {e}")
            return False
    
    def find_related_work(self) -> bool:
        """自动识别 Related Work 部分"""
        patterns = [
            r'(?:^|\n)(Related\s+Work|R\s+E\s+L\s+A\s+T\s+E\s+D\s+\w+)[.\s]*\n',
            r'(?:^|\n)(\d+\.?\s*Related\s+\w+)[.\s]*\n',
            r'(?:^|\n)(Background|B\s+G\s+R\s+O\s+U\s+N\s+D)[.\s]*\n',
        ]
        
        sections = []
        for pattern in patterns:
            matches = re.finditer(pattern, self.pdf_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                start = match.start()
                sections.append({
                    'start': start,
                    'title': match.group(0).strip()
                })
        
        sections.sort(key=lambda x: x['start'])
        
        if not sections:
            return False
        
        # 提取第一个 Related Work 部分到下一个主要部分之前
        start = sections[0]['start']
        end = sections[1]['start'] if len(sections) > 1 else len(self.pdf_text)
        
        # 排除参考文献列表
        ref_match = re.search(r'\nReferences?\n', self.pdf_text[start:end], re.IGNORECASE)
        if ref_match:
            end = start + ref_match.start()
        
        self.related_work_text = self.pdf_text[start:end]
        return bool(self.related_work_text)
    
    def extract_references(self) -> List[PaperReference]:
        """提取引用论文"""
        citations = []
        
        # 匹配 [Author Year] 或 [Author et al. Year]
        pattern = r'\[([A-Z][a-z]+(?:\s+et\s+al\.|\s+and\s+[A-Z][a-z]+)?)\s+(\d{4})\]'
        
        for match in re.finditer(pattern, self.related_work_text):
            author = match.group(1).replace(' et al.', '').strip()
            year = match.group(2)
            raw = match.group(0)
            
            # 去重
            if not any(c.authors == author and c.year == year for c in citations):
                citations.append(PaperReference(author, year, raw))
        
        self.references = citations
        return citations
    
    def identify_themes(self) -> List[str]:
        """识别研究主题"""
        themes_map = {
            'Developable Surfaces': ['developable', 'isometric', 'planar sheet'],
            'Elastic Structures': ['elastic', 'bending', 'flexible'],
            'Deployable Structures': ['deployable', 'planar-to-spatial', 'deployment'],
            'Computational Design': ['computational design', 'optimization', 'algorithm'],
            'Fabrication': ['fabrication', 'manufacturing', 'production'],
            'Gridshells': ['gridshell', 'grid', 'lattice'],
            'Geodesics': ['geodesic', 'shortest path'],
            'Auxetics': ['auxetic', 'negative poisson'],
            'Origami': ['origami', 'folding'],
            'Self-Supporting Structures': ['self-supporting', 'masonry'],
            'Wire Mesh': ['wire mesh', 'rod mesh'],
        }
        
        themes = []
        text_lower = self.related_work_text.lower()
        
        for theme, keywords in themes_map.items():
            if any(kw in text_lower for kw in keywords):
                themes.append(theme)
        
        return themes
    
    def generate_mindmap(self) -> str:
        """生成研究脉络思维导图"""
        lines = ["研究脉络思维导图", "│"]
        themes = self.identify_themes()
        
        for theme in themes:
            lines.append(f"├─ {theme}")
            
            # 找出属于该主题的引用
            theme_cits = []
            theme_text = ""
            
            # 简化：按主题分段
            paragraphs = self.related_work_text.split('\n\n')
            for para in paragraphs:
                if any(kw in para.lower() for kw in theme.lower().split()):
                    theme_text += para
            
            for ref in self.references[:5]:
                lines.append(f"│   ├─ {ref.authors} [{ref.year}]")
            
            if len(self.references) > 5:
                lines.append(f"│   └─ ... 共 {len(self.references)} 篇")
        
        return "\n".join(lines)
    
    def analyze(self) -> Dict:
        """执行完整分析"""
        print("=" * 60)
        print("📚 Related Work 分析工具 v3.0")
        print("=" * 60)
        
        if self.pdf_path:
            print(f"\n📄 分析文件: {self.pdf_path}")
            
            if not self.extract_pdf_text():
                return {"error": "PDF 文本提取失败"}
            print(f"✅ 提取文本成功 ({len(self.pdf_text)} 字符)")
            
            if not self.find_related_work():
                return {"error": "未找到 Related Work 部分"}
            print(f"✅ 找到 Related Work ({len(self.related_work_text)} 字符)")
        
        references = self.extract_references()
        themes = self.identify_themes()
        mindmap = self.generate_mindmap()
        
        result = {
            "total_references": len(references),
            "research_themes": themes,
            "references": [
                {
                    "author": r.authors,
                    "year": r.year,
                    "citation": r.raw_citation
                }
                for r in references
            ],
            "mindmap": mindmap,
            "full_text": self.related_work_text if self.pdf_path else ""
        }
        
        # 保存结果
        if self.pdf_path:
            output_dir = os.path.dirname(self.pdf_path)
            output_file = os.path.join(output_dir, "related_work_analysis.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 结果已保存: {output_file}")
        
        return result


def main():
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        analyzer = RelatedWorkAnalyzer(pdf_path)
        result = analyzer.analyze()
        
        if "error" not in result:
            print("\n" + "=" * 60)
            print("📊 分析结果")
            print("=" * 60)
            print(f"✅ 识别 {result['total_references']} 篇引用论文")
            print(f"✅ 研究主题: {', '.join(result['research_themes'])}")
            print("\n" + result['mindmap'])
    else:
        print("使用方法: python3 related_work_analyzer.py <pdf_file>")


if __name__ == "__main__":
    main()
