#!/usr/bin/env python3
"""
学习内容分析 Pipeline - 豆包转录方案

完整工作流：
    1. 下载音频（B站/YouTube/本地文件）
    2. 自动分配序号 + 标题简化命名，创建独立文件夹
    3. 搜索网络文稿，输出一版基于网络信息的转录稿
    4. 提示用户用豆包转录
    5. 处理豆包转录稿（格式化 + 说话者识别 + 词语校正）
    6. 生成 HTML 阅读页 + 思维导图

文件夹结构：
    output/
    ├── 01_秦深涛_神经接口的下一个十年/
    │   ├── audio.mp3
    │   ├── transcript_web.md
    │   ├── transcript_processed.md
    │   ├── analysis.html
    │   ├── key_points.md
    │   └── mindmap.md
    ├── 02_张一鸣_字节跳动创业故事/
    │   └── ...

用法：
    python3 learning_pipeline.py <视频URL或音频文件> [--output-dir ./output]
    python3 learning_pipeline.py --process 豆包转录稿.txt [--folder 01_xxx] [--speakers 张津剑,秦深涛]
    python3 learning_pipeline.py --html 转录稿.md [--folder 01_xxx]
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


def get_next_index(output_dir):
    """扫描输出目录，获取下一个序号

    扫描所有 NN_ 开头的文件夹，返回最大序号 + 1
    序号从 01 开始
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return 1

    max_idx = 0
    for item in output_path.iterdir():
        if item.is_dir():
            m = re.match(r'^(\d{2})_', item.name)
            if m:
                idx = int(m.group(1))
                if idx > max_idx:
                    max_idx = idx

    return max_idx + 1


def create_transcript_folder(output_dir, title_slug):
    """创建转录独立文件夹，自动分配序号

    Returns:
        Path: 文件夹路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    idx = get_next_index(output_dir)
    folder_name = f"{idx:02d}_{title_slug}"
    folder_path = output_path / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)

    return folder_path


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


def download_audio(url, output_folder):
    """下载音频到指定文件夹

    Args:
        url: 视频URL或本地文件路径
        output_folder: 输出文件夹路径

    Returns:
        str: 音频文件路径
    """
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)

    if Path(url).is_file():
        import shutil
        src = Path(url)
        dst = folder / f"audio{src.suffix}"
        shutil.copy2(src, dst)
        return str(dst)

    try:
        import yt_dlp

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(folder / 'audio.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        mp3_path = folder / 'audio.mp3'
        if mp3_path.exists():
            return str(mp3_path)

        for f in folder.iterdir():
            if f.name.startswith('audio') and f.suffix in ('.mp3', '.wav', '.m4a', '.webm'):
                return str(f)

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

    return None


def print_doubao_instructions(audio_path, folder_path):
    print("\n" + "="*60)
    print("🎤 用豆包进行语音转录")
    print("="*60)
    print()
    print(f"📁 音频文件: {audio_path}")
    print(f"📂 项目文件夹: {folder_path}")
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
    print(f"   5. 把转录结果保存为 doubao_transcript.txt")
    print(f"      放到项目文件夹: {folder_path}/")
    print()
    print("="*60)
    print()
    print("💡 豆包转录完成后，运行以下命令继续处理：")
    print()
    print(f"   python3 {sys.argv[0]} --process {folder_path}/doubao_transcript.txt")
    print()

    try:
        webbrowser.open('https://www.doubao.com/chat/')
        print("🌐 已自动打开豆包网页版")
    except Exception:
        pass


def process_doubao_transcript(input_file, speakers=None, folder_path=None):
    """处理豆包转录稿

    Args:
        input_file: 豆包转录稿路径
        speakers: 说话者姓名，逗号分隔
        folder_path: 输出文件夹（默认使用输入文件所在目录）

    Returns:
        str: 处理后的文件路径
    """
    script_path = SCRIPT_DIR / 'process_doubao_transcript.py'

    if folder_path is None:
        folder_path = Path(input_file).parent
    folder_path = Path(folder_path)
    folder_path.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(script_path), input_file]

    if speakers:
        cmd.extend(['--speakers', speakers])

    output_path = str(folder_path / 'transcript_processed.md')
    cmd.extend(['--output', output_path])

    print(f"\n🔧 处理豆包转录稿...")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0 and os.path.exists(output_path):
        print(f"\n✅ 处理完成: {output_path}")
        return output_path
    else:
        print(f"\n❌ 处理失败")
        return None


def generate_html(transcript_file, folder_path=None):
    """生成 HTML 阅读页和思维导图

    Args:
        transcript_file: 转录稿路径
        folder_path: 输出文件夹（默认使用输入文件所在目录）

    Returns:
        str: HTML 文件路径
    """
    script_path = SCRIPT_DIR / 'dialogue_extractor.py'

    if not script_path.exists():
        print(f"⚠️ 未找到 dialogue_extractor.py，跳过 HTML 生成")
        return None

    if folder_path is None:
        folder_path = Path(transcript_file).parent
    folder_path = Path(folder_path)

    cmd = [sys.executable, str(script_path), transcript_file, '--output-dir', str(folder_path)]

    print(f"\n📊 生成 HTML 阅读页和思维导图...")

    result = subprocess.run(cmd, capture_output=False)

    html_files = list(folder_path.glob('*.html'))
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
        audio_path_input = url
        info = {'title': Path(url).stem, 'description': '', 'uploader': '', 'webpage_url': ''}
        print(f"📁 使用本地文件: {audio_path_input}")
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
        audio_path_input = url

    title_slug = slugify_title(info.get('title', ''))
    folder_path = create_transcript_folder(output_dir, title_slug)
    print(f"\n📂 项目文件夹: {folder_path.name}")
    print(f"   完整路径: {folder_path}")

    speakers = extract_speakers_from_info(info)
    if speakers:
        print(f"👥 识别到说话者: {', '.join(speakers)}")

    print(f"\n⬇️ 下载音频...")
    audio_path = download_audio(audio_path_input, folder_path)
    if not audio_path:
        print("❌ 下载失败")
        return

    print(f"   音频已保存: {audio_path}")

    web_results = []
    if info.get('title') and info.get('webpage_url'):
        web_results = search_web_transcript(info['title'], info['webpage_url'])

    web_transcript_path = folder_path / 'transcript_web.md'
    if web_results:
        generate_web_based_transcript(web_results, info, str(web_transcript_path))
        print(f"\n📄 网络版文稿: {web_transcript_path.name}")
        print(f"   来源: {web_results[0]['title'][:50]}...")
    else:
        generate_web_based_transcript([], info, str(web_transcript_path))
        print(f"\n📄 简介版文稿: {web_transcript_path.name}")
        print("   （网络搜索未找到完整文稿，仅包含简介信息）")

    print_doubao_instructions(audio_path, folder_path)

    print("\n" + "="*60)
    print("📋 项目文件夹内容：")
    print(f"   📁 {folder_path.name}/")
    for item in sorted(folder_path.iterdir()):
        if item.is_file():
            size_kb = item.stat().st_size // 1024
            print(f"      └── {item.name}  ({size_kb}KB)")
    print("="*60)
    print()
    print("💡 豆包转录完成后，运行：")
    speaker_arg = f"--speakers '{','.join(speakers)}'" if speakers else ""
    print(f"   python3 {sys.argv[0]} --process {folder_path}/doubao_transcript.txt {speaker_arg}")


def step2_process(transcript_file, speakers=None, folder=None):
    """步骤 2：处理豆包转录稿 + 生成 HTML"""
    if folder:
        folder_path = Path(folder)
    else:
        folder_path = Path(transcript_file).parent

    folder_path.mkdir(parents=True, exist_ok=True)

    processed = process_doubao_transcript(transcript_file, speakers, folder_path)
    if not processed:
        return

    html = generate_html(processed, folder_path)
    if html:
        print(f"\n🎉 全部完成！")
        print(f"   📁 项目文件夹: {folder_path}")
        print(f"   📄 转录稿: {Path(processed).name}")
        print(f"   🌐 HTML: {Path(html).name}")
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

  # 步骤2：处理豆包转录稿并生成HTML（输出到同一文件夹）
  python3 learning_pipeline.py --process 01_xxx/doubao_transcript.txt --speakers "张津剑,秦深涛"

  # 只生成HTML
  python3 learning_pipeline.py --html transcript_processed.md

文件夹结构：
  output/
  ├── 01_秦深涛_神经接口的下一个十年/
  │   ├── audio.mp3
  │   ├── transcript_web.md
  │   ├── transcript_processed.md
  │   ├── analysis.html
  │   ├── key_points.md
  │   └── mindmap.md
  └── 02_xxx/
        """
    )
    parser.add_argument('url', nargs='?', help='视频URL或本地音频文件')
    parser.add_argument('--output-dir', '-o', default='./output', help='输出根目录（默认 ./output）')
    parser.add_argument('--process', help='处理豆包转录稿（.txt 文件）')
    parser.add_argument('--html', help='为已处理的转录稿生成 HTML')
    parser.add_argument('--folder', help='指定输出文件夹（默认自动创建）')
    parser.add_argument('--speakers', help='说话者姓名，逗号分隔')

    args = parser.parse_args()

    if args.html:
        generate_html(args.html, args.folder)
    elif args.process:
        step2_process(args.process, args.speakers, args.folder)
    elif args.url:
        step1_download_and_prepare(args.url, args.output_dir)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
