#!/usr/bin/env python3
"""
本地 Whisper 转录工具 - 完全免费！
不需要 API Key，不需要信用卡，不需要网络（除了下载视频）
支持B站反爬虫处理
"""

import sys
import os
import yt_dlp
from pathlib import Path

def is_bilibili(url):
    """判断是否是B站链接"""
    return 'bilibili.com' in url.lower()

def download_audio(url, output_dir='./audio_downloads'):
    """只下载音频，支持B站反爬虫"""
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

def _select_device():
    """自动选择计算设备：优先 CPU（兼容性最好），其次 CUDA

    注意：MPS (Apple Silicon GPU) 在 whisper 20250625 版本上有 float64 兼容性问题，
    因此默认使用 CPU。
    """
    try:
        import torch
        if torch.cuda.is_available():
            print(f"⚡ 已启用 NVIDIA GPU 加速（CUDA）")
            return "cuda"
    except ImportError:
        pass
    print(f"💻 使用 CPU 转录")
    return "cpu"


def transcribe_local(audio_path, model_size='base', language=None, speaker_diarization=False):
    """使用本地 Whisper 转录

    说话者识别逻辑（智能开关）：
      speaker_diarization=True  → pyannote 音色识别（精准，慢）
      speaker_diarization=False → 简单分组（基于沉默间隔，快，默认）
    """
    try:
        import whisper
    except ImportError:
        print("\n❌ 需要先安装 Whisper！")
        print("\n请运行: pip install openai-whisper")
        print("如果在 macOS 上还需要: brew install ffmpeg")
        sys.exit(1)

    device = _select_device()

    print(f"🎤 正在加载模型: {model_size}（device={device}）...")
    print(f"💡 提示: 第一次运行会自动下载模型")
    model = whisper.load_model(model_size, device=device)

    print(f"📝 正在转录...")
    base_kwargs = {'word_timestamps': True, 'verbose': False}

    if language:
        print(f"🔤 指定语言: {language}")
    else:
        print(f"🔤 自动检测语言...")

    # 逐步回退策略，确保各种 whisper 版本都能工作
    result = None

    # 方案1：直接传 language
    try:
        kwargs = dict(base_kwargs)
        if language:
            kwargs['language'] = language
        result = model.transcribe(audio_path, **kwargs)
    except TypeError:
        # 方案2：通过 decode_options 传 language
        try:
            kwargs = dict(base_kwargs)
            if language:
                kwargs['decode_options'] = {'language': language}
            result = model.transcribe(audio_path, **kwargs)
        except TypeError:
            # 方案3：最基础版本
            result = model.transcribe(audio_path, word_timestamps=True, verbose=False)

    # 说话者识别（智能开关）
    if speaker_diarization:
        # 用户显式 --speaker，用 pyannote 音色识别（精准但慢）
        result = add_speaker_labels(result, audio_path)
    else:
        # 默认用简单分组（快，基于沉默间隔）
        result = add_simple_speaker_labels(result)
        print(f"🏷️ 已启用简单说话者分组（如需精准音色识别请加 --speaker）")

    print(f"✅ 转录成功！")
    if 'language' in result:
        print(f"🌍 检测到的语言: {result['language']}")
    return result

def _get_hf_token():
    """读取 HuggingFace access token

    优先级：环境变量 HF_TOKEN > HUGGING_FACE_HUB_TOKEN > 文件 ~/.huggingface_token
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

    需要：pip install pyannote.audio torch + HuggingFace token（见 SKILL.md）
    任何步骤失败都回退到 add_simple_speaker_labels（基于沉默间隔，无依赖）。
    """
    try:
        from pyannote.audio import Pipeline
        import torch
        print(f"🎙️ 正在进行音色识别（pyannote.audio）...")

        token = _get_hf_token()
        if not token:
            print(f"⚠️ 未找到 HuggingFace token，无法下载 pyannote 模型")
            print(f"   配置方式见 SKILL.md「安装音色识别依赖」一节")
            print(f"   本次回退到简单说话者分组")
            return add_simple_speaker_labels(result)

        # 新版 pyannote.audio 用 token= 参数（旧版 use_auth_token 已废弃）
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=token
            )
        except Exception as e:
            print(f"⚠️ 模型加载失败: {e}")
            print(f"   请确认：1) 已申请三个模型权限  2) token 有效  3) 网络通畅")
            print(f"   本次回退到简单说话者分组")
            return add_simple_speaker_labels(result)

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
        print(f"   安装方式：pip3.11 install pyannote.audio torch")
        return add_simple_speaker_labels(result)
    except Exception as e:
        print(f"⚠️ 音色识别失败: {e}，回退到简单分组")
        return add_simple_speaker_labels(result)

def add_simple_speaker_labels(result, num_speakers=2):
    """简单的说话者识别：基于间隔和对话模式分组

    改进点：
    - SPEAKER 编号从 0 开始（与 assign_speaker_names 映射一致）
    - 默认 2 人对话，按实际人数循环而非硬编码 3
    - 沉默阈值从 1.5s 提高到 3s（减少过度合并）
    """
    from collections import defaultdict

    segments = result.get('segments', [])
    if not segments:
        return result

    # 首先，合并时间上非常接近的片段
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

    # 为每个组分配说话者（从 SPEAKER_00 开始，与 assign_speaker_names 一致）
    speaker_counter = 0
    for group in merged_segments:
        speaker_id = f"SPEAKER_{speaker_counter:02d}"
        for seg in group:
            seg['speaker'] = speaker_id

        # 按实际人数循环
        speaker_counter += 1
        if speaker_counter >= num_speakers:
            speaker_counter = 0

    return result

def format_timestamp(seconds):
    """将秒数转换为 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def _to_simplified_chinese(result):
    """将转录结果中的繁体中文转换为简体中文

    优先用 opencc（需 pip install opencc-python-reimplemented），
    未安装时回退到内置高频异体字映射。
    """
    try:
        from opencc import OpenCC
        cc = OpenCC('t2s')
        def convert_text(text):
            return cc.convert(text)
        print(f"🌐 使用 opencc 繁简转换（精准）")
    except ImportError:
        # 回退：高频繁简异体字映射（覆盖 400+ 常见繁简差异字）
        _T2S = {
            # === 代词/疑问词 ===
            '什麼': '什么', '怎麼': '怎么', '為什麼': '为什么', '誰': '谁',
            '這裡': '这里', '那裡': '那里', '這樣': '这样', '那樣': '那样',
            '怎麼樣': '怎么样', '每個': '每个', '各個': '各个',
            '這些': '这些', '那些': '那些',
            
            # === 常见动词 ===
            '發現': '发现', '覺得': '觉得', '認為': '认为', '聽到': '听到',
            '說話': '说话', '讀書': '读书', '寫': '写', '學习': '学习',
            '開始': '开始', '結束': '结束', '過來': '过来', '過去': '过去',
            '起來': '起来', '進入': '进入', '離開': '离开', '達到': '达到',
            '實現': '实现', '獲得': '获得', '產生': '产生', '變成': '变成',
            '稱為': '称为', '叫作': '叫作', '屬於': '属于', '包括': '包括',
            '需要': '需要', '應該': '应该', '能夠': '能够', '必須': '必须',
            '願意': '愿意',
            
            # === 时间相关 ===
            '時間': '时间', '時候': '时候', '現在': '现在', '過去': '过去',
            '將來': '将来', '未來': '未来', '剛才': '刚才', '然後': '然后',
            '後來': '后来', '以後': '以后', '以前': '以前', '同時': '同时',
            '隨時': '随时', '暫時': '暂时', '永遠': '永远', '已經': '已经',
            '曾經': '曾经', '總是': '总是', '經常': '经常', '常常': '常常',
            '時常': '时常', '偶爾': '偶尔', '終於': '终于',
            
            # === 地点/方位 ===
            '地方': '地方', '哪裡': '哪里', '上面': '上面', '下面': '下面',
            '左邊': '左边', '右邊': '右边', '中間': '中间', '旁邊': '旁边',
            '對面': '对面', '國家': '国家', '城市': '城市', '地區': '地区',
            '區域': '区域', '環境': '环境',
            
            # === 形容词 ===
            '年輕': '年轻', '美麗': '美丽', '聰明': '聪明', '快樂': '快乐',
            '難過': '难过', '高興': '高兴', '生氣': '生气', '擔心': '担心',
            '緊張': '紧张', '輕鬆': '轻松', '認真': '认真', '馬虎': '马虎',
            '仔細': '仔细', '勇敢': '勇敢', '膽小': '胆小', '誠實': '诚实',
            '虛偽': '虚伪', '真誠': '真诚', '虛假': '虚假', '熱情': '热情',
            '冷漠': '冷漠', '親切': '亲切', '嚴肅': '严肃', '和藹': '和蔼',
            
            # === 数量词 ===
            '萬': '万', '億': '亿', '百萬': '百万', '千萬': '千万',
            '第一': '第一', '第二': '第二', '許多': '许多', '眾多': '众多',
            '少數': '少数', '全部': '全部',
            
            # === 科技/互联网 ===
            '電腦': '电脑', '手機': '手机', '網絡': '网络', '網路': '网络',
            '互聯網': '互联网', '軟件': '软件', '硬體': '硬件',
            '程式': '程序', '數據': '数据', '資料': '数据', '訊息': '信息',
            '服務': '服务', '服務器': '服务器', '數碼': '数码', '相機': '相机',
            '顯示': '显示', '顯示器': '显示器', '鍵盤': '键盘', '鼠標': '鼠标',
            '檔案': '文件', '文檔': '文档', '圖片': '图片', '圖像': '图像',
            '視頻': '视频', '音頻': '音频', '錄音': '录音', '錄像': '录像',
            '播放': '播放', '下載': '下载', '上傳': '上传', '鏈接': '链接',
            '網站': '网站', '頁面': '页面', '登錄': '登录', '註冊': '注册',
            '賬號': '账号', '密碼': '密码', '搜索': '搜索', '引擎': '引擎',
            '智能': '智能', '智慧': '智慧', '人工智慧': '人工智能',
            '機器人': '机器人', '自動': '自动', '虛擬': '虚拟', '現實': '现实',
            '增強': '增强',
            
            # === 商业/经济 ===
            '經濟': '经济', '商業': '商业', '企業': '企业', '公司': '公司',
            '集團': '集团', '品牌': '品牌', '產品': '产品', '市場': '市场',
            '營銷': '营销', '銷售': '销售', '購買': '购买', '消費': '消费',
            '價格': '价格', '貨幣': '货币', '資金': '资金', '資本': '资本',
            '投資': '投资', '融資': '融资', '貸款': '贷款', '儲蓄': '储蓄',
            '利息': '利息', '利潤': '利润', '盈利': '盈利', '虧損': '亏损',
            '成本': '成本', '費用': '费用', '收入': '收入', '支出': '支出',
            '預算': '预算', '稅務': '税务', '財務': '财务', '會計': '会计',
            '審計': '审计', '管理': '管理', '運營': '运营', '營運': '运营',
            '戰略': '战略', '計劃': '计划', '目標': '目标', '績效': '绩效',
            '考核': '考核', '獎勵': '奖励', '激勵': '激励', '員工': '员工',
            '職員': '职员', '經理': '经理', '總裁': '总裁', '總監': '总监',
            '負責人': '负责人', '創始人': '创始人', '合夥人': '合伙人',
            '股東': '股东', '董事': '董事', '監事': '监事',
            
            # === 汽车/交通 ===
            '汽車': '汽车', '跑車': '跑车', '轎車': '轿车', '卡車': '卡车',
            '公車': '公车', '巴士': '巴士', '地鐵': '地铁', '高鐵': '高铁',
            '鐵路': '铁路', '飛機': '飞机', '輪船': '轮船', '自行車': '自行车',
            '電動車': '电动车', '新能源': '新能源', '充電': '充电',
            '電池': '电池', '發動機': '发动机', '變速箱': '变速箱',
            '底盤': '底盘', '車身': '车身', '車燈': '车灯', '輪胎': '轮胎',
            '刹車': '刹车', '轉向': '转向', '駕駛': '驾驶',
            '自動駕駛': '自动驾驶', '導航': '导航', '儀表盤': '仪表盘',
            '座椅': '座椅', '空調': '空调', '音響': '音响',
            
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
            '穩穩當當': '稳稳当当', '實實在在': '实实在在',
            
            # === 常见双字词 ===
            '重要': '重要', '主要': '主要', '關鍵': '关键', '核心': '核心',
            '基礎': '基础', '根本': '根本', '基本': '基本', '原則': '原则',
            '規則': '规则', '標準': '标准', '水準': '水平', '水平': '水平',
            '品質': '质量', '質量': '质量', '數量': '数量', '體積': '体积',
            '面積': '面积', '重量': '重量', '長度': '长度', '寬度': '宽度',
            '高度': '高度', '深度': '深度', '速度': '速度', '強度': '强度',
            '硬度': '硬度', '密度': '密度', '溫度': '温度', '濕度': '湿度',
            
            # === 常见漏网之鱼（按实际转录发现） ===
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
            
            # === 感觉/情感 ===
            '覺得': '觉得', '感覺': '感觉', '感受': '感受', '感動': '感动',
            '激動': '激动', '興奮': '兴奋', '傷心': '伤心', '痛苦': '痛苦',
            '煩惱': '烦恼', '憂慮': '忧虑', '焦慮': '焦虑', '恐懼': '恐惧',
            '害怕': '害怕', '羞': '羞', '恥': '耻', '驕傲': '骄傲',
            '謙虛': '谦虚', '自卑': '自卑', '自信': '自信',
            
            # === 思考/认知 ===
            '思想': '思想', '思維': '思维', '觀點': '观点', '看法': '看法',
            '見解': '见解', '認識': '认识', '了解': '了解', '理解': '理解',
            '明白': '明白', '清楚': '清楚', '模糊': '模糊', '混亂': '混乱',
            '記得': '记得', '忘記': '忘记', '回憶': '回忆', '想象': '想象',
            '幻想': '幻想', '夢想': '梦想', '理想': '理想', '打算': '打算',
            '準備': '准备', '預計': '预计',
            
            # === 高频单字 ===
            '灣': '湾', '體': '体', '國': '国', '來': '来', '會': '会',
            '說': '说', '見': '见', '過': '过', '給': '给', '時': '时',
            '對': '对', '們': '们', '這': '这', '個': '个', '經': '经',
            '後': '后', '從': '从', '現': '现', '發': '发', '為': '为',
            '與': '与', '於': '于', '電': '电', '實': '实', '學': '学',
            '動': '动', '車': '车', '間': '间', '員': '员', '裡': '里',
            '還': '还', '邊': '边', '開': '开', '關': '关', '點': '点',
            '頭': '头', '兩': '两', '應': '应', '該': '该', '無': '无',
            '業': '业', '產': '产', '當': '当', '處': '处', '據': '据',
            '認': '认', '計': '计', '結': '结', '論': '论', '資': '资',
            '訊': '讯', '場': '场', '辦': '办', '氣': '气', '數': '数',
            '農': '农', '運': '运', '軍': '军', '廠': '厂', '歷': '历',
            '藝': '艺', '術': '术', '節': '节', '簡': '简', '單': '单',
            '網': '网', '絡': '络', '視': '视', '頻': '频', '腦': '脑',
            '軟': '软', '語': '语', '導': '导', '雖': '虽', '備': '备',
            '條': '条', '萬': '万', '塊': '块', '錢': '钱', '買': '买',
            '賣': '卖', '機': '机', '進': '进', '歐': '欧', '亞': '亚',
            '聯': '联', '億': '亿', '麥': '麦', '風': '风', '雲': '云',
            '龍': '龙', '鳳': '凤', '鳥': '鸟', '魚': '鱼', '馬': '马',
            '豬': '猪', '貓': '猫', '書': '书', '畫': '画', '樂': '乐',
            '詩': '诗', '詞': '词', '戲': '戏', '劇': '剧', '報': '报',
            '紙': '纸', '雜': '杂', '誌': '志', '圖': '图', '館': '馆',
            '醫': '医', '藥': '药', '貿': '贸', '銀': '银', '幣': '币',
            '稅': '税', '務': '务', '財': '财', '窮': '穷', '貧': '贫',
            '貴': '贵', '賤': '贱', '強': '强', '壯': '壮', '長': '长',
            '寬': '宽', '輕': '轻', '熱': '热', '溫': '温', '涼': '凉',
            '乾': '干', '濕': '湿', '陰': '阴', '陽': '阳', '聲': '声',
            '鹹': '咸', '飽': '饱', '餓': '饿', '飛': '飞', '騎': '骑',
            '鐵': '铁', '鋼': '钢', '銅': '铜', '寶': '宝', '磚': '砖',
            '塵': '尘', '煙': '烟', '霧': '雾', '紅': '红', '黃': '黄',
            '藍': '蓝', '綠': '绿', '暈': '晕', '輝': '辉', '燦': '灿',
            '爛': '烂', '濁': '浊', '淨': '净', '髒': '脏', '潔': '洁',
            '純': '纯', '離': '离', '遠': '远', '淺': '浅', '雙': '双',
            '週': '周', '紀': '纪', '歲': '岁', '鐘': '钟', '錶': '表',
            '針': '针', '觀': '观', '討': '讨', '讓': '让', '記': '记',
            '錄': '录', '區': '区', '類': '类', '種': '种', '樣': '样',
            '態': '态', '構': '构', '碼': '码', '鍵': '键', '盤': '盘',
            '標': '标', '螢': '萤', '檔': '档', '庫': '库', '頁': '页',
            '尋': '寻', '篩': '筛', '選': '选', '擇': '择', '擊': '击',
            '觸': '触', '捲': '卷', '軸': '轴', '滾': '滚',
            '輪': '轮', '齒': '齿', '槓': '杠', '桿': '杆', '潤': '润',
            '劑': '剂', '損': '损', '勞': '劳', '變': '变', '彎': '弯',
            '轉': '转', '盪': '荡', '搖': '摇', '顫': '颤', '諧': '谐',
            '鳴': '鸣', '響': '响', '擾': '扰', '號': '号', '遲': '迟',
            '誤': '误', '準': '准', '調': '调', '適': '适', '滿': '满',
            '達': '达', '優': '优', '勝': '胜', '敗': '败', '終': '终',
            '屬': '属', '慮': '虑', '臨': '临', '順': '顺', '隨': '随',
            '辨': '辨', '察': '察', '鑒': '鉴', '審': '审', '權': '权',
            '親': '亲', '賢': '贤', '舉': '举', '錯': '错', '諸': '诸',
            '寧': '宁', '縱': '纵', '設': '设', '複': '复', '難': '难',
            '緩': '缓', '鈍': '钝', '靈': '灵', '銳': '锐', '確': '确',
            '著': '着', '麼': '么',
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

    if 'segments' in result:
        for seg in result['segments']:
            if 'text' in seg:
                seg['text'] = convert_text(seg['text'])
    if 'text' in result:
        result['text'] = convert_text(result['text'])
    return result


def generate_transcript(result, output_file=None):
    """生成带时间戳和说话者标签的转录稿（对话段落式）

    合并同一说话者的连续片段为一个段落，段首标注 [开始-结束] [说话者]
    """
    from content_searcher import generate_transcript_filename

    # 繁体 → 简体转换（Whisper 中文转录默认是繁体）
    result = _to_simplified_chinese(result)

    if not output_file:
        output_file = generate_transcript_filename(Path.cwd())

    with open(output_file, 'w', encoding='utf-8') as f:
        if 'segments' in result:
            groups = _merge_consecutive_speakers(result['segments'], {})
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

    print(f"\n✅ 转录稿已保存: {output_file}")
    return output_file


def _merge_consecutive_speakers(segments, speaker_names):
    """将连续的同一说话者片段合并为段落

    改进点：
    - 单段落时长上限 5 分钟（避免超长段落）
    - 同一说话者两片段间隔超过 3 分钟也拆分
    - 未映射的 SPEAKER_XX 根据上下文交替推断

    返回列表，每段包含 start, end, speaker, text
    """
    groups = []
    current_group = None

    MAX_PARAGRAPH_DURATION = 300  # 5 分钟
    MAX_SILENCE_BETWEEN_SAME_SPEAKER = 180  # 3 分钟

    # 收集已知说话者名
    known_speakers = list(set(speaker_names.values())) if speaker_names else []
    if not known_speakers:
        all_speakers = set()
        for seg in segments:
            spk = seg.get('speaker', '')
            if spk:
                all_speakers.add(spk)
        known_speakers = sorted(all_speakers)
    known_real_names = [s for s in known_speakers if not s.startswith('SPEAKER_')]
    if known_real_names:
        known_speakers = known_real_names

    # 第一遍：推断未映射的 SPEAKER_XX
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
            speaker_display = spk
            last_known_speaker = speaker_display
        elif spk and spk.startswith('SPEAKER_'):
            if len(known_speakers) == 2:
                if last_known_speaker:
                    other = [s for s in known_speakers if s != last_known_speaker]
                    speaker_display = other[0] if other else spk
                else:
                    speaker_display = known_speakers[0]
            elif known_speakers:
                speaker_display = spk
            else:
                speaker_display = spk
        else:
            speaker_display = '旁白'

        seg_copy = dict(seg)
        seg_copy['_speaker_display'] = speaker_display
        inferred_segments.append(seg_copy)

    # 第二遍：合并
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
            gap = start - current_group['end']
            duration = current_group['end'] - current_group['start']
            should_split = False
            if duration > MAX_PARAGRAPH_DURATION:
                should_split = True
            if gap > MAX_SILENCE_BETWEEN_SAME_SPEAKER:
                should_split = True
            if current_group['text'].rstrip().endswith(('?', '？')) and len(text) > 30:
                should_split = True

            if should_split:
                groups.append(current_group)
                current_group = {
                    'start': start,
                    'end': end,
                    'speaker': speaker_display,
                    'text': text
                }
            else:
                current_group['end'] = end
                prev_text = current_group['text']
                if prev_text and prev_text[-1] in '，。！？、；：,.;:!?…':
                    current_group['text'] = prev_text + text
                else:
                    current_group['text'] = prev_text + '，' + text
        else:
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

def main():
    if len(sys.argv) < 2:
        print("用法: python local_whisper_transcriber.py <视频链接或本地音频文件> [--语言] [--模型大小] [--说话者识别]")
        print("示例:")
        print("  python local_whisper_transcriber.py https://www.bilibili.com/video/BV1Z9QABeEgf")
        print("  python local_whisper_transcriber.py /Users/dorian/audio.mp3 --ja")
        print("  python local_whisper_transcriber.py /Users/dorian/audio.mp3 --speaker")
        print("\n💡 可选参数:")
        print("  --zh, --cn, --chinese   - 指定为中文")
        print("  --ja, --jp, --japanese  - 指定为日语")
        print("  --en, --english         - 指定为英语")
        print("  --tiny                  - 最快，但准确率最低（约 32MB）")
        print("  --base                  - 推荐日常使用（约 150MB，默认）")
        print("  --small                 - 更准确，但更慢（约 500MB）")
        print("  --medium                - 非常准确，但很慢（约 1.5GB）")
        print("  --speaker, --diarize    - 启用说话者识别（区分不同说话者）")
        sys.exit(1)
    
    # 解析参数
    video_url = sys.argv[1]
    model_size = 'base'  # 默认
    language = None      # 默认自动检测
    speaker_diarization = False  # 默认不启用说话者识别
    
    # 语言参数
    if '--zh' in sys.argv or '--cn' in sys.argv or '--chinese' in sys.argv:
        language = 'zh'
    elif '--ja' in sys.argv or '--jp' in sys.argv or '--japanese' in sys.argv:
        language = 'ja'
    elif '--en' in sys.argv or '--english' in sys.argv:
        language = 'en'
    
    # 模型大小参数
    if '--tiny' in sys.argv:
        model_size = 'tiny'
    elif '--small' in sys.argv:
        model_size = 'small'
    elif '--medium' in sys.argv:
        model_size = 'medium'
    
    # 说话者识别参数
    if '--speaker' in sys.argv or '--diarize' in sys.argv:
        speaker_diarization = True
        print(f"🎙️ 已启用说话者识别")
    
    # 检测是否是本地文件
    is_url = video_url.startswith('http://') or video_url.startswith('https://')
    
    if is_url:
        # 第一步：下载音频
        audio_file = download_audio(video_url)
    else:
        # 本地文件，直接使用
        audio_file = video_url
        print(f"📁 使用本地文件: {audio_file}")
    
    # 第二步：本地转录
    result = transcribe_local(audio_file, model_size, language, speaker_diarization)
    
    # 第三步：生成带时间戳的转录稿
    transcript_file = generate_transcript(result)
    
    print("\n" + "="*60)
    print("🎉 全部完成！")
    print(f"📄 转录稿: {transcript_file}")
    print(f"💡 提示: 现在可以把转录稿发给 learning-content-analyzer skill 分析了！")
    print("="*60)

if __name__ == '__main__':
    main()
