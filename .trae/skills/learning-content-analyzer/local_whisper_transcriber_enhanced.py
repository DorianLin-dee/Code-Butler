#!/usr/bin/env python3
"""
增强版 Whisper 转录工具 - 支持更好的说话者识别
结合 whisperx，提供专业的说话者识别、标点符号等功能
"""

import sys
import os
from pathlib import Path

# 全局配置
DEFAULT_MODEL = 'base'
SUPPORTED_FORMATS = ['txt', 'srt', 'vtt', 'json', 'md']


def is_bilibili(url):
    """判断是否是B站链接"""
    return 'bilibili.com' in url.lower()


def download_audio(url, output_dir='./audio_downloads'):
    """只下载音频，支持B站反爬虫"""
    import yt_dlp
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📥 正在下载音频...")
    
    if is_bilibili(url):
        print(f"🔧 检测到B站链接，启用反爬虫配置...")
        
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
            print(f"🍪 使用cookies文件: {cookie_file}")
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
            print(f"✅ 音频下载完成: {audio_file}")
            return str(audio_file)
        except Exception as e:
            if is_bilibili(url):
                print(f"\n⚠️ B站下载失败")
                return None
            else:
                raise e


def transcribe_with_whisperx(audio_path, model_size='base', language=None):
    """使用 whisperx 进行转录 - 更准确的说话者识别"""
    try:
        import whisperx
    except ImportError:
        print("\n⚠️ whisperx 未安装")
        print("💡 安装命令: pip3 install whisperx")
        return None
    
    print(f"\n🎙️ 使用 whisperx 进行转录...")
    
    device = "cpu"
    print(f"🎤 正在加载 Whisper {model_size} 模型...")
    model = whisperx.load_model(model_size, device)
    
    print(f"📝 正在转录...")
    audio = whisperx.load_audio(audio_path)
    
    if language:
        print(f"🔤 指定语言: {language}")
        result = model.transcribe(audio, language=language)
    else:
        print(f"🔤 自动检测语言...")
        result = model.transcribe(audio)
    
    print(f"✅ 转录完成！语言: {result.get('language', 'unknown')}")
    
    # 说话者识别
    print(f"🎙️ 正在进行说话者识别...")
    try:
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=False)
        diarize_segments = diarize_model(audio_path)
        result = whisperx.assign_word_speakers(diarize_segments, result)
        print(f"✅ 说话者识别完成！")
    except Exception as e:
        print(f"⚠️ 说话者识别失败: {e}")
    
    return result


def improve_speaker_labels_simple(result):
    """改进的简单说话者识别算法"""
    from collections import defaultdict
    
    segments = result.get('segments', [])
    if not segments:
        return result
    
    print(f"🎙️ 正在进行智能说话者分组...")
    
    # 计算特征
    for i, seg in enumerate(segments):
        if i > 0:
            prev_seg = segments[i-1]
            pause = seg.get('start', 0) - prev_seg.get('end', 0)
            seg['pause_before'] = pause
        else:
            seg['pause_before'] = 0
        
        duration = seg.get('end', 0) - seg.get('start', 0)
        seg['duration'] = duration
    
    # 智能分组
    speaker_counter = 1
    for i, seg in enumerate(segments):
        pause = seg.get('pause_before', 0)
        duration = seg.get('duration', 0)
        
        # 基于停顿时间的智能判断
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
            # 检查前一个说话者是否太短
            total_duration = sum(s.get('duration', 0) for s in smoothed[-5:]) if len(smoothed) >= 5 else sum(s.get('duration', 0) for s in smoothed)
            if total_duration < 2.0:
                # 合并到前一组
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


def generate_transcript(result, output_file, output_format='txt', speaker_names=None):
    """生成转录稿"""
    if speaker_names is None:
        speaker_names = {}
    
    if output_format == 'txt':
        with open(output_file, 'w', encoding='utf-8') as f:
            if 'segments' in result:
                for segment in result['segments']:
                    start_time = format_timestamp(segment.get('start', 0))
                    text = segment.get('text', '').strip()
                    speaker = segment.get('speaker', None)
                    
                    if text:
                        if speaker and speaker in speaker_names:
                            speaker_display = speaker_names[speaker]
                        elif speaker:
                            speaker_display = speaker
                        else:
                            speaker_display = None
                        
                        if speaker_display:
                            line = f"{start_time} - [{speaker_display}] {text}\n"
                        else:
                            line = f"{start_time} - {text}\n"
                        f.write(line)
            else:
                f.write(result['text'])
        
        print(f"✅ {output_format.upper()} 转录稿已保存: {output_file}")
        return output_file
    
    elif output_format == 'md':
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# 转录笔记\n\n")
            
            total_segments = len(result.get('segments', []))
            if total_segments > 0:
                duration = result['segments'][-1].get('end', 0)
                f.write(f"- **总片段数**: {total_segments}\n")
                f.write(f"- **总时长**: {format_timestamp(duration)}\n")
                if 'language' in result:
                    f.write(f"- **语言**: {result['language']}\n")
            f.write("\n---\n\n")
            
            if 'segments' in result:
                for segment in result['segments']:
                    start_time = format_timestamp(segment.get('start', 0))
                    text = segment.get('text', '').strip()
                    speaker = segment.get('speaker', None)
                    
                    if text:
                        if speaker and speaker in speaker_names:
                            speaker_display = speaker_names[speaker]
                        elif speaker:
                            speaker_display = speaker
                        else:
                            speaker_display = None
                        
                        if speaker_display:
                            f.write(f"**{start_time}** - [{speaker_display}] {text}\n\n")
                        else:
                            f.write(f"**{start_time}** - {text}\n\n")
        
        print(f"✅ {output_format.upper()} 笔记已保存: {output_file}")
        return output_file
    
    else:
        print(f"⚠️ 暂不支持 {output_format} 格式")
        return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="增强版 Whisper 转录工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("input", help="音频文件路径")
    parser.add_argument("--whisperx", action="store_true", help="使用 whisperx")
    parser.add_argument("--zh", dest="lang_zh", action="store_true", help="中文")
    parser.add_argument("--ja", dest="lang_ja", action="store_true", help="日语")
    parser.add_argument("--en", dest="lang_en", action="store_true", help="英语")
    parser.add_argument("--speaker", action="store_true", help="启用说话者识别")
    parser.add_argument("--speaker-names", type=str, default="", help="自定义说话者名称")
    parser.add_argument("--formats", type=str, default="txt", help="输出格式: txt,md")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录")
    
    args = parser.parse_args()
    
    # 确定语言
    language = None
    if args.lang_zh:
        language = 'zh'
    elif args.lang_ja:
        language = 'ja'
    elif args.lang_en:
        language = 'en'
    
    # 解析说话者名称
    speaker_names = {}
    if args.speaker_names:
        names = args.speaker_names.split(',')
        for i, name in enumerate(names):
            speaker_names[f"SPEAKER_{i+1:02d}"] = name.strip()
    
    # 输出格式
    output_formats = [f.strip() for f in args.formats.split(',')]
    output_formats = [f for f in output_formats if f in SUPPORTED_FORMATS]
    if not output_formats:
        output_formats = ['txt']
    
    audio_file = args.input
    print(f"📁 使用本地文件: {audio_file}")
    
    # 选择转录方法
    if args.whisperx:
        print(f"\n✨ 模式: whisperx")
        result = transcribe_with_whisperx(audio_file, language=language)
        if result is None:
            return 1
    else:
        print(f"\n✨ 模式: 基础 Whisper + 改进说话者识别")
        try:
            import whisper
        except ImportError:
            print("\n❌ 需要安装 Whisper: pip3 install openai-whisper")
            return 1
        
        print(f"🎤 正在加载模型...")
        model = whisper.load_model('base')
        
        print(f"📝 正在转录...")
        if language:
            result = model.transcribe(audio_file, language=language, word_timestamps=True)
        else:
            result = model.transcribe(audio_file, word_timestamps=True)
        
        if args.speaker:
            result = improve_speaker_labels_simple(result)
    
    # 生成输出
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    base_name = Path(audio_file).stem
    output_files = []
    
    for fmt in output_formats:
        output_file = output_dir / f"{base_name}.{fmt}"
        gen_file = generate_transcript(result, str(output_file), fmt, speaker_names)
        if gen_file:
            output_files.append(gen_file)
    
    print("\n" + "="*70)
    print("🎉 完成！")
    print(f"📄 文件: {', '.join(str(f) for f in output_files)}")
    print("="*70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
