#!/usr/bin/env python3
"""
处理李录演讲内容并生成分析
"""

import sys
from analyzer import ContentAnalyzer

def main():
    # 读取转录稿内容
    transcript_file = "/Users/dorian/transcript.txt"
    
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"错误：找不到文件 {transcript_file}")
        print("请先运行转录脚本")
        sys.exit(1)
    
    # 创建分析器并加载内容
    analyzer = ContentAnalyzer()
    analyzer.load_content(content)
    
    # 生成思维导图
    print("="*70)
    print("📚 李录《全球价值投资与时代》内容框架（带时间戳）")
    print("="*70)
    mind_map = analyzer.generate_mind_map()
    print(mind_map)
    print()
    
    # 生成时间轴
    print("="*70)
    print("⏱️ 音频/视频时间轴")
    print("="*70)
    timeline = analyzer.generate_timeline()
    print(timeline)
    print()
    
    # 提取核心要点
    print("="*70)
    print("📋 核心要点")
    print("="*70)
    key_points = analyzer.extract_key_points()
    for i, point in enumerate(key_points[:30], 1):
        print(f"{i:2d}. {point}")

if __name__ == "__main__":
    main()
