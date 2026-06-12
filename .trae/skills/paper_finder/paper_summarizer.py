#!/usr/bin/env python3
"""
论文总结工具 - 分析和总结论文内容
"""

import argparse
import os
import re
from typing import Dict, List, Optional
from pdf_extractor import PDFExtractor

class PaperSummarizer:
    def __init__(self):
        self.extractor = PDFExtractor()

    def find_key_sentences(self, text: str, max_count: int = 10) -> List[str]:
        """找出关键句子"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
        
        # 简单规则：包含关键词的句子可能更重要
        keywords = ['propose', 'introduce', 'present', 'achieve', 'outperform', 
                   'significant', 'important', 'novel', 'new', 'method', 
                   'algorithm', 'model', 'results', 'conclusion', 'we show']
        
        scored = []
        for sent in sentences:
            score = 0
            for kw in keywords:
                if kw.lower() in sent.lower():
                    score += 1
            if score > 0:
                scored.append((score, sent))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        return [s[1] for s in scored[:max_count]]

    def extract_findings(self, text: str) -> List[str]:
        """提取研究发现"""
        findings = []
        
        # 查找包含结果的句子
        result_patterns = [
            r'(?:results?|findings?|shows?|achieves?|outperforms?).{0,200}?(?:\.|$)',
            r'(?:we|our).{0,100}?(?:find|show|demonstrate|achieve).{0,200}?(?:\.|$)',
        ]
        
        for pattern in result_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            findings.extend([m.strip() for m in matches if len(m.strip()) > 30])
        
        return findings[:8]

    def extract_methodology(self, sections: Dict[str, str]) -> Optional[str]:
        """提取研究方法"""
        method_keywords = ['method', 'methodology', 'approach', 'algorithm', 
                          'model', 'architecture', 'experiment']
        
        for title, content in sections.items():
            if any(kw.lower() in title.lower() for kw in method_keywords):
                return content[:1000]
        
        # 如果没有找到专门的方法章节，查找正文中的方法描述
        all_text = '\n'.join(sections.values())
        method_pattern = r'(?:method|approach|algorithm).{0,500}?(?:\n\s*\n|$)'
        match = re.search(method_pattern, all_text, re.DOTALL | re.IGNORECASE)
        return match.group(0)[:1000] if match else None

    def summarize(self, pdf_path: str) -> Dict:
        """完整总结论文"""
        # 先提取PDF内容
        analysis = self.extractor.analyze(pdf_path)
        if not analysis:
            return {}

        full_text = analysis.get('full_text', '')
        sections = analysis.get('sections', {})

        summary = {
            'title': analysis.get('title', ''),
            'abstract': analysis.get('abstract', ''),
            'key_sentences': self.find_key_sentences(full_text),
            'findings': self.extract_findings(full_text),
            'methodology': self.extract_methodology(sections),
            'sections': list(sections.keys()),
        }

        return summary

    def generate_summary_report(self, summary: Dict, output_path: Optional[str] = None):
        """生成总结报告"""
        report = []
        report.append("=" * 80)
        report.append("📄 论文总结报告")
        report.append("=" * 80)
        
        # 标题
        if summary.get('title'):
            report.append(f"\n📝 标题: {summary['title']}")
        
        # 摘要
        if summary.get('abstract'):
            report.append("\n" + "-" * 80)
            report.append("📋 摘要:")
            abstract = summary['abstract']
            report.append(abstract[:800] + "..." if len(abstract) > 800 else abstract)
        
        # 章节结构
        if summary.get('sections'):
            report.append("\n" + "-" * 80)
            report.append("📚 论文结构:")
            for i, sec in enumerate(summary['sections'], 1):
                report.append(f"   {i}. {sec}")
        
        # 关键句子
        if summary.get('key_sentences'):
            report.append("\n" + "-" * 80)
            report.append("🔑 关键内容:")
            for i, sent in enumerate(summary['key_sentences'], 1):
                report.append(f"   {i}. {sent[:150]}...")
        
        # 研究发现
        if summary.get('findings'):
            report.append("\n" + "-" * 80)
            report.append("📈 主要发现:")
            for i, finding in enumerate(summary['findings'], 1):
                report.append(f"   {i}. {finding[:150]}...")
        
        # 研究方法
        if summary.get('methodology'):
            report.append("\n" + "-" * 80)
            report.append("🔬 研究方法:")
            method = summary['methodology']
            report.append(method[:500] + "..." if len(method) > 500 else method)
        
        report.append("\n" + "=" * 80)
        
        report_text = '\n'.join(report)
        print(report_text)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
                f.write("\n\n" + "=" * 80 + "\n")
                f.write("📝 完整文本（前5000字符）:\n")
                f.write("=" * 80 + "\n")
                if self.extractor.text:
                    f.write(self.extractor.text[:5000])
            print(f"\n💾 报告已保存至: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='论文总结工具')
    parser.add_argument('pdf_path', help='PDF文件路径')
    parser.add_argument('-o', '--output', help='输出报告文件路径（可选）')
    args = parser.parse_args()

    summarizer = PaperSummarizer()
    summary = summarizer.summarize(args.pdf_path)
    
    if summary:
        summarizer.generate_summary_report(summary, args.output)

if __name__ == '__main__':
    main()
