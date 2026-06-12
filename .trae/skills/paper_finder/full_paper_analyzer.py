#!/usr/bin/env python3
"""
论文全部分析工具 v2.0
分析论文的全部章节：摘要、引言、相关工作、方法、实验、结论
补充背景信息与引用内容
"""

import re
import sys
import json
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class PaperSection:
    """论文章节"""
    name: str
    title: str
    content: str
    references: List[str] = None
    
    def __post_init__(self):
        if self.references is None:
            self.references = []


class FullPaperAnalyzer:
    """论文全部分析器"""
    
    def __init__(self, pdf_path: str = None):
        self.pdf_path = pdf_path
        self.pdf_text = ""
        self.sections: Dict[str, PaperSection] = {}
        self.all_references: List[Dict[str, str]] = []
        
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
    
    def identify_sections(self) -> Dict[str, PaperSection]:
        """自动识别论文的所有章节"""
        # 章节标题模式
        section_patterns = {
            'abstract': r'(?:^|\n)(ABSTRACT|R\s+E\s+S\s+U\s+M\s+E)[.\s]*\n',
            'introduction': r'(?:^|\n)(\d+\.?\s*INTRODUCTION)[.\s]*\n',
            'related_work': r'(?:^|\n)(\d+\.?\s*RELATED\s+WORK)[.\s]*\n',
            'background': r'(?:^|\n)(\d+\.?\s*BACKGROUND)[.\s]*\n',
            'preliminaries': r'(?:^|\n)(\d+\.?\s*PRELIMINARIES)[.\s]*\n',
            'method': r'(?:^|\n)(\d+\.?\s*(?:METHOD|APPROACH|ALGORITHM))[.\s]*\n',
            'implementation': r'(?:^|\n)(\d+\.?\s*IMPLEMENTATION)[.\s]*\n',
            'experiments': r'(?:^|\n)(\d+\.?\s*(?:EXPERIMENTS|RESULTS|EVALUATION))[.\s]*\n',
            'conclusion': r'(?:^|\n)(\d+\.?\s*(?:CONCLUSION|SUMMARY|DISCUSSION))[.\s]*\n',
        }
        
        sections = []
        for section_id, pattern in section_patterns.items():
            matches = re.finditer(pattern, self.pdf_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                sections.append({
                    'id': section_id,
                    'start': match.start(),
                    'title': match.group(0).strip()
                })
        
        # 按位置排序
        sections.sort(key=lambda x: x['start'])
        
        # 提取每个章节内容
        for i, section_info in enumerate(sections):
            start = section_info['start']
            end = sections[i+1]['start'] if i+1 < len(sections) else len(self.pdf_text)
            
            content = self.pdf_text[start:end]
            
            # 提取引用
            refs = self._extract_references_from_text(content)
            
            self.sections[section_info['id']] = PaperSection(
                name=section_info['id'],
                title=section_info['title'],
                content=content[:5000],  # 限制长度
                references=refs
            )
        
        return self.sections
    
    def _extract_references_from_text(self, text: str) -> List[str]:
        """从文本中提取引用"""
        pattern = r'\[([A-Z][a-z]+(?:\s+et\s+al\.|\s+and\s+[A-Z][a-z]+)?)\s+(\d{4})\]'
        citations = []
        
        for match in re.finditer(pattern, text):
            author = match.group(1).replace(' et al.', '').strip()
            year = match.group(2)
            citation = f"{author} [{year}]"
            if citation not in citations:
                citations.append(citation)
        
        return citations
    
    def extract_references_list(self) -> List[Dict[str, str]]:
        """提取参考文献列表"""
        refs = []
        
        # 查找 References 部分
        ref_start = re.search(r'\nReferences?\n', self.pdf_text, re.IGNORECASE)
        if ref_start:
            ref_text = self.pdf_text[ref_start.end():ref_start.end()+10000]
            
            # 提取引用格式 [number] Author Year
            pattern = r'\[\d+\]\s+([A-Z][a-z]+(?:\s+(?:et\s+al\.|and\s+[A-Z][a-z]+))?),?\s*([\w\s]+)\.\s*"?([^"]+)"?\.?\s*(\d{4})'
            
            for match in re.finditer(pattern, ref_text):
                author = match.group(1).strip()
                year = match.group(4)
                title = match.group(3).strip() if match.group(3) else ""
                
                refs.append({
                    'author': author,
                    'year': year,
                    'title': title,
                    'citation': f"[{author} {year}]"
                })
        
        self.all_references = refs
        return refs
    
    def generate_report(self) -> Dict:
        """生成完整分析报告"""
        print("=" * 70)
        print("📚 论文全部分析工具 v2.0")
        print("=" * 70)
        
        if self.pdf_path:
            print(f"\n📄 分析文件: {self.pdf_path}")
            
            if not self.extract_pdf_text():
                return {"error": "PDF 文本提取失败"}
            print(f"✅ 提取文本成功 ({len(self.pdf_text)} 字符)")
            
            sections = self.identify_sections()
            print(f"✅ 识别 {len(sections)} 个章节")
            
            refs = self.extract_references_list()
            print(f"✅ 提取 {len(refs)} 条参考文献")
        
        # 生成报告
        report = {
            "paper_info": {
                "path": self.pdf_path,
                "total_chars": len(self.pdf_text),
                "total_sections": len(self.sections),
                "total_references": len(self.all_references)
            },
            "sections": {
                name: {
                    "title": section.title,
                    "content_preview": section.content[:500],
                    "references": section.references
                }
                for name, section in self.sections.items()
            },
            "references": self.all_references,
            "section_summary": self._generate_section_summary()
        }
        
        # 保存报告
        if self.pdf_path:
            output_dir = os.path.dirname(self.pdf_path)
            output_file = os.path.join(output_dir, "full_paper_analysis.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\n💾 报告已保存: {output_file}")
        
        return report
    
    def _generate_section_summary(self) -> Dict[str, str]:
        """生成章节摘要"""
        summaries = {}
        
        section_names = {
            'abstract': '📝 摘要',
            'introduction': '📖 引言/背景',
            'related_work': '📚 相关工作',
            'background': '🔬 背景知识',
            'preliminaries': '📐 预备知识',
            'method': '💡 方法',
            'implementation': '🔧 实现',
            'experiments': '📊 实验',
            'conclusion': '✅ 结论'
        }
        
        for name, section in self.sections.items():
            display_name = section_names.get(name, name)
            # 提取前200字符作为摘要
            summary = ' '.join(section.content.split()[:50])
            summaries[display_name] = summary
        
        return summaries
    
    def print_summary(self):
        """打印摘要"""
        print("\n" + "=" * 70)
        print("📊 论文结构摘要")
        print("=" * 70)
        
        for name, section in self.sections.items():
            display_name = name.upper().replace('_', ' ')
            print(f"\n{display_name}")
            print(f"  {section.title}")
            print(f"  引用: {len(section.references)} 篇")
        
        print(f"\n参考文献: {len(self.all_references)} 条")


def main():
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        analyzer = FullPaperAnalyzer(pdf_path)
        result = analyzer.generate_report()
        
        if "error" not in result:
            analyzer.print_summary()
            
            print("\n" + "=" * 70)
            print("📄 章节内容预览")
            print("=" * 70)
            
            for name, section in result['sections'].items():
                print(f"\n### {name.upper().replace('_', ' ')}")
                print(section['content_preview'][:300])
                if section['references']:
                    print(f"引用: {', '.join(section['references'][:5])}")
    else:
        print("使用方法: python3 full_paper_analyzer.py <pdf_file>")


if __name__ == "__main__":
    main()
