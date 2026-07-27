
#!/usr/bin/env python3
"""
Podwise简单测试
"""

import re
from pathlib import Path
from datetime import datetime

def main():
    print("=" * 70)
    print("Podwise 工作流程演示")
    print("=" * 70)
    
    # 1. 读取转录稿
    transcript_path = Path("/Users/dorian/transcript.txt")
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
    output_path = Path("/Users/dorian/Documents/solo/codeskill/podwise_report.md")
    write_report(output_path, mindmap, segments)
    print(f"📊 4. 报告已保存到: {output_path}")
    
    # 显示预览
    print("\n" + "=" * 70)
    print("🎉 完成！结果预览:")
    print("=" * 70)
    display_mindmap(mindmap)
    print(f"\n💡 完整报告: {output_path}")


def build_mindmap(segments):
    """构建简单的思维导图"""
    sections = [
        ("开场与背景", 0, len(segments)//6),
        ("时代的困惑", len(segments)//6, len(segments)//3),
        ("历史与文明", len(segments)//3, len(segments)//2),
        ("资本市场", len(segments)//2, len(segments)*2//3),
        ("中国现状", len(segments)*2//3, len(segments)*5//6),
        ("未来与总结", len(segments)*5//6, len(segments))
    ]
    
    children = []
    for title, start, end in sections:
        child = {
            'title': title,
            'timestamp': segments[start]['timestamp'] if start < len(segments) else '00:00:00',
            'sub_points': [s['text'][:40] for s in segments[start:end][:3]]
        }
        children.append(child)
    
    return {
        'title': "李录：全球价值投资与时代",
        'children': children
    }


def write_report(output_path, mindmap, segments):
    """写Markdown报告"""
    md = "# 李录《全球价值投资与时代》分析报告\n\n"
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
    for seg in segments[::5]:
        preview = seg['text'][:40] + '...' if len(seg['text'])>40 else seg['text']
        md += f"| {seg['timestamp']} | {preview} |\n"
    md += "\n---\n\n"
    
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
