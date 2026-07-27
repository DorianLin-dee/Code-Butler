#!/usr/bin/env python3
"""
增强版 Whisper 转录工具 - 支持日语翻译成简体中文
"""

import sys
import os
from pathlib import Path
import time

DEFAULT_MODEL = 'base'
SUPPORTED_FORMATS = ['txt', 'srt', 'vtt', 'json', 'md']


def translate_japanese_to_chinese(text):
    """将日文翻译成简体中文"""
    import requests
    
    if not text or not text.strip():
        return text
    
    text = text.strip()
    
    # 方法1：Google Translate
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


def download_audio(url, output_dir='./audio_downloads'):
    """只下载音频"""
    import yt_dlp
    
    os.makedirs(output_dir, exist_ok=True)
    
    if 'bilibili.com' in url.lower():
        print(f"🔧 检测到B站链接...")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Origin': 'https://www.bilibili.com',
            },
        }
        
        cookie_file = Path.home() / '.bilibili_cookies.txt'
        if cookie_file.exists():
            ydl_opts['cookiefile'] = str(cookie_file)
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
        }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            audio_file = Path(output_dir) / f"{info['id']}.mp3"
            return str(audio_file)
        except Exception as e:
            print(f"⚠️ 下载失败: {e}")
            return None


def improve_speaker_labels_simple(result):
    """改进的简单说话者识别算法"""
    from collections import defaultdict
    
    segments = result.get('segments', [])
    if not segments:
        return result
    
    print(f"🎙️ 正在进行智能说话者分组...")
    
    for i, seg in enumerate(segments):
        if i > 0:
            prev_seg = segments[i-1]
            pause = seg.get('start', 0) - prev_seg.get('end', 0)
            seg['pause_before'] = pause
        else:
            seg['pause_before'] = 0
        
        duration = seg.get('end', 0) - seg.get('start', 0)
        seg['duration'] = duration
    
    speaker_counter = 1
    for i, seg in enumerate(segments):
        pause = seg.get('pause_before', 0)
        duration = seg.get('duration', 0)
        
        if pause > 3.0:
            speaker_counter += 1
            if speaker_counter > 3:
                speaker_counter = 1
        elif pause > 1.5 and duration < 3:
            speaker_counter += 1
            if speaker_counter > 3:
                speaker_counter = 1
        
        seg['speaker'] = f"SPEAKER_{speaker_counter:02d}"
    
    # 平滑处理
    smoothed = []
    for i, seg in enumerate(segments):
        speaker = seg['speaker']
        
        if smoothed and speaker != smoothed[-1].get('speaker'):
            total_duration = sum(s.get('duration', 0) for s in smoothed[-5:]) if len(smoothed) >= 5 else sum(s.get('duration', 0) for s in smoothed)
            if total_duration < 2.0:
                seg['speaker'] = smoothed[-1].get('speaker', speaker)
        
        smoothed.append(seg)
    
    result['segments'] = smoothed
    
    # 统计
    speaker_stats = defaultdict(lambda: {'count': 0, 'total_duration': 0})
    for seg in result['segments']:
        speaker = seg.get('speaker', 'UNKNOWN')
        speaker_stats[speaker]['count'] += 1
        speaker_stats[speaker]['total_duration'] += seg.get('duration', 0)
    
    print(f"✅ 说话者分组完成！检测到 {len(speaker_stats)} 个说话者：")
    for speaker, stats in sorted(speaker_stats.items()):
        minutes = int(stats['total_duration'] // 60)
        seconds = int(stats['total_duration'] % 60)
        print(f"   {speaker}: {stats['count']} 段, 共 {minutes}分{seconds}秒")
    
    return result


def format_timestamp(seconds):
    """将秒数转换为 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def translate_segments(segments, show_progress=True):
    """批量翻译所有片段"""
    if show_progress:
        print(f"\n🌐 开始翻译为简体中文...")
    
    translated_count = 0
    total = len(segments)
    
    for i, seg in enumerate(segments):
        original_text = seg.get('text', '').strip()
        if original_text:
            if show_progress and (i + 1) % 5 == 0:
                print(f"   翻译进度: {i+1}/{total} ({100*(i+1)//total}%)")
            
            translation = translate_japanese_to_chinese(original_text)
            seg['text_cn'] = translation
            translated_count += 1
            
            time.sleep(0.3)
    
    if show_progress:
        print(f"✅ 翻译完成！共翻译 {translated_count} 段")
    
    return segments


def generate_transcript_cn(result, output_file, speaker_names=None, show_translation=True):
    """生成带翻译的中文转录稿"""
    if speaker_names is None:
        speaker_names = {}
    
    segments = result.get('segments', [])
    
    if show_translation:
        segments = translate_segments(segments)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        if segments:
            for segment in segments:
                start_time = format_timestamp(segment.get('start', 0))
                text_jp = segment.get('text', '').strip()
                text_cn = segment.get('text_cn', text_jp)
                speaker = segment.get('speaker', None)
                
                if text_jp:
                    if speaker and speaker in speaker_names:
                        speaker_display = speaker_names[speaker]
                    elif speaker:
                        speaker_display = speaker
                    else:
                        speaker_display = None
                    
                    if speaker_display:
                        f.write(f"{start_time} [{speaker_display}] {text_cn}\n")
                        if show_translation and text_jp != text_cn:
                            f.write(f"   原文: {text_jp}\n\n")
                    else:
                        f.write(f"{start_time} {text_cn}\n")
                        if show_translation and text_jp != text_cn:
                            f.write(f"   原文: {text_jp}\n\n")
    
    print(f"✅ 中文转录稿已保存: {output_file}")
    return output_file


def generate_markdown_cn(result, output_file, speaker_names=None, show_translation=True):
    """生成中文Markdown笔记"""
    if speaker_names is None:
        speaker_names = {}
    
    segments = result.get('segments', [])
    
    if show_translation:
        segments = translate_segments(segments)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 转录笔记（中文翻译版）\n\n")
        
        total_segments = len(segments)
        if total_segments > 0:
            duration = segments[-1].get('end', 0)
            f.write(f"- **总片段数**: {total_segments}\n")
            f.write(f"- **总时长**: {format_timestamp(duration)}\n")
            if 'language' in result:
                f.write(f"- **原文语言**: {result['language']}\n")
            f.write(f"- **翻译语言**: 简体中文\n")
        f.write("\n---\n\n")
        
        if segments:
            for segment in segments:
                start_time = format_timestamp(segment.get('start', 0))
                text_jp = segment.get('text', '').strip()
                text_cn = segment.get('text_cn', text_jp)
                speaker = segment.get('speaker', None)
                
                if text_jp:
                    if speaker and speaker in speaker_names:
                        speaker_display = speaker_names[speaker]
                    elif speaker:
                        speaker_display = speaker
                    else:
                        speaker_display = None
                    
                    f.write(f"**{start_time}** - ")
                    if speaker_display:
                        f.write(f"[{speaker_display}] ")
                    f.write(f"{text_cn}\n\n")
                    
                    if show_translation and text_jp != text_cn:
                        f.write(f"> 原文：{text_jp}\n\n")
        
        # 添加总结部分
        f.write("\n---\n\n")
        f.write("## 🎙️ 说话者信息\n\n")
        
        speaker_stats = {}
        for seg in segments:
            speaker = seg.get('speaker', 'UNKNOWN')
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    'count': 0,
                    'total_duration': 0,
                    'name': speaker_names.get(speaker, speaker)
                }
            speaker_stats[speaker]['count'] += 1
            speaker_stats[speaker]['total_duration'] += seg.get('duration', 0)
        
        for speaker, stats in sorted(speaker_stats.items()):
            minutes = int(stats['total_duration'] // 60)
            seconds = int(stats['total_duration'] % 60)
            f.write(f"- **{stats['name']}**: {stats['count']} 段发言, 共 {minutes}分{seconds}秒\n")
    
    print(f"✅ 中文Markdown笔记已保存: {output_file}")
    return output_file


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="增强版 Whisper 转录工具 - 支持日语翻译成简体中文")
    
    parser.add_argument("input", help="音频文件路径")
    parser.add_argument("--speaker", action="store_true", help="启用说话者识别")
    parser.add_argument("--speaker-names", type=str, default="", help="自定义说话者名称，格式: '张三,李四'")
    parser.add_argument("--formats", type=str, default="txt,md", help="输出格式: txt,md")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录")
    
    args = parser.parse_args()
    
    # 解析说话者名称
    speaker_names = {}
    if args.speaker_names:
        names = args.speaker_names.split(',')
        for i, name in enumerate(names):
            speaker_names[f"SPEAKER_{i+1:02d}"] = name.strip()
    
    output_formats = [f.strip() for f in args.formats.split(',')]
    output_formats = [f for f in output_formats if f in SUPPORTED_FORMATS]
    if not output_formats:
        output_formats = ['txt', 'md']
    
    audio_file = args.input
    print(f"📁 使用本地文件: {audio_file}")
    print(f"🌐 将自动翻译为简体中文")
    
    # 转录
    print(f"\n✨ 正在转录...")
    try:
        import whisper
    except ImportError:
        print("\n❌ 需要安装 Whisper: pip3 install openai-whisper")
        return 1
    
    print(f"🎤 正在加载模型...")
    model = whisper.load_model('base')
    
    print(f"📝 正在转录...")
    result = model.transcribe(audio_file, language='ja', word_timestamps=True)
    print(f"✅ 转录完成！检测到语言: {result.get('language', 'unknown')}")
    
    # 说话者识别
    if args.speaker:
        result = improve_speaker_labels_simple(result)
    
    # 生成输出
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    base_name = Path(audio_file).stem
    output_files = []
    
    for fmt in output_formats:
        output_file = output_dir / f"{base_name}_中文.{fmt}"
        
        if fmt == 'txt':
            gen_file = generate_transcript_cn(result, str(output_file), speaker_names, True)
            output_files.append(gen_file)
        elif fmt == 'md':
            gen_file = generate_markdown_cn(result, str(output_file), speaker_names, True)
            output_files.append(gen_file)
    
    print("\n" + "="*70)
    print("🎉 完成！")
    print(f"📄 文件: {', '.join(str(f) for f in output_files)}")
    print("="*70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
