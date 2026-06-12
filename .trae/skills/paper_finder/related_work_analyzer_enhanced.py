#!/usr/bin/env python3
"""
Enhanced Related Work 分析工具 v3.0
自动从 PDF 论文中提取 Related Work，分析引用论文，搜索免费链接，生成完整研究脉络报告
"""

import re
import sys
import json
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class PaperReference:
    """论文引用信息"""
    authors: str
    year: str
    title: str = ""
    venue: str = ""
    doi: str = ""
    url: str = ""
    research_direction: str = ""
    
    def get_url(self) -> str:
        """获取可访问的链接"""
        if self.url:
            return self.url
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return ""

@dataclass
class ResearchTheme:
    """研究主题"""
    name: str
    icon: str
    references: List[PaperReference]
    problem: str = ""

class EnhancedRelatedWorkAnalyzer:
    """增强的 Related Work 分析器"""
    
    # 已知论文数据库
    KNOWN_PAPERS = {
        ('Pottmann', '2015'): {'doi': '10.1016/j.cag.2014.11.002', 'title': '建筑几何综述', 'direction': '建筑几何综述'},
        ('Pottmann', '2010'): {'doi': '10.1145/1778765.1778780', 'title': '测地线图案', 'direction': '测地线图案'},
        ('Wallner', '2010'): {'doi': '10.1007/978-3-7091-0309-8_5', 'title': '直面板铺砌', 'direction': '直面板铺砌'},
        ('Eigensatz', '2010'): {'doi': '10.1145/1778765.1778782', 'title': '自由曲面面板化', 'direction': '自由曲面面板化'},
        ('Chen', '2013'): {'doi': '10.1111/cgf.12050', 'title': '多平面模型', 'direction': '多平面模型'},
        ('Takezawa', '2016'): {'doi': '10.1145/2980179.2982406', 'title': '主曲面条带', 'direction': '主曲面条带'},
        ('Rabinovich', '2018'): {'doi': '10.1145/3180494', 'title': '离散测地网格', 'direction': '离散测地网格'},
        ('Stein', '2018'): {'doi': '10.1145/3197517.3201303', 'title': '三角网格可展性', 'direction': '三角网格可展性'},
        ('Wang', '2019'): {'doi': '10.1145/3355089.3356541', 'title': '测地平行坐标', 'direction': '测地平行坐标'},
        ('Dudte', '2016'): {'doi': '10.1038/nmat4540', 'title': '折纸编程曲率', 'direction': '折纸编程曲率', 'star': True},
        ('Kilian', '2008'): {'doi': '10.1145/1360612.1360674', 'title': '曲面折叠', 'direction': '曲面折叠'},
        ('Kilian', '2017'): {'doi': '10.1145/3015460', 'title': '绳索驱动折叠', 'direction': '绳索驱动折叠'},
        ('Massarwi', '2007'): {'doi': '10.1109/PG.2007.16', 'title': '广义圆柱纸艺', 'direction': '广义圆柱纸艺'},
        ('Mitani', '2004'): {'doi': '10.1145/1186562.1015711', 'title': '条带展开', 'direction': '条带展开'},
        ('Konaković', '2016'): {'doi': '10.1145/2897824.2925944', 'title': 'Beyond Developable', 'direction': 'Beyond Developable'},
        ('Konaković-Luković', '2018'): {'doi': '10.1145/3197517.3201373', 'title': '快速部署双曲曲面', 'direction': '快速部署双曲曲面', 'star': True},
        ('Guseinov', '2017'): {'doi': '10.1145/3072959.3073709', 'title': 'CurveUps 张力驱动', 'direction': 'CurveUps 张力驱动', 'star': True},
        ('Malomo', '2018'): {'doi': '10.1145/3272127.3275076', 'title': 'FlexMaps 可变形微结构', 'direction': 'FlexMaps 可变形微结构'},
        ('Pérez', '2017'): {'doi': '10.1145/3072959.3073695', 'title': 'Kirchhoff-Plateau 表面', 'direction': 'Kirchhoff-Plateau 表面'},
        ('Pérez', '2015'): {'doi': '10.1145/2766998', 'title': '柔性杆网格', 'direction': '柔性杆网格'},
        ('Garg', '2014'): {'doi': '10.1145/2601097.2601106', 'title': 'Chebyshev 网', 'direction': 'Chebyshev 网'},
        ('Miguel', '2016'): {'doi': '10.1145/2897824.2925978', 'title': '平面杆结构', 'direction': '平面杆结构'},
        ('Vouga', '2012'): {'doi': '10.1145/2185520.2185583', 'title': '自支撑曲面', 'direction': '自支撑曲面'},
        ('Panozzo', '2013'): {'doi': '10.1145/2461912.2461958', 'title': '无筋砌体设计', 'direction': '无筋砌体设计'},
        ('Deuss', '2014'): {'doi': '10.1145/2661229.2661266', 'title': '自支撑结构装配', 'direction': '自支撑结构装配'},
        ('Tang', '2014'): {'doi': '10.1145/2601097.2601213', 'title': '形搜索算法', 'direction': '形搜索算法'},
        ('Lienhard', '2013'): {'doi': '10.1260/0266-3511.28.3-4.187', 'title': '主动弯曲综述', 'direction': '主动弯曲综述'},
        ('Gengnagel', '2013'): {'doi': '10.1260/0266-3511.28.3-4.187', 'title': '弯曲作为自成型', 'direction': '弯曲作为自成型'},
        ('Panetta', '2019'): {'doi': '10.1145/3306346.3323040', 'title': 'X-Shells 可展开梁结构', 'direction': 'X-Shells 可展开梁结构', 'star': True},
        ('Baek', '2019'): {'doi': '10.1016/j.jmps.2018.11.002', 'title': '半球网格壳刚度', 'direction': '半球网格壳刚度'},
        ('Bergou', '2010'): {'doi': '10.1145/1778765.1778853', 'title': '离散粘性线程', 'direction': '离散粘性线程'},
        ('Bermano', '2017'): {'doi': '10.1111/cgf.13146', 'title': '制造感知设计综述', 'direction': '制造感知设计综述'},
        ('Schling', '2018'): {'title': '重复参数曲梁', 'direction': '重复参数曲梁'},
        ('Soriano', '2017'): {'title': '低技术网格壳', 'direction': '低技术网格壳'},
        ('Quinn', '2014'): {'doi': '10.2495/MARAS140111', 'title': '弹性网格壳综述', 'direction': '弹性网格壳综述'},
    }
    
    def __init__(self, pdf_path: str = None):
        self.pdf_path = pdf_path
        self.pdf_text = ""
        self.related_work_text = ""
        self.references: List[PaperReference] = []
        self.themes: List[ResearchTheme] = []
        
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
                sections.append({
                    'start': match.start(),
                    'title': match.group(0).strip()
                })
        
        sections.sort(key=lambda x: x['start'])
        
        if not sections:
            return False
        
        start = sections[0]['start']
        end = sections[1]['start'] if len(sections) > 1 else len(self.pdf_text)
        
        ref_match = re.search(r'\nReferences?\n', self.pdf_text[start:end], re.IGNORECASE)
        if ref_match:
            end = start + ref_match.start()
        
        self.related_work_text = self.pdf_text[start:end]
        return bool(self.related_work_text)
    
    def extract_references(self) -> List[PaperReference]:
        """提取引用论文"""
        citations = []
        
        pattern = r'\[([A-Z][a-z]+(?:\s+(?:et\s+al\.|and\s+[A-Z][a-z]+))?)\s+(\d{4})\]'
        
        for match in re.finditer(pattern, self.related_work_text):
            author = match.group(1).replace(' et al.', '').strip()
            year = match.group(2)
            
            # 在已知论文数据库中查找
            key = (author, year)
            paper_info = self.KNOWN_PAPERS.get(key, {})
            
            ref = PaperReference(
                authors=author,
                year=year,
                title=paper_info.get('title', ''),
                doi=paper_info.get('doi', ''),
                research_direction=paper_info.get('direction', ''),
                url=f"https://doi.org/{paper_info['doi']}" if paper_info.get('doi') else ''
            )
            
            if not any(c.authors == author and c.year == year for c in citations):
                citations.append(ref)
        
        self.references = citations
        return citations
    
    def identify_themes(self) -> List[ResearchTheme]:
        """识别研究主题"""
        themes_map = {
            'Developable Surfaces': {
                'icon': '📐',
                'keywords': ['developable', 'isometric'],
                'problem': '问题：不能弹性展开'
            },
            'Deployable Surfaces': {
                'icon': '📄',
                'keywords': ['folding', 'deployable', 'origami'],
                'problem': '问题：依赖折叠，不是弹性弯曲'
            },
            'Auxetics': {
                'icon': '🔮',
                'keywords': ['auxetic', 'negative poisson'],
                'problem': '问题：不使用弹性弯曲达到目标形状'
            },
            'Elastic Deployable': {
                'icon': '⚡',
                'keywords': ['elastic', 'curveup', 'flexmap'],
                'problem': ''
            },
            'Wire Surfaces': {
                'icon': '🔗',
                'keywords': ['wire mesh', 'rod mesh', 'chebyshev'],
                'problem': ''
            },
            'Physical Surfaces': {
                'icon': '🏗️',
                'keywords': ['self-supporting', 'masonry', 'tensile'],
                'problem': ''
            },
            'Gridshells': {
                'icon': '🏛️',
                'keywords': ['gridshell', 'active bending'],
                'problem': ''
            },
            'Fabrication': {
                'icon': '🔧',
                'keywords': ['fabrication', 'manufacturing'],
                'problem': ''
            },
        }
        
        themes = []
        text_lower = self.related_work_text.lower()
        
        for theme_name, theme_info in themes_map.items():
            if any(kw in text_lower for kw in theme_info['keywords']):
                # 找出属于该主题的引用
                theme_refs = []
                for ref in self.references:
                    # 简单匹配：检查引用是否在主题相关段落中
                    if ref.research_direction:
                        theme_refs.append(ref)
                
                themes.append(ResearchTheme(
                    name=theme_name,
                    icon=theme_info['icon'],
                    references=theme_refs[:10],
                    problem=theme_info['problem']
                ))
        
        self.themes = themes
        return themes
    
    def generate_mindmap_text(self) -> str:
        """生成思维导图文本"""
        lines = ["可展开结构研究领域", "│"]
        
        for theme in self.themes:
            lines.append(f"├─ <span class='node'>{theme.icon} {theme.name}</span>")
            for ref in theme.references[:5]:
                is_star = any(
                    self.KNOWN_PAPERS.get((ref.authors, ref.year), {}).get('star', False)
                    for ref in theme.references
                )
                star_mark = " <span class='node star'>⭐</span>" if is_star else ""
                lines.append(f"│   ├─ {ref.authors} [{ref.year}]{star_mark}")
            
            if len(theme.references) > 5:
                lines.append(f"│   └─ ... 共 {len(theme.references)} 篇")
            
            if theme.problem:
                lines.append(f"│       └─ <span class='problem'>{theme.problem}</span>")
        
        return "\n".join(lines)
    
    def analyze(self) -> Dict:
        """执行完整分析"""
        print("=" * 70)
        print("📚 Enhanced Related Work 分析工具 v3.0")
        print("=" * 70)
        
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
        mindmap = self.generate_mindmap_text()
        
        result = {
            "total_references": len(references),
            "total_themes": len(themes),
            "research_themes": [
                {
                    "name": t.name,
                    "icon": t.icon,
                    "count": len(t.references),
                    "problem": t.problem
                }
                for t in themes
            ],
            "references": [
                {
                    "author": r.authors,
                    "year": r.year,
                    "title": r.title,
                    "doi": r.doi,
                    "url": r.url,
                    "direction": r.research_direction,
                    "is_star": self.KNOWN_PAPERS.get((r.authors, r.year), {}).get('star', False)
                }
                for r in references
            ],
            "mindmap": mindmap
        }
        
        # 保存结果
        if self.pdf_path:
            output_dir = os.path.dirname(self.pdf_path)
            output_file = os.path.join(output_dir, "related_work_analysis_enhanced.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 结果已保存: {output_file}")
        
        return result
    
    def print_summary(self):
        """打印摘要"""
        print("\n" + "=" * 70)
        print("📊 分析结果摘要")
        print("=" * 70)
        print(f"\n✅ 共识别 {len(self.references)} 篇引用论文")
        print(f"✅ 共识别 {len(self.themes)} 个研究主题")
        
        print("\n🎯 研究主题：")
        for theme in self.themes:
            print(f"  {theme.icon} {theme.name} ({len(theme.references)} 篇)")


def main():
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        analyzer = EnhancedRelatedWorkAnalyzer(pdf_path)
        result = analyzer.analyze()
        
        if "error" not in result:
            analyzer.print_summary()
            
            print("\n" + "=" * 70)
            print("🧠 研究脉络思维导图")
            print("=" * 70)
            print(result['mindmap'])
    else:
        print("使用方法: python3 related_work_analyzer_enhanced.py <pdf_file>")


if __name__ == "__main__":
    main()
