
#!/usr/bin/env python3
"""
Podwise完整流程测试 - 使用现有转录稿
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime

def main():
    print("=" * 70)
    print("Podwise 完整工作流程演示")
    print("=" * 70)
    
    # 1. 读取转录稿
    transcript_path = Path("/Users/dorian/transcript.txt")
    if not transcript_path.exists():
        print(f"转录稿不存在: {transcript_path}")
        return
    
    print("\n📄 步骤 1: 读取转录稿")
    print("-" * 50)
    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript_content = f.read()
    print(f"✅ 读取成功，约 {len(transcript_content)} 字符")
    
    # 2. 解析带时间戳的内容
    print("\n🎯 步骤 2: 解析转录稿")
    print("-" * 50)
    segments = parse_transcript(transcript_content)
    print(f"✅ 解析到 {len(segments)} 个时间戳片段")
    
    # 3. 提取Highlights和关键词
    print("\n✨ 步骤 3: 提取Highlights和关键词")
    print("-" * 50)
    highlights, keywords = extract_insights(segments, transcript_content)
    print(f"✅ 提取到 {len(highlights)} 个Highlights")
    print(f"✅ 提取到 {len(keywords)} 个关键词")
    
    # 4. 生成思维导图结构
    print("\n🧠 步骤 4: 生成思维导图结构")
    print("-" * 50)
    mindmap = generate_mindmap(segments, transcript_content)
    print("✅ 思维导图结构生成成功")
    
    # 5. 生成Markdown报告
    print("\n📊 步骤 5: 生成完整报告")
    print("-" * 50)
    output_path = Path("/Users/dorian/Documents/solo/codeskill/podwise_report.md")
    generate_markdown_report(output_path, mindmap, highlights, keywords, segments)
    print(f"✅ 报告已保存到: {output_path}")
    
    # 6. 显示结果
    print("\n" + "=" * 70)
    print("🎉 完整流程演示完成！")
    print("=" * 70)
    
    print("\n📚 生成的内容预览:")
    print_mindmap_summary(mindmap)
    print(f"\n💡 完整报告请查看: {output_path}")


def parse_transcript(content):
    """解析时间戳格式: 00:00:00 - 内容"""
    segments = []
    pattern = r'(\d{2}:\d{2}:\d{2})\s*-\s*(.+?)(?=(?:\d{2}:\d{2}:\d{2}\s*-)|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for timestamp, text in matches:
        segments.append({
            'timestamp': timestamp,
            'text': text.strip()
        })
    
    return segments


def extract_insights(segments, full_text):
    """简单提取Highlights和关键词"""
    # 基于词频提取关键词
    words = re.findall(r'[\u4e00-\u9fff]{2,4}', full_text)
    from collections import Counter
    word_counts = Counter(words)
    
    # 过滤掉停用词
    stop_words = {'我们', '这个', '就是', '一个', '可以', '没有', '但是', '还是', '这样', '那么', 
                 '如果', '需要', '已经', '现在', '其实', '因为', '所以', '不是', '或者', '只有',
                 '对于', '然后', '他们', '你们', '这些', '那些', '什么', '一些', '怎么', '自己'}
    
    keywords = []
    for word, count in word_counts.most_common(100):
        if word not in stop_words:
            keywords.append(word)
            if len(keywords) >= 30:
                break
    
    # 基于长度和位置提取Highlights
    highlights = []
    for i, segment in enumerate(segments):
        if len(segment['text']) &gt; 80:
            highlights.append({
                'timestamp': segment['timestamp'],
                'content': segment['text'][:150] + '...' if len(segment['text']) &gt; 150 else segment['text'],
                'position': f'片段 {i+1}/{len(segments)}'
            })
    
    # 取前10个Highlights
    highlights = highlights[:10]
    
    return highlights, keywords


def generate_mindmap(segments, full_text):
    """生成思维导图结构"""
    # 按内容阶段划分
    sections = []
    
    # 识别主要内容区块
    section_titles = [
        ("开场与背景", 0, len(segments) // 6),
        ("时代的困惑", len(segments) // 6, len(segments) // 3),
        ("历史与文明", len(segments) // 3, len(segments) // 2),
        ("资本市场", len(segments) // 2, len(segments) * 2 // 3),
        ("中国的现状", len(segments) * 2 // 3, len(segments) * 5 // 6),
        ("未来与总结", len(segments) * 5 // 6, len(segments))
    ]
    
    for title, start, end in section_titles:
        section_segments = segments[start:end]
        if section_segments:
            sub_points = []
            for seg in section_segments[:5]:
                sub_points.append({
                    'title': seg['text'][:30] + '...' if len(seg['text']) &gt; 30 else seg['text'],
                    'content': seg['text'],
                    'timestamp': seg['timestamp']
                })
            
            sections.append({
                'title': title,
                'timestamp': section_segments[0]['timestamp'] if section_segments else '00:00:00',
                'children': sub_points
            })
    
    return {
        'title': "李录：全球价值投资与时代",
        'children': sections
    }


def generate_markdown_report(output_path, mindmap, highlights, keywords, segments):
    """生成Markdown报告"""
    md = f"# 李录《全球价值投资与时代》分析报告\n\n"
    md += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += "---\n\n"
    
    # 思维导图
    md += "## 📚 内容思维导图\n\n"
    md += render_mindmap_markdown(mindmap)
    md += "\n---\n\n"
    
    # Highlights
    md += "## ✨ 精彩片段\n\n"
    for i, highlight in enumerate(highlights, 1):
        md += f"### {i}. [{highlight['timestamp']}] {highlight['position']}\n\n"
        md += f"{highlight['content']}\n\n"
    md += "---\n\n"
    
    # 关键词
    md += "## 🔑 关键词\n\n"
    md += ", ".join([f"**{k}**" for k in keywords[:20]]) + "\n\n"
    md += "---\n\n"
    
    # 时间轴
    md += "## ⏱️ 完整时间轴\n\n"
    md += "| 时间戳 | 内容摘要 |\n"
    md += "|--------|----------|\n"
    for i, seg in enumerate(segments[::5]):  # 每5个片段显示一个
        preview = seg['text'][:40] + '...' if len(seg['text']) &gt; 40 else seg['text']
        md += f"| {seg['timestamp']} | {preview} |\n"
    md += "\n---\n\n"
    
    # 完整转录稿（截断展示）
    md += "## 📝 完整转录稿\n\n"
    full_text = "\n".join([f"**{s['timestamp']}**  {s['text']}" for s in segments])
    if len(full_text) &gt; 50000:
        md += "*(内容较长，已截断，查看原始文件)*\n\n"
        md += full_text[:50000]
    else:
        md += full_text
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)


def render_mindmap_markdown(mindmap, level=1):
    """渲染思维导图为Markdown"""
    md = ""
    indent = "  " * level
    
    md += f"{indent}- **{mindmap['title']}**\n"
    
    if 'children' in mindmap:
        for child in mindmap['children']:
            if 'timestamp' in child:
                md += f"  {indent}- [{child['timestamp']}] {child['title']}\n"
            else:
                md += f"  {indent}- {child['title']}\n"
            
            if 'children' in child:
                for subchild in child['children'][:3]:  # 每个子节点只显示前3个
                    preview = subchild.get('content', '')[:60]
                    if 'timestamp' in subchild:
                        md += f"    {indent}- [{subchild['timestamp']}] {preview}\n"
                    else:
                        md += f"    {indent}- {preview}\n"
    
    return md


def print_mindmap_summary(mindmap):
    """显示思维导图摘要"""
    print(f"\n📌 {mindmap['title']}")
    print("-" * 40)
    for child in mindmap['children']:
        print(f"  ✅ {child['title']} [{child['timestamp']}]")


if __name__ == "__main__":
    main()
