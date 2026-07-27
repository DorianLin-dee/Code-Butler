#!/usr/bin/env python3
"""
学习内容分析 Pipeline - 豆包转录方案

完整工作流：
    1. 下载音频（B站/YouTube/本地文件）
    2. 用标题简化命名
    3. 搜索网络文稿，输出一版基于网络信息的转录稿
    4. 提示用户用豆包转录
    5. 处理豆包转录稿（格式化 + 说话者识别 + 词语校正）
    6. 生成 HTML 阅读页 + 思维导图

用法：
    python3 learning_pipeline.py <视频URL或音频文件>
    python3 learning_pipeline.py --process 豆包转录稿.txt [--speakers 张津剑,秦深涛]
    python3 learning_pipeline.py --html 处理后的转录稿.md
"""

import os
import sys
import re
import argparse
import subprocess
import webbrowser
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


def slugify_title(title, max_len=40):
    """将标题简化为安全的文件名

    - 去掉特殊字符，保留中英文，截取前 max_len 个字符
    """
    if not title:
        return 'transcript'

    result = title.strip()

    result = result.replace('：', '_').replace(':', '_')
    result = result.replace('【', '').replace('】', '')
    result = result.replace('「', '').replace('」', '')
    result = result.replace('『', '').replace('』', '')
    result = result.replace('（', '(').replace('）', ')')

    result = re.sub(r'[-|_]+', '_', result)
    result = re.sub(r'[\\/*?"<>|]', '', result)
    result = re.sub(r'\s+', '_', result)
    result = result.strip('_')

    if len(result) > max_len:
        result = result[:max_len].rstrip('_')

    if not result:
        result = 'transcript'

    return result


def extract_video_info(url):
    try:
        import yt_dlp

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', ''),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', ''),
                'duration': info.get('duration', 0),
                'webpage_url': info.get('webpage_url', url),
            }
    except Exception as e:
        print(f"⚠️ 获取视频信息失败: {e}")
        return {'title': '', 'description': '', 'uploader': '', 'webpage_url': url}


def extract_speakers_from_info(info):
    desc = info.get('description', '')
    title = info.get('title', '')
    combined = title + '\n' + desc

    speakers = []

    host_patterns = [
        r'主持[人]?[：:]\s*([\u4e00-\u9fa5]{2,4})',
        r'主播[：:]\s*([\u4e00-\u9fa5]{2,4})',
    ]
    for p in host_patterns:
        m = re.search(p, combined)
        if m:
            speakers.append(m.group(1))
            break

    guest_patterns = [
        r'嘉宾[：:]\s*([\u4e00-\u9fa5]{2,4}(?:[、,]\s*[\u4e00-\u9fa5]{2,4})*)',
        r'做客[：:]\s*([\u4e00-\u9fa5]{2,4}(?:[、,]\s*[\u4e00-\u9fa5]{2,4})*)',
    ]
    for p in guest_patterns:
        m = re.search(p, combined)
        if m:
            guests = re.split(r'[、,，]', m.group(1))
            speakers.extend([g.strip() for g in guests if g.strip()])
            break

    if not speakers:
        m = re.match(r'^([\u4e00-\u9fa5]{2,4})[：:]', title)
        if m:
            name = m.group(1)
            if name not in ('嘉宾', '专访', '对话', '对谈', '访谈', '完整版', '精华'):
                speakers.append(name)

    return speakers


def search_web_transcript(title, url):
    """搜索网络文稿（从 content_searcher 复用逻辑）

    Returns:
        list: [{title, url, content}]
    """
    try:
        from content_searcher import search_web_transcript, extract_content_from_url
    except ImportError:
        print("⚠️ 未找到 content_searcher.py，跳过网络搜索")
        return []

    print(f"\n🔍 搜索网络文稿...")

    results = search_web_transcript(title, url)

    if not results:
        print("   未找到网络文稿")
        return []

    print(f"   找到 {len(results)} 个候选结果")

    best_content = None
    best_source = None
    best_score = 0

    for r in results[:3]:
        content = extract_content_from_url(r['url'])
        if content and len(content) > 500:
            score = min(len(content) // 1000)
            print(f"   ✅ {r['title'][:40]}... ({len(content)}字)")
            if score > best_score:
                best_score = score
                best_content = content
                best_source = r
        else:
            print(f"   ❌ {r['title'][:40]}... (内容不足)")

    if best_content:
        return [{
            'title': best_source['title'],
            'url': best_source['url'],
            'content': best_content,
        }]

    return []


def generate_web_based_transcript(web_results, info, output_path):
    """生成基于网络信息的转录稿（文稿 + 章节信息 + 简介）

    Returns:
        str: 文件路径
    """
    lines = []

    title = info.get('title', '未知标题')
    lines.append(f"# {title}")
    lines.append("")

    if info.get('uploader'):
        lines.append(f"**来源**: {info['uploader']}")
        lines.append("")

    if info.get('webpage_url'):
        lines.append(f"**链接**: {info['webpage_url']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("> 📋 说明")
    lines.append("")
    lines.append("本文稿基于网络搜索信息整理，仅供参考。")
    lines.append("如需完整内容请以音频为准。")
    lines.append("")
    lines.append("---")
    lines.append("")

    if web_results:
        lines.append("## 网络文稿")
        lines.append("")
        for wr in web_results:
            lines.append(f"### 来源: {wr['title']}")
            lines.append(f"链接: {wr['url']}")
            lines.append("")
            lines.append(wr['content'][:5000])
            lines.append("")
            if len(wr['content']) > 5000:
                lines.append("... (内容过长，已截断)")
                lines.append("")
    else:
        lines.append("## 简介")
        lines.append("")
        desc = info.get('description', '')
        if desc:
            lines.append(desc[:2000])
        else:
            lines.append("（暂无简介）")
        lines.append("")

    if info.get('duration'):
        dur = info['duration']
        mins = dur // 60
        secs = dur % 60
        lines.append(f"**时长**: {mins}分{secs}秒")
        lines.append("")

    Path(output_path).write_text('\n'.join(lines), encoding='utf-8')
    return output_path


def download_audio(url, output_dir='./audio_downloads'):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        import yt_dlp

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id', '')
            mp3_path = os.path.join(output_dir, f"{video_id}.mp3")
            if os.path.exists(mp3_path):
                return mp3_path

            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith('.mp3'):
                    return os.path.join(output_dir, f)

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

    return None


def print_doubao_instructions(audio_path, output_dir='.'):
    print("\n" + "="*60)
    print("🎤 用豆包进行语音转录")
    print("="*60)
    print()
    print(f"📁 音频文件: {audio_path}")
    print()
    print("📌 操作步骤：")
    print()
    print("   1. 打开豆包网页版：")
    print("      🔗 https://www.doubao.com/chat/")
    print()
    print("   2. 登录您的豆包账号")
    print()
    print("   3. 把上面的音频文件拖进聊天窗口")
    print("      （支持 .mp3 .wav .m4a 等格式）")
    print()
    print("   4. 等待豆包完成转录（长音频约 2-5 分钟）")
    print()
    print("   5. 把转录结果复制保存为 .txt 文件")
    print(f"      建议保存到: {output_dir}/")
    print()
    print("="*60)
    print()
    print("💡 豆包转录完成后，运行以下命令继续处理：")
    print()
    print(f"   python3 {sys.argv[0]} --process 豆包转录稿.txt")
    print()

    try:
        webbrowser.open('https://www.doubao.com/chat/')
        print("🌐 已自动打开豆包网页版")
    except Exception:
        pass


def process_doubao_transcript(input_file, speakers=None, output_dir='.', base_name=None):
    script_path = SCRIPT_DIR / 'process_doubao_transcript.py'

    cmd = [sys.executable, str(script_path), input_file]

    if speakers:
        cmd.extend(['--speakers', speakers])

    if base_name:
        output_path = str(Path(output_dir) / f"{base_name}_processed.md")
    else:
        output_path = str(Path(output_dir) / f"{Path(input_file).stem}_processed.md")
    cmd.extend(['--output', output_path])

    print(f"\n🔧 处理豆包转录稿...")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0 and os.path.exists(output_path):
        print(f"\n✅ 处理完成: {output_path}")
        return output_path
    else:
        print(f"\n❌ 处理失败")
        return None


def generate_html(transcript_file, output_dir='.'):
    script_path = SCRIPT_DIR / 'dialogue_extractor.py'

    if not script_path.exists():
        print(f"⚠️ 未找到 dialogue_extractor.py，跳过 HTML 生成")
        return None

    cmd = [sys.executable, str(script_path), transcript_file, '--output-dir', output_dir]

    print(f"\n📊 生成 HTML 阅读页和思维导图...")

    result = subprocess.run(cmd, capture_output=False)

    html_files = list(Path(output_dir).glob('*.html'))
    if html_files:
        latest = max(html_files, key=lambda x: x.stat().st_mtime)
        print(f"\n✅ HTML 已生成: {latest}")
        return str(latest)
    else:
        print(f"\n⚠️ 未找到生成的 HTML 文件")
        return None


def step1_download_and_prepare(url, output_dir='./output'):
    """步骤 1：下载音频 + 搜索网络文稿 + 准备"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("📥 步骤 1：下载音频并准备")
    print("="*60)

    if Path(url).is_file():
        audio_path = url
        info = {'title': Path(url).stem, 'description': '', 'uploader': '', 'webpage_url': ''}
        print(f"📁 使用本地文件: {audio_path}")
    else:
        print(f"🔍 获取视频信息...")
        info = extract_video_info(url)
        if info['title']:
            print(f"📺 标题: {info['title']}")
        if info['uploader']:
            print(f"👤 UP主: {info['uploader']}")
        if info['duration']:
            dur = info['duration']
            print(f"⏱️  时长: {dur//60}分{dur%60}秒")

        print(f"\n⬇️ 下载音频...")
        audio_path = download_audio(url, output_dir=os.path.join(output_dir, 'audio'))
        if not audio_path:
            print("❌ 下载失败")
            return

    base_name = slugify_title(info.get('title', ''))
    print(f"\n📝 文件命名: {base_name}")

    speakers = extract_speakers_from_info(info)
    if speakers:
        print(f"👥 识别到说话者: {', '.join(speakers)}")

    transcript_dir = os.path.join(output_dir, 'transcripts')
    Path(transcript_dir).mkdir(parents=True, exist_ok=True)

    web_results = []
    if info.get('title') and info.get('webpage_url'):
        web_results = search_web_transcript(info['title'], info['webpage_url'])

    web_transcript_path = os.path.join(transcript_dir, f"{base_name}_web.md")
    if web_results:
        generate_web_based_transcript(web_results, info, web_transcript_path)
        print(f"\n📄 基于网络信息的文稿: {web_transcript_path}")
        print(f"   来源: {web_results[0]['title'][:50]}...")
    else:
        generate_web_based_transcript([], info, web_transcript_path)
        print(f"\n📄 基于简介版文稿已生成: {web_transcript_path}")
        print("   （网络搜索未找到完整文稿，仅包含简介信息）")

    print_doubao_instructions(audio_path, transcript_dir)

    print("\n" + "="*60)
    print("📋 已准备好的文件：")
    print(f"   音频文件: {audio_path}")
    print(f"   网络版文稿: {web_transcript_path}")
    if speakers:
        print(f"   说话者: {', '.join(speakers)}")
    print(f"   转录稿目录: {transcript_dir}/")
    print("="*60)
    print()
    print("💡 豆包转录完成后，运行：")
    speaker_arg = f"--speakers '{','.join(speakers)}'" if speakers else ""
    print(f"   python3 {sys.argv[0]} --process {{转录稿.txt}} {speaker_arg}")
    print()
    print("💡 或者直接处理并生成HTML：")
    print(f"   python3 {sys.argv[0]} --process {{转录稿.txt}} {speaker_arg}")


def step2_process(transcript_file, speakers=None, output_dir='./output'):
    """步骤 2：处理豆包转录稿 + 生成 HTML"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    processed = process_doubao_transcript(transcript_file, speakers, output_dir)
    if not processed:
        return

    html = generate_html(processed, output_dir)
    if html:
        print(f"\n🎉 全部完成！")
        print(f"   转录稿: {processed}")
        print(f"   HTML: {html}")
        print()
        print("🌐 在浏览器中打开 HTML 查看思维导图和分析")


def main():
    parser = argparse.ArgumentParser(
        description='学习内容分析 Pipeline - 豆包转录方案',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 步骤1：下载音频 + 搜索网络文稿 + 准备豆包转录
  python3 learning_pipeline.py "https://www.bilibili.com/video/BVxxx"

  # 步骤2：处理豆包转录稿并生成HTML
  python3 learning_pipeline.py --process transcript.txt --speakers "张津剑,秦深涛"

  # 只生成HTML
  python3 learning_pipeline.py --html processed.md
        """
    )
    parser.add_argument('url', nargs='?', help='视频URL或本地音频文件')
    parser.add_argument('--output-dir', '-o', default='./output', help='输出目录')
    parser.add_argument('--process', help='处理豆包转录稿（.txt 文件）')
    parser.add_argument('--html', help='为已处理的转录稿生成 HTML')
    parser.add_argument('--speakers', help='说话者姓名，逗号分隔')

    args = parser.parse_args()

    if args.html:
        generate_html(args.html, args.output_dir)
    elif args.process:
        step2_process(args.process, args.speakers, args.output_dir)
    elif args.url:
        step1_download_and_prepare(args.url, args.output_dir)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
