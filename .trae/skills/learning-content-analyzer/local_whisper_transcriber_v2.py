#!/usr/bin/env python3
"""
本地 Whisper 转录工具 V2.0 - 完全免费！
不需要 API Key，不需要信用卡，不需要网络（除了下载视频）
支持B站反爬虫处理、多格式输出、自定义说话者名称、进度条显示
"""

import sys
import os
import json
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
    
    # 检测是否是B站
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
            # B站反爬虫关键配置
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Origin': 'https://www.bilibili.com',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
            },
        }
        
        # 如果有cookies文件，使用cookies
        cookie_file = Path.home() / '.bilibili_cookies.txt'
        if cookie_file.exists():
            print(f"🍪 使用cookies文件: {cookie_file}")
            ydl_opts['cookiefile'] = str(cookie_file)
    else:
        # 非B站链接的普通配置
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
                print(f"\n⚠️ B站下载失败，尝试备用方案...")
                # 尝试使用B站API下载
                return download_bilibili_fallback(url, output_dir)
            else:
                raise e


def download_bilibili_fallback(url, output_dir):
    """B站备用下载方案：使用移动端API"""
    import requests
    
    print(f"🔄 尝试备用方案...")
    
    # 从URL中提取BVID
    import re
    match = re.search(r'BV[a-zA-Z0-9]+', url)
    if not match:
        print("❌ 无法提取BVID")
        return None
    
    bvid = match.group(0)
    print(f"📹 BVID: {bvid}")
    
    # 使用B站API获取视频信息
    api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://www.bilibili.com/',
    }
    
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        data = resp.json()
        
        if data['code'] == 0:
            cid = data['data']['cid']
            title = data['data']['title']
            print(f"✅ 获取视频信息成功: {title}")
            
            # 尝试从多个CDN获取音频
            cdn_urls = [
                f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=0&fnver=0&type=mp4",
                f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=16&fnval=404&type=mp4",
            ]
            
            for cdn_url in cdn_urls:
                try:
                    print(f"🔄 尝试CDN: {cdn_url[:50]}...")
                    resp = requests.get(cdn_url, headers=headers, timeout=15)
                    data = resp.json()
                    
                    if data['code'] == 0 and data['data']['durl']:
                        audio_url = data['data']['durl'][0]['url']
                        
                        # 下载音频
                        print(f"📥 从备用CDN下载...")
                        audio_resp = requests.get(audio_url, headers=headers, timeout=60, stream=True)
                        
                        audio_file = Path(output_dir) / f"{bvid}.mp3"
                        with open(audio_file, 'wb') as f:
                            for chunk in audio_resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        print(f"✅ 备用下载成功: {audio_file}")
                        return str(audio_file)
                except Exception as e:
                    print(f"⚠️ CDN失败: {e}")
                    continue
            
            print("❌ 所有CDN都失败")
            return None
        else:
            print(f"❌ API请求失败: {data['message']}")
            return None
    except Exception as e:
        print(f"❌ 备用方案失败: {e}")
        return None


def preprocess_audio(audio_path, output_dir=None, denoise=True, normalize=True):
    """音频预处理：降噪 + 音量标准化 + 转 16kHz 单声道

    显著提高 Whisper 识别准确率，尤其是背景噪音大的音频。
    依赖 ffmpeg（系统已安装）。

    返回处理后的音频路径，失败时返回原路径。
    """
    if output_dir is None:
        output_dir = Path(audio_path).parent

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    stem = Path(audio_path).stem
    output_path = str(Path(output_dir) / f"{stem}_processed.wav")

    try:
        import subprocess

        filters = []
        operations = []

        # 1. 降噪（afftdn 音频频域降噪）
        if denoise:
            filters.append("afftdn=nf=-25:tn=-10")
            operations.append("降噪")

        # 2. 音量标准化（loudnorm 响度标准化到 -16 LUFS）
        if normalize:
            filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")
            operations.append("音量标准化")

        # 3. 转 16kHz 单声道（Whisper 内部会转，但提前转好更稳）
        filters.append("aresample=16000")
        filters.append("pan=mono|c0=c0")

        if not operations:
            return audio_path

        print(f"🎛️  音频预处理: {' + '.join(operations)} + 重采样 16kHz 单声道...")

        filter_complex = ','.join(filters)
        cmd = [
            'ffmpeg', '-y', '-i', audio_path,
            '-af', filter_complex,
            '-ar', '16000', '-ac', '1',
            '-c:a', 'pcm_s16le',
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0 and Path(output_path).exists():
            # 检查文件大小是否合理
            orig_size = Path(audio_path).stat().st_size
            new_size = Path(output_path).stat().st_size
            if new_size > 1000:  # 至少 1KB 才算成功
                print(f"✅ 预处理完成: {output_path}")
                return output_path
            else:
                print(f"⚠️  预处理输出文件太小，使用原音频")
        else:
            print(f"⚠️  预处理失败，使用原音频: {result.stderr[:100]}")

    except Exception as e:
        print(f"⚠️  预处理异常，使用原音频: {e}")

    return audio_path


def _select_device():
    """自动选择计算设备：优先 CPU（兼容性最好），其次 CUDA

    注意：MPS (Apple Silicon GPU) 在 whisper 20250625 版本上有 float64 兼容性问题，
    因此默认使用 CPU。如果安装了 torch 且用户明确知道 MPS 可用，可以手动选择。
    """
    try:
        import torch
        # CUDA 优先（NVIDIA 显卡）
        if torch.cuda.is_available():
            print(f"⚡ 已启用 NVIDIA GPU 加速（CUDA）")
            return "cuda"
        # MPS 暂时禁用，因为 whisper 20250625 + MPS 有 float64 兼容性问题
        # 如果未来版本修复了，可以重新启用
        # if torch.backends.mps.is_available():
        #     print(f"⚡ 已启用 Apple Silicon GPU 加速（MPS）")
        #     return "mps"
    except ImportError:
        pass
    print(f"💻 使用 CPU 转录（安装正确版本 torch 可启用 GPU 加速）")
    return "cpu"


def transcribe_local(audio_path, model_size='base', language=None, speaker_diarization=False, 
                     initial_prompt=None, vad_filter=True, callback=None, speakers=None):
    """使用本地 Whisper 转录

    说话者识别逻辑（智能开关）：
      speaker_diarization=True  → pyannote 音色识别（精准，慢）
      speaker_diarization=False → 智能分组（基于沉默间隔+内容启发式，快，默认）

    优化参数：
      initial_prompt: 上下文提示词，显著提高专有名词识别准确率
      vad_filter: 是否启用 VAD 静音过滤（取决于 whisper 版本是否支持）
      speakers: 说话者列表（从 shownotes 提取），用于确定分组人数和内容启发式判断
    """
    try:
        import whisper
    except ImportError:
        print("\n❌ 需要先安装 Whisper！")
        print("\n请运行: pip install openai-whisper")
        print("如果在 macOS 上还需要: brew install ffmpeg")
        sys.exit(1)

    # 选择设备（CPU 优先，确保兼容性）
    device = _select_device()

    print(f"🎤 正在加载模型: {model_size}（device={device}）...")
    print(f"💡 提示: 第一次运行会自动下载模型")
    model = whisper.load_model(model_size, device=device)

    # 打印优化信息
    if initial_prompt:
        print(f"💡 已启用上下文提示词（提高专有名词识别率）")
        if len(initial_prompt) > 60:
            print(f"   提示词: {initial_prompt[:60]}...")
        else:
            print(f"   提示词: {initial_prompt}")

    print(f"📝 正在转录...")

    # 基础参数（所有版本都支持的）
    transcribe_kwargs = {
        'word_timestamps': True,
        'verbose': False,
        'temperature': (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    }

    # 初始提示词（提高专有名词识别准确率）
    if initial_prompt:
        transcribe_kwargs['initial_prompt'] = initial_prompt

    # 语言设置：whisper 20250625 版本通过 decode_options 传 language
    # 旧版本直接传 language 参数
    if language:
        print(f"🔤 指定语言: {language}")
    else:
        print(f"🔤 自动检测语言...")

    # 策略：从最完整的参数开始，逐步回退
    # 方案1：尝试 vad_filter + 直接传 language（whisper 20230314 等版本）
    # 方案2：只传 language，不传 vad_filter
    # 方案3：通过 decode_options 传 language
    # 方案4：最基础版本

    result = None

    # 尝试方案1：直接传 language（旧版 whisper 常用方式）
    try:
        kwargs = dict(transcribe_kwargs)
        if language:
            kwargs['language'] = language
        result = model.transcribe(audio_path, **kwargs)
    except TypeError as e:
        # 方案2：不支持 language 直接传，试试通过 decode_options
        try:
            kwargs = dict(transcribe_kwargs)
            if language:
                kwargs['decode_options'] = {'language': language}
            result = model.transcribe(audio_path, **kwargs)
        except TypeError as e2:
            # 方案3：最基础版本，只传 word_timestamps 和 verbose
            try:
                result = model.transcribe(
                    audio_path,
                    word_timestamps=True,
                    verbose=False,
                )
            except Exception as e3:
                print(f"❌ 转录失败: {e3}")
                raise

    # 说话者识别（智能开关）
    if speaker_diarization:
        # 用户显式 --speaker，用 pyannote 音色识别（精准但慢）
        result = add_speaker_labels(result, audio_path)
    else:
        # 默认用智能分组（快，基于沉默间隔+内容启发式）
        num_speakers = len(speakers) if speakers else 2
        result = add_smart_speaker_labels(result, num_speakers=num_speakers, speakers=speakers)
        print(f"🏷️ 已启用智能说话者分组（{num_speakers} 位说话者），如需精准音色识别请加 --speaker")

    print(f"✅ 转录成功！")
    if 'language' in result:
        print(f"🌍 检测到的语言: {result['language']}")
    return result


def _get_hf_token():
    """读取 HuggingFace access token

    优先级：
      1. 环境变量 HF_TOKEN
      2. 环境变量 HUGGING_FACE_HUB_TOKEN
      3. 文件 ~/.huggingface_token（内容为 token 字符串，一行）
    """
    import os
    for var in ('HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'):
        token = os.environ.get(var, '').strip()
        if token:
            return token
    token_file = Path.home() / '.huggingface_token'
    if token_file.exists():
        token = token_file.read_text(encoding='utf-8').strip()
        if token:
            return token
    return None


def add_speaker_labels(result, audio_path):
    """添加说话者标签（使用pyannote.audio 音色识别）

    需要：
      1. pip install pyannote.audio torch
      2. 在 HuggingFace 申请 pyannote/speaker-diarization-3.1 模型访问权限
      3. 生成 access token 写入环境变量 HF_TOKEN 或文件 ~/.huggingface_token

    任何步骤失败都会回退到 add_simple_speaker_labels（基于沉默间隔，无需依赖）。
    """
    try:
        from pyannote.audio import Pipeline
        import torch
        print(f"🎙️ 正在进行音色识别（pyannote.audio）...")

        # 读取 HF token
        token = _get_hf_token()
        if not token:
            print(f"⚠️ 未找到 HuggingFace token，无法下载 pyannote 模型")
            print(f"   获取方式：")
            print(f"   1. 注册 https://huggingface.co 账号")
            print(f"   2. 申请模型访问权限：https://huggingface.co/pyannote/speaker-diarization-3.1")
            print(f"   3. 生成 token：https://huggingface.co/settings/tokens（选 Read 权限）")
            print(f"   4. 写入文件：echo '你的token' > ~/.huggingface_token")
            print(f"   本次回退到简单说话者分组")
            return add_simple_speaker_labels(result)

        # 加载 pyannote 说话者识别 pipeline
        # 注意：新版 pyannote.audio 用 token= 参数（旧版 use_auth_token 已废弃）
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=token
            )
        except Exception as e:
            print(f"⚠️ 模型加载失败: {e}")
            print(f"   请确认：1) 已申请模型权限  2) token 有效  3) 网络通畅")
            print(f"   本次回退到简单说话者分组")
            return add_simple_speaker_labels(result)

        # 处理音频
        print(f"🔄 正在分析音色（首次运行会下载模型，约 1GB）...")
        diarization = pipeline(audio_path)

        # 为每个 segment 分配说话者
        speaker_segments = []
        for segment, _, speaker in diarization.itertracks(yield_label=True):
            speaker_segments.append({
                'start': segment.start,
                'end': segment.end,
                'speaker': speaker
            })

        # 匹配到 whisper 的结果（按时间重叠最大化）
        for seg in result['segments']:
            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', 0)

            best_speaker = None
            best_overlap = 0
            for sp_seg in speaker_segments:
                overlap = max(0, min(seg_end, sp_seg['end']) - max(seg_start, sp_seg['start']))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = sp_seg['speaker']

            if best_speaker:
                seg['speaker'] = best_speaker

        print(f"✅ 音色识别完成（识别到 {len(set(s.get('speaker') for s in speaker_segments))} 位说话者）")
        return result

    except ImportError:
        print(f"⚠️ pyannote.audio 未安装，回退到简单说话者分组")
        print(f"   安装方式：pip3 install pyannote.audio torch")
        return add_simple_speaker_labels(result)
    except Exception as e:
        print(f"⚠️ 音色识别失败: {e}，回退到简单分组")
        return add_simple_speaker_labels(result)


def add_smart_speaker_labels(result, num_speakers=2, speakers=None):
    """智能说话者识别：基于沉默间隔 + 内容启发式 + 上下文理解

    改进点：
    - SPEAKER 编号从 0 开始（与 assign_speaker_names 映射一致）
    - 支持可变数量说话者（从 shownotes 获取）
    - 内容启发式：问号结尾（提问）+ 长度对比（回答长）+ 上下文理解（称呼、自我介绍）
    - 不是机械轮流分配，而是智能判断说话者切换

    Args:
        result: whisper 转录结果
        num_speakers: 说话者数量（从 shownotes 提取）
        speakers: 说话者姓名列表（用于上下文理解）
    """
    from collections import defaultdict

    segments = result.get('segments', [])
    if not segments:
        return result

    if speakers is None:
        speakers = []

    # 首先，合并时间上非常接近的片段（< 3秒沉默）
    merged_segments = []
    if segments:
        current_group = [segments[0]]
        for i in range(1, len(segments)):
            prev_seg = segments[i-1]
            curr_seg = segments[i]
            silence_duration = curr_seg.get('start', 0) - prev_seg.get('end', 0)

            # 沉默时间 < 3秒，合并到同一组
            if silence_duration < 3.0:
                current_group.append(curr_seg)
            else:
                merged_segments.append(current_group)
                current_group = [curr_seg]
        merged_segments.append(current_group)

    # 将每组转换为带文本的单元
    groups_with_text = []
    for group in merged_segments:
        group_text = ''.join(s.get('text', '') for s in group).strip()
        groups_with_text.append({
            'segments': group,
            'start': group[0].get('start', 0),
            'end': group[-1].get('end', 0),
            'text': group_text,
            'length': len(group_text),
        })

    # 智能分配说话者
    # 策略：
    # 1. 第一段：如果是自我介绍（"我是XXX"），分配给第一个说话者
    # 2. 后续段：基于内容启发式判断是否切换
    # 3. 对话模式：提问（短、问号）→ 回答（长）→ 提问（短、问号）→ ...
    current_speaker_idx = 0
    speaker_counter = 0

    for i, group in enumerate(groups_with_text):
        text = group['text']
        length = group['length']

        # 第一段特殊处理：判断是否自我介绍
        if i == 0:
            # 检查是否包含"大家好""我是""欢迎"等主持人口气
            is_host_intro = any(keyword in text for keyword in ['大家好', '欢迎', '我是', '这里是', '节目'])
            if is_host_intro and speakers:
                # 主持人通常是第一个
                current_speaker_idx = 0
            else:
                current_speaker_idx = speaker_counter % num_speakers
                speaker_counter += 1
        else:
            prev_group = groups_with_text[i-1]
            prev_text = prev_group['text']
            prev_length = prev_group['length']
            gap = group['start'] - prev_group['end']

            should_switch = False

            # 规则1：间隔超过 4 秒，很可能换人
            if gap > 4.0:
                should_switch = True

            # 规则2：上一段很短（提问），这一段很长（回答）→ 切换
            if prev_length < 30 and length > 60:
                should_switch = True

            # 规则3：上一段很长（回答），这一段很短（提问）→ 切换
            if prev_length > 60 and length < 30:
                should_switch = True

            # 规则4：上一段以问号结尾（提问），这一段较长 → 切换（回答）
            if prev_text.rstrip().endswith(('?', '？')) and length > 30:
                should_switch = True

            # 规则5：上下文理解 - 称呼检测
            # 如果这一段提到了某说话者的名字，很可能是另一个人在说话
            for j, speaker_name in enumerate(speakers):
                if speaker_name in text and j != current_speaker_idx:
                    # 提到了其他说话者的名字，可能是在回应
                    # 但也要考虑自己说自己名字的情况（自我介绍）
                    if i > 2 and not any(speaker_name in g['text'] for g in groups_with_text[:i-2]):
                        should_switch = True
                        current_speaker_idx = j
                        break

            # 规则6：自我介绍检测
            # 如果这一段包含"我是XXX"且XXX是已知说话者名，分配给该说话者
            for j, speaker_name in enumerate(speakers):
                if f'我是{speaker_name}' in text or f'我叫{speaker_name}' in text:
                    current_speaker_idx = j
                    should_switch = False
                    break

            if should_switch and not any(f'我是{s}' in text or f'我叫{s}' in text for s in speakers):
                # 切换到下一个说话者（支持多人循环）
                current_speaker_idx = (current_speaker_idx + 1) % num_speakers

        # 分配说话者
        speaker_id = f"SPEAKER_{current_speaker_idx:02d}"
        for seg in group['segments']:
            seg['speaker'] = speaker_id

    return result


def format_timestamp(seconds):
    """将秒数转换为 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_timestamp_srt(seconds):
    """将秒数转换为 SRT 格式的时间戳 HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


def format_timestamp_vtt(seconds):
    """将秒数转换为 WebVTT 格式的时间戳 HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"


def _to_simplified_chinese(result):
    """将转录结果中的繁体中文转换为简体中文

    优先用 opencc（精准，需 pip install opencc-python-reimplemented），
    未安装时回退到内置的高频异体字映射（覆盖常见繁简差异字）。
    英文/数字/标点不受影响。
    """
    # 尝试用 opencc
    try:
        from opencc import OpenCC
        cc = OpenCC('t2s')  # 繁体 → 简体

        def convert_text(text):
            return cc.convert(text)

        print(f"🌐 使用 opencc 繁简转换（精准）")
    except ImportError:
        # 回退：高频繁简异体字映射（覆盖 400+ 常见繁简差异字）
        # 按使用频率排序，确保 Whisper 中文转录最常出现的字都覆盖
        _T2S = {
            # === 最常见（高频 100 字）===
            '的': '的', '了': '了', '是': '是', '在': '在', '我': '我',
            '有': '有', '他': '他', '个': '个', '们': '们', '这': '这',
            '中': '中', '來': '来', '那': '那', '就': '就', '都': '都',
            '說': '说', '要': '要', '會': '会', '著': '着', '沒有': '没有',
            '看': '看', '好': '好', '自己': '自己', '這': '这', '樣': '样',
            '麼': '么', '想': '想', '她': '她', '裡': '里', '給': '给',
            '對': '对', '多': '多', '麼': '么', '日': '日', '過': '过',
            '麼': '么', '長': '长', '從': '从', '後': '后', '然': '然',
            '走': '走', '很': '很', '像': '像', '說': '说', '見': '见',
            '知': '知', '道': '道', '時': '时', '候': '候', '經': '经',
            '將': '将', '過': '过', '地': '地', '學': '学', '以': '以',
            '也': '也', '就': '就', '那': '那', '後': '后', '因': '因',
            '為': '为', '可': '可', '家': '家', '還': '还', '只': '只',
            '能': '能', '對': '对', '而': '而', '且': '且', '並': '并',
            '沒': '没', '有': '有', '做': '做', '當': '当', '怎': '怎',
            '麼': '么', '樣': '样', '發': '发', '現': '现', '新': '新',
            '電': '电', '視': '视', '機': '机', '車': '车', '話': '话',
            
            # === 代词/疑问词 ===
            '什麼': '什么', '怎麼': '怎么', '為什麼': '为什么', '哪': '哪',
            '誰': '谁', '這裡': '这里', '那裡': '那里', '這樣': '这样',
            '那樣': '那样', '怎麼樣': '怎么样', '每個': '每个',
            '各個': '各个', '這些': '这些', '那些': '那些',
            
            # === 常见动词 ===
            '做': '做', '作': '作', '發現': '发现', '覺得': '觉得',
            '知道': '知道', '認為': '认为', '看到': '看到', '聽到': '听到',
            '說話': '说话', '讀書': '读书', '寫': '写', '學习': '学习',
            '開始': '开始', '結束': '结束', '進': '进', '出': '出',
            '回': '回', '過來': '过来', '過去': '过去', '起來': '起来',
            '下去': '下去', '進入': '进入', '離開': '离开', '達到': '达到',
            '實現': '实现', '獲得': '获得', '產生': '产生', '變成': '变成',
            '稱為': '称为', '叫作': '叫作', '屬於': '属于', '包括': '包括',
            '需要': '需要', '應該': '应该', '能夠': '能够', '可以': '可以',
            '必須': '必须', '願意': '愿意', '敢': '敢', '肯': '肯',
            
            # === 时间相关 ===
            '時間': '时间', '時候': '时候', '今天': '今天', '昨天': '昨天',
            '明天': '明天', '去年': '去年', '今年': '今年', '現在': '现在',
            '過去': '过去', '將來': '将来', '未來': '未来', '剛才': '刚才',
            '然後': '然后', '後來': '后来', '以後': '以后', '以前': '以前',
            '同時': '同时', '隨時': '随时', '暫時': '暂时', '永遠': '永远',
            '已經': '已经', '曾經': '曾经', '總是': '总是', '經常': '经常',
            '常常': '常常', '時常': '时常', '偶爾': '偶尔', '終於': '终于',
            
            # === 地点/方位 ===
            '地方': '地方', '這裡': '这里', '那裡': '那里', '哪裡': '哪里',
            '上面': '上面', '下面': '下面', '左邊': '左边', '右邊': '右边',
            '前': '前', '後': '后', '裡': '里', '外': '外', '中間': '中间',
            '旁邊': '旁边', '對面': '对面', '東': '东', '西': '西',
            '南': '南', '北': '北', '國家': '国家', '城市': '城市',
            '地區': '地区', '區域': '区域', '環境': '环境',
            
            # === 形容词 ===
            '好': '好', '壞': '坏', '大': '大', '小': '小', '多': '多',
            '少': '少', '高': '高', '矮': '矮', '長': '长', '短': '短',
            '寬': '宽', '窄': '窄', '厚': '厚', '薄': '薄', '深': '深',
            '淺': '浅', '重': '重', '輕': '轻', '快': '快', '慢': '慢',
            '新': '新', '舊': '旧', '年輕': '年轻', '老': '老',
            '美麗': '美丽', '醜': '丑', '聰明': '聪明', '傻': '傻',
            '快樂': '快乐', '難過': '难过', '高興': '高兴', '生氣': '生气',
            '害怕': '害怕', '擔心': '担心', '緊張': '紧张', '輕鬆': '轻松',
            '認真': '认真', '馬虎': '马虎', '仔細': '仔细', '粗心': '粗心',
            '勇敢': '勇敢', '膽小': '胆小', '誠實': '诚实', '虛偽': '虚伪',
            '真誠': '真诚', '虛假': '虚假', '熱情': '热情', '冷漠': '冷漠',
            '親切': '亲切', '嚴肅': '严肃', '和藹': '和蔼', '兇': '凶',
            
            # === 数量词 ===
            '個': '个', '隻': '只', '條': '条', '張': '张', '本': '本',
            '件': '件', '雙': '双', '對': '对', '套': '套', '副': '副',
            '群': '群', '批': '批', '堆': '堆', '團': '团', '隊': '队',
            '萬': '万', '億': '亿', '百萬': '百万', '千萬': '千万',
            '第一': '第一', '第二': '第二', '幾': '几', '許多': '许多',
            '眾多': '众多', '少數': '少数', '半': '半', '全': '全',
            '整': '整', '部分': '部分', '全部': '全部',
            
            # === 科技/互联网 ===
            '電腦': '电脑', '手機': '手机', '網絡': '网络', '網路': '网络',
            '互聯網': '互联网', '軟件': '软件', '硬體': '硬件', '程序': '程序',
            '程式': '程序', '數據': '数据', '資料': '数据/资料', '信息': '信息',
            '訊息': '信息', '服務': '服务', '器': '器', '服務器': '服务器',
            '數碼': '数码', '相機': '相机', '顯示': '显示', '顯示器': '显示器',
            '鍵盤': '键盘', '鼠標': '鼠标', '檔案': '文件/档案', '文檔': '文档',
            '圖片': '图片', '圖像': '图像', '視頻': '视频', '音頻': '音频',
            '錄音': '录音', '錄像': '录像', '播放': '播放', '下載': '下载',
            '上傳': '上传', '鏈接': '链接', '網站': '网站', '頁面': '页面',
            '登錄': '登录', '註冊': '注册', '賬號': '账号', '密碼': '密码',
            '搜索': '搜索', '引擎': '引擎', '智能': '智能', '智慧': '智慧',
            '人工智慧': '人工智能', '機器人': '机器人', '自動': '自动',
            '虛擬': '虚拟', '現實': '现实', '增強': '增强',
            
            # === 商业/经济 ===
            '經濟': '经济', '商業': '商业', '企業': '企业', '公司': '公司',
            '集團': '集团', '品牌': '品牌', '產品': '产品', '服務': '服务',
            '市場': '市场', '營銷': '营销', '銷售': '销售', '賣': '卖',
            '買': '买', '購買': '购买', '消費': '消费', '價格': '价格',
            '錢': '钱', '幣': '币', '貨幣': '货币', '資金': '资金',
            '資本': '资本', '投資': '投资', '融資': '融资', '貸款': '贷款',
            '儲蓄': '储蓄', '利息': '利息', '利潤': '利润', '盈利': '盈利',
            '虧損': '亏损', '成本': '成本', '費用': '费用', '收入': '收入',
            '支出': '支出', '預算': '预算', '稅': '税', '稅務': '税务',
            '財務': '财务', '會計': '会计', '審計': '审计', '管理': '管理',
            '運營': '运营', '營運': '运营', '戰略': '战略', '計劃': '计划',
            '目標': '目标', '績效': '绩效', '考核': '考核', '獎勵': '奖励',
            '激勵': '激励', '員工': '员工', '職員': '职员', '經理': '经理',
            '總裁': '总裁', '總監': '总监', '負責人': '负责人', '創始人': '创始人',
            '合夥人': '合伙人', '股東': '股东', '董事': '董事', '監事': '监事',
            
            # === 汽车/交通 ===
            '汽車': '汽车', '車': '车', '跑車': '跑车', '轎車': '轿车',
            '卡車': '卡车', '公車': '公车', '巴士': '巴士', '地鐵': '地铁',
            '高鐵': '高铁', '鐵路': '铁路', '飛機': '飞机', '輪船': '轮船',
            '自行車': '自行车', '電動車': '电动车', '新能源': '新能源',
            '充電': '充电', '電池': '电池', '發動機': '发动机', '變速箱': '变速箱',
            '底盤': '底盘', '車身': '车身', '車燈': '车灯', '輪胎': '轮胎',
            '刹車': '刹车', '轉向': '转向', '駕駛': '驾驶', '自動駕駛': '自动驾驶',
            '導航': '导航', '儀表盤': '仪表盘', '中控': '中控', '座椅': '座椅',
            '空調': '空调', '音響': '音响',
            
            # === 人物/称谓 ===
            '爺爺': '爷爷', '奶奶': '奶奶', '姥姥': '姥姥', '姥爺': '姥爷',
            '外公': '外公', '外婆': '外婆', '爸爸': '爸爸', '媽媽': '妈妈',
            '哥哥': '哥哥', '姐姐': '姐姐', '弟弟': '弟弟', '妹妹': '妹妹',
            '叔叔': '叔叔', '阿姨': '阿姨', '伯伯': '伯伯', '姑姑': '姑姑',
            '舅舅': '舅舅', '嬸嬸': '婶婶', '伯母': '伯母', '姑父': '姑父',
            '舅媽': '舅妈', '姨夫': '姨夫', '堂哥': '堂哥', '表哥': '表哥',
            '老師': '老师', '學生': '学生', '同學': '同学', '朋友': '朋友',
            '同事': '同事', '領導': '领导', '下屬': '下属', '客戶': '客户',
            '用戶': '用户', '觀眾': '观众', '讀者': '读者', '聽眾': '听众',
            '粉絲': '粉丝', '網友': '网友', '專家': '专家', '學者': '学者',
            '教授': '教授', '博士': '博士', '碩士': '硕士', '學士': '学士',
            
            # === 常见成语/固定搭配 ===
            '一目瞭然': '一目了然', '一絲不苟': '一丝不苟', '一舉兩得': '一举两得',
            '一視同仁': '一视同仁', '一蹴而就': '一蹴而就', '一帆風順': '一帆风顺',
            '水到渠成': '水到渠成', '順理成章': '顺理成章', '理所當然': '理所当然',
            '自然而然': '自然而然', '與眾不同': '与众不同', '獨一無二': '独一无二',
            '數不勝數': '数不胜数', '不計其數': '不计其数', '各式各樣': '各种各样',
            '各種各樣': '各种各样', '許許多多': '许许多多', '千千萬萬': '千千万万',
            '堂堂正正': '堂堂正正', '偷偷摸摸': '偷偷摸摸', '匆匆忙忙': '匆匆忙忙',
            '穩穩當當': '稳稳当当', '實實在在': '实实在在', '的確確': '的确确',
            
            # === 常见双字词（高频） ===
            '重要': '重要', '主要': '主要', '關鍵': '关键', '核心': '核心',
            '基礎': '基础', '根本': '根本', '基本': '基本', '原則': '原则',
            '規則': '规则', '標準': '标准', '水準': '水准/水平', '水平': '水平',
            '品質': '质量/品质', '質量': '质量', '數量': '数量', '體積': '体积',
            '面積': '面积', '重量': '重量', '長度': '长度', '寬度': '宽度',
            '高度': '高度', '深度': '深度', '速度': '速度', '強度': '强度',
            '硬度': '硬度', '密度': '密度', '溫度': '温度', '濕度': '湿度',
            
            # === 补充：常见漏网之鱼（按实际转录发现） ===
            '遷': '迁', '嚮': '向', '橫': '横', '喬': '乔', '嘯': '啸',
            '墮': '堕', '痠': '酸', '麼': '么', '裡': '里', '嚐': '尝',
            '嚇': '吓', '圍': '围', '圖': '图', '圓': '圆', '塊': '块',
            '壞': '坏', '聲': '声', '變': '变', '臺': '台', '颱': '台',
            '體': '体', '髮': '发', '鬍': '胡', '鬍子': '胡子', '髒': '脏',
            '齒': '齿', '齡': '龄', '龍': '龙', '龜': '龟', '風': '风',
            '飛': '飞', '飛起': '飞起', '食': '食', '飲': '饮', '餐': '餐',
            '飯': '饭', '餓': '饿', '飽': '饱', '餃子': '饺子', '饅頭': '馒头',
            '麵': '面', '麵條': '面条', '米飯': '米饭', '粥': '粥', '湯': '汤',
            '菜': '菜', '肉': '肉', '魚': '鱼', '雞': '鸡', '鴨': '鸭',
            '鵝': '鹅', '豬': '猪', '牛': '牛', '羊': '羊', '馬': '马',
            '鳥': '鸟', '蟲': '虫', '貓': '猫', '狗': '狗', '兔': '兔',
            
            # === 更多高频单字 ===
            '報': '报', '貴': '贵', '賤': '贱', '買': '买', '賣': '卖',
            '費': '费', '貨': '货', '購': '购', '銷': '销', '售': '售',
            '產': '产', '廠': '厂', '農': '农', '牧': '牧', '漁': '渔',
            '礦': '矿', '油': '油', '煤': '煤', '氣': '气', '電': '电',
            '燈': '灯', '火': '火', '水': '水', '土': '土', '金': '金',
            '木': '木', '石': '石', '沙': '沙', '海': '海', '河': '河',
            '湖': '湖', '江': '江', '山': '山', '林': '林', '田': '田',
            '園': '园', '院': '院', '樓': '楼', '層': '层', '間': '间',
            '房': '房', '屋': '屋', '室': '室', '門': '门', '窗': '窗',
            '牆': '墙', '頂': '顶', '底': '底', '邊': '边', '角': '角',
            
            # === 感觉/情感 ===
            '覺得': '觉得', '感覺': '感觉', '感受': '感受', '感動': '感动',
            '激動': '激动', '興奮': '兴奋', '難過': '难过', '傷心': '伤心',
            '痛苦': '痛苦', '煩惱': '烦恼', '憂慮': '忧虑', '焦慮': '焦虑',
            '恐懼': '恐惧', '害怕': '害怕', '羞': '羞', '恥': '耻',
            '驕傲': '骄傲', '謙虛': '谦虚', '自卑': '自卑', '自信': '自信',
            
            # === 思考/认知 ===
            '思想': '思想', '思維': '思维', '觀點': '观点', '看法': '看法',
            '見解': '见解', '認識': '认识', '了解': '了解', '理解': '理解',
            '明白': '明白', '清楚': '清楚', '模糊': '模糊', '混亂': '混乱',
            '記得': '记得', '忘記': '忘记', '回憶': '回忆', '想象': '想象',
            '幻想': '幻想', '夢想': '梦想', '理想': '理想', '目標': '目标',
            '計劃': '计划', '打算': '打算', '準備': '准备', '預計': '预计',
        }

        def convert_text(text):
            # 第一步：多字词替换（按长度从长到短，确保长词优先匹配）
            multi_char = {k: v for k, v in _T2S.items() if len(k) > 1}
            for old in sorted(multi_char.keys(), key=len, reverse=True):
                if old in text:
                    text = text.replace(old, multi_char[old])
            # 第二步：单字替换
            return ''.join(_T2S.get(ch, ch) for ch in text)

        print(f"🌐 使用内置繁简映射（建议 pip install opencc-python-reimplemented 提升精准度）")

    # 转换 segments 中的文本
    if 'segments' in result:
        for seg in result['segments']:
            if 'text' in seg:
                seg['text'] = convert_text(seg['text'])
    # 转换整体文本
    if 'text' in result:
        result['text'] = convert_text(result['text'])

    return result


def generate_transcript(result, output_file, output_format='txt', speaker_names=None):
    """生成多种格式的转录稿"""

    if speaker_names is None:
        speaker_names = {}

    if output_format == 'txt':
        return generate_txt(result, output_file, speaker_names)
    elif output_format == 'srt':
        return generate_srt(result, output_file, speaker_names)
    elif output_format == 'vtt':
        return generate_vtt(result, output_file, speaker_names)
    elif output_format == 'json':
        return generate_json(result, output_file, speaker_names)
    elif output_format == 'md':
        return generate_md(result, output_file, speaker_names)
    else:
        print(f"⚠️ 不支持的格式: {output_format}，使用默认 txt 格式")
        return generate_txt(result, output_file, speaker_names)


def generate_txt(result, output_file, speaker_names):
    """生成 TXT 格式的转录稿（对话段落式）

    合并同一说话者的连续片段为一个段落，段首标注 [开始-结束] [说话者]
    示例：
        [00:00:00 - 00:05:23] [SPEAKER_01]
        哈喽大家好，我是小俊。今天我们来聊聊...

        [00:05:23 - 00:08:45] [SPEAKER_02]
        我有不同的看法...
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        if 'segments' in result:
            # 合并同一说话者的连续片段
            groups = _merge_consecutive_speakers(result['segments'], speaker_names)
            
            for group in groups:
                start_str = format_timestamp(group['start'])
                end_str = format_timestamp(group['end'])
                speaker = group['speaker']
                text = group['text']
                
                header = f"[{start_str} - {end_str}] [{speaker}]"
                f.write(header + "\n")
                f.write(text + "\n\n")
                print(f"  {header}")
                print(f"    {text[:60]}..." if len(text) > 60 else f"    {text}")
        else:
            f.write(result['text'])
            print(result['text'])
    
    print(f"\n✅ TXT转录稿已保存: {output_file}")
    return output_file


def _merge_consecutive_speakers(segments, speaker_names):
    """将连续的同一说话者片段合并为段落

    改进点：
    - 单段落时长上限 5 分钟（超过就拆分，避免 25 分钟的超长段落）
    - 同一说话者两片段间隔超过 3 分钟也拆分（中间可能被遗漏的对话）
    - 基于内容启发式：问号结尾 + 下一段较长 → 可能是问答切换
    - 未映射的 SPEAKER_XX 根据上下文交替推断真实身份

    返回列表，每段包含 start, end, speaker, text
    """
    groups = []
    current_group = None

    # 单段落时长上限（秒）：超过 5 分钟就强制拆分
    MAX_PARAGRAPH_DURATION = 300
    # 同一说话者两片段间隔上限（秒）：超过 3 分钟就拆分
    MAX_SILENCE_BETWEEN_SAME_SPEAKER = 180

    # 收集已知的说话者名（用于推断未映射的 SPEAKER_XX）
    known_speakers = list(set(speaker_names.values())) if speaker_names else []
    # 如果没有已知说话者，尝试从 segments 中收集所有 SPEAKER_XX
    if not known_speakers:
        all_speakers = set()
        for seg in segments:
            spk = seg.get('speaker', '')
            if spk:
                all_speakers.add(spk)
        known_speakers = sorted(all_speakers)
    # 去掉未映射的 SPEAKER_XX，只保留真名
    known_real_names = [s for s in known_speakers if not s.startswith('SPEAKER_')]
    # 如果有真名，用真名；否则用所有 SPEAKER_XX
    if known_real_names:
        known_speakers = known_real_names

    # 第一遍：把未映射的 SPEAKER_XX 推断为已知说话者
    inferred_segments = []
    last_known_speaker = None
    for seg in segments:
        text = seg.get('text', '').strip()
        if not text:
            continue

        spk = seg.get('speaker', None)
        if spk and spk in speaker_names:
            speaker_display = speaker_names[spk]
            last_known_speaker = speaker_display
        elif spk and not spk.startswith('SPEAKER_'):
            # 已经是真名
            speaker_display = spk
            last_known_speaker = speaker_display
        elif spk and spk.startswith('SPEAKER_'):
            # 未映射的 SPEAKER_XX，根据上下文交替推断
            if len(known_speakers) == 2:
                # 2 人对话：交替推断
                if last_known_speaker:
                    # 用另一个人
                    other = [s for s in known_speakers if s != last_known_speaker]
                    speaker_display = other[0] if other else spk
                else:
                    # 没有上文，用第一个
                    speaker_display = known_speakers[0]
            elif known_speakers:
                # 多人：暂时保留，后面根据上下文判断
                speaker_display = spk
            else:
                speaker_display = spk
        else:
            speaker_display = '未知'

        seg_copy = dict(seg)
        seg_copy['_speaker_display'] = speaker_display
        inferred_segments.append(seg_copy)

    # 第二遍：合并连续同一说话者的片段
    for seg in inferred_segments:
        text = seg.get('text', '').strip()
        speaker_display = seg['_speaker_display']
        start = seg.get('start', 0)
        end = seg.get('end', 0)

        if current_group is None:
            current_group = {
                'start': start,
                'end': end,
                'speaker': speaker_display,
                'text': text
            }
        elif current_group['speaker'] == speaker_display:
            # 同一说话者
            gap = start - current_group['end']
            duration = current_group['end'] - current_group['start']

            # 检查是否需要拆分
            should_split = False
            # 条件1：当前段落已经超过时长上限
            if duration > MAX_PARAGRAPH_DURATION:
                should_split = True
            # 条件2：两片段间隔太大（可能中间有遗漏的对话）
            if gap > MAX_SILENCE_BETWEEN_SAME_SPEAKER:
                should_split = True
            # 条件3：内容启发式 — 上一段以问号结尾，可能是问答切换
            if current_group['text'].rstrip().endswith(('?', '？')) and len(text) > 30:
                should_split = True

            if should_split:
                # 保存当前段，开启新段（即使是同一说话者）
                groups.append(current_group)
                current_group = {
                    'start': start,
                    'end': end,
                    'speaker': speaker_display,
                    'text': text
                }
            else:
                # 合并：追加文字，更新结束时间
                current_group['end'] = end
                prev_text = current_group['text']
                if prev_text and prev_text[-1] in '，。！？、；：,.;:!?…':
                    current_group['text'] = prev_text + text
                else:
                    current_group['text'] = prev_text + '，' + text
        else:
            # 不同说话者，保存当前段，开启新段
            groups.append(current_group)
            current_group = {
                'start': start,
                'end': end,
                'speaker': speaker_display,
                'text': text
            }

    if current_group:
        groups.append(current_group)

    return groups


def generate_srt(result, output_file, speaker_names):
    """生成 SRT 字幕格式"""
    with open(output_file, 'w', encoding='utf-8') as f:
        index = 1
        if 'segments' in result:
            for segment in result['segments']:
                start_time = format_timestamp_srt(segment.get('start', 0))
                end_time = format_timestamp_srt(segment.get('end', 0))
                text = segment.get('text', '').strip()
                speaker = segment.get('speaker', None)
                
                if text:
                    # 替换说话者名称
                    if speaker and speaker in speaker_names:
                        speaker_display = speaker_names[speaker]
                    elif speaker:
                        speaker_display = speaker
                    else:
                        speaker_display = None
                    
                    f.write(f"{index}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    if speaker_display:
                        f.write(f"[{speaker_display}] {text}\n\n")
                    else:
                        f.write(f"{text}\n\n")
                    index += 1
    
    print(f"✅ SRT字幕已保存: {output_file}")
    return output_file


def generate_vtt(result, output_file, speaker_names):
    """生成 WebVTT 字幕格式"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        if 'segments' in result:
            for segment in result['segments']:
                start_time = format_timestamp_vtt(segment.get('start', 0))
                end_time = format_timestamp_vtt(segment.get('end', 0))
                text = segment.get('text', '').strip()
                speaker = segment.get('speaker', None)
                
                if text:
                    if speaker and speaker in speaker_names:
                        speaker_display = speaker_names[speaker]
                    elif speaker:
                        speaker_display = speaker
                    else:
                        speaker_display = None
                    
                    f.write(f"{start_time} --> {end_time}\n")
                    if speaker_display:
                        f.write(f"<v {speaker_display}>{text}</v>\n\n")
                    else:
                        f.write(f"{text}\n\n")
    
    print(f"✅ WebVTT字幕已保存: {output_file}")
    return output_file


def generate_json(result, output_file, speaker_names):
    """生成 JSON 结构化格式"""
    data = {
        'language': result.get('language', 'unknown'),
        'segments': []
    }
    
    if 'segments' in result:
        for segment in result['segments']:
            text = segment.get('text', '').strip()
            if text:
                speaker = segment.get('speaker', None)
                if speaker and speaker in speaker_names:
                    speaker_display = speaker_names[speaker]
                elif speaker:
                    speaker_display = speaker
                else:
                    speaker_display = None
                
                data['segments'].append({
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0),
                    'text': text,
                    'speaker': speaker_display
                })
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON数据已保存: {output_file}")
    return output_file


def generate_md(result, output_file, speaker_names):
    """生成 Markdown 格式（对话段落式）

    合并同一说话者的连续片段为一个段落
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 转录笔记\n\n")
        
        # 添加摘要
        if 'segments' in result:
            total_segments = len(result['segments'])
            duration = result['segments'][-1].get('end', 0)
            groups = _merge_consecutive_speakers(result['segments'], speaker_names)
            f.write(f"- **总片段数**: {total_segments}\n")
            f.write(f"- **总时长**: {format_timestamp(duration)}\n")
            f.write(f"- **对话段落数**: {len(groups)}\n")
            if 'language' in result:
                f.write(f"- **语言**: {result['language']}\n")
        f.write("\n---\n\n")
        
        # 添加内容（对话段落式）
        if 'segments' in result:
            groups = _merge_consecutive_speakers(result['segments'], speaker_names)
            
            for group in groups:
                start_str = format_timestamp(group['start'])
                end_str = format_timestamp(group['end'])
                speaker = group['speaker']
                text = group['text']
                
                f.write(f"**[{start_str} - {end_str}] [{speaker}]**\n\n")
                f.write(f"{text}\n\n")
    
    print(f"✅ Markdown笔记已保存: {output_file}")
    return output_file


def get_output_filename(output_dir=None, surname=''):
    """生成不带扩展名的输出文件路径

    使用 transcript_{序号}_{姓氏} 命名规则，自动扫描目录递增序号，避免覆盖。
    返回不带扩展名的路径，调用方按需追加 .txt / .md / .srt 等。
    所有输出格式共用同一序号，确保一次转录的多个文件序号一致。
    """
    # 确保 content_searcher 模块可导入
    SKILL_DIR = Path(__file__).parent
    if str(SKILL_DIR) not in sys.path:
        sys.path.insert(0, str(SKILL_DIR))
    from content_searcher import generate_transcript_basepath

    if output_dir is None:
        output_dir = Path.cwd()
    return generate_transcript_basepath(output_dir, surname)


def extract_surname_from_url(url):
    """从视频/音频 URL 获取标题和简介并提取受访者姓氏

    使用 yt-dlp 的 skip_download 模式获取标题和简介，再调用 extract_surname_from_title。
    提取失败时返回空字符串，不影响主流程。

    返回: (surname, title, description)
    """
    title, description, surname = '', '', ''
    try:
        import yt_dlp
        SKILL_DIR = Path(__file__).parent
        if str(SKILL_DIR) not in sys.path:
            sys.path.insert(0, str(SKILL_DIR))
        from content_searcher import extract_surname_from_title

        ydl_opts = {'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '')
            description = info.get('description', '') or ''
            if title:
                surname = extract_surname_from_title(title)
                if surname:
                    print(f"🏷️ 从标题提取受访者姓氏: {surname}（来源: {title}）")
    except Exception as e:
        print(f"⚠️ 提取受访者姓氏失败: {e}")
    return surname, title, description


def auto_assign_speakers(title='', description=''):
    """从标题和 shownotes 自动提取说话者，生成 SPEAKER_XX → 真名映射

    返回 (speaker_names_dict, detected_speakers_list)
    """
    try:
        SKILL_DIR = Path(__file__).parent
        if str(SKILL_DIR) not in sys.path:
            sys.path.insert(0, str(SKILL_DIR))
        from content_searcher import extract_speakers_from_shownotes, assign_speaker_names

        speakers = extract_speakers_from_shownotes(title, description)
        if speakers:
            mapping = assign_speaker_names(speakers, num_speakers=len(speakers))
            print(f"🎙️ 从 shownotes 识别说话者: {', '.join(speakers)}")
            return mapping, speakers
    except Exception as e:
        print(f"⚠️ 自动识别说话者失败: {e}")
    return {}, []


def parse_speaker_names(arg_value):
    """解析自定义说话者名称参数"""
    speaker_names = {}
    if arg_value:
        pairs = arg_value.split(',')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                speaker_names[key.strip()] = value.strip()
            else:
                # 如果没有 =，按顺序分配
                index = len(speaker_names) + 1
                speaker_names[f"SPEAKER_{index:02d}"] = pair.strip()
    return speaker_names


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Whisper 本地转录工具 V2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python local_whisper_transcriber_v2.py https://www.bilibili.com/video/BV1Z9QABeEgf
  python local_whisper_transcriber_v2.py /Users/dorian/audio.mp3 --ja --speaker
  python local_whisper_transcriber_v2.py /Users/dorian/audio.mp3 --speaker --speaker-names "妹岛和世,西泽立卫,主持人"
  python local_whisper_transcriber_v2.py /Users/dorian/audio.mp3 --formats "srt,vtt,md" --output-dir ./outputs
        """
    )
    
    # 必选参数
    parser.add_argument(
        "input",
        help="视频链接或本地音频文件路径"
    )
    
    # 语言参数
    parser.add_argument("--zh", "--cn", "--chinese", dest="lang_zh", action="store_true", help="指定为中文")
    parser.add_argument("--ja", "--jp", "--japanese", dest="lang_ja", action="store_true", help="指定为日语")
    parser.add_argument("--en", "--english", dest="lang_en", action="store_true", help="指定为英语")
    
    # 模型参数
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument("--tiny", action="store_true", help="最快，但准确率最低（约 32MB）")
    model_group.add_argument("--base", action="store_true", help="推荐日常使用（约 150MB，默认）")
    model_group.add_argument("--small", action="store_true", help="更准确，但更慢（约 500MB）")
    model_group.add_argument("--medium", action="store_true", help="非常准确，但很慢（约 1.5GB）")
    
    # 说话者识别
    parser.add_argument("--speaker", "--diarize", action="store_true", help="启用说话者识别")
    parser.add_argument("--speaker-names", type=str, default="", help="自定义说话者名称，格式: 'SPEAKER_01=张三,SPEAKER_02=李四' 或直接 '张三,李四'")
    
    # 输出格式
    parser.add_argument("--formats", type=str, default="txt", help="输出格式，多个用逗号分隔: txt,srt,vtt,json,md")
    parser.add_argument("--output-dir", type=str, default=None, help="输出目录，默认为当前目录")

    # 受访者姓氏（用于文件命名）
    parser.add_argument("--name", type=str, default="", help="受访者/作者姓氏，用于文件命名（如 --name xie → transcript_1_xie.txt）。不指定时自动从标题提取。")
    parser.add_argument("--no-simplified", action="store_true", help="关闭繁体→简体转换（默认开启，Whisper 中文转录默认输出繁体）")
    parser.add_argument("--no-correct", action="store_true", help="关闭自动校正（默认开启：字典+专有名词校正）")

    # 优化选项
    parser.add_argument("--preprocess", action="store_true", help="启用音频预处理（降噪+音量标准化+重采样，提高准确率）")
    parser.add_argument("--no-vad", action="store_true", help="关闭 VAD 静音过滤（默认开启，提速约 1.5-2 倍）")
    parser.add_argument("--initial-prompt", type=str, default="", help="手动指定 Whisper 初始提示词（提高专有名词识别率），不指定时自动从标题/shownotes生成")

    # 音频下载目录
    parser.add_argument("--audio-dir", type=str, default="./audio_downloads", help="音频下载目录")
    
    args = parser.parse_args()
    
    # 确定模型大小
    model_size = DEFAULT_MODEL
    if args.tiny:
        model_size = 'tiny'
    elif args.small:
        model_size = 'small'
    elif args.medium:
        model_size = 'medium'
    
    # 确定语言
    language = None
    if args.lang_zh:
        language = 'zh'
    elif args.lang_ja:
        language = 'ja'
    elif args.lang_en:
        language = 'en'
    
    # 解析说话者名称
    speaker_names = parse_speaker_names(args.speaker_names)
    if speaker_names:
        print(f"👤 自定义说话者名称: {speaker_names}")
    
    # 解析输出格式
    output_formats = [f.strip() for f in args.formats.split(',') if f.strip()]
    # 验证格式
    output_formats = [f for f in output_formats if f in SUPPORTED_FORMATS]
    if not output_formats:
        output_formats = ['txt']
    
    print(f"📝 输出格式: {', '.join(output_formats)}")
    if args.output_dir:
        print(f"📁 输出目录: {args.output_dir}")
    
    # 检测是否是URL
    is_url = args.input.startswith('http://') or args.input.startswith('https://')

    # 确定受访者姓氏（用于文件命名）：--name 优先，否则从 URL 标题自动提取
    surname = args.name
    title = ''  # 视频标题，用于后续校正和说话者识别
    description = ''  # 节目简介，用于提取说话者
    if not surname and is_url:
        surname, title, description = extract_surname_from_url(args.input)
    elif is_url:
        # 手动指定了姓氏，但还是获取标题和简介用于校正和说话者识别
        _, title, description = extract_surname_from_url(args.input)
    if surname:
        print(f"🏷️ 文件命名姓氏: {surname}（输出格式: transcript_{{序号}}_{surname}.{{ext}}）")

    # 自动识别说话者（从 shownotes）：用户没手动指定 speaker-names 时自动填充
    auto_speakers_list = []
    if not args.speaker_names and is_url:
        auto_speakers, auto_speakers_list = auto_assign_speakers(title, description)
        if auto_speakers:
            speaker_names.update(auto_speakers)
            print(f"🎙️ 从 shownotes 识别到 {len(auto_speakers_list)} 位说话者: {', '.join(auto_speakers_list)}")
            # 不再自动启用 --speaker（智能分组已足够好，且不需要 pyannote 依赖）
            # args.speaker = True

    # 生成 initial_prompt（提高专有名词识别准确率）
    initial_prompt = args.initial_prompt
    if not initial_prompt and (title or description or auto_speakers_list):
        try:
            SKILL_DIR = Path(__file__).parent
            if str(SKILL_DIR) not in sys.path:
                sys.path.insert(0, str(SKILL_DIR))
            from content_searcher import generate_initial_prompt
            initial_prompt = generate_initial_prompt(
                title=title,
                description=description,
                speakers=auto_speakers_list,
                language=language or 'zh'
            )
        except Exception as e:
            print(f"⚠️ 生成提示词失败: {e}")
            initial_prompt = ''

    if is_url:
        # 第一步：下载音频
        audio_file = download_audio(args.input, output_dir=args.audio_dir)
        if not audio_file:
            print("\n❌ 音频下载失败，无法继续")
            return 1
    else:
        # 本地文件，直接使用
        audio_file = args.input
        print(f"📁 使用本地文件: {audio_file}")
    
    # 音频预处理（可选，提高准确率）
    if args.preprocess:
        audio_file = preprocess_audio(audio_file, output_dir=args.audio_dir)
    
    # 第二步：本地转录
    result = transcribe_local(
        audio_file, 
        model_size=model_size, 
        language=language, 
        speaker_diarization=args.speaker,
        initial_prompt=initial_prompt if initial_prompt else None,
        vad_filter=not args.no_vad,
        speakers=auto_speakers_list if auto_speakers_list else None
    )
    
    # 第三步：生成各种格式的转录稿（统一使用 transcript_{序号}_{姓氏} 命名，所有格式共用同一序号）
    base_filename = get_output_filename(args.output_dir, surname)

    # 繁体 → 简体转换（默认开启，Whisper 中文转录默认是繁体）
    if not args.no_simplified:
        result = _to_simplified_chinese(result)

    output_files = []
    for fmt in output_formats:
        output_file = f"{base_filename}.{fmt}"
        generate_transcript(
            result,
            output_file,
            output_format=fmt,
            speaker_names=speaker_names
        )
        output_files.append(output_file)

    # 第四步：自动校正（A+B+C+D 方案，秒级）
    # 字典校正 + 专有名词校正 + 一致性校正 + prompt 残留清理
    if not args.no_correct:
        try:
            from transcript_corrector import correct_transcript
            print(f"\n🔧 自动校正转录稿...")
            # 用实际传入的 initial_prompt（如果有）或者自动生成的
            prompt_for_clean = initial_prompt if initial_prompt else None
            for output_file in output_files:
                if output_file.endswith('.txt') or output_file.endswith('.md'):
                    text = Path(output_file).read_text(encoding='utf-8')
                    corrected, total, details = correct_transcript(
                        text, title=title, keywords=None,
                        initial_prompt=prompt_for_clean
                    )
                    if total > 0:
                        Path(output_file).write_text(corrected, encoding='utf-8')
                        print(f"   ✅ {Path(output_file).name}: 校正 {total} 处")
                        for desc, info, cnt in details:
                            print(f"      - {desc}: {cnt} 处")
                    else:
                        print(f"   ✅ {Path(output_file).name}: 无需校正")
        except ImportError:
            print(f"⚠️ 校正模块未找到，跳过自动校正")
        except Exception as e:
            print(f"⚠️ 自动校正失败: {e}")

    print("\n" + "="*70)
    print("🎉 全部完成！")
    print(f"📄 生成的文件:")
    for f in output_files:
        print(f"   - {f}")
    print(f"💡 提示: 现在可以把转录稿发给 learning-content-analyzer skill 分析了！")
    print("="*70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
