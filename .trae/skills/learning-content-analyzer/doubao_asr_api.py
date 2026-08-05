#!/usr/bin/env python3
"""
豆包录音文件识别模型 2.0 API 调用工具

使用火山引擎豆包 ASR 2.0 (Doubao-Seed-ASR-2.0) 进行语音转录。
支持说话人分离、标点、顺滑、ITN 文本规范化。

工作流程：
1. 提交音频 URL → 获取任务 ID
2. 轮询查询结果 → 获取转录文本
3. 保存为豆包转录格式（Speaker X HH:MM:SS.mmm）

API 文档：https://www.volcengine.com/docs/6561/1354868

用法：
    # 直接用音频 URL 转录
    python3 doubao_asr_api.py "https://example.com/audio.mp3" -o transcript.txt

    # 从视频链接获取直链 URL 后转录
    python3 doubao_asr_api.py --url "https://www.bilibili.com/video/BVxxx" -o transcript.txt

    # 指定说话者名称（用于结果映射）
    python3 doubao_asr_api.py "https://example.com/audio.mp3" --speakers "张三,李四" -o transcript.txt

    # 启用热词/上下文（提升专有名词识别率）
    python3 doubao_asr_api.py "https://example.com/audio.mp3" --hotwords "美团龙珠,王新宇,程曼祺"

API Key 配置：
    echo 'your-api-key' > ~/.doubao_asr_key
"""

import os
import sys
import json
import time
import uuid
import argparse
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ 需要安装 requests: pip3 install requests")
    sys.exit(1)


# ============================================================
# 配置
# ============================================================

SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
RESOURCE_ID = "volc.seedasr.auc"  # 豆包录音文件识别模型 2.0

# API Key 查找路径（按优先级排序）
# 1. skill 目录下的 api_key.txt（本地存储，已加入 .gitignore）
# 2. 用户主目录下的 ~/.doubao_asr_key（兼容旧配置）
# 3. 环境变量 DOUBAO_ASR_KEY
SKILL_DIR = Path(__file__).parent
KEY_FILES = [
    SKILL_DIR / "api_key.txt",               # skill 本地目录（优先）
    Path.home() / ".doubao_asr_key",          # 用户主目录（备选）
]


def load_api_key():
    """从配置文件加载 API Key

    查找顺序：
    1. skill 目录下的 api_key.txt
    2. ~/.doubao_asr_key
    3. 环境变量 DOUBAO_ASR_KEY
    """
    # 从配置文件查找
    for key_file in KEY_FILES:
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8").strip()
            if key:
                return key
    # 从环境变量查找
    env_key = os.environ.get("DOUBAO_ASR_KEY", "").strip()
    if env_key:
        return env_key
    return None


# ============================================================
# 获取音频直链 URL
# ============================================================

def get_direct_url(video_url):
    """用 yt-dlp 获取音频直链 URL

    对于 B站/YouTube/小宇宙等视频链接，用 yt-dlp 获取音频流的直链 URL。
    注意：直链 URL 通常有时效性（几小时），需要尽快提交给 API。

    Returns:
        str: 音频直链 URL，失败返回 None
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "-g", "-f", "bestaudio", "--no-warnings", video_url],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            urls = result.stdout.strip().split("\n")
            return urls[0]  # 第一个 URL 是音频直链
        else:
            print(f"❌ yt-dlp 获取直链失败: {result.stderr[:200]}")
            return None
    except FileNotFoundError:
        print("❌ 未安装 yt-dlp，请运行: pip3 install yt-dlp")
        return None
    except subprocess.TimeoutExpired:
        print("❌ yt-dlp 获取直链超时")
        return None


def guess_audio_format(url):
    """从 URL 猜测音频格式"""
    url_lower = url.lower()
    if ".mp3" in url_lower:
        return "mp3"
    elif ".wav" in url_lower:
        return "wav"
    elif ".ogg" in url_lower:
        return "ogg"
    elif ".m4a" in url_lower:
        return "mp3"  # m4a 用 mp3 格式提交，API 通常兼容
    else:
        return "mp3"  # 默认 mp3


# ============================================================
# API 调用
# ============================================================

def submit_task(audio_url, api_key, enable_speaker=True, enable_punc=True,
                enable_ddc=True, enable_itn=True, hotwords=None, language=""):
    """提交转录任务

    Args:
        audio_url: 音频文件的公网 URL
        api_key: 火山引擎 API Key
        enable_speaker: 启用说话人分离
        enable_punc: 启用标点
        enable_ddc: 启用顺滑（去掉停顿词）
        enable_itn: 启用文本规范化（数字、金额等）
        hotwords: 热词列表，用于提升专有名词识别率
        language: 指定语言（空为自动识别）

    Returns:
        str: 任务 ID（X-Api-Request-Id），失败返回 None
    """
    task_id = str(uuid.uuid4())

    headers = {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": task_id,
        "X-Api-Sequence": "-1",
        "Content-Type": "application/json",
    }

    audio_format = guess_audio_format(audio_url)

    request_body = {
        "user": {"uid": "learning-content-analyzer"},
        "audio": {
            "url": audio_url,
            "format": audio_format,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": enable_itn,
            "enable_punc": enable_punc,
            "enable_ddc": enable_ddc,
            "enable_speaker_info": enable_speaker,
            "show_utterances": True,
        },
    }

    # 指定语言
    if language:
        request_body["audio"]["language"] = language

    # 热词/上下文
    if hotwords:
        word_list = [{"word": w.strip()} for w in hotwords if w.strip()]
        if word_list:
            context = json.dumps({"hotwords": word_list}, ensure_ascii=False)
            request_body["request"]["corpus"] = context

    print(f"📤 提交转录任务...")
    print(f"   任务 ID: {task_id}")
    print(f"   音频格式: {audio_format}")
    print(f"   说话人分离: {'✅' if enable_speaker else '❌'}")
    if hotwords:
        print(f"   热词: {', '.join(hotwords[:5])}{'...' if len(hotwords) > 5 else ''}")

    try:
        resp = requests.post(SUBMIT_URL, headers=headers, json=request_body, timeout=30)

        status_code = resp.headers.get("X-Api-Status-Code", "")
        message = resp.headers.get("X-Api-Message", "")
        log_id = resp.headers.get("X-Tt-Logid", "")

        if status_code == "20000000":
            print(f"   ✅ 提交成功！")
            return task_id
        else:
            print(f"   ❌ 提交失败: {message} (code={status_code})")
            print(f"   LogID: {log_id}")
            if resp.text:
                print(f"   响应: {resp.text[:300]}")
            return None

    except requests.RequestException as e:
        print(f"   ❌ 网络错误: {e}")
        return None


def query_result(task_id, api_key, timeout=600, poll_interval=10):
    """轮询查询转录结果

    Args:
        task_id: 任务 ID
        api_key: API Key
        timeout: 最大等待时间（秒）
        poll_interval: 轮询间隔（秒）

    Returns:
        dict: 转录结果，失败返回 None
    """
    headers = {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": task_id,
        "Content-Type": "application/json",
    }

    print(f"\n⏳ 等待转录完成（最长 {timeout}秒，每 {poll_interval}秒 查询一次）...")

    elapsed = 0
    while elapsed < timeout:
        try:
            resp = requests.post(QUERY_URL, headers=headers, json={}, timeout=30)

            status_code = resp.headers.get("X-Api-Status-Code", "")
            message = resp.headers.get("X-Api-Message", "")

            if status_code == "20000000":
                # 成功
                result = resp.json()
                print(f"   ✅ 转录完成！")
                return result
            elif status_code in ("20000001", "20000002"):
                # 处理中 / 排队中
                print(f"   ⏳ {message}（已等待 {elapsed}秒）...")
                time.sleep(poll_interval)
                elapsed += poll_interval
            else:
                # 错误
                print(f"   ❌ 查询失败: {message} (code={status_code})")
                if resp.text:
                    print(f"   响应: {resp.text[:300]}")
                return None

        except requests.RequestException as e:
            print(f"   ⚠️ 网络错误，重试: {e}")
            time.sleep(poll_interval)
            elapsed += poll_interval

    print(f"   ❌ 超时（{timeout}秒）")
    return None


# ============================================================
# 结果格式化
# ============================================================

def format_timestamp(ms):
    """毫秒转 HH:MM:SS.mmm 格式"""
    total_seconds = ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def format_transcript(result, speakers=None):
    """格式化转录结果为豆包转录格式

    输出格式：
        Speaker X HH:MM:SS.mmm
        转录文本内容...

    Args:
        result: API 返回的结果
        speakers: 说话者姓名列表（用于映射 Speaker 1→姓名）

    Returns:
        str: 格式化后的转录文本
    """
    lines = []

    # 提取 utterances
    utterances = []
    if isinstance(result, dict):
        api_result = result.get("result", {})
        if isinstance(api_result, dict):
            utterances = api_result.get("utterances", [])
        elif isinstance(api_result, list) and api_result:
            utterances = api_result[0].get("utterances", [])

    if not utterances:
        # 没有 utterances，用完整文本
        text = ""
        if isinstance(result, dict):
            api_result = result.get("result", {})
            if isinstance(api_result, dict):
                text = api_result.get("text", "")
            elif isinstance(api_result, list) and api_result:
                text = api_result[0].get("text", "")
        if text:
            lines.append("Speaker 1 00:00:00.000")
            lines.append(text)
        return "\n".join(lines)

    # 格式化每个 utterance
    for u in utterances:
        start_ms = u.get("start_time", 0)
        text = u.get("text", "").strip()
        if not text:
            continue

        # 说话人标签
        speaker_label = u.get("speaker_id", "1")
        if isinstance(speaker_label, str) and speaker_label.startswith("Speaker"):
            speaker_id = speaker_label
        else:
            speaker_id = f"Speaker {speaker_label}"

        # 映射说话人姓名
        if speakers:
            try:
                idx = int(speaker_label) - 1 if isinstance(speaker_label, (int, str)) else 0
                if 0 <= idx < len(speakers):
                    speaker_id = speakers[idx]
            except (ValueError, IndexError):
                pass

        timestamp = format_timestamp(start_ms)
        lines.append(f"{speaker_id} {timestamp}")
        lines.append(text)
        lines.append("")  # 空行分隔

    return "\n".join(lines).strip()


def save_transcript(text, output_path):
    """保存转录结果"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(text, encoding="utf-8")
    print(f"\n💾 转录稿已保存: {output_path}")
    print(f"   字数: {len(text)}")
    return output_path


# ============================================================
# 主流程
# ============================================================

def transcribe(audio_url_or_video, api_key=None, speakers=None, hotwords=None,
               language="", output_path="doubao_transcript.txt",
               timeout=600, poll_interval=10):
    """完整的转录流程

    Args:
        audio_url_or_video: 音频 URL 或视频链接（会自动获取直链）
        api_key: API Key（不传则从配置文件读取）
        speakers: 说话者姓名列表
        hotwords: 热词列表
        language: 指定语言
        output_path: 输出文件路径
        timeout: 最大等待时间
        poll_interval: 轮询间隔

    Returns:
        str: 输出文件路径，失败返回 None
    """
    # 1. 加载 API Key
    if not api_key:
        api_key = load_api_key()
    if not api_key:
        print("❌ 未找到 API Key！")
        print(f"   请把 API Key 写入以下任一文件：")
        print(f"   - {SKILL_DIR / 'api_key.txt'}（推荐，skill 本地目录）")
        print(f"   - {Path.home() / '.doubao_asr_key'}（用户主目录）")
        print(f"   或设置环境变量 DOUBAO_ASR_KEY")
        return None

    # 2. 获取音频 URL
    input_str = audio_url_or_video.strip()

    # 判断是 URL 还是本地文件
    if input_str.startswith("http://") or input_str.startswith("https://"):
        # 判断是直接音频 URL 还是视频页面 URL
        audio_extensions = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")
        if any(input_str.lower().endswith(ext) for ext in audio_extensions):
            # 直接音频 URL
            audio_url = input_str
            print(f"🎵 使用音频 URL: {audio_url[:80]}...")
        else:
            # 视频页面 URL，用 yt-dlp 获取直链
            print(f"🎬 检测到视频链接，获取音频直链...")
            audio_url = get_direct_url(input_str)
            if not audio_url:
                print("❌ 无法获取音频直链 URL")
                return None
            print(f"   ✅ 获取成功: {audio_url[:80]}...")
    else:
        # 本地文件 - API 需要公网 URL，无法直接处理
        print(f"❌ 本地文件无法直接提交给 API")
        print(f"   豆包 ASR API 需要音频的公网 URL。")
        print(f"   解决方案：")
        print(f"   1. 用视频链接而不是本地文件（推荐）")
        print(f"   2. 把本地文件上传到对象存储（如火山引擎 TOS）获取 URL")
        return None

    # 3. 提交任务
    task_id = submit_task(
        audio_url, api_key,
        enable_speaker=True,
        enable_punc=True,
        enable_ddc=True,
        enable_itn=True,
        hotwords=hotwords,
        language=language,
    )
    if not task_id:
        return None

    # 4. 轮询结果
    result = query_result(task_id, api_key, timeout=timeout, poll_interval=poll_interval)
    if not result:
        return None

    # 5. 格式化输出
    transcript_text = format_transcript(result, speakers)
    if not transcript_text:
        print("❌ 转录结果为空")
        print(f"   原始结果: {json.dumps(result, ensure_ascii=False)[:500]}")
        return None

    # 6. 保存
    return save_transcript(transcript_text, output_path)


# ============================================================
# 命令行
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="豆包录音文件识别模型 2.0 API 转录工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 用音频 URL 转录
  python3 doubao_asr_api.py "https://example.com/audio.mp3" -o transcript.txt

  # 从视频链接转录（自动获取直链）
  python3 doubao_asr_api.py "https://www.bilibili.com/video/BVxxx" -o transcript.txt

  # 指定说话者和热词
  python3 doubao_asr_api.py "https://xxx" --speakers "张三,李四" --hotwords "美团,龙珠" -o transcript.txt

API Key 配置:
  echo 'your-api-key' > ~/.doubao_asr_key
        """,
    )

    parser.add_argument("input", help="音频 URL 或视频链接")
    parser.add_argument("-o", "--output", default="doubao_transcript.txt",
                        help="输出文件路径（默认: doubao_transcript.txt）")
    parser.add_argument("--speakers", help="说话者姓名，逗号分隔（如: 张三,李四）")
    parser.add_argument("--hotwords", help="热词，逗号分隔，提升专有名词识别率（如: 美团,龙珠,王新宇）")
    parser.add_argument("--language", default="", help="指定语言（空为自动识别）")
    parser.add_argument("--timeout", type=int, default=600, help="最大等待时间（秒，默认 600）")
    parser.add_argument("--poll-interval", type=int, default=10, help="轮询间隔（秒，默认 10）")
    parser.add_argument("--api-key", help="API Key（默认从 ~/.doubao_asr_key 读取）")

    args = parser.parse_args()

    speakers = None
    if args.speakers:
        speakers = [s.strip() for s in args.speakers.split(",") if s.strip()]

    hotwords = None
    if args.hotwords:
        hotwords = [w.strip() for w in args.hotwords.split(",") if w.strip()]

    result = transcribe(
        audio_url_or_video=args.input,
        api_key=args.api_key,
        speakers=speakers,
        hotwords=hotwords,
        language=args.language,
        output_path=args.output,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )

    if result:
        print(f"\n🎉 转录成功！")
        print(f"   文件: {result}")
        print(f"\n💡 接下来可以用 learning_pipeline.py --process 处理转录稿")
    else:
        print(f"\n❌ 转录失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
