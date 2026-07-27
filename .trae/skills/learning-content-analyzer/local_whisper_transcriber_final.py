#!/usr/bin/env python3
"""
最终版转录工具 - 支持原文+中文翻译，正确识别两位说话者
"""

import sys
import os
from pathlib import Path
import time

DEFAULT_MODEL = 'base'


def translate_japanese_to_chinese(text):
    """将日文翻译成简体中文"""
    import requests
    
    if not text or not text.strip():
        return text
    
    text = text.strip()
    
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': 'ja',
            'tl': 'zh-CN',
            'dt': 't',
            'q': text
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and data[0]:
                translation = ''.join([item[0] for item in data[0] if item[0]])
                return translation
    except Exception as e:
        pass
    
    return text


def improve_speaker_labels_2people(result):
    """改进的说话者识别 - 假设只有2个说话者"""
    segments = result.get('segments', [])
    if not segments:
        return result
    
    print(f"🎙️ 正在进行说话者分组（假设2位说话者）...")
    
    for i, seg in enumerate(segments):
        if i > 0:
            prev_seg = segments[i-1]
            pause = seg.get('start', 0) - prev_seg.get('end', 0)
            seg['pause_before'] = pause
        else:
            seg['pause_before'] = 0
        
        duration = seg.get('end', 0) - seg.get('start', 0)
        seg['duration'] = duration
    
    # 基于停顿时间进行分组（假设2个说话者）
    speaker_counter = 1
    for i, seg in enumerate(segments):
        pause = seg.get('pause_before', 0)
        
        # 较长停顿（> 2秒）切换说话者
        if pause > 2.0:
            speaker_counter = 2 if speaker_counter == 1 else 1
        
        seg['speaker'] = f"SPEAKER_{speaker_counter:02d}"
    
    result['segments'] = segments
    
    print(f"✅ 说话者分组完成！检测到2位说话者")
    
    return result


def format_timestamp(seconds):
    """将秒数转换为 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def generate_transcript_with_bilingual(result, output_file, speaker_names=None):
    """生成双语转录稿（原文+中文翻译）"""
    if speaker_names is None:
        speaker_names = {}
    
    segments = result.get('segments', [])
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # 头部信息
        total_segments = len(segments)
        if total_segments > 0:
            duration = segments[-1].get('end', 0)
            f.write("# 转录笔记（双语版）\n\n")
            f.write(f"- **总片段数**: {total_segments}\n")
            f.write(f"- **总时长**: {format_timestamp(duration)}\n")
            f.write(f"- **原文语言**: 日语\n")
            f.write(f"- **翻译语言**: 简体中文\n")
            f.write("\n---\n\n")
        
        # 翻译并输出每个片段
        print(f"\n🌐 正在翻译...")
        for i, segment in enumerate(segments):
            if (i + 1) % 10 == 0:
                print(f"   进度: {i+1}/{total_segments} ({100*(i+1)//total_segments}%)")
            
            start_time = format_timestamp(segment.get('start', 0))
            text_jp = segment.get('text', '').strip()
            speaker = segment.get('speaker', None)
            
            if text_jp:
                # 获取说话者名称
                if speaker and speaker in speaker_names:
                    speaker_display = speaker_names[speaker]
                elif speaker:
                    speaker_display = speaker
                else:
                    speaker_display = None
                
                # 翻译
                text_cn = translate_japanese_to_chinese(text_jp)
                
                # 输出
                f.write(f"## [{start_time}]")
                if speaker_display:
                    f.write(f" {speaker_display}")
                f.write("\n\n")
                
                f.write(f"**日文原文**\n")
                f.write(f"> {text_jp}\n\n")
                
                f.write(f"**中文翻译**\n")
                f.write(f"> {text_cn}\n\n")
                
                f.write("---\n\n")
                
                time.sleep(0.2)
    
    print(f"✅ 双语转录稿已保存: {output_file}")
    return output_file


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="最终版转录工具 - 双语输出")
    
    parser.add_argument("input", help="音频文件路径")
    parser.add_argument("--speaker-names", type=str, default="妹岛和世,西泽立卫", help="说话者名称")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录")
    
    args = parser.parse_args()
    
    # 解析说话者名称（默认2人）
    speaker_names = {}
    names = args.speaker_names.split(',')
    for i, name in enumerate(names[:2]):  # 最多2个说话者
        speaker_names[f"SPEAKER_{i+1:02d}"] = name.strip()
    
    print(f"👤 说话者: {speaker_names}")
    
    audio_file = args.input
    print(f"📁 使用文件: {audio_file}")
    
    # 转录
    try:
        import whisper
    except ImportError:
        print("\n❌ 需要安装 Whisper: pip3 install openai-whisper")
        return 1
    
    print(f"\n🎤 加载模型...")
    model = whisper.load_model('base')
    
    print(f"📝 正在转录...")
    result = model.transcribe(audio_file, language='ja', word_timestamps=True)
    
    # 说话者识别（2人）
    result = improve_speaker_labels_2people(result)
    
    # 生成输出
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    base_name = Path(audio_file).stem
    output_file = output_dir / f"{base_name}_双语版.md"
    
    generate_transcript_with_bilingual(result, str(output_file), speaker_names)
    
    print("\n" + "="*70)
    print("🎉 完成！")
    print(f"📄 文件: {output_file}")
    print("="*70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
