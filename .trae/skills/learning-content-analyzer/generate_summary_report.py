
#!/usr/bin/env python3
"""
生成观点总结报告
"""

import re
from pathlib import Path
from datetime import datetime

def main():
    print("=" * 70)
    print("🎯 生成观点总结报告")
    print("=" * 70)
    
    # 1. 读取转录稿
    transcript_path = Path("/Users/dorian/Documents/solo/codeskill/transcript.txt")
    with open(transcript_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 2. 解析时间戳
    segments = []
    pattern = r'(\d{2}:\d{2}:\d{2})\s*-\s*(.+?)(?=(?:\d{2}:\d{2}:\d{2}\s*-)|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for ts, text in matches:
        segments.append({'timestamp': ts, 'text': text.strip()})
    
    # 3. 提取观点总结
    insights = extract_insights(segments, content)
    
    # 4. 构建思维导图
    mindmap = build_mindmap(segments, insights)
    
    # 5. 生成Markdown报告
    output_path = Path("/Users/dorian/Documents/solo/codeskill/AI_investment_summary.md")
    write_summary_report(output_path, mindmap, insights, segments)
    
    # 6. 生成PDF准备文件
    pdf_ready = output_path.with_suffix('.pdf.md')
    write_pdf_ready_file(pdf_ready, mindmap, insights, segments)
    
    # 显示结果
    print("\n" + "=" * 70)
    print("🎉 完成！生成文件:")
    print(f"   {output_path} (完整总结报告)")
    print(f"   {pdf_ready} (PDF准备文件)")
    print("=" * 70)
    
    print_report_preview(mindmap, insights)


def extract_insights(segments, full_text):
    """提取核心观点"""
    insights = []
    
    # 基于关键句子和观点提取
    keywords = ['认为', '觉得', '应该', '相信', '关键', '核心', '重要', '总结', 
                '主要', '最重要', '最关键', '其实', '但是', '不过']
    
    for i, seg in enumerate(segments):
        text = seg['text']
        
        # 检查关键句子
        if len(text) &gt; 60 and (any(k in text for k in keywords) or '，' in text):
            # 提取核心观点句
            points = text.split('，')
            for point in points:
                if len(point) &gt; 20:
                    insight = {
                        'content': point.strip(),
                        'timestamp': seg['timestamp'],
                        'position': i + 1,
                        'type': '观点'
                    }
                    insights.append(insight)
                    if len(insights) &gt;= 30:
                        break
            if len(insights) &gt;= 30:
                break
    
    # 进一步筛选最重要的15个观点
    unique_insights = []
    seen = set()
    for insight in insights:
        key = insight['content'][:30]
        if key not in seen:
            seen.add(key)
            unique_insights.append(insight)
    
    return unique_insights[:15]


def build_mindmap(segments, insights):
    """构建思维导图"""
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
    
    return {
        'title': "AI投资与市场洞察 - 2025年",
        'children': children
    }


def write_summary_report(output_path, mindmap, insights, segments):
    """写完整的总结报告Markdown"""
    md = f"# {mindmap['title']}\n\n"
    md += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += "---\n\n"
    
    # 内容思维导图
    md += "## 📚 内容思维导图\n\n"
    md += f"- **{mindmap['title']}**\n"
    for child in mindmap['children']:
        md += f"  - [{child['timestamp']}] **{child['title']}**\n"
        for sub in child['sub_points']:
            md += f"    - {sub}\n"
    md += "\n---\n\n"
    
    # 观点总结
    md += "## 💡 核心观点总结\n\n"
    md += "### 15个核心观点：\n\n"
    for i, insight in enumerate(insights, 1):
        md += f"{i}. **[{insight['timestamp']}]** {insight['content']}\n\n"
    md += "\n---\n\n"
    
    # 关键结论
    md += "## 📊 关键结论\n\n"
    md += "1. **三大主线**: AI、Re-industrialization、金融数字化\n"
    md += "2. **AI泡沫判断**: 2025年大家还在谈论泡沫，说明还没到泡沫阶段\n"
    md += "3. **2026关键词**: \"Returns\"（回报）\n"
    md += "4. **OpenAI定位**: 产品公司而非单纯模型公司\n"
    md += "5. **技术影响**: 自动驾驶等技术会深刻改变交通和房地产格局\n"
    md += "\n---\n\n"
    
    # 完整章节内容
    md += "## 📝 完整章节内容\n\n"
    for child in mindmap['children']:
        md += f"### {child['title']} [{child['timestamp']}]\n\n"
        for sub in child['sub_points']:
            md += f"- {sub}\n"
        md += "\n"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)


def write_pdf_ready_file(output_path, mindmap, insights, segments):
    """写PDF准备文件（更好的打印格式）"""
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


def print_report_preview(mindmap, insights):
    """打印报告预览"""
    print(f"\n📌 {mindmap['title']}")
    print("-" * 50)
    for child in mindmap['children']:
        print(f"  ✅ [{child['timestamp']}] {child['title']}")
    
    print(f"\n💡 已提取 {len(insights)} 个核心观点")


if __name__ == "__main__":
    main()
