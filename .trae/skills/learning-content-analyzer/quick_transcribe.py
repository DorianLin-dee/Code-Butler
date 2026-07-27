
#!/usr/bin/env python3
"""
快速转录工具 - 在当前工作目录保存结果
先搜索网上文稿，有的话先展示再问是否转录
完全免费，不需要 API Key，使用本地 Whisper
"""

import sys
import os
from pathlib import Path

# 自动添加 skill 目录到 Python 路径
SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

def search_transcript_first(url, surname=''):
    """先尝试搜索网上文稿"""
    try:
        from content_searcher import extract_video_info, search_web_transcript, extract_content_from_url, format_transcript_with_timestamps, save_transcript, extract_surname_from_title

        print(f"\n🔍 第一步：搜索网上文稿...")
        
        video_info = extract_video_info(url)

        # 如果用户没有手动指定姓氏，从标题自动提取
        if not surname and video_info.get('title'):
            auto_surname = extract_surname_from_title(video_info['title'])
            if auto_surname:
                surname = auto_surname
                print(f"🏷️ 从标题提取受访者姓氏: {surname}（来源: {video_info['title']}）")

        search_results = search_web_transcript(video_info['title'], video_info['url'])
        
        if search_results:
            print(f"\n✅ 找到 {len(search_results)} 个可能的文稿来源:")
            print("-" * 70)
            for i, result in enumerate(search_results, 1):
                print(f"{i}. {result['title'][:60]}...")
            
            found_content = None
            for result in search_results[:3]:
                content = extract_content_from_url(result['url'])
                if content:
                    print(f"\n🎉 成功获取文稿内容! (约 {len(content)} 字符)")
                    found_content = content
                    break
            
            if found_content:
                formatted = format_transcript_with_timestamps(found_content)
                if formatted:
                    current_dir = Path.cwd()
                    output_file = save_transcript(formatted, current_dir, surname)

                    # 自动校正 + 对话段落式格式化
                    try:
                        SKILL_DIR = Path(__file__).parent
                        if str(SKILL_DIR) not in sys.path:
                            sys.path.insert(0, str(SKILL_DIR))
                        from transcript_corrector import correct_transcript, reformat_transcript
                        print(f"\n🔧 自动校正 + 格式化...")

                        # 1. 校正
                        corrected, total, details = correct_transcript(
                            formatted, title=video_info.get('title', ''), keywords=None
                        )
                        if total > 0:
                            print(f"   ✅ 校正 {total} 处")
                            for desc, info, cnt in details:
                                print(f"      - {desc}: {cnt} 处")

                        # 2. 对话段落式 + 说话者识别
                        reformatted, speakers = reformat_transcript(
                            corrected, title=video_info.get('title', '')
                        )
                        if speakers:
                            print(f"   🎤 识别到说话者: {speakers}")

                        # 保存最终版本
                        Path(output_file).write_text(reformatted, encoding='utf-8')
                        formatted = reformatted
                    except Exception as e:
                        print(f"⚠️ 自动校正/格式化失败: {e}")

                    print("\n" + "=" * 70)
                    print("✅ 网上文稿已获取!")
                    print("=" * 70)
                    print("\n文稿预览:")
                    print("-" * 70)
                    preview_lines = formatted.split('\n')[:20]
                    print('\n'.join(preview_lines))
                    if len(preview_lines) < len(formatted.split('\n')):
                        print(f"... (更多内容请查看 {output_file})")

                    return {
                        'found': True,
                        'file': output_file,
                        'content': formatted
                    }
            else:
                print("\n⚠️ 找到一些链接，但未能提取到可用的文稿内容")
        else:
            print("\n❌ 未找到现成文稿")
        
        return {'found': False}
    except Exception as e:
        print(f"\n⚠️ 文稿搜索出错: {e}")
        return {'found': False}

def do_transcription(video_url, model_size='base', language=None, speaker_diarization=False, surname=''):
    """执行转录"""
    from local_whisper_transcriber import download_audio, transcribe_local, generate_transcript
    from content_searcher import generate_transcript_filename, extract_surname_from_title

    current_dir = Path.cwd()
    audio_dir = current_dir / 'audio_downloads'

    # 如果用户没有手动指定姓氏，尝试从视频标题自动提取
    if not surname and (video_url.startswith('http://') or video_url.startswith('https://')):
        try:
            import yt_dlp
            ydl_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                title = info.get('title', '')
                if title:
                    auto_surname = extract_surname_from_title(title)
                    if auto_surname:
                        surname = auto_surname
                        print(f"🏷️ 从标题提取受访者姓氏: {surname}（来源: {title}）")
        except Exception:
            pass  # 提取失败不影响主流程

    transcript_file = generate_transcript_filename(current_dir, surname)

    print(f"\n📂 工作目录: {current_dir}")
    print(f"📄 转录文件: {transcript_file}")

    # 检测是否是B站
    is_bilibili = 'bilibili.com' in video_url.lower()
    if is_bilibili:
        print(f"🔧 检测到B站链接，将启用反爬虫配置...")

    # 第一步：下载音频（如果是URL）
    if video_url.startswith('http://') or video_url.startswith('https://'):
        audio_file = download_audio(video_url, output_dir=str(audio_dir))
        if not audio_file:
            print("\n❌ 音频下载失败，无法继续转录")
            print("\n💡 可能的解决方案:")
            print("1. B站视频需要登录状态才能下载")
            print("   - 方法1: 使用浏览器插件导出cookies到 ~/.bilibili_cookies.txt")
            print("   - 方法2: 登录后手动下载视频，然后使用本地文件路径")
            print("2. 其他平台视频可以尝试更换网络环境")
            return None
    else:
        # 本地文件
        audio_file = video_url
        print(f"📁 使用本地文件: {audio_file}")

    # 第二步：本地转录
    result = transcribe_local(audio_file, model_size, language, speaker_diarization)

    # 第三步：生成带时间戳的转录稿（在当前目录）
    transcript_file = generate_transcript(result, output_file=str(transcript_file))

    # 第四步：自动校正（A+B 方案，秒级）
    try:
        SKILL_DIR = Path(__file__).parent
        if str(SKILL_DIR) not in sys.path:
            sys.path.insert(0, str(SKILL_DIR))
        from transcript_corrector import correct_transcript
        print(f"\n🔧 自动校正转录稿（字典+专有名词）...")
        text = Path(transcript_file).read_text(encoding='utf-8')
        # 标题作为校正依据（提取专有名词），与转录前一致
        correct_title = video_url if video_url.startswith('http') else ''
        corrected, total, details = correct_transcript(text, title=correct_title, keywords=None)
        if total > 0:
            Path(transcript_file).write_text(corrected, encoding='utf-8')
            print(f"   ✅ 校正 {total} 处")
            for desc, info, cnt in details:
                print(f"      - {desc}: {cnt} 处")
        else:
            print(f"   ✅ 无需校正")
    except Exception as e:
        print(f"⚠️ 自动校正失败: {e}")

    return transcript_file


def auto_extract_content(transcript_file, title=''):
    """自动提炼对话内容（生成 HTML + 思维导图 + 金句）

    如果是对话式转录稿（有说话者），自动调用 dialogue_extractor
    """
    try:
        from dialogue_extractor import extract_dialogue_content, parse_dialogue_transcript

        # 先检查是不是对话式转录稿
        text = Path(transcript_file).read_text(encoding='utf-8')
        paragraphs = parse_dialogue_transcript(text)

        if len(paragraphs) < 2:
            print(f"⚠️  不是对话式转录稿，跳过内容提炼")
            return None

        if not title:
            # 从文件名生成标题
            base = Path(transcript_file).stem
            title = base.replace('_', ' ').replace('transcript', '').strip()
            if not title:
                title = '对话内容提炼'

        print(f"\n📊 正在提炼核心观点...")
        result = extract_dialogue_content(
            str(transcript_file),
            title=title,
            output_dir=str(Path(transcript_file).parent)
        )

        if result:
            print(f"   ✅ HTML: {result['html_file']}")
            print(f"   ✅ Markdown: {result['md_file']}")
            print(f"   ✅ 思维导图: {result['mindmap_file']}")
            print(f"   💡 {len(result['points'])} 个观点 · {len(result['quotes'])} 条金句 · {len(result['modules'])} 个模块")
        return result
    except Exception as e:
        print(f"⚠️  内容提炼失败: {e}")
        return None


def main():
    print("=" * 70)
    print("🎬 视频/音频智能获取工具")
    print("   先搜索网上文稿 → 找到展示 → 询问是否转录")
    print("=" * 70)
    
    if len(sys.argv) < 2:
        print("\n用法: python3 quick_transcribe.py <视频链接或本地文件路径> [--name 姓]")
        print("\n示例:")
        print("  python3 quick_transcribe.py https://www.bilibili.com/video/BV1Z9QABeEgf")
        print("  python3 quick_transcribe.py /Users/dorian/video.mp3 --speaker --name xie")
        print("\n可选参数:")
        print("  --name 姓     - 受访者/作者姓氏，用于文件命名（如 --name xie → transcript_1_xie.txt）")
        print("  --skip-search - 直接转录，不搜索文稿")
        print("  --zh, --cn    - 指定为中文")
        print("  --ja, --jp    - 指定为日语")
        print("  --en, --eng   - 指定为英语")
        print("  --speaker, --diarize - 启用说话者识别（区分不同说话者）")
        print("  --extract, --analysis - 转录后自动提炼核心观点（生成HTML/思维导图/金句）")
        print("  --title '标题'   - 提炼内容的标题（配合 --extract 使用）")
        print("  --tiny        - 最快，但准确率最低（约 32MB）")
        print("  --base        - 推荐日常使用（约 150MB，默认）")
        print("  --small       - 更准确，但更慢（约 500MB）")
        print("  --medium      - 非常准确，但很慢（约 1.5GB）")
        sys.exit(1)
    
    # 解析参数
    # 找到URL参数（不是以--开头的参数）
    video_url = None
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            video_url = arg
            break
    
    if not video_url:
        print("\n❌ 请提供视频链接或本地文件路径！")
        sys.exit(1)
    
    model_size = 'base'
    skip_search = '--skip-search' in sys.argv
    language = None
    speaker_diarization = False
    surname = ''
    auto_extract = False
    extract_title = ''

    # 解析 --name 参数（受访者/作者姓氏，用于文件命名）
    if '--name' in sys.argv:
        idx = sys.argv.index('--name')
        if idx + 1 < len(sys.argv):
            surname = sys.argv[idx + 1]
    
    # 语言参数
    if '--zh' in sys.argv or '--cn' in sys.argv or '--chinese' in sys.argv:
        language = 'zh'
    elif '--ja' in sys.argv or '--jp' in sys.argv or '--japanese' in sys.argv:
        language = 'ja'
    elif '--en' in sys.argv or '--eng' in sys.argv or '--english' in sys.argv:
        language = 'en'
    
    # 说话者识别参数
    if '--speaker' in sys.argv or '--diarize' in sys.argv:
        speaker_diarization = True
        print(f"🎙️ 已启用说话者识别")
    
    # 内容提炼参数
    if '--extract' in sys.argv or '--analysis' in sys.argv:
        auto_extract = True
        print(f"📊 转录后自动提炼核心观点")
    
    if '--title' in sys.argv:
        idx = sys.argv.index('--title')
        if idx + 1 < len(sys.argv):
            extract_title = sys.argv[idx + 1]
    
    if '--tiny' in sys.argv:
        model_size = 'tiny'
    elif '--small' in sys.argv:
        model_size = 'small'
    elif '--medium' in sys.argv:
        model_size = 'medium'
    
    # 如果是本地文件，直接转录
    is_url = video_url.startswith('http://') or video_url.startswith('https://')
    
    if not is_url:
        print(f"\n📁 本地文件，直接转录")
        transcript_file = do_transcription(video_url, model_size, language, speaker_diarization, surname)
        
        # 自动提炼内容
        if auto_extract and transcript_file:
            auto_extract_content(transcript_file, extract_title)
        
        print("\n" + "=" * 70)
        print("🎉 全部完成！")
        print(f"📄 转录稿: {transcript_file}")
        print(f"💡 下一步: 打开 {transcript_file} 整理格式，然后提供给学习内容分析助手！")
        print("=" * 70)
        return

    # 先搜索文稿（除非指定跳过）
    if not skip_search:
        search_result = search_transcript_first(video_url, surname)
        
        if search_result.get('found'):
            print("\n" + "=" * 70)
            print("💬 网上文稿已获取!")
            print("=" * 70)
            print("\n你可以:")
            print("1. 直接使用这个文稿（推荐）")
            print("2. 还是进行转录")
            
            try:
                choice = input("\n请选择 (1 直接使用 / 2 转录，默认 1): ").strip()
                if choice == '2':
                    print("\n🔄 开始转录...")
                    transcript_file = do_transcription(video_url, model_size, language, speaker_diarization, surname)
                    
                    # 自动提炼内容
                    if auto_extract and transcript_file:
                        auto_extract_content(transcript_file, extract_title)
                    
                    print("\n" + "=" * 70)
                    print("🎉 转录完成！")
                    print(f"📄 转录稿: {transcript_file}")
                    print(f"💡 下一步: 打开 {transcript_file} 整理格式，然后提供给学习内容分析助手！")
                    print("=" * 70)
                else:
                    print("\n✅ 使用网上文稿完成!")
                    print(f"📄 文稿文件: {search_result['file']}")
                    
                    # 自动提炼内容（网上文稿也支持）
                    if auto_extract and search_result.get('file'):
                        auto_extract_content(search_result['file'], extract_title)
                    
                    print(f"💡 下一步: 打开 {search_result['file']} 整理格式，然后提供给学习内容分析助手！")
                    print("=" * 70)
            except KeyboardInterrupt:
                print("\n\n已取消，使用网上文稿")
            return
    
    # 直接转录
    print("\n🔄 开始转录...")
    transcript_file = do_transcription(video_url, model_size, language, speaker_diarization, surname)
    
    # 自动提炼内容
    if auto_extract and transcript_file:
        auto_extract_content(transcript_file, extract_title)
    
    print("\n" + "=" * 70)
    print("🎉 全部完成！")
    print(f"📄 转录稿: {transcript_file}")
    print(f"💡 下一步: 打开 {transcript_file} 整理格式，然后提供给学习内容分析助手！")
    print("=" * 70)

if __name__ == '__main__':
    main()

