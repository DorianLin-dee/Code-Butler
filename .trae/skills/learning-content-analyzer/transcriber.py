#!/usr/bin/env python3
"""
视频转录工具 - 支持 Whisper API 和本地 Whisper 转录
支持 B站视频下载和自动转录

推荐转录方式：豆包语音识别（https://www.doubao.com/chat/）
处理豆包转录稿：python3 process_doubao_transcript.py 转录稿.txt
"""

import os
import sys
import argparse
from pathlib import Path


def install_dependencies():
    """检查并提示安装依赖"""
    required = ['yt-dlp']

    print("正在检查依赖...")
    
    for package in required:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"❌ 缺少必要依赖: {package}")
            print(f"请运行: pip install {package}")
            sys.exit(1)
    
    print("✅ 必要依赖已安装")


def download_bilibili_video(url, output_dir='./downloads'):
    """下载B站视频"""
    import yt_dlp
    
    os.makedirs(output_dir, exist_ok=True)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': False,
    }
    
    print(f"📥 正在下载视频: {url}")
    print(f"📁 保存到: {output_dir}")
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        audio_path = ydl.prepare_filename(info)
        audio_path = Path(audio_path).with_suffix('.mp3')
        
    print(f"✅ 下载完成: {audio_path}")
    return str(audio_path)


def transcribe_with_whisper_api(audio_path, api_key=None, model='whisper-1'):
    """使用 OpenAI Whisper API 转录"""
    import openai
    
    if api_key:
        openai.api_key = api_key
    elif not os.getenv('OPENAI_API_KEY'):
        print("❌ 请设置 OPENAI_API_KEY 环境变量")
        print("或修改脚本中的 api_key 参数")
        sys.exit(1)
    
    print(f"🎤 正在使用 Whisper API 转录: {audio_path}")
    print(f"📝 使用模型: {model}")
    
    with open(audio_path, 'rb') as audio_file:
        transcript = openai.Audio.transcribe(
            model=model,
            file=audio_file,
            response_format='verbose_json',
            timestamp_granularities=['segment']
        )
    
    return transcript


def transcribe_with_local_whisper(audio_path, model='base'):
    """使用本地 Whisper 转录"""
    import whisper

    print(f"🎤 正在加载本地 Whisper 模型: {model}")
    model = whisper.load_model(model)

    print(f"📝 正在转录: {audio_path}")
    result = model.transcribe(audio_path, word_timestamps=True)

    return result


def format_timestamp(seconds):
    """将秒数转换为 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def generate_transcript_with_timestamps(result, output_file='transcript.txt'):
    """生成带时间戳的转录稿"""
    print(f"📝 正在生成转录稿...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        if 'segments' in result:
            for segment in result['segments']:
                start_time = format_timestamp(segment.get('start', 0))
                text = segment.get('text', '').strip()
                if text:
                    f.write(f"{start_time} - {text}\n")
                    print(f"  {start_time} - {text[:50]}...")
        else:
            f.write(result['text'])
            print(f"  {result['text'][:100]}...")
    
    print(f"✅ 转录稿已生成: {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description='视频转录工具 - 支持 B站视频下载和多种转录方式'
    )
    parser.add_argument('url', help='B站视频URL或本地音频文件路径')
    parser.add_argument('-o', '--output', default='transcript.txt', help='输出文件路径')
    parser.add_argument('-m', '--model', default='base', 
                       choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='本地 Whisper 模型大小 (默认: base)')
    parser.add_argument('--api', action='store_true', help='使用 OpenAI Whisper API')
    parser.add_argument('--api-key', help='OpenAI API Key (或设置 OPENAI_API_KEY 环境变量)')
    parser.add_argument('--local', action='store_true', help='使用本地 Whisper')
    parser.add_argument('--download-dir', default='./downloads', help='下载目录')
    
    args = parser.parse_args()
    
    install_dependencies()
    
    audio_path = None
    
    if args.url:
        if 'bilibili.com' in args.url:
            audio_path = download_bilibili_video(args.url, args.download_dir)
        else:
            audio_path = args.url
    
    if not audio_path:
        print("❌ 请提供视频URL或本地音频文件路径")
        sys.exit(1)
    
    if args.api:
        result = transcribe_with_whisper_api(
            audio_path,
            api_key=args.api_key
        )
    else:
        result = transcribe_with_local_whisper(
            audio_path,
            model=args.model
        )

    if result is None:
        print("❌ 转录失败")
        sys.exit(1)

    output_file = generate_transcript_with_timestamps(result, args.output)

    print("\n" + "="*50)
    print(f"🎉 转录完成！")
    print(f"📄 转录稿: {output_file}")
    print("💡 提示: 推荐使用豆包转录（https://www.doubao.com/chat/）获得更高准确率")
    print("="*50)


if __name__ == '__main__':
    main()

