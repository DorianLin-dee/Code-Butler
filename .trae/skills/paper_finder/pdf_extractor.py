#!/usr/bin/env python3
"""
PDF内容提取工具 - 从PDF文件中提取文本内容
"""

import argparse
import os
import re
from typing import Dict, Optional, List

class PDFExtractor:
    def __init__(self):
        self.text = ""
        self.sections = {}

    def extract_with_pypdf2(self, pdf_path: str) -> Optional[str]:
        """使用PyPDF2提取文本"""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except ImportError:
            print("提示: PyPDF2未安装")
            return None
        except Exception as e:
            print(f"PyPDF2提取出错: {e}")
            return None

    def extract_with_pdfminer(self, pdf_path: str) -> Optional[str]:
        """使用pdfminer.six提取文本"""
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(pdf_path)
            return text
        except ImportError:
            print("提示: pdfminer.six未安装")
            return None
        except Exception as e:
            print(f"pdfminer提取出错: {e}")
            return None

    def extract_text(self, pdf_path: str) -> str:
        """从PDF中提取文本（尝试多种方法）"""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"文件不存在: {pdf_path}")

        print(f"📄 正在处理: {pdf_path}")

        # 尝试各种方法
        text = self.extract_with_pdfminer(pdf_path)
        if not text:
            text = self.extract_with_pypdf2(pdf_path)
        
        if text:
            self.text = text
            print(f"✅ 成功提取文本，共 {len(text)} 字符")
            return text
        else:
            print("❌ 无法提取文本")
            print("\n💡 提示: 请安装PDF解析库")
            print("   pip install pdfminer.six")
            print("   pip install PyPDF2")
            return ""

    def extract_title(self) -> Optional[str]:
        """提取标题"""
        lines = self.text.split('\n')
        # 取前几行中最长的非空行作为候选
        candidates = []
        for line in lines[:20]:
            line = line.strip()
            if line and len(line) > 10:
                candidates.append(line)
        return candidates[0] if candidates else None

    def extract_abstract(self) -> Optional[str]:
        """提取摘要"""
        abstract_patterns = [
            r'Abstract[:\s\n]+(.*?)(?=\n\s*[1-9]\.\s*Introduction)',
            r'Abstract[:\s\n]+(.*?)(?=\n\s*Introduction)',
            r'摘要[:\s\n]+(.*?)(?=\n\s*1\.\s*引言)',
        ]
        
        for pattern in abstract_patterns:
            match = re.search(pattern, self.text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def extract_sections(self) -> Dict[str, str]:
        """提取各章节"""
        sections = {}
        
        # 常见的章节标题模式
        section_pattern = r'\n\s*(\d+\.?\d*\s*[A-Z][^\n]{5,80})\s*\n'
        matches = list(re.finditer(section_pattern, self.text))
        
        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.end()
            end = matches[i+1].start() if i+1 < len(matches) else len(self.text)
            content = self.text[start:end].strip()
            sections[title] = content
        
        return sections

    def extract_references(self) -> Optional[str]:
        """提取参考文献"""
        ref_patterns = [
            r'References[:\s\n]+(.*)',
            r'Reference[:\s\n]+(.*)',
            r'Bibliography[:\s\n]+(.*)',
            r'参考文献[:\s\n]+(.*)',
        ]
        
        for pattern in ref_patterns:
            match = re.search(pattern, self.text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def analyze(self, pdf_path: str) -> Dict:
        """完整分析PDF"""
        text = self.extract_text(pdf_path)
        if not text:
            return {}

        result = {
            'path': pdf_path,
            'title': self.extract_title(),
            'abstract': self.extract_abstract(),
            'sections': self.extract_sections(),
            'references': self.extract_references(),
            'full_text': text,
        }
        return result

    def save_text(self, output_path: str, text: Optional[str] = None):
        """保存提取的文本"""
        text_to_save = text or self.text
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text_to_save)
        print(f"💾 文本已保存至: {output_path}")

    def display_analysis(self, result: Dict):
        """显示分析结果"""
        print("\n" + "=" * 80)
        print("📊 PDF分析结果")
        print("=" * 80)
        
        if result.get('title'):
            print(f"\n📝 标题: {result['title']}")
        
        if result.get('abstract'):
            print("\n" + "-" * 80)
            print("📋 摘要:")
            print(result['abstract'][:500] + "..." if len(result['abstract']) > 500 else result['abstract'])
        
        if result.get('sections'):
            print("\n" + "-" * 80)
            print("📚 检测到的章节:")
            for title in result['sections'].keys():
                print(f"   - {title}")
        
        print("\n" + "=" * 80)

def main():
    parser = argparse.ArgumentParser(description='PDF内容提取工具')
    parser.add_argument('pdf_path', help='PDF文件路径')
    parser.add_argument('-o', '--output', help='输出文本文件路径（可选）')
    args = parser.parse_args()

    extractor = PDFExtractor()
    result = extractor.analyze(args.pdf_path)
    
    if result:
        extractor.display_analysis(result)
        
        if args.output:
            extractor.save_text(args.output, result.get('full_text'))
        else:
            # 默认保存为同名txt文件
            default_output = os.path.splitext(args.pdf_path)[0] + '.txt'
            if input(f"\n是否保存文本到 {default_output}? (y/n): ").lower() == 'y':
                extractor.save_text(default_output, result.get('full_text'))

if __name__ == '__main__':
    main()
