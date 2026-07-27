#!/usr/bin/env python3
"""
在线 Whisper API 转录工具 - 最简单的版本
直接使用 OpenAI Whisper API 转录视频/音频
"""

import sys
import os
import requests
import yt_dlp
import tempfile
from pathlib import Path

def download_audio_only(url, output_dir='./audio_downloads'):
    """只下载音频，不下载视频"""
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📥 正在下载音频...")
    
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
        info = ydl.extract_info(url, download=True)
        audio_file = Path(output_dir) / f"{info['id']}.mp3"
    
    print(f"✅ 音频下载完成: {audio_file}")
    return str(audio_file)

def transcribe_with_whisper_api(audio_path, api_key):
    """使用 OpenAI Whisper API 转录"""
    print(f"🎤 正在使用 Whisper API 转录...")
    
    url = "https://api.openai.com/v1/audio/transcriptions"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    files = {
        "file": open(audio_path, "rb")
    }
    
    data = {
        "model": "whisper-1",
        "response_format": "verbose_json",
        "language": "zh",
        "timestamp_granularities": ["segment"]
    }
    
    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        result = response.json()
        print(f"✅ 转录成功！")
        return result
    except Exception as e:
        print(f"❌ 转录失败: {e}")
        sys.exit(1)

def format_timestamp(seconds):
    """将秒数转换为 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def generate_transcript(result, output_file='transcript.txt'):
    """生成带时间戳的转录稿"""
    with open(output_file, 'w', encoding='utf-8') as f:
        if 'segments' in result:
            for segment in result['segments']:
                start_time = format_timestamp(segment.get('start', 0))
                text = segment.get('text', '').strip()
                if text:
                    f.write(f"{start_time} - {text}\n")
                    print(f"  {start_time} - {text[:60]}...")
        else:
            f.write(result['text'])
            print(result['text'])
    
    print(f"\n✅ 转录稿已保存: {output_file}")
    return output_file

def main():
    if len(sys.argv) < 2:
        print("用法: python whisper_api_transcriber.py <视频链接>")
        print("示例: python whisper_api_transcriber.py https://www.bilibili.com/video/BV1Z9QABeEgf")
        sys.exit(1)
    
    # 检查 API Key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("\n❌ 未找到 OpenAI API Key！")
        print("\n请按以下步骤操作：")
        print("1. 访问: https://platform.openai.com/api-keys")
        print("2. 注册/登录账号")
        print("3. 创建新的 API Key")
        print("4. 运行: export OPENAI_API_KEY='你的APIKey'")
        print("5. 或在命令中: OPENAI_API_KEY='你的APIKey' python whisper_api_transcriber.py <视频链接>")
        sys.exit(1)
    
    video_url = sys.argv[1]
    
    # 第一步：下载音频
    audio_file = download_audio_only(video_url)
    
    # 第二步：使用 API 转录
    result = transcribe_with_whisper_api(audio_file, api_key)
    
    # 第三步：生成带时间戳的转录稿
    transcript_file = generate_transcript(result)
    
    print("\n" + "="*60)
    print("🎉 全部完成！")
    print(f"📄 转录稿: {transcript_file}")
    print(f"💡 提示: 现在可以把转录稿发给 learning-content-analyzer skill 分析了！")
    print("="*60)

if __name__ == '__main__':
    main()
