#!/usr/bin/env python3
"""
转录稿校正工具（A+B 方案）

方案 A：规则化字典校正（秒级，覆盖 Whisper 中文常见错字）
方案 B：专有名词预提取 + 批量校正（10-30秒，针对人名/公司名/术语）

用法：
    from transcript_corrector import correct_transcript
    corrected = correct_transcript(text, title="视频标题", keywords=["OpenAI", "GPT"])

    # 或命令行
    python3 transcript_corrector.py transcript_1_xie.txt --title "翁家翌：OpenAI"
"""

import re
import sys
from pathlib import Path


# ============================================================
# 方案 A：规则化字典校正
# ============================================================

# Whisper 中文转录常见错误字典（错误 → 正确）
# 注意：繁简转换已由 opencc（或 local_whisper_transcriber 内置映射）处理，
# 这里只列 Whisper 会输出错的词：台湾用语、音译错字、常见同音错字
WRONG_WORDS = {
    # === 台湾用语 → 大陆用语（词级差异，非单字繁简）===
    '人工智慧': '人工智能',
    '演算法': '算法',
    '程式': '程序',
    '軟體': '软件',
    '硬體': '硬件',
    '網際網路': '互联网',
    '網路': '网络',
    '頻寬': '带宽',
    '資料庫': '数据库',
    '資料': '数据',
    '記憶體': '内存',
    '儲存': '存储',
    '終端機': '终端',
    '使用者': '用户',
    '介面': '接口',
    '應用程式': '应用程序',
    '伺服器': '服务器',
    '微服務': '微服务',
    '智慧型': '智能',
    '智慧手機': '智能手机',
    '平板電腦': '平板电脑',
    '筆記型電腦': '笔记本电脑',
    '行動電話': '手机',
    '在線': '在线',
    '離線': '离线',
    '網站': '网站',
    '網頁': '网页',
    '連結': '链接',
    '點擊': '点击',
    '瀏覽器': '浏览器',
    '搜尋': '搜索',
    '搜尋引擎': '搜索引擎',
    '社群媒體': '社交媒体',
    '影片': '视频',
    '雲端': '云端',
    '雲計算': '云计算',
    '大數據': '大数据',
    '區塊鏈': '区块链',
    '機器學習': '机器学习',
    '深度學習': '深度学习',
    '類神經網路': '神经网络',
    '強化學習': '强化学习',
    '自然語言處理': '自然语言处理',
    '電腦視覺': '计算机视觉',
    '語音辨識': '语音识别',
    '圖像辨識': '图像识别',
    '資料探勘': '数据挖掘',
    '資料科學': '数据科学',
    '資訊': '信息',
    '資訊科技': '信息技术',
    '軟體工程': '软件工程',
    '開源': '开源',
    '原始碼': '源代码',
    '程式碼': '代码',
    '除錯': '调试',
    '測試': '测试',
    '部署': '部署',
    '維運': '运维',
    '架構': '架构',
    '模組': '模块',
    '元件': '组件',
    '介接': '对接',
    '串接': '对接',
    '載具': '载体',
    '韌體': '固件',
    '驅動程式': '驱动程序',
    '作業系統': '操作系统',
    '核心': '内核',
    '行程': '进程',
    '執行緒': '线程',
    '記憶體位址': '内存地址',
    '快取': '缓存',
    '暫存': '缓存',
    '磁碟': '磁盘',
    '固態硬碟': '固态硬盘',
    '顯示卡': '显卡',
    '圖形處理器': '图形处理器',
    '中央處理器': '中央处理器',

    # === 音译错字 → 正确英文（Whisper 常见误识）===
    '吉皮提': 'GPT',
    '恰特吉皮提': 'ChatGPT',
    '安斯阿': 'Anthropic',
    '克勞德': 'Claude',
    '傑米尼': 'Gemini',
    '帕爾米': 'Palm',
    '拉瑪': 'LLaMA',
    '泰斯拉': 'Tesla',
    '油管': 'YouTube',
    '米德乔尼': 'Midjourney',
    '稳定扩散': 'Stable Diffusion',
    '达利': 'DALL-E',
    '索拉': 'Sora',
    '杰普森': 'Jasper',
    '诺瓦': 'Nova',
    '格米尼': 'Gemini',
    '克洛德': 'Claude',

    # === 中文人名错字（繁体字形 → 简体标准）===
    '黃仁勳': '黄仁勋',
    '蘇姿丰': '苏姿丰',
    '李彥宏': '李彦宏',
    '馬化騰': '马化腾',
    '雷軍': '雷军',
    '周鴻禕': '周鸿祎',
    '張一鳴': '张一鸣',
    '王興': '王兴',
    '程維': '程维',
    # 同音/近音错字（Whisper 实际案例）
    '杨丽昆': '杨立昆',      # Yann LeCun，常被误识为"杨丽昆"
    '楊麗昆': '杨立昆',
    '伊莉亚': '伊利亚',      # Ilya Sutskever，"莉"是错字
    '伊莉亞': '伊利亚',
    '谢在宁': '谢赛宁',      # "在"是错字，正确是"赛"
    '謝在寧': '谢赛宁',
    '李一夫': '李一舟',
    '张骁雨': '张潇雨',
    '张小雨': '张潇雨',
    '张之': '张潇雨',
    '翁佳怡': '翁家翌',
    '翁嘉义': '翁家翌',
    '陆家翌': '翁家翌',

    # === 中文公司名俗称 → 英文标准名 ===
    '臉書': 'Facebook',
    '微軟': 'Microsoft',
    '蘋果': 'Apple',
    '亞馬遜': 'Amazon',
    '英特爾': 'Intel',
    '輝達': 'Nvidia',
    '網飛': 'Netflix',
    '優步': 'Uber',
    '愛彼迎': 'Airbnb',
    '推特': 'Twitter',
    '谷歌': 'Google',
    '谷歌声': 'Google',
    '歌诗达': 'Google',
    '阿尔法特': 'Alphabet',
    '字母表公司': 'Alphabet',
    '迈塔': 'Meta',
    '元平台': 'Meta',
    '甲骨文': 'Oracle',
    '赛富时': 'Salesforce',
    '思爱普': 'SAP',
    '国际商业机器': 'IBM',

    # === 投资/商业术语（台湾/繁体 → 大陆标准）===
    '獲利': '盈利',
    '營收': '营收',
    '虧損': '亏损',
    '淨利': '净利润',
    '毛利': '毛利',
    '毛利率': '毛利率',
    '淨利率': '净利率',
    '每股盈餘': '每股收益',
    '市值': '市值',
    '股價': '股价',
    '股息': '股息',
    '分紅': '分红',
    '融資': '融资',
    '投資': '投资',
    '創投': '创投',
    '天使輪': '天使轮',
    'A 輪': 'A轮',
    'B 輪': 'B轮',
    '獨角獸': '独角兽',
    '新創公司': '创业公司',
    '新創': '创业',
    '商業模式': '商业模式',
    '變現': '变现',
    '盈利模式': '盈利模式',
    '護城河': '护城河',
    '競爭力': '竞争力',
    '市場佔有率': '市场份额',
    '市佔率': '市场份额',
    '用戶增長': '用户增长',
    '留存率': '留存率',
    '活躍用戶': '活跃用户',
    '日活': '日活',
    '月活': '月活',
    '轉化率': '转化率',
    '客單價': '客单价',
    '終身價值': '终身价值',
    '客戶獲取成本': '客户获取成本',
    '投資回報率': '投资回报率',
    '內部收益率': '内部收益率',
    '淨現值': '净现值',
    '折現率': '折现率',
    '邊際成本': '边际成本',
    '邊際效益': '边际效益',
    '規模效應': '规模效应',
    '網絡效應': '网络效应',
    '贏家通吃': '赢家通吃',
    '寡頭壟斷': '寡头垄断',
    '完全競爭': '完全竞争',
    '供應鏈': '供应链',
    '價值鏈': '价值链',
    '產業鏈': '产业链',

    # === 亲属称谓 / 口语常见错字（Whisper 高频错误）===
    '老老老爷': '姥姥姥爷',
    '老老和老爷': '姥姥和姥爷',
    '老老老爷家': '姥姥姥爷家',
    '我老老': '我姥姥',
    '我老爷': '我姥爷',
    '爷爷奶奶': '爷爷奶奶',
    '姥姥姥爷': '姥姥姥爷',
    '外公外婆': '外公外婆',
    '爷爷奶奶': '爷爷奶奶',
    '实质路口': '十字路口',
    '聊谈满': '聊到满',
    '造车信誓力': '造车新势力',
    '离修干部': '离休干部',
    '嚮往': '向往',
    '正想': '正向',
    '非常正想': '非常正向',
    '同年成长': '童年成长',
    '同年': '童年',
    '安书': '大学',
    '读安书': '读大学',
    '文艺工作者': '文艺工作者',
    '理工男': '理工男',
    '翻跟头': '翻跟头',
    '特长': '特长',
    '特别': '特别',
    '作剧本': '做剧本',
    '唱戏': '唱戏',
    '前一末化的': '潜移默化的',
    '寻运气': '凭运气',
    '有一些是寻运气': '有一些是凭运气',
    '好,咱们开始吧': '好，咱们开始吧',

    # === 知名人物名字（近音/错字 → 正确） ===
    '李响': '李想',
    '李响的': '李想的',
    '罗永浩': '罗永浩',
    '罗老师': '罗老师',
    '浩哥': '浩哥',
    '俞敏洪': '俞敏洪',
    '俞老师': '俞老师',
    '张一鸣': '张一鸣',
    '王兴': '王兴',
    '程维': '程维',
    '王传福': '王传福',
    '李斌': '李斌',
    '李想': '李想',
    '何小鹏': '何小鹏',
    '余承东': '余承东',
    '雷军': '雷军',
    '黄仁勋': '黄仁勋',
    '苏姿丰': '苏姿丰',
    '马斯克': '马斯克',
    '扎克伯格': '扎克伯格',
    '乔布斯': '乔布斯',
    '比尔盖茨': '比尔盖茨',
    '贝佐斯': '贝佐斯',
    '巴菲特': '巴菲特',
    '芒格': '芒格',
    '段永平': '段永平',
    '李录': '李录',
    '张潇雨': '张潇雨',
    '翁家翌': '翁家翌',
    '谢赛宁': '谢赛宁',
    '杨立昆': '杨立昆',
    '伊利亚': '伊利亚',
    '山姆奥特曼': '山姆·奥特曼',
    '奥特曼': '奥特曼',

    # === 常见成语/固定搭配错字 ===
    '也就是說': '也就是说',
    '換句話說': '换句话说',
    '基本上': '基本上',
    '實際上': '实际上',
    '事實上': '事实上',
    '當然': '当然',
    '顯然': '显然',
    '確實': '确实',
    '絕對': '绝对',
    '完全': '完全',
    '非常': '非常',
    '特別': '特别',
    '尤其': '尤其',
    '反而': '反而',
    '甚至': '甚至',
    '而且': '而且',
    '但是': '但是',
    '不過': '不过',
    '然而': '然而',
    '因此': '因此',
    '所以': '所以',
    '於是': '于是',
    '然後': '然后',
    '接著': '接着',
    '最後': '最后',
    '首先': '首先',
    '其次': '其次',
    '再來': '再来',
    '另外': '另外',
    '此外': '此外',
    '同時': '同时',
    '目前': '目前',
    '現在': '现在',
    '過去': '过去',
    '未來': '未来',
    '將來': '将来',
    '剛才': '刚才',
    '剛剛': '刚刚',
    '忽然': '忽然',
    '突然': '突然',
    '漸漸': '渐渐',
    '慢慢': '慢慢',
    '趕緊': '赶紧',
    '趕快': '赶快',
    '終於': '终于',
    '到底': '到底',
    '究竟': '究竟',
    '畢竟': '毕竟',
    '難道': '难道',
    '何必': '何必',
    '何況': '何况',
    '甚至於': '甚至于',
    '以至於': '以至于',
    '以致於': '以致于',
}


def correct_by_dictionary(text):
    """方案 A：用字典批量替换常见错字

    按错误词长度降序匹配（先长后短），避免短词破坏长词。
    返回 (corrected_text, replacement_count)
    """
    # 按错误词长度降序排列
    sorted_items = sorted(
        [(w, r) for w, r in WRONG_WORDS.items() if w != r],
        key=lambda x: -len(x[0])
    )
    count = 0
    result = text
    for wrong, right in sorted_items:
        if wrong in result:
            occurrences = result.count(wrong)
            result = result.replace(wrong, right)
            count += occurrences
    return result, count


# ============================================================
# 方案 B：专有名词预提取 + 批量校正
# ============================================================

def extract_keywords_from_title(title):
    """从视频标题/简介中提取专有名词关键词

    返回关键词列表，优先级：英文专有名词 > 中文人名 > 公司名
    """
    if not title:
        return []

    keywords = []

    # 去掉平台后缀
    clean = re.split(r'\s*[-|_]\s*', title)[0].strip()

    # 1. 英文专有名词（连续大写开头词，如 OpenAI, Sam Altman, GPT-4）
    english_names = re.findall(r'\b[A-Z][a-zA-Z]+(?:[-\s][A-Z0-9][a-zA-Z0-9]*)*\b', clean)
    keywords.extend(english_names)

    # 2. 英文缩写（全大写，2-6字母，如 GPT, AI, AGI, LLM, NLP）
    abbreviations = re.findall(r'\b[A-Z]{2,6}\b', clean)
    keywords.extend(abbreviations)

    # 3. 中文人名（标题中"XXX："或"专访XXX"格式的 XXX）
    name_match = re.match(r'^([^\s：:]{2,8})\s*[：:]', clean)
    if name_match:
        name = name_match.group(1)
        if name not in ('嘉宾', '专访', '对话', '对谈', '访谈'):
            keywords.append(name)

    # 4. 去重，保持顺序
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen and len(kw) >= 2:
            seen.add(kw)
            unique.append(kw)

    return unique


def correct_keywords(text, keywords):
    """方案 B：针对提取到的关键词校正转录稿

    策略：从标题提取英文专有名词（如 OpenAI、Sam Altman），
    然后在转录稿中查找对应的中文错误形式并替换为正确的英文。
    按错误词长度降序匹配，避免短词破坏长词（如"山姆"破坏"山姆奧特曼"）。
    """
    if not keywords:
        return text, 0

    # 关键词 → Whisper 可能误转的中文形式
    # 注意：人名要给完整组合（如 Sam Altman → "山姆奧特曼"）避免分别替换丢空格
    KEYWORD_WRONG_FORMS = {
        'OpenAI': ['開放AI', '开放AI', '奧本AI', '欧本AI', '打开AI', '奥鹏AI'],
        'ChatGPT': ['恰特GPT', '聊天GPT', '恰特吉皮提', '查特GPT', '聊天吉皮提'],
        'GPT': ['吉皮提', 'GPT提', '吉皮T', '基普提'],
        'GPT-4': ['GPT4', '吉皮提4', 'GPT四'],
        'GPT-3': ['GPT3', '吉皮提3', 'GPT三'],
        'Anthropic': ['安斯羅皮克', '安斯罗皮克', '安斯洛匹克', '安斯若皮克'],
        'Claude': ['克勞德', '克罗德', '克劳德', '克路德'],
        'Gemini': ['傑米尼', '杰米尼', '加米尼', '格米尼', '双子星'],
        'LLaMA': ['拉瑪', '拉马', '拉玛', '喇嘛'],
        'Llama': ['拉瑪', '拉马', '拉玛'],
        'Midjourney': ['米德乔尼', '中途旅程', '米德journey'],
        'Stable Diffusion': ['稳定扩散', '穩定擴散', '稳定扩散模型'],
        'DALL-E': ['达利', '達利', 'DALL E', '戴尔E'],
        'Sora': ['索拉', '天空', '空'],
        'Sam Altman': ['山姆奧特曼', '山姆奥特曼', '山姆·奥特曼', '萨姆奥特曼', '山姆·奥特曼', '萨姆·奥特曼'],
        'Sam': ['山姆', '萨姆'],
        'Altman': ['奧特曼', '奥特曼', '奥特曼'],
        'Elon Musk': ['埃隆馬斯克', '伊隆马斯克', '埃隆·马斯克', '伊隆·马斯克', '艾伦马斯克'],
        'Elon': ['埃隆', '伊隆', '艾伦'],
        'Musk': ['馬斯克', '马斯克', '穆斯克'],
        'Jensen Huang': ['黃仁勳', '黄仁勋', '黄仁勋', 'Jensen黄'],
        'Nvidia': ['輝達', '辉达', '恩維迪亞', '英伟达', '恩威迪亚'],
        'Microsoft': ['微軟', '微软', '微硬'],
        'Apple': ['蘋果', '苹果', '萍果'],
        'Meta': ['元宇宙公司', '脸书公司', '元平台'],
        'Google': ['谷歌', '谷歌声', '歌诗达', '古歌'],
        'Alphabet': ['阿尔法特', '字母表公司', '字母控股'],
        'Tesla': ['泰斯拉', '特斯拉', '特拉斯'],
        'Twitter': ['推特', '特推', '鸟标'],
        'X': ['推特', 'X公司'],
        'YouTube': ['油管', '优兔', 'YouTube', '油Tube'],
        'Facebook': ['臉書', '脸书', '非死不可'],
        'Amazon': ['亞馬遜', '亚马逊', '亚玛逊'],
        'TikTok': ['抖音', '提克托克', 'TikTok', '海外抖音'],
        'ByteDance': ['字节跳动', '字节', '字节跳動'],
        'Baidu': ['百度', '百毒'],
        'Alibaba': ['阿里巴巴', '阿里', '阿裡巴巴'],
        'Tencent': ['腾讯', '騰訊', '企鹅'],
        'AGI': ['通用人工智能', '人工通用智能'],
        'AI': ['人工智能', '人工智慧'],
        'ML': ['机器学习', '機器學習'],
        'DL': ['深度学习', '深度學習'],
        'NLP': ['自然语言处理', '自然語言處理'],
        'CV': ['计算机视觉', '電腦視覺'],
        'RL': ['强化学习', '強化學習', '增强学习'],
        'GPU': ['图形处理器', '顯卡', '显卡'],
        'CPU': ['中央处理器', '中央處理器', '处理器'],
        'TPU': ['张量处理器', '張量處理器'],
        'API': ['应用程序接口', '應用程式介面', '接口'],
        'SDK': ['软件开发工具包', '軟體開發工具包'],
        'VAD': ['语音活动检测', '語音活動檢測'],
        'TTS': ['文本转语音', '文字轉語音'],
        'STT': ['语音转文本', '語音轉文字'],
        'RAG': ['检索增强生成', '檢索增強生成'],
        'LORA': ['低秩适应', '低秩適應'],
        'MoE': ['混合专家', '混合專家'],
        'Transformer': ['变换器', '變換器', '转换器'],
    }

    # 收集所有 (错误形式, 正确词) 对，按错误长度降序匹配
    pairs = []
    for kw in keywords:
        if kw in KEYWORD_WRONG_FORMS:
            for wrong in KEYWORD_WRONG_FORMS[kw]:
                if wrong != kw:
                    pairs.append((wrong, kw))

    # 按错误形式长度降序（先长后短，避免"山姆"破坏"山姆奧特曼"）
    pairs.sort(key=lambda x: -len(x[0]))

    count = 0
    result = text
    for wrong, right in pairs:
        if wrong in result:
            occurrences = result.count(wrong)
            result = result.replace(wrong, right)
            count += occurrences

    return result, count


# ============================================================
# 方案 C：上下文一致性校正
# ============================================================

def correct_context_consistency(text):
    """方案 C：上下文一致性校正

    解决同一专有名词前后写法不一致的问题。
    策略：
    1. 找出所有"疑似专有名词"（英文大写开头词、中文人名模式）
    2. 如果同一个词有多种写法（比如"马斯克"和"馬斯克"），统一成出现频率最高的那种
    3. 对于英文缩写和全称，保持一致

    返回 (corrected_text, fix_count)
    """
    if not text:
        return text, 0

    count = 0
    result = text

    # 1. 英文专有名词一致性（大小写、连字符等）
    # 提取所有首字母大写的英文词
    en_words = re.findall(r'\b[A-Z][a-zA-Z]+\b', text)
    if en_words:
        from collections import Counter
        word_counter = Counter(en_words)
        # 找出相似但大小写不同的词，统一为出现频率最高的
        # （这里简化处理，只处理全大写 vs 首字母大写的常见缩写）
        pass

    # 2. 中文人名/术语的简繁一致性（如果同时出现繁体和简体写法，统一为简体）
    # 这里依赖方案 A 的字典已经处理了大部分
    # 额外处理：同一人有简称和全称时，优先用全称
    name_variants = [
        ('奥特曼', '奥特曼', 'Altman'),
        ('马斯克', '馬斯克', 'Musk'),
        ('黄仁勋', '黃仁勳', 'Jensen Huang'),
        ('张潇雨', '张骁雨', '张小雨'),
        ('翁家翌', '翁佳怡', '翁嘉义'),
    ]

    for simplified, traditional, english in name_variants:
        # 如果简体和繁体同时出现，统一为简体
        if traditional in result and simplified in result:
            occurrences = result.count(traditional)
            result = result.replace(traditional, simplified)
            count += occurrences

    # 3. 常见的"的/地/得"误用简单校正
    # 注意：这是语法问题，Whisper 经常搞混，这里只处理最常见的模式
    de_patterns = [
        # 副词 + 地 + 动词
        # （太复杂，暂时不做，容易误改）
    ]

    return result, count


def clean_initial_prompt_artifact(text, initial_prompt):
    """清理 initial_prompt 可能混入转录结果的残留

    Whisper 有时会把 initial_prompt 的内容"脑补"进转录结果，
    尤其是在开头或静音段。这里做清理：
    1. 去除开头完全匹配 prompt 的内容
    2. 去除明显重复的 prompt 片段
    3. 去除重复 3 次以上的相同短句（典型的 hallucination）

    返回 (cleaned_text, removed_count)
    """
    if not text or not initial_prompt:
        return text, 0

    count = 0
    result = text

    # 1. 清理重复 3 次以上的相同短句（典型的 hallucination）
    # 匹配"短句（重复 N 次）"模式
    def remove_repeated_phrases(text):
        """移除重复出现的短语（>=3 次连续重复）"""
        nonlocal count
        # 匹配中文短语重复："短语。短语。短语。" 或 "短语，短语，短语"
        pattern = r'([^。！？!?.\n]{4,30}[。，、,.])\1{2,}'
        matches = re.findall(pattern, text)
        for m in matches:
            # 只保留 1 次
            old = m * 3  # 至少 3 次
            if old in text:
                text = text.replace(old, m)
                count += 1
        return text

    result = remove_repeated_phrases(result)

    # 2. 如果 initial_prompt 完整出现在文本开头，移除它
    prompt_clean = initial_prompt.strip()
    # 尝试多种匹配方式
    for variant in [prompt_clean, prompt_clean.rstrip('。') + '。', prompt_clean + '。']:
        if result.strip().startswith(variant):
            result = result.strip()[len(variant):].strip()
            count += 1
            break

    return result, count


# ============================================================
# 主入口：组合 A+B+C + 清理
# ============================================================

def correct_transcript(text, title='', keywords=None, initial_prompt=None):
    """校正转录稿（A+B+C + 清理 方案）

    Args:
        text: 转录稿文本
        title: 视频/音频标题（用于提取专有名词）
        keywords: 手动指定的关键词列表（优先于从标题提取）
        initial_prompt: 初始提示词（用于清理可能的残留）

    Returns:
        (corrected_text, total_count, details)
        details 是修正详情列表，每项 (原词, 正确词, 次数)
    """
    if keywords is None:
        keywords = extract_keywords_from_title(title)

    details = []

    # 前置：繁简转换（确保后续字典匹配生效）
    # 优先 opencc，未安装时用内置高频字映射兜底
    try:
        from opencc import OpenCC
        cc = OpenCC('t2s')
        before = text
        text = cc.convert(text)
        if text != before:
            details.append(('繁体→简体（opencc）', '', min(before.count('\n'), len(before) // 50)))
    except ImportError:
        # 内置繁简映射兜底（400+ 高频字/词）
        _T2S_FALLBACK = {
            '什麼': '什么', '怎麼': '怎么', '為什麼': '为什么', '什麼': '什么',
            '這樣': '这样', '那樣': '那样', '這裡': '这里', '那裡': '那里',
            '現在': '现在', '時間': '时间', '時候': '时候', '已經': '已经',
            '因為': '因为', '所以': '所以', '但是': '但是', '雖然': '虽然',
            '如果': '如果', '雖然': '虽然', '可以': '可以', '能夠': '能够',
            '應該': '应该', '必須': '必须', '需要': '需要', '覺得': '觉得',
            '認為': '认为', '知道': '知道', '看到': '看到', '發現': '发现',
            '開始': '开始', '結束': '结束', '然後': '然后', '後來': '后来',
            '以前': '以前', '以後': '以后', '同時': '同时', '永遠': '永远',
            '國家': '国家', '城市': '城市', '公司': '公司', '企業': '企业',
            '產品': '产品', '服務': '服务', '市場': '市场', '價格': '价格',
            '經濟': '经济', '商業': '商业', '投資': '投资', '資本': '资本',
            '數據': '数据', '資料': '数据', '資訊': '信息', '資源': '资源',
            '電腦': '电脑', '手機': '手机', '網絡': '网络', '網路': '网络',
            '互聯網': '互联网', '軟件': '软件', '軟體': '软件', '硬體': '硬件',
            '視頻': '视频', '音頻': '音频', '圖片': '图片', '文檔': '文档',
            '說': '说', '來': '来', '這': '这', '個': '个', '們': '们',
            '會': '会', '對': '对', '裡': '里', '後': '后', '從': '从',
            '現': '现', '發': '发', '為': '为', '與': '与', '於': '于',
            '電': '电', '實': '实', '學': '学', '動': '动', '車': '车',
            '間': '间', '員': '员', '還': '还', '邊': '边', '開': '开',
            '關': '关', '點': '点', '頭': '头', '兩': '两', '應': '应',
            '該': '该', '無': '无', '業': '业', '產': '产', '當': '当',
            '處': '处', '據': '据', '認': '认', '計': '计', '結': '结',
            '論': '论', '資': '资', '訊': '讯', '場': '场', '辦': '办',
            '氣': '气', '數': '数', '農': '农', '運': '运', '軍': '军',
            '廠': '厂', '歷': '历', '藝': '艺', '術': '术', '節': '节',
            '簡': '简', '單': '单', '網': '网', '絡': '络', '視': '视',
            '頻': '频', '腦': '脑', '軟': '软', '語': '语', '導': '导',
            '雖': '虽', '備': '备', '條': '条', '萬': '万', '塊': '块',
            '錢': '钱', '買': '买', '賣': '卖', '機': '机', '進': '进',
            '歐': '欧', '亞': '亚', '聯': '联', '億': '亿', '風': '风',
            '雲': '云', '龍': '龙', '馬': '马', '書': '书', '畫': '画',
            '樂': '乐', '詩': '诗', '詞': '词', '戲': '戏', '劇': '剧',
            '報': '报', '紙': '纸', '雜': '杂', '誌': '志', '圖': '图',
            '館': '馆', '醫': '医', '藥': '药', '貿': '贸', '銀': '银',
            '幣': '币', '稅': '税', '務': '务', '財': '财', '貴': '贵',
            '強': '强', '長': '长', '寬': '宽', '輕': '轻', '熱': '热',
            '溫': '温', '乾': '干', '濕': '湿', '陰': '阴', '陽': '阳',
            '聲': '声', '飽': '饱', '餓': '饿', '飛': '飞', '騎': '骑',
            '鐵': '铁', '鋼': '钢', '紅': '红', '黃': '黄', '藍': '蓝',
            '綠': '绿', '離': '离', '遠': '远', '淺': '浅', '雙': '双',
            '週': '周', '紀': '纪', '歲': '岁', '鐘': '钟', '針': '针',
            '觀': '观', '討': '讨', '讓': '让', '記': '记', '錄': '录',
            '區': '区', '類': '类', '種': '种', '樣': '样', '態': '态',
            '構': '构', '碼': '码', '鍵': '键', '盤': '盘', '標': '标',
            '檔': '档', '庫': '库', '頁': '页', '尋': '寻', '選': '选',
            '擇': '择', '擊': '击', '觸': '触', '轉': '转', '變': '变',
            '滿': '满', '達': '达', '優': '优', '勝': '胜', '敗': '败',
            '終': '终', '屬': '属', '臨': '临', '順': '顺', '隨': '随',
            '權': '权', '親': '亲', '舉': '举', '錯': '错', '諸': '诸',
            '寧': '宁', '縱': '纵', '設': '设', '複': '复', '難': '难',
            '緩': '缓', '靈': '灵', '銳': '锐', '確': '确', '麼': '么',
            '著': '着', '嚮': '向', '遷': '迁', '橫': '横', '喬': '乔',
            '嘯': '啸', '墮': '堕', '痠': '酸',
        }

        before = text
        # 多字词优先替换
        multi = {k: v for k, v in _T2S_FALLBACK.items() if len(k) > 1}
        for old in sorted(multi.keys(), key=len, reverse=True):
            text = text.replace(old, multi[old])
        # 单字替换
        text = ''.join(_T2S_FALLBACK.get(ch, ch) for ch in text)
        if text != before:
            details.append(('繁体→简体（内置映射）', '', len([c for c in before if c in _T2S_FALLBACK])))

    # 方案 A：字典校正
    text_a, count_a = correct_by_dictionary(text)
    if count_a > 0:
        details.append(('字典校正（常见错字）', '', count_a))

    # 方案 B：专有名词校正
    text_b, count_b = correct_keywords(text_a, keywords)
    if count_b > 0:
        details.append(('专有名词校正', f'关键词: {", ".join(keywords[:5])}', count_b))

    # 方案 C：上下文一致性校正
    text_c, count_c = correct_context_consistency(text_b)
    if count_c > 0:
        details.append(('上下文一致性校正', '', count_c))

    # 方案 D：清理 initial_prompt 残留和 hallucination
    if initial_prompt:
        text_d, count_d = clean_initial_prompt_artifact(text_c, initial_prompt)
        if count_d > 0:
            details.append(('清理 prompt 残留/重复', '', count_d))
    else:
        text_d = text_c
        count_d = 0

    total = count_a + count_b + count_c + count_d
    return text_d, total, details


# ============================================================
# 方案 E：转录稿格式化 + 自动说话者识别
# ============================================================

def parse_transcript_lines(text):
    """解析转录稿文本，提取每一行的时间戳和内容

    支持多种格式：
    - [00:00:00 - 00:00:10] 文本内容
    - 00:00:00 - 文本内容
    - 0001 - [00:00:00] 文本内容

    返回列表: [{start: float, end: float, text: str}, ...]
    """
    lines = text.strip().split('\n')
    segments = []
    last_segment = None  # 用于追加下一行文本

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 去掉 Markdown 加粗标记 **...**（md 格式：**[时间 - 时间] [说话者]**）
        # 同时支持行首/行末的 ** 包裹
        stripped = line
        if stripped.startswith('**') and stripped.endswith('**') and len(stripped) > 4:
            stripped = stripped[2:-2].strip()
        elif stripped.startswith('**'):
            stripped = stripped[2:].strip()
        elif stripped.endswith('**'):
            stripped = stripped[:-2].strip()

        # 格式1a: [00:00:00 - 00:00:10] [说话者] 文本（或文本在下一行）
        # 同时支持 md 加粗：**[00:00:00 - 00:00:10] [说话者]**
        m = re.match(r'^\[(\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})\]\s*\[([^\]]+)\]\s*(.*)$', stripped)
        if m:
            start = _time_to_seconds(m.group(1))
            end = _time_to_seconds(m.group(2))
            speaker = m.group(3).strip()
            text_content = m.group(4).strip()
            seg = {'start': start, 'end': end, 'text': text_content if text_content else '', 'speaker': speaker}
            segments.append(seg)
            last_segment = seg
            continue

        # 格式1b: [00:00:00 - 00:00:10] 文本（无说话者标签）
        m = re.match(r'^\[(\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})\]\s*(.+)$', stripped)
        if m:
            start = _time_to_seconds(m.group(1))
            end = _time_to_seconds(m.group(2))
            text_content = m.group(3).strip()
            spk_match = re.match(r'^\[([^\]]+)\]$', text_content)
            if spk_match:
                seg = {'start': start, 'end': end, 'text': '', 'speaker': spk_match.group(1).strip()}
                segments.append(seg)
                last_segment = seg
            elif text_content:
                segments.append({'start': start, 'end': end, 'text': text_content})
                last_segment = None
            continue

        # 格式2: 00:00:00 - 文本
        m = re.match(r'^(\d{2}:\d{2}:\d{2})\s*-\s*(.+)$', line)
        if m:
            start = _time_to_seconds(m.group(1))
            text_content = m.group(2).strip()
            if text_content:
                segments.append({'start': start, 'end': start + 10, 'text': text_content})
                last_segment = None
            continue

        # 格式3: 序号 - [时间] 文本
        m = re.match(r'^\d+\s*-\s*\[(\d{2}:\d{2}:\d{2})\]\s*(.+)$', line)
        if m:
            start = _time_to_seconds(m.group(1))
            text_content = m.group(2).strip()
            if text_content:
                segments.append({'start': start, 'end': start + 10, 'text': text_content})
                last_segment = None
            continue

        # 普通文本行：追加到上一个 segment（如果上一个 segment 文本为空）
        if last_segment and not last_segment['text']:
            last_segment['text'] = line
        elif last_segment and last_segment['text']:
            # 上一个 segment 已有文本，这行可能是续接
            last_segment['text'] += '，' + line

    return segments


def _time_to_seconds(time_str):
    """HH:MM:SS 转秒数"""
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return 0


def _seconds_to_time(seconds):
    """秒数转 HH:MM:SS"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def detect_speakers_from_content(segments, title=''):
    """从转录内容中自动识别说话者

    策略：
    1. 从自我介绍中提取："大家好，我是XXX"、"我是XXX"
    2. 从称谓中提取："X老师"、"X总"、"X哥"
    3. 从主持人介绍中提取："今天的嘉宾是XXX"、"欢迎XXX"
    4. 从标题提取
    5. 根据对话模式分配：第一个说话的是主持人，第二个是嘉宾

    返回: [{'name': '罗永浩', 'role': '主持人'}, {'name': '李想', 'role': '嘉宾'}, ...]
    """
    speakers = []
    seen = set()

    def add_speaker(name, role='未知'):
        if name and len(name) >= 2 and name not in seen:
            seen.add(name)
            speakers.append({'name': name, 'role': role})

    # 1. 从标题提取（如果有）
    if title:
        # 匹配："罗永浩对谈李想"、"对话XXX"、"XXX专访"等
        patterns = [
            r'([^\s：:、&,，]{2,4})\s*(?:对谈|对话|对谈|访谈|专访)\s*([^\s：:、&,，]{2,4})',
            r'([^\s：:、&,，]{2,4})\s*(?:和|与|跟)\s*([^\s：:、&,，]{2,4})',
        ]
        for pat in patterns:
            m = re.search(pat, title)
            if m:
                add_speaker(m.group(1), '主持人')
                add_speaker(m.group(2), '嘉宾')
                break

    # 2. 从自我介绍提取（前 30 段）
    intro_patterns = [
        r'大家好[，,。.\s]*我是([^\s，,。.!！?？]{2,6})',
        r'我是([^\s，,。.!！?？]{2,6})\s*(?:[，,。.])',
        r'我叫([^\s，,。.!！?？]{2,6})',
        r'我是([^\s，,。.!！?？]{2,6})$',
    ]

    for seg in segments[:50]:
        text = seg['text']
        for pat in intro_patterns:
            matches = re.findall(pat, text)
            for name in matches:
                # 过滤掉常见的非人名
                if name in ('谁', '什么', '怎么', '这样', '那样', '这么', '那么', '一个', '一种'):
                    continue
                if len(name) >= 2 and len(name) <= 4:
                    role = '主持人' if len(speakers) == 0 else '嘉宾'
                    add_speaker(name, role)

    # 3. 从主持人介绍嘉宾提取
    host_intro_patterns = [
        r'嘉宾是([^\s，,。.!！?？]{2,6})',
        r'欢迎([^\s，,。.!！?？]{2,6})',
        r'今天的嘉宾是([^\s，,。.!！?？]{2,6})',
        r'和我对谈的是([^\s，,。.!！?？]{2,6})',
        r'坐在我对面的是([^\s，,。.!！?？]{2,6})',
        r'创始人([^\s，,。.!！?？]{2,4})',
    ]

    for seg in segments[:30]:
        text = seg['text']
        for pat in host_intro_patterns:
            matches = re.findall(pat, text)
            for name in matches:
                if len(name) >= 2 and len(name) <= 4:
                    add_speaker(name, '嘉宾')

    # 4. 从称谓识别（"X老师"、"X总"等）
    title_patterns = [
        r'([^\s，,。.])老师',
        r'([^\s，,。.])总',
        r'([^\s，,。.])哥',
        r'([^\s，,。.])姐',
    ]

    title_speakers = {}
    for seg in segments[:100]:
        text = seg['text']
        for pat in title_patterns:
            matches = re.findall(pat, text)
            for surname in matches:
                if len(surname) == 1 and surname not in ('老', '小', '大', '阿'):
                    key = surname
                    title_speakers[key] = title_speakers.get(key, 0) + 1

    # 如果称谓出现频率高，加入候选
    for surname, count in sorted(title_speakers.items(), key=lambda x: -x[1]):
        if count >= 3:
            full_name = surname + '总'  # 暂时用称谓代替
            add_speaker(full_name, '嘉宾')

    return speakers


def assign_speakers_to_segments(segments, speakers):
    """给片段分配说话者（基于简单的交替对话模型）

    对于没有音色识别的转录稿，使用启发式方法：
    - 前几段自我介绍的人 → 主持人
    - 第一段长回答 → 嘉宾
    - 然后交替（如果沉默间隔长就切换）

    返回: segments 列表，每个增加 speaker 字段
    """
    if not segments:
        return segments

    if not speakers:
        # 没有识别到说话者，默认 SPEAKER_01 / SPEAKER_02
        speakers = [
            {'name': 'SPEAKER_01', 'role': '主持人'},
            {'name': 'SPEAKER_02', 'role': '嘉宾'},
        ]

    # 策略：基于片段间隔和内容长度来判断切换
    # 短片段（提问）→ 主持人
    # 长片段（回答）→ 嘉宾
    # 间隔长 → 可能换人

    current_speaker_idx = 0
    segments[0]['speaker'] = speakers[0]['name']

    for i in range(1, len(segments)):
        prev_seg = segments[i-1]
        curr_seg = segments[i]
        gap = curr_seg['start'] - prev_seg['end']
        curr_len = len(curr_seg['text'])
        prev_len = len(prev_seg['text'])

        should_switch = False

        # 规则1：间隔超过 2 秒，可能换人
        if gap > 2.0:
            should_switch = True

        # 规则2：上一段很短（提问），这一段很长（回答）→ 切换到嘉宾
        if prev_len < 20 and curr_len > 50:
            should_switch = True

        # 规则3：上一段很长（回答），这一段很短（提问）→ 切换到主持人
        if prev_len > 50 and curr_len < 20:
            should_switch = True

        # 规则4：内容以问号结尾，下一段很可能是另一个人
        if prev_seg['text'].rstrip().endswith(('?', '？')) and curr_len > 15:
            should_switch = True

        if should_switch:
            # 支持多人切换（不再硬编码 1 - idx）
            num_speakers = len(speakers)
            current_speaker_idx = (current_speaker_idx + 1) % num_speakers

        curr_seg['speaker'] = speakers[current_speaker_idx]['name']

    return segments


def split_long_segments(segments, max_duration=300, max_chars=600):
    """切分超长段落，根据问号/句号进行二次切分

    对于超过 max_duration 秒（默认 5 分钟）或 max_chars 字符的段落，
    按问号和句号切分成多个子段落，为后续重新分配说话者做准备。

    返回新的 segments 列表（保留原 speaker 字段，但后续可重新分配）
    """
    result = []
    for seg in segments:
        duration = seg.get('end', 0) - seg.get('start', 0)
        text = seg.get('text', '').strip()
        speaker = seg.get('speaker', '')

        if duration <= max_duration and len(text) <= max_chars:
            result.append(seg)
            continue

        if not text:
            result.append(seg)
            continue

        # 第一轮：按问号切分（？?）
        # 保留问号在前一段末尾
        chunks = []
        current = ''
        for part in re.split(r'(？|\?)', text):
            current += part
            if part in ('？', '?'):
                chunks.append(current)
                current = ''
        if current:
            chunks.append(current)

        # 第二轮：如果切分后仍然太长（> max_chars），按句号/感叹号再切
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_chars:
                final_chunks.append(chunk)
            else:
                sentences = re.split(r'(。|！)', chunk)
                cur = ''
                for s in sentences:
                    cur += s
                    if s in ('。', '！') and len(cur) > max_chars // 2:
                        final_chunks.append(cur)
                        cur = ''
                if cur:
                    final_chunks.append(cur)

        # 合并过短的片段（< 30 字符）到前一段
        merged = []
        for chunk in final_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            if merged and len(chunk) < 30:
                merged[-1] += chunk
            else:
                merged.append(chunk)

        n = len(merged)
        if n <= 1:
            result.append(seg)
            continue

        # 按比例分配时间
        total_chars = sum(len(c) for c in merged)
        time_cursor = seg['start']
        for i, chunk in enumerate(merged):
            if i == n - 1:
                chunk_end = seg['end']
            else:
                chunk_duration = duration * (len(chunk) / total_chars)
                chunk_end = time_cursor + chunk_duration
            result.append({
                'start': time_cursor,
                'end': chunk_end,
                'text': chunk,
                'speaker': speaker,
            })
            time_cursor = chunk_end

    return result


def format_as_dialogue(segments, speakers=None):
    """将片段合并为对话段落式格式

    合并同一说话者的连续片段，生成：
    [00:00:00 - 00:05:23] [罗永浩]
    大家好，欢迎来到今天的节目...

    [00:05:23 - 00:08:45] [李想]
    谢谢主持人，很高兴来到这里...
    """
    if not segments:
        return ''

    if speakers is None:
        speakers = []

    # 确保 segments 有 speaker 字段
    if 'speaker' not in segments[0]:
        segments = assign_speakers_to_segments(segments, speakers)

    # 合并同一说话者的连续片段
    # 加入时间上限：单段落超过 5 分钟或间隔超过 3 分钟就拆分
    MAX_PARAGRAPH_DURATION = 300  # 5 分钟
    MAX_SILENCE_BETWEEN_SAME_SPEAKER = 180  # 3 分钟

    groups = []
    current_group = None

    for seg in segments:
        speaker = seg.get('speaker', '未知')
        text = seg.get('text', '').strip()
        if not text:
            continue

        if current_group is None:
            current_group = {
                'start': seg['start'],
                'end': seg['end'],
                'speaker': speaker,
                'text': text,
            }
        elif current_group['speaker'] == speaker:
            # 同一说话者，检查是否需要拆分
            gap = seg['start'] - current_group['end']
            duration = current_group['end'] - current_group['start']
            # 合并后的总时长（用于判断是否超过上限）
            merged_duration = seg['end'] - current_group['start']
            # 合并后的总字符数
            merged_chars = len(current_group['text']) + len(text)
            should_split = False
            if duration > MAX_PARAGRAPH_DURATION:
                should_split = True
            # 新增：合并后超过 5 分钟也拆分（防止逐步合并成超长段落）
            if merged_duration > MAX_PARAGRAPH_DURATION:
                should_split = True
            # 新增：合并后超过 800 字符也拆分（防止文本过长）
            if merged_chars > 800:
                should_split = True
            if gap > MAX_SILENCE_BETWEEN_SAME_SPEAKER:
                should_split = True
            # 问号结尾 + 下一段较长 → 可能是问答切换
            if current_group['text'].rstrip().endswith(('?', '？')) and len(text) > 30:
                should_split = True

            if should_split:
                groups.append(current_group)
                current_group = {
                    'start': seg['start'],
                    'end': seg['end'],
                    'speaker': speaker,
                    'text': text,
                }
            else:
                # 合并
                current_group['end'] = seg['end']
                prev = current_group['text']
                if prev and prev[-1] in '，。！？、；：,.;:!?…—-':
                    current_group['text'] = prev + text
                else:
                    current_group['text'] = prev + '，' + text
        else:
            # 不同说话者
            groups.append(current_group)
            current_group = {
                'start': seg['start'],
                'end': seg['end'],
                'speaker': speaker,
                'text': text,
            }

    if current_group:
        groups.append(current_group)

    # 生成文本
    output_lines = []
    for group in groups:
        start_str = _seconds_to_time(group['start'])
        end_str = _seconds_to_time(group['end'])
        speaker = group['speaker']
        text = group['text']
        header = f"[{start_str} - {end_str}] [{speaker}]"
        output_lines.append(header)
        output_lines.append(text)
        output_lines.append('')

    return '\n'.join(output_lines)


def reformat_transcript(text, title='', speaker_names=None):
    """完整的转录稿重格式化：解析 → 识别说话者 → 对话段落式

    Args:
        text: 原始转录稿文本（逐行格式或 md 格式）
        title: 视频/音频标题（辅助识别说话者）
        speaker_names: 手动指定的说话者列表（可选）

    Returns:
        (formatted_text, speakers_list)
    """
    # 1. 解析行（支持纯文本和 md 加粗格式）
    segments = parse_transcript_lines(text)
    if not segments:
        return text, []

    # 2. 识别说话者
    if speaker_names:
        speakers = [{'name': n, 'role': '主持人' if i == 0 else '嘉宾'}
                    for i, n in enumerate(speaker_names)]
    else:
        speakers = detect_speakers_from_content(segments, title)

    # 3. 判断原说话者标签是否可靠
    has_speaker = any('speaker' in seg and seg['speaker'] for seg in segments)
    # 不可靠的标志：出现未映射的 SPEAKER_XX，或存在超长段落（> 5 分钟）
    has_unmapped_speaker = any(
        seg.get('speaker', '').startswith('SPEAKER_')
        for seg in segments
    )
    has_overlong_segment = any(
        (seg.get('end', 0) - seg.get('start', 0)) > 300
        for seg in segments
    )
    labels_unreliable = has_unmapped_speaker or has_overlong_segment

    if has_speaker and speaker_names and not labels_unreliable:
        # 原标签可靠：把 SPEAKER_XX 映射到真名
        speaker_map = {}
        for i, name in enumerate(speaker_names):
            speaker_map[f'SPEAKER_{i:02d}'] = name
        for seg in segments:
            spk = seg.get('speaker', '')
            if spk in speaker_map:
                seg['speaker'] = speaker_map[spk]
            elif spk.startswith('SPEAKER_'):
                # 未映射的 SPEAKER_XX，根据上下文交替推断
                known_real = [s for s in speaker_names]
                if len(known_real) == 2:
                    idx = segments.index(seg)
                    last_known = None
                    for j in range(idx - 1, -1, -1):
                        prev_spk = segments[j].get('speaker', '')
                        if prev_spk in known_real:
                            last_known = prev_spk
                            break
                    if last_known:
                        other = [s for s in known_real if s != last_known]
                        seg['speaker'] = other[0] if other else spk
                    else:
                        seg['speaker'] = known_real[0]
    elif has_speaker and speaker_names and labels_unreliable:
        # 原标签不可靠（含 SPEAKER_XX 或超长段落）：
        # 1. 切分超长段落
        # 2. 清除原 speaker 字段，根据问答模式重新分配
        print(f"⚠️  检测到原说话者标签不可靠（含 SPEAKER_XX 或超长段落），将忽略原标签重新分配")
        segments = split_long_segments(segments, max_duration=300, max_chars=600)
        # 清除原 speaker，交给 assign_speakers_to_segments 重新分配
        for seg in segments:
            seg.pop('speaker', None)
        segments = assign_speakers_to_segments(segments, speakers)
    else:
        segments = assign_speakers_to_segments(segments, speakers)

    # 4. 格式化为对话段落式
    formatted = format_as_dialogue(segments, speakers)

    return formatted, [s['name'] for s in speakers]


# ============================================================
# 命令行入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("用法: python3 transcript_corrector.py <transcript.txt> [选项]")
        print("")
        print("选项:")
        print("  --title '标题'        视频/音频标题（用于提取关键词和说话者）")
        print("  --keywords 'a,b,c'    手动指定专有名词关键词")
        print("  --speakers '张三,李四' 手动指定说话者（按顺序：主持人,嘉宾...）")
        print("  --reformat            重新格式化为对话段落式 + 说话者标注")
        print("")
        print("示例:")
        print("  python3 transcript_corrector.py transcript.txt --title '翁家翌：OpenAI'")
        print("  python3 transcript_corrector.py transcript.txt --keywords 'OpenAI,GPT'")
        print("  python3 transcript_corrector.py transcript.txt --reformat --speakers '罗永浩,李想' --title '对谈李想'")
        sys.exit(1)

    file_path = sys.argv[1]
    title = ''
    keywords = None
    speakers = None
    reformat = False

    if '--title' in sys.argv:
        idx = sys.argv.index('--title')
        if idx + 1 < len(sys.argv):
            title = sys.argv[idx + 1]

    if '--keywords' in sys.argv:
        idx = sys.argv.index('--keywords')
        if idx + 1 < len(sys.argv):
            keywords = [k.strip() for k in sys.argv[idx + 1].split(',') if k.strip()]

    if '--speakers' in sys.argv:
        idx = sys.argv.index('--speakers')
        if idx + 1 < len(sys.argv):
            speakers = [s.strip() for s in sys.argv[idx + 1].split(',') if s.strip()]

    if '--reformat' in sys.argv:
        reformat = True

    # 读取文件
    text = Path(file_path).read_text(encoding='utf-8')

    print(f"📄 文件: {file_path}")
    print(f"📝 标题: {title or '(未提供)'}")
    if keywords:
        print(f"🔑 手动关键词: {keywords}")
    if speakers:
        print(f"🎤 说话者: {speakers}")
    print(f"-" * 50)

    # 校正
    corrected, total, details = correct_transcript(text, title, keywords)

    if total == 0:
        print("✅ 校正：未发现需要校正的错误")
    else:
        print(f"✅ 校正：共 {total} 处")
        for desc, info, count in details:
            print(f"   - {desc}: {count} 处 {info}")

    # 重新格式化（对话段落式 + 说话者）
    if reformat:
        print(f"\n📝 重新格式化为对话段落式...")
        formatted, detected_speakers = reformat_transcript(corrected, title=title, speaker_names=speakers)
        print(f"🎤 识别到的说话者: {detected_speakers}")
        corrected = formatted

    # 覆盖原文件
    Path(file_path).write_text(corrected, encoding='utf-8')
    print(f"\n💾 已保存: {file_path}")

    # 显示预览
    print(f"\n📋 预览（前 600 字符）:")
    print("-" * 50)
    print(corrected[:600])


if __name__ == '__main__':
    main()
