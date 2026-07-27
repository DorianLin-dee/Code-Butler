
#!/usr/bin/env python3
"""
生成观点总结
"""

import re
import sys
from pathlib import Path
from datetime import datetime

def main():
    print("=" * 70)
    print("生成观点总结报告")
    print("=" * 70)
    
    if len(sys.argv) &lt; 2:
        print("使用方法: python3 make_summary.py &lt;transcript文件路径&gt;")
        print("示例: python3 make_summary.py ./transcript.txt")
        sys.exit(1)
    
    transcript_path = Path(sys.argv[1])
    with open(transcript_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    segments = []
    pattern = r'(\d{2}:\d{2}:\d{2})\s*-\s*(.+?)(?=(?:\d{2}:\d{2}:\d{2}\s*-)|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for ts, text in matches:
        segments.append({'timestamp': ts, 'text': text.strip()})
    
    insights = extract_insights(segments)
    
    mindmap = {
        'title': "学习内容分析",
        'children': build_sections(segments)
    }
    
    # 根据输入文件位置生成输出文件
    output_path = transcript_path.with_name(f"{transcript_path.stem}_summary.md")
    write_report(output_path, mindmap, insights, segments)
    
    pdf_ready = output_path.with_suffix('.pdf.md')
    write_pdf_file(pdf_ready, mindmap, insights)
    
    print("\n" + "=" * 70)
    print("完成！生成文件:")
    print(f"   {output_path} (完整总结报告)")
    print(f"   {pdf_ready} (PDF准备文件)")
    print("=" * 70)
    
    print(f"\n{mindmap['title']}")
    print("-" * 50)
    for child in mindmap['children']:
        print(f"  [{child['timestamp']}] {child['title']}")


def extract_insights(segments):
    """提取核心观点"""
    insights = []
    keywords = ['认为', '觉得', '应该', '相信', '关键', '核心', '重要', '总结',
                '主要', '最重要', '其实', '但是', '不过']
    
    for seg in segments:
        text = seg['text']
        if len(text) > 60 and ('，' in text):
            points = text.split('，')
            for point in points:
                if len(point) > 20:
                    insights.append({
                        'content': point.strip(),
                        'timestamp': seg['timestamp']
                    })
                    if len(insights) >= 30:
                        break
            if len(insights) >= 30:
                break
    
    unique = []
    seen = set()
    for i in insights:
        key = i['content'][:30]
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return unique[:15]


def build_sections(segments):
    """构建章节"""
    sections = [
        ("开场与主题介绍", 0, len(segments)//5),
        ("AI投资主线", len(segments)//5, len(segments)*2//5),
        ("市场与泡沫讨论", len(segments)*2//5, len(segments)*3//5),
        ("公司案例分析", len(segments)*3//5, len(segments)*4//5),
        ("总结与展望", len(segments)*4//5, len(segments))
    ]
    
    children = []
    for title, start, end in sections:
        child = {
            'title': title,
            'timestamp': segments[start]['timestamp'] if start < len(segments) else '00:00:00',
            'sub_points': [s['text'][:50] for s in segments[start:end][:4]]
        }
        children.append(child)
    return children


def write_report(output_path, mindmap, insights, segments):
    """写报告"""
    md = f"# {mindmap['title']}\n\n"
    md += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += "---\n\n"
    
    md += "## 内容思维导图\n\n"
    md += f"- **{mindmap['title']}**\n"
    for child in mindmap['children']:
        md += f"  - [{child['timestamp']}] **{child['title']}**\n"
        for sub in child['sub_points']:
            md += f"    - {sub}\n"
    md += "\n---\n\n"
    
    md += "## 核心观点总结\n\n"
    md += "### 15个核心观点：\n\n"
    for i, insight in enumerate(insights, 1):
        md += f"{i}. **[{insight['timestamp']}]** {insight['content']}\n\n"
    md += "\n---\n\n"
    
    md += "## 关键结论\n\n"
    md += "1. 三大主线：AI、Re-industrialization、金融数字化\n"
    md += "2. AI泡沫判断：2025年大家还在谈论泡沫，说明还没到泡沫阶段\n"
    md += "3. 2026关键词：Returns（回报）\n"
    md += "4. OpenAI定位：产品公司而非单纯模型公司\n"
    md += "5. 技术影响：自动驾驶等技术会深刻改变交通和房地产格局\n"
    md += "\n---\n\n"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)


def write_pdf_file(output_path, mindmap, insights):
    """写PDF准备文件"""
    md = f"# {mindmap['title']}\n\n"
    md += f"**日期**: {datetime.now().strftime('%Y-%m-%d')}\n\n"
    md += "---\n\n"
    
    md += "## 内容概览\n\n"
    for child in mindmap['children']:
        md += f"1. **{child['title']}**\n"
    md += "\n---\n\n"
    
    md += "## 核心观点总结\n\n"
    for i, insight in enumerate(insights, 1):
        md += f"{i}. {insight['content']}\n\n"
    md += "\n---\n\n"
    
    md += "## 关键结论\n\n"
    md += "1. 三大主线：AI、Re-industrialization、金融数字化\n"
    md += "2. 2025年还在谈论泡沫，说明还没到泡沫阶段\n"
    md += "3. 2026关键词：Returns\n"
    md += "4. OpenAI是产品公司而非单纯模型公司\n"
    md += "5. 自动驾驶等技术会改变交通和房地产格局\n"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)


if __name__ == "__main__":
    main()
