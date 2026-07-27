
#!/usr/bin/env python3
"""
生成PDF报告
"""

import subprocess
from pathlib import Path

def main():
    print("=" * 70)
    print("生成PDF报告")
    print("=" * 70)
    
    md_file = Path("/Users/dorian/Documents/solo/codeskill/AI_investment_summary.pdf.md")
    pdf_file = md_file.with_suffix('.pdf')
    
    print(f"\n输入: {md_file}")
    print(f"输出: {pdf_file}")
    
    # 检查 pandoc 是否存在
    if check_pandoc():
        print("\n使用 Pandoc 生成 PDF...")
        result = convert_with_pandoc(md_file, pdf_file)
        if result:
            print(f"\n✅ PDF 生成成功！")
            print(f"📄 位置: {pdf_file}")
        else:
            print("\n⚠️ Pandoc 转换失败，显示替代方案...")
            show_alternatives(md_file)
    else:
        print("\n⚠️ 未找到 Pandoc，显示替代方案...")
        show_alternatives(md_file)


def check_pandoc():
    """检查 Pandoc 是否安装"""
    try:
        result = subprocess.run(['pandoc', '--version'], 
                             capture_output=True, 
                             text=True, 
                             timeout=5)
        return result.returncode == 0
    except:
        return False


def convert_with_pandoc(input_md, output_pdf):
    """使用 Pandoc 转换"""
    try:
        cmd = [
            'pandoc',
            str(input_md),
            '-o', str(output_pdf),
            '--pdf-engine=xelatex',
            '-V', 'CJKmainfont=Songti SC',
            '-V', 'mainfont=Songti SC',
            '-V', 'geometry:margin=2cm'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and output_pdf.exists():
            return True
        else:
            # 尝试简单版本
            cmd_simple = ['pandoc', str(input_md), '-o', str(output_pdf)]
            result = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=60)
            return result.returncode == 0 and output_pdf.exists()
            
    except Exception as e:
        print(f"转换错误: {e}")
        return False


def show_alternatives(md_file):
    """显示替代转换方案"""
    print("\n" + "=" * 70)
    print("PDF 生成替代方案")
    print("=" * 70)
    
    print("\n方案1: 在线转换")
    print("  - 访问 https://www.markdowntopdf.com")
    print("  - 上传 Markdown 文件")
    print(f"  - 文件位置: {md_file}")
    
    print("\n方案2: 使用 VS Code 扩展")
    print("  - 安装 'Markdown PDF' 扩展")
    print("  - 打开 Markdown 文件")
    print("  - 右键 'Markdown PDF: Export (pdf)'")
    
    print("\n方案3: 安装 Pandoc")
    print("  macOS:")
    print("    brew install pandoc")
    print("    brew install --cask basictex")
    print("")
    print("  然后运行:")
    print("    pandoc input.md -o output.pdf")
    
    print("\n" + "=" * 70)
    print(f"Markdown 文件已生成: {md_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
