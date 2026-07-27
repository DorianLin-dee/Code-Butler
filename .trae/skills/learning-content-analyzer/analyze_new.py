
#!/usr/bin/env python3
"""
分析新的转录稿
"""

import re
from pathlib import Path
from datetime import datetime

def main():
    print("=" * 70)
    print("🎙️ 分析新的播客内容")
    print("=" * 70)
    
    # 1. 读取转录稿
    transcript_path = Path("/Users/dorian/Documents/solo/codeskill/transcript.txt")
    with open(transcript_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n📄 1. 读取转录稿 - 成功")
    
    # 2. 解析时间戳
    segments = []
    pattern = r'(\d{2}:\d{2}:\d{2})\s*-\s*(.+?)(?=(?:\d{2}:\d{2}:\d{2}\s*-)|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for ts, text in matches:
        segments.append({'timestamp': ts, 'text': text.strip()})
    
    print(f"🎯 2. 解析到 {len(segments)} 个时间戳片段")
    
    # 3. 生成思维导图结构
    mindmap = build_mindmap(segments)
    print(f"🧠 3. 生成思维导图结构 - 成功")
    
    # 4. 生成报告
    output_path = Path("/Users/dorian/Documents/solo/codeskill/AI_investment_report.md")
    write_report(output_path, mindmap, segments)
    print(f"📊 4. 报告已保存到: {output_path}")
    
    # 显示预览
    print("\n" + "=" * 70)
    print("🎉 完成！结果预览:")
    print("=" * 70)
    display_mindmap(mindmap)
    print(f"\n💡 完整报告: {output_path}")


def build_mindmap(segments):
    """构建思维导图"""
    sections = [
        ("开场与主题介绍", 0, len(segments)//5),
        ("AI主线与市场讨论", len(segments)//5, len(segments)*2//5),
        ("泡沫与投资观点", len(segments)*2//5, len(segments)*3//5),
        ("公司案例分析", len(segments)*3//5, len(segments)*4//5),
        ("总结与展望", len(segments)*4//5, len(segments))
    ]
    
    children = []
    for title, start, end in sections:
        child = {
            'title': title,
            'timestamp': segments[start]['timestamp'] if start < len(segments) else '00:00:00',
            'sub_points': [s['text'][:45] for s in segments[start:end][:4]]
        }
        children.append(child)
    
    return {
        'title': "AI投资与市场洞察 - 2025年",
        'children': children
    }


def write_report(output_path, mindmap, segments):
    """写Markdown报告"""
    md = "# AI投资与市场洞察分析报告\n\n"
    md += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += "---\n\n"
    
    # 思维导图
    md += "## 📚 内容思维导图\n\n"
    md += f"- **{mindmap['title']}**\n"
    for child in mindmap['children']:
        md += f"  - [{child['timestamp']}] **{child['title']}**\n"
        for sub in child['sub_points']:
            md += f"    - {sub}\n"
    md += "\n---\n\n"
    
    # 时间轴
    md += "## ⏱️ 完整时间轴\n\n"
    md += "| 时间戳 | 内容预览 |\n"
    md += "|--------|----------|\n"
    for seg in segments[::4]:
        preview = seg['text'][:45] + '...' if len(seg['text'])>45 else seg['text']
        md += f"| {seg['timestamp']} | {preview} |\n"
    md += "\n---\n\n"
    
    # 完整内容
    md += "## 📝 完整内容\n\n"
    for seg in segments:
        md += f"**[{seg['timestamp']}]** {seg['text']}\n\n"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)


def display_mindmap(mindmap):
    """显示思维导图"""
    print(f"\n📌 {mindmap['title']}")
    print("-" * 50)
    for child in mindmap['children']:
        print(f"  ✅ [{child['timestamp']}] {child['title']}")


if __name__ == "__main__":
    main()
