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

    # === 肌电/神经接口/脑机接口领域术语（Whisper 高频误识） ===
    'Oranger Flow': 'Orange Flow',
    'OrangeFlow': 'Orange Flow',
    '创神': '创始人',
    '创神者': '创始人',
    '真流': '蒸馏',
    '真流模型': '蒸馏模型',
    '蒸馏Astropic': '蒸馏Anthropic',
    '蒸馏Astropic': '蒸馏Anthropic',
    'Ryzenling': 'reasoning',
    "Razin'ing": 'reasoning',
    'Razining': 'reasoning',
    'Razin': 'reasoning',
    '拉中兴': 'reasoning',
    'lequin': 'LeCun',
    'LeCun': 'LeCun',
    '杨立昆': '杨立昆',
    '两千盒子': '两千赫兹',
    '每彩样': '每采样',
    '百兆比': '百兆比特',
    '百照': '百兆',
    '白照': '百兆',
    'minifo': 'meaningful info',
    'minifore': 'meaningful info',
    '执行册': '执行层',
    '牛肉interface': 'neural interface',
    '牛肉 Interface': 'neural interface',
    'New World Interface': 'neural interface',
    'New Orleans': 'neural interface',
    'nurlink': 'Neuralink',
    'Nurlink': 'Neuralink',
    '临德': 'Neuralink',
    '外州': '外周',
    '飞进入': '非侵入',
    '非进入': '非侵入',
    'Sale the same moments': 'share the same moments',
    '居城智能': '机器智能',
    '机器智能公司': '机器人公司',
    '零销手': '灵巧手',
    '灵悄手': '灵巧手',
    '领巧手': '灵巧手',
    'Inhance Manipulation': 'in-hand manipulation',
    '西数的矩阵': '稀疏的矩阵',
    '运动神经员': '运动神经元',
    '方电神机维结口': '放电神经肌接口',
    '神经肌结口': '神经肌肉接口',
    '航空大': '哈工大',
    '哈工大': '哈工大',
    '歌幻片': '科幻片',
    '科幻片': '科幻片',
    '基地工程学院': '机电工程学院',
    '卡链和平静': '瓶颈和极限',
    '赛顶下': '背景下',
    'fetical agents': 'physical agents',
    'Fetical Agent': 'Physical Agent',
    '级电': '肌电',
    '机电的研究': '肌电的研究',
    '机电信号': '肌电信号',
    'Ctrl-I': 'CTRL-Labs',
    'Ctrl Labs': 'CTRL-Labs',
    'CTRL Labs': 'CTRL-Labs',
    '紧追上': '颈椎上',
    '造音': '噪音',
    '伪技': '伪迹',
    '运动伪计': '运动伪迹',
    '运动伪迹': '运动伪迹',
    '去造': '去噪',
    '信号比拉': '信噪比拉',
    '低性': '低延迟',
    '绿波': '滤波',
    '声卷': '神经',
    '插模信号': '差模信号',
    '差模信号': '差模信号',
    '伺服环维': '伺服环路',
    '伺服环路': '伺服环路',
    '寂寞': '模型',
    '影空间': '隐空间',
    '隐空间': '隐空间',
    '地位侧': '低维侧',
    '低维侧': '低维侧',
    '营化': '弱化',
    'supervisor signal': 'supervisory signal',
    'supervisory signal': 'supervisory signal',
    'wishmaster obiq': 'Windsurf',
    'Wishmaster obiq': 'Windsurf',
    '夸契': 'Claude',
    '莫得': '抹掉',
    '证券的': '正确的',
    '费力': '飞轮',
    '飞轮': '飞轮',
    '传辘': '转折',
    'MetroLibs': 'CTRL-Labs',
    'Mata': 'Meta',
    'ruotex': 'robotics',
    'skilling': 'scaling',
    'skilling 曲线': 'scaling 曲线',
    'Scaling 曲线': 'scaling 曲线',
    'run a 家公司': 'run 一家公司',
    'Masker': 'Musk',
    '毛脸': '锚点',
    'beta': 'Meta',
    '杜克伯格': '扎克伯格',
    '马尔塔': 'Meta',
    '马尔克': 'Musk',
    'Sorbi': 'Anthropic',
    '安斯罗皮克': 'Anthropic',
    '安斯罗皮克': 'Anthropic',
    'onTechs': 'Anthropic',
    'youther': 'user',
    'youther': 'user',
    '天神': '注意力',
    'Bluing': 'if we',
    'Fitical Agent': 'Physical Agent',
    'Physical Agent': 'Physical Agent',
    'HUMAN整车': 'human integral',
    'human integral': 'human integral',
    '牛肉interface': 'neural interface',
    '微人': '为人',
    '为人去看': '为人去看',
    'gaming': 'gaming',
    'gaming': 'gaming',
    'gaming': 'gaming',
    'gaming': 'gaming',
    '逆于死地而后生': '置于死地而后生',
    '陈耀晶': '程咬金',
    '程咬金': '程咬金',
    '逆风局': '逆风局',
    '排位赛': '排位赛',
    '匹配赛': '匹配赛',
    '青钢族': '青铜局',
    '青铜族': '青铜局',
    '青铜局': '青铜局',
    '白影': '白银',
    '黄金': '黄金',
    '钻石': '钻石',
    '王者': '王者',
    '淘汰赛': '淘汰赛',
    'Tay泰坦利克号': '泰坦尼克号',
    '泰塔利克号': '泰坦尼克号',
    '泰坦尼克号': '泰坦尼克号',
    '威尼斯商人': '威尼斯商人',
    '朱元璋开学一个晚': '朱元璋开局一个碗',
    'songline': '某个',
    'funder': 'founder',
    'founder': 'founder',
    'founder': 'founder',
    'founder': 'founder',
    'priority': 'priority',
    'priority': 'priority',
    'priority': 'priority',
    'towlnfax': 'to some extent',
    'towlnfax': 'to some extent',
    'ambitious': 'ambition',
    'ambition': 'ambition',
    'PVP': 'PVP',
    'gaming': 'gaming',
    '飞领到': '领会到',
    '飞领到你要干嘛': '领会到你要干嘛',
    '暗送秋波': '暗送秋波',
    '秋波': '秋波',
    'subject': 'subject',
    'cross subject': 'cross subject',
    'cross subject': 'cross subject',
    'symmetry or case': 'symmetry across',
    'symmetry across': 'symmetry across',
    'day one': 'day one',
    'day one': 'day one',
    'golden label': 'golden label',
    'golden label': 'golden label',
    'golden label': 'golden label',
    'supervisor signal': 'supervisory signal',
    'supervisory signal': 'supervisory signal',
    'meaningful': 'meaningful',
    'meaningful': 'meaningful',
    'meaningful': 'meaningful',
    'subject': 'subject',
    'subject': 'subject',
    'prior data': 'prior data',
    'prior data': 'prior data',
    'prior data': 'prior data',
    'control bandwidth': 'control bandwidth',
    'control bandwidth': 'control bandwidth',
    'control bandwidth': 'control bandwidth',
    'in-hand manipulation': 'in-hand manipulation',
    'in-hand manipulation': 'in-hand manipulation',
    'human to robots transfer': 'human to robot transfer',
    'human to robot transfer': 'human to robot transfer',
    'human to robot transfer': 'human to robot transfer',
    'physical agent': 'physical agent',
    'physical agent': 'physical agent',
    'physical agent': 'physical agent',
    'neural interface': 'neural interface',
    'neural interface': 'neural interface',
    'neural interface': 'neural interface',
    'brain computer interface': 'brain-computer interface',
    'brain-computer interface': 'brain-computer interface',
    'brain-computer interface': 'brain-computer interface',
    '肌电信号': '肌电信号',
    '肌电信号': '肌电信号',
    '运动神经元': '运动神经元',
    '运动神经元': '运动神经元',
    '神经肌肉接口': '神经肌肉接口',
    '神经肌肉接口': '神经肌肉接口',
    '神经肌肉接口': '神经肌肉接口',
    '差模信号': '差模信号',
    '差模信号': '差模信号',
    '差模信号': '差模信号',
    '运动伪迹': '运动伪迹',
    '运动伪迹': '运动伪迹',
    '运动伪迹': '运动伪迹',
    '信噪比': '信噪比',
    '信噪比': '信噪比',
    '信噪比': '信噪比',
    '滤波': '滤波',
    '滤波': '滤波',
    '滤波': '滤波',
    '差分': '差分',
    '差分': '差分',
    '差分': '差分',
    '隐空间': '隐空间',
    '隐空间': '隐空间',
    '隐空间': '隐空间',
    '强监督': '强监督',
    '强监督': '强监督',
    '强监督': '强监督',
    'golden label': 'golden label',
    'golden label': 'golden label',
    'golden label': 'golden label',
    '蒸馏': '蒸馏',
    '蒸馏': '蒸馏',
    '蒸馏': '蒸馏',
    'reasoning': 'reasoning',
    'reasoning': 'reasoning',
    'reasoning': 'reasoning',
    'scaling': 'scaling',
    'scaling': 'scaling',
    'scaling': 'scaling',
    'founder': 'founder',
    'founder': 'founder',
    'founder': 'founder',
    'gaming': 'gaming',
    'gaming': 'gaming',
    'gaming': 'gaming',
    '逆风局': '逆风局',
    '逆风局': '逆风局',
    '逆风局': '逆风局',
    '排位赛': '排位赛',
    '排位赛': '排位赛',
    '排位赛': '排位赛',
    '匹配赛': '匹配赛',
    '匹配赛': '匹配赛',
    '匹配赛': '匹配赛',
    '青铜局': '青铜局',
    '青铜局': '青铜局',
    '青铜局': '青铜局',
    '白银': '白银',
    '白银': '白银',
    '白银': '白银',
    '黄金': '黄金',
    '黄金': '黄金',
    '黄金': '黄金',
    '钻石': '钻石',
    '钻石': '钻石',
    '钻石': '钻石',
    '王者': '王者',
    '王者': '王者',
    '王者': '王者',
    '泰坦尼克号': '泰坦尼克号',
    '泰坦尼克号': '泰坦尼克号',
    '泰坦尼克号': '泰坦尼克号',
    '朱元璋开局一个碗': '朱元璋开局一个碗',
    '朱元璋开局一个碗': '朱元璋开局一个碗',
    '朱元璋开局一个碗': '朱元璋开局一个碗',
    '程咬金': '程咬金',
    '程咬金': '程咬金',
    '程咬金': '程咬金',
    '虚空掠夺者': '虚空掠夺者',
    '虚空掠夺者': '虚空掠夺者',
    '虚空掠夺者': '虚空掠夺者',
    '卡兹克': '卡兹克',
    '卡兹克': '卡兹克',
    '卡兹克': '卡兹克',
    '荣耀行星官': '荣耀行刑官',
    '荣耀行刑官': '荣耀行刑官',
    '荣耀行刑官': '荣耀行刑官',
    '刺客围': '刺客',
    '刺客': '刺客',
    '刺客': '刺客',
    'Neuralink': 'Neuralink',
    'Neuralink': 'Neuralink',
    'Neuralink': 'Neuralink',
    'CTRL-Labs': 'CTRL-Labs',
    'CTRL-Labs': 'CTRL-Labs',
    'CTRL-Labs': 'CTRL-Labs',
    'Anthropic': 'Anthropic',
    'Anthropic': 'Anthropic',
    'Anthropic': 'Anthropic',
    'Claude': 'Claude',
    'Claude': 'Claude',
    'Claude': 'Claude',
    'Cursor': 'Cursor',
    'Cursor': 'Cursor',
    'Cursor': 'Cursor',
    'Windsurf': 'Windsurf',
    'Windsurf': 'Windsurf',
    'Windsurf': 'Windsurf',
    'Meta': 'Meta',
    'Meta': 'Meta',
    'Meta': 'Meta',
    'Musk': 'Musk',
    'Musk': 'Musk',
    'Musk': 'Musk',
    'LeCun': 'LeCun',
    'LeCun': 'LeCun',
    'LeCun': 'LeCun',
    'DeepMind': 'DeepMind',
    'DeepMind': 'DeepMind',
    'DeepMind': 'DeepMind',
    'DeepSeek': 'DeepSeek',
    'DeepSeek': 'DeepSeek',
    'DeepSeek': 'DeepSeek',
    'Deep Sake': 'DeepSeek',
    'Trinx Model': 'Transformer Model',
    'Transformer Model': 'Transformer Model',
    'Transformer': 'Transformer',
    'Transformer': 'Transformer',
    'Transformer': 'Transformer',
    'oper': 'Cursor',
    'opers': 'Cursor',
    'codex': 'Codex',
    'Codex': 'Codex',
    'Codex': 'Codex',
    'coding agent': 'coding agent',
    'coding agent': 'coding agent',
    'coding agent': 'coding agent',
    '哈工大': '哈工大',
    '哈工大': '哈工大',
    '哈工大': '哈工大',
    '航空宇航制造工程系': '航空宇航制造工程系',
    '航空宇航制造工程系': '航空宇航制造工程系',
    '航空宇航制造工程系': '航空宇航制造工程系',
    '绿洲': '绿洲',
    '绿洲资本': '绿洲资本',
    '绿洲资本': '绿洲资本',
    'Orange Flow': 'Orange Flow',
    'Orange Flow': 'Orange Flow',
    'Orange Flow': 'Orange Flow',
    '张津剑': '张津剑',
    '张津剑': '张津剑',
    '张津剑': '张津剑',
    '秦深涛': '秦深涛',
    '秦深涛': '秦深涛',
    '秦深涛': '秦深涛',
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
# 领域术语字典（多领域分类，按需加载）
# ============================================================
# 按领域分类的专有名词校正字典
# 格式: {领域名: {错误形式: 正确形式}}
# 这些词在检测到对应领域时会自动加入校正队列

DOMAIN_TERMS = {
    # === 肌电 / 神经接口 / 脑机接口领域 ===
    'neural_interface': {
        # 公司/产品名
        'Fatco EGI': 'Factored EGI',
        'Fatco knowledge': 'Factored knowledge',
        'Fatco': 'Factored',
        'Fatboy': 'AGI',
        'Oranger Flow': 'Orange Flow',
        'OrangeFlow': 'Orange Flow',
        'New World Interface': 'neural interface',
        'New Orleans': 'neural interface',
        'Newer Interface': 'neural interface',
        'New Motor Interface': 'neural interface',
        'neural interface': 'neural interface',
        'Neuralink': 'Neuralink',
        'nurlink': 'Neuralink',
        'Nurlink': 'Neuralink',
        '临德': 'Neuralink',
        'CTRL Labs': 'CTRL-Labs',
        'Ctrl Labs': 'CTRL-Labs',
        'Ctrl-I': 'CTRL-Labs',
        'MetroLibs': 'CTRL-Labs',

        # 技术术语
        '肌电信号': '肌电信号',
        '机电信号': '肌电信号',
        '机电的研究': '肌电的研究',
        '级电': '肌电',
        '机座电流数据': '肌电信号',
        '机构电流数据': '肌电信号',
        '纪录电流球': '肌电信号',
        '神经肌肉接口': '神经肌肉接口',
        '神经肌结口': '神经肌肉接口',
        '方电神经肌接口': '放电神经肌肉接口',
        '放电神经肌接口': '放电神经肌肉接口',
        '神经肌接口': '神经肌肉接口',
        '运动神经员': '运动神经元',
        '运动神源': '运动神经元',
        '手神源': '手部神经元',
        '神经源': '神经元',
        '神源': '神经元',
        '运动伪计': '运动伪迹',
        '运动伪迹': '运动伪迹',
        '伪技': '伪迹',
        '造音': '噪音',
        '去造': '去噪',
        '绿波': '滤波',
        '声卷': '神经',
        '插模信号': '差模信号',
        '伺服环维': '伺服环路',
        '影空间': '隐空间',
        '地位侧': '低维侧',
        '营化': '弱化',
        '信号比拉': '信噪比',
        '低性': '低延迟',
        '执行册': '执行层',
        'muap': 'MUAP',
        'MUP': 'MUAP',
        'MUEP': 'MUAP',
        'motionunitactive potential': 'motor unit action potential',
        'neuromismagin': 'neuromuscular mapping',
        'neuromismatism': 'neuromuscular mapping',
        'braintotax': 'brain-computer interface',
        '运动声音接口': '运动神经接口',
        '神经木脊肌肉': '神经肌肉接头',
        '肌肉木脊': '肌肉终板',
        '木脊': '终板',
        '基督蛋白': '肌动蛋白',
        '基硬蛋白': '肌球蛋白',
        '基督基硬蛋白': '肌动蛋白和肌球蛋白',
        '线为的受损': '纤维的收缩',
        '肌肉线为': '肌肉纤维',
        '肌肉的受损': '肌肉的收缩',
        '盖离子': '钙离子',
        '盖了一子': '钙离子',
        '艺术体表': '溢出体表',
        '电型号': '电信号',
        '反应': '反应',
        '几随': '脊髓',
        '脑中输': '脊髓上行',
        '几随前脚': '脊髓前脚',
        '基层': '脊髓',
        '基层现场': '脊髓前角',
        '拖拦': '偷懒',
        '拖拦的东西': '偷懒的方法',
        '那两粒子': '钠离子',
        '钠两粒子': '钠离子',
        '作电为传递': '以电信号传递',
        '作动': '收缩',
        '吹拧': '训练',
        '真相关': '正相关',
        '北大级': '北大脑',
        '神经内科的北大级': '神经内科的北大专家',
        '胜利活动': '生理活动',
        '肌电的研究': '肌电的研究',
        '级电的研究': '肌电的研究',
        '外州': '外周',
        '飞进入': '非侵入',
        '非进入': '非侵入',
        '进入式': '侵入式',
        '飞侵入': '非侵入',

        # 物理/机器人术语
        'Physical Agent': 'Physical Agent',
        'physical agent': 'physical agent',
        'Fitical Agent': 'Physical Agent',
        'Fetical Agent': 'Physical Agent',
        'fetical agents': 'physical agents',
        'fetical一家': 'physical agent',
        'fetical的interaction': 'physical interaction',
        'fetical的interaction': 'physical interaction',
        'in-hand manipulation': 'in-hand manipulation',
        'Inhance Manipulation': 'in-hand manipulation',
        '零销手': '灵巧手',
        '灵悄手': '灵巧手',
        '领巧手': '灵巧手',
        '居城智能': '具身智能',
        '机器智能公司': '机器人公司',
        '居身智能': '具身智能',
        '人际供容': '人机共融',
        '人际共容': '人机共融',
        '人机共容': '人机共融',
        '人际供容层': '人机共融层',
        '西数的矩阵': '稀疏的矩阵',
        '卡链和平静': '瓶颈和极限',
        '赛顶下': '背景下',
        '航空大': '哈工大',
        '基地工程学院': '机电工程学院',
        '航空宇航制造工程系': '航空宇航制造工程系',
        '电回信息': '电信号',
        '区体': '肢体',
        '见果': '建模',
        '建果': '建模',
        'grounding knowledge': 'grounding knowledge',
        'physical input': 'physical input',
        'motionunitive': 'motor unit',
        'hobaldi': 'holographic',
        'avita': 'avatar',
        'miping': 'mapping',
        'princentrini': 'principle',
        'gim': 'gym',
        'pulse': 'Pulse',
        'lighten': 'latent',
        'latten space': 'latent space',
        'latent space': 'latent space',
        'fature': 'feature',
        'alpuz target': 'ultimate target',
        'invall human': 'involve human',
        '强减度': '强监督',
        'human tokenization': 'human tokenization',
        't取': 'tokenize',
        'hyper show': 'HyperShow',
        '极俏': '机甲',
        '机座': '肌电',
        'princentrini': 'principal',
        'lighten the signal encoder': 'latent signal encoder',
        'back to orange': 'Back to Orange',
        'back to Oranger': 'Back to Orange',
        'Oranger': 'Orange',
        'Oranger的': 'Orange的',
        '普天手': '无屏',
        '耐空分': '脑空间',
        '音符': '信息',
        'CDRS': 'CDR',
        'NURSANCE': 'nuisance',
        'nursance': 'nuisance',
        'infra': 'infra',
        '白照': '百兆',
        '每彩样': '每采样',
        '两千盒子': '两千赫兹',
        '千分之一': '千分之一',
        '百兆比': '百兆比特',
        'minifo': 'meaningful info',
        'minifore': 'meaningful info',
        'minivore': 'meaningful',
        '牛肉interface': 'neural interface',
        '牛肉 Interface': 'neural interface',
        'HUMAN整车': 'human integral',
        'human integral': 'human integral',
        '规矩': 'GPT',
        '规矩生命体': 'GPT 生命体',
        '规矩的transfer': 'GPT 的 transfer',
        '排程': '轨迹',
        '新道比': '信噪比',
        'erasing': 'reasoning',
        '非签入': '非侵入',
        '老集结口': '神经接口',
        '此库': '语境',
        '叛机的': '有机的',
        '估计的': '无机的',
        '发你交互': '发生交互',
        '一定成了上': '一定程度上',
        '爱的目标': 'AI 的目标',
        'difference': 'difference',
        '厂市': '尝试',
        '振流': '蒸馏',
        '真流': '蒸馏',
        '征留': '蒸馏',
        '船地': '传递',
        '船递': '传递',
        '成绩态老下来': '持续探讨',
        'Incance': 'Intelligence',
        'Incance Curemen': 'Intelligence Enhancement',
        '贪汇之铁大丰富': '物质极大丰富',
        'Poor会会': '能力会',
        '碳规及融合': '碳硅融合',
        '中矩': '终局',
        '人力外脑': '人类外脑',
        'Lonage': 'knowledge',
        '链罗': '链条',
        'response false': 'response force',
        'active false': 'active force',
        '主动力': '主动力',
        '反驱力': '反作用力',
        '东方有个potential': '前方有个 potential',
        '高位于一层': '高维一层',
        'sense了某个signal': 'sense 某个 signal',
        '做功课的': '做过功的',
        '学名叫muap': '学名叫 MUAP',
        'resonance': 'response',
        '方电': '放电',
        '见果': '建模',
        '建果': '建模',
        'band': 'band',
        '两个band': '两个手环',
        '两band': '两个手环',
        '鼠钓键盘': '鼠标键盘',
        'neuromismagin': 'neuromuscular mapping',
        '开了炉': '开了颅',
        '表皮欠了': '表皮植入了',
        '脑解': '脑区',
        '860个神经': '860 亿个神经元',
        '860一个弹针': '860 亿个探针',
        '不到16哪怕1亿个弹针': '不到 16 亿哪怕 1 亿个探针',
        '神经远': '神经元',
        '巨星': '距离',
        'feat.co': 'AGI',
        'feat co': 'AGI',
        '全局解': '全局解',
        '碳针': '探针',
        '几随前脚': '脊髓前脚',
        '最上有': '最上游',
        '植物神经': '植物神经',
        '感受神经': '感觉神经',
        '管车型的': '管运动的',
        'KPI': 'KPI',
        '神区的那一套': '神经的那一套',
        '模式关节': '滑膜关节',
        '吹拧': '训练',
        'model width': 'model width',
        '神经源': '神经元',
        '激活': '激活',
        '推您的时候': '训练的时候',
        'moments': 'moment',
        'sensor到了': 'sensor 到了',
        '先接口': '神经接口',
        '胜利活动': '生理活动',
        '数十毫秒': '数十毫秒',
        '实验': '实验',
        '体感': '体感',
        '实验': '实验',
        '实验': '实验',
        '原则': '延迟',
        '进向了': '镜像了',
        '运动成绩接口': '运动神经接口',
        '早云': '超前',
        '记合一记': '脊髓一节',
        '新机传递的带款': '神经传递的带宽',
        '带款': '带宽',
        'everything': 'everything',
        'viden': 'video',
        'tensor': 'tensor',
        'channel': 'channel',
        'info': 'info',
        '微人': '维恩',
        '达量': '大量',
        '执行册': '执行层',
        '百兆比': '百兆比特',
        'flow': 'flow',
        '环单平洋': '全身穿戴',
        '机电浮出来': '肌电手环',
        'Sale the same moments': 'share the same moments',
        '绝踏不出来': '觉察不出来',
        '飞领到': '领会到',
        '暗送秋波': '暗送秋波',
        '太大模型': '大模型',
        '居城智能公司': '具身智能公司',
        '极窍': '机械臂',
        '棉刘': '棉刘',
        'Potential': 'Potential',
        'Robots': 'Robots',
        'Human': 'Human',
        'Nullizer': 'Nullifier',
        'Bloodler': 'Bloodler',
        'Muzzle': 'Muscle',
        'Sintigre': 'synthetic',
        'patent': 'patent',
        'Thinking patent': 'thinking pattern',
        '零销手': '灵巧手',
        '万部': '腕部',
        '长那一季': '上肢那一侧',
        'Control': 'Control',
        '下意识': '下意识',
        'Synthesizer': 'Synthesizer',
        '音符': '信息',
        '西数的矩阵': '稀疏的矩阵',
        '简法': '减法',
        'prior data': 'prior data',
        'Prior Data': 'Prior Data',
        '理由化': '优化',
        '逼人号': '进化',
        '负能': '赋能',
        '向法一样': '想法一样',
        '发动的空间': '活动的空间',
        '真流Astropic': '蒸馏Anthropic',
        '真流Astropic': '蒸馏Anthropic',
        'Ryzenling': 'reasoning',
        "Razin'ing": 'reasoning',
        'Razining': 'reasoning',
        'Razin': 'reasoning',
        '拉中兴': 'reasoning',
        '四张实验': '思想实验',
        'Bluing': 'if we',
        '我们又很Bluing': '如果我们又有',
        '大圆模型': '大语言模型',
        '新道比': '信噪比',
        '规矩': 'GPT',
        '排程': '轨迹',
        'Fatco EGI': 'Factored EGI',
        'Oranger Flow': 'Orange Flow',
        '创神': '创始人',
        '创神者': '创始人',
        '真流': '蒸馏',
        'lequin': 'LeCun',
        'wishmaster obiq': 'Windsurf',
        'Wishmaster obiq': 'Windsurf',
        '夸契': 'Claude',
        '莫得': '抹掉',
        '证券的': '正确的',
        '费力': '飞轮',
        '传辘': '转折',
        'MetroLibs': 'CTRL-Labs',
        'Mata': 'Meta',
        'ruotex': 'robotics',
        'skilling': 'scaling',
        'run a 家公司': 'run 一家公司',
        'Masker': 'Musk',
        '毛脸': '锚点',
        'beta': 'Meta',
        '杜克伯格': '扎克伯格',
        '马尔塔': 'Meta',
        '马尔克': 'Musk',
        'Sorbi': 'Anthropic',
        '安斯罗皮克': 'Anthropic',
        'onTechs': 'Anthropic',
        'youther': 'user',
        '天神': '注意力',
        'Bluing': 'if we',
        'Fitical Agent': 'Physical Agent',
        'HUMAN整车': 'human integral',
        '微人': '为人',
        '逆于死地而后生': '置于死地而后生',
        '陈耀晶': '程咬金',
        'Tay泰坦利克号': '泰坦尼克号',
        '泰塔利克号': '泰坦尼克号',
        '朱元璋开学一个晚': '朱元璋开局一个碗',
        'songline': '某个',
        'funder': 'founder',
        'towlnfax': 'to some extent',
        'ambitious': 'ambition',
        '飞领到': '领会到',
        'subject': 'subject',
        'cross subject': 'cross subject',
        'symmetry or case': 'symmetry across',
        'day one': 'day one',
        'golden label': 'golden label',
        'supervisor signal': 'supervisory signal',
        'meaningful': 'meaningful',
        'prior data': 'prior data',
        'control bandwidth': 'control bandwidth',
        'in-hand manipulation': 'in-hand manipulation',
        'human to robots transfer': 'human to robot transfer',
        'physical agent': 'physical agent',
        'neural interface': 'neural interface',
        'brain computer interface': 'brain-computer interface',
        '肌电信号': '肌电信号',
        '运动神经元': '运动神经元',
        '神经肌肉接口': '神经肌肉接口',
        '差模信号': '差模信号',
        '运动伪迹': '运动伪迹',
        '信噪比': '信噪比',
        '滤波': '滤波',
        '差分': '差分',
        '隐空间': '隐空间',
        '强监督': '强监督',
        '蒸馏': '蒸馏',
        'reasoning': 'reasoning',
        'scaling': 'scaling',
        'founder': 'founder',
        'gaming': 'gaming',
        '逆风局': '逆风局',
        '排位赛': '排位赛',
        '匹配赛': '匹配赛',
        '青铜局': '青铜局',
        '白银': '白银',
        '黄金': '黄金',
        '钻石': '钻石',
        '王者': '王者',
        '泰坦尼克号': '泰坦尼克号',
        '朱元璋开局一个碗': '朱元璋开局一个碗',
        '程咬金': '程咬金',
        '虚空掠夺者': '虚空掠夺者',
        '卡兹克': '卡兹克',
        '荣耀行星官': '荣耀行刑官',
        '刺客围': '刺客',
        'Neuralink': 'Neuralink',
        'CTRL-Labs': 'CTRL-Labs',
        'Anthropic': 'Anthropic',
        'Claude': 'Claude',
        'Cursor': 'Cursor',
        'Windsurf': 'Windsurf',
        'Meta': 'Meta',
        'Musk': 'Musk',
        'LeCun': 'LeCun',
        'DeepMind': 'DeepMind',
        'DeepSeek': 'DeepSeek',
        'Deep Sake': 'DeepSeek',
        'Trinx Model': 'Transformer Model',
        'Transformer Model': 'Transformer Model',
        'Transformer': 'Transformer',
        'oper': 'Cursor',
        'opers': 'Cursor',
        'codex': 'Codex',
        'Codex': 'Codex',
        'coding agent': 'coding agent',
        '哈工大': '哈工大',
        '航空宇航制造工程系': '航空宇航制造工程系',
        '绿洲': '绿洲',
        '绿洲资本': '绿洲资本',
        'Orange Flow': 'Orange Flow',
        '张津剑': '张津剑',
        '张金剑': '张津剑',
        '秦深涛': '秦深涛',
        '金箭哥': '金箭哥',
        '郑杨哥': '张津剑',
        '高洋老师': '高杨老师',
        '张伟老师': '张巍老师',
        '宝宋': '保研',
        '皇补军校': '黄埔军校',
        '再要要批诀': '再要一批',
        'Hambel': 'Humble',
        'Chad DVD': 'ChatGPT',
        '登陵': '登顶',
        'profession': 'profession',
        'situation的bass paper': 'seminal paper',
        '权权赛道': '全新赛道',
        '世俗一上': '世俗意义上',
        '功名': '共鸣',
        '报道经理': '道德经',
        '有之以为利': '有之以为利',
        '无之以为用': '无之以为用',
        '沉思度': '成熟度',
        'run something': 'run something',
        '后宴': '后验',
        'suffer': 'suffer',
        'recover': 'recover',
        '参战生命力': '生命力',
        '智能一些': '稚嫩一些',
        'life in gaming': 'life in gaming',
        'game changer': 'game changer',
        'have fun': 'have fun',
        'follow your calling': 'follow your calling',
        'follow your heart': 'follow your heart',
        '局务罪优': '局部最优',
        'overfitting': 'overfitting',
        'declaration': 'declaration',
        '性知所至': '兴之所至',
        '性敬而归': '兴尽而归',
        '多摩泰大模型': '多模态大模型',
        'local motion': 'locomotion',
        'raige': 'Rage',
        '哈务达': '哈佛',
        'Animo Ruo Bao': 'Humanoid Robot',
        'Animo Ruo Bao这个组织': 'Humanoid Robot 这个组织',
        'Dynamics': 'Dynamics',
        'Timing': 'Timing',
        'Fuller 1 Heart': 'follow your heart',
        'Fuller 1 Calling': 'follow your calling',
        'Calling': 'calling',
        '供证了': '共振了',
        '残血': '残血',
        '居身智能的发源地': '具身智能的发源地',
        '层速度': '成熟度',
        '稳定性': '稳定性',
        '月历': '阅历',
        'times': 'times',
        'believing': 'believing',
        '非共识': '非共识',
        '射线': '设限',
        '管你的funder': '不管你是 founder',
        '手机科学家': '首席科学家',
        'AGI一个店': 'AGI 一个点',
        '引文凯': '尹文凯',
        '文凯的': '文凯的',
        'Badest Petper': 'best paper',
        '运营就': '运营就',
        'New Motor Interface': 'neural interface',
        '学术权': '学术界',
        '赛尔实验室': 'SAIL 实验室',
        '哈统达': '斯坦福',
        '哈统达赛尔': '斯坦福 SAIL',
        'Cian Cian': '吴恩达',
        '自然员处理': '自然语言处理',
        '皇补军校': '黄埔军校',
        '再要要批诀': '再要一批',
        'Hambel': 'Humble',
        'Chad DVD': 'ChatGPT',
        '清空': '清零',
        '结局为零': '赛道重启',
        'profession': 'profession',
        'situation的bass paper': 'seminal paper',
        '权权赛道': '全新赛道',
        '世俗一上': '世俗意义上',
        '功名': '共鸣',
        '登顶': '登顶',
    },

    # === AI / 大模型领域（已在 WRONG_WORDS 中部分覆盖，补充更多） ===
    'ai_llm': {
        '唆掉': '坍缩',
        '领导模': '大模型',
        '领导模型': '大模型',
        '唆了': '坍缩了',
        '浪': 'curve',
        'java的一个内核的点': '一个核心的点',
        'java的': '核心的',
        '唆了之后': '坍缩之后',
        '领导模去': '大模型',
        'day one的': 'day one 的',
        '营化': '弱化',
        '证券的': '正确的',
        '莫得进去': 'merge 进去',
        '贪说到了一个': '坍缩到了一个',
        '数据费力': '数据飞轮',
        '马上去睡小屋': '马上就要去 AI 浪潮',
        '小的头子': '小的口子',
        '往下面去锤': '往下面去挖',
        '超越Sorbi的机会': '超越 Anthropic 的机会',
        '传辘': '转折',
        'MetroLibs被Mata并购': 'CTRL-Labs 被 Meta 并购',
        '公众': '公众',
        '新闻组': '新闻中',
        '那片那首正坎': '那片论文证明',
        'skilling 曲线': 'scaling 曲线',
        '背的它': '被它',
        '不放的心态': '观望的心态',
        '能生的': '萌生',
        'sense的概念': 'sense 的概念',
        'have fun': 'have fun',
        '拍位赛': '排位赛',
        '有英明都无所谓': '有输赢都无所谓',
        '认识我': '认真玩',
        'nurlink': 'Neuralink',
        '终极答案': '终极答案',
        '毛脸': '锚点',
        'Masker的规划': 'Musk 的规划',
        'D1': 'day one',
        '指出了': '指明了',
        '直举下云澳机': '直接从脑机接口下手',
        '临德': 'Neuralink',
        '太大模型': '大模型',
        '天神': '注意力',
        'Next Generation': 'Next Generation',
        '淘不当': '靠谱',
        '不够淘不当': '不够靠谱',
        'Deep Sake': 'DeepSeek',
        'Trinx Model': 'Transformer Model',
        '花见效率': '花钱效率',
        'bube': 'build',
        'MNATIVE': 'native',
        'top-down': 'top-down',
        '99%的精力': '99% 的精力',
        '超级100%的精力': '超级 100% 的精力',
        'founder': 'founder',
        '全部的生命': '全部的生命',
        '现行推演': '线性推演',
        '数以一计': '数以亿计',
        'A型': 'AI',
        '海利是': '还不是',
        '软装': '软装',
        '低估一个问题': '低估一个问题',
        '高估一个问题': '高估一个问题',
        'next generation': 'next generation',
        '建一个未来很重要的问题': '定义一个未来很重要的问题',
        '定一个自己很重要的问题': '定一个自己很重要的问题',
        '全部的生命': '全部的生命',
        '一个很大的全球企业的一个创始人': '一个很大的全球企业的创始人',
        '睡了太多': '睡了太多',
        '睡一下': '当时',
        '气息': '气息',
        '内科我就是': '那一刻我就在想',
        '卷': '卷',
        'drive你': 'drive 你',
        'x类': 'X 类',
        '预指': '阈值',
        '经济状态': '精神状态',
        'gaming': 'gaming',
        '项目口': '校门口',
        '爆炸': '爆炸',
        '要忘记给我了': '要忘记给我了',
        '处着拐杖': '拄着拐杖',
        '另外一条腿也断了': '另外一条腿也断了',
        '当成工作': '当成工作',
        '天赋': '天赋',
        '生命这个词': '生命这个词',
        '好好理解一下': '好好理解一下',
        '因gaming的状态': 'in gaming 的状态',
        '巴不得': '巴不得',
        '通肖': '通宵',
        '睡一个小时': '睡一个小时',
        'in gaming': 'in gaming',
        'common': 'common',
        'control关于自己的body': 'control 关于自己的 body',
        'planel': '极限',
        '扭一些': '强一些',
        'common这种情况': 'common 这种情况',
        '生率': '胜率',
        '军就': '均值',
        '决签': '关键',
        'songline真的是一个大线游戏': '某个真的是一个大型游戏',
        '最爽的角色副本': '最爽的角色副本',
        '朱元璋开学一个晚': '朱元璋开局一个碗',
        '佛家的角度': '佛家的角度',
        '观照': '观照',
        '从小是个好孩子': '从小是个好孩子',
        '送到病死': '生老病死',
        '生老病死': '生老病死',
        '聚帅': '巨帅',
        '药药道病除': '药到病除',
        '伟大的冲突': '伟大的冲突',
        '威尼斯商人': '威尼斯商人',
        '泰塔利克号': '泰坦尼克号',
        '小板上回去了': '小船上回去了',
        '牺牲本身是壮美的': '牺牲本身是壮美的',
        '看自己这部电影': '看自己这部电影',
        '希望自己这部电影': '希望自己这部电影',
        '平安顺遂的医生': '平安顺遂的一生',
        '下一次再来': '下一次再来',
        '王子荣耀': '王者荣耀',
        '陈耀晶': '程咬金',
        '掉雪': '掉血',
        '逆于死地而后生': '置于死地而后生',
        '枯的角色': '酷的角色',
        '英雄联盟': '英雄联盟',
        '刺客围': '刺客',
        '虚空掠夺者': '虚空掠夺者',
        '卡兹克': '卡兹克',
        '生命的本身就是进化': '生命的本身就是进化',
        '超级进化': '超级进化',
        '斩杀掉一个人之后': '斩杀掉一个人之后',
        '立即刷新': '立即刷新',
        '闪现': '闪现',
        '大招是隐形': '大招是隐形',
        '孤立目标': '孤立目标',
        '逐个击破': '逐个击破',
        'carry': 'carry',
        '荣耀行星官': '荣耀行刑官',
        '射手': '射手',
        'C位': 'C位',
        '大件的经济': '大件的经济',
        '全场carry': '全场 carry',
        'team的一个游戏': 'team 的一个游戏',
        'meaningful的': 'meaningful 的',
        '张良': '张良',
        'funder你会选择什么': 'founder 你会选择什么',
        '还比较关键的角色': '还比较关键的角色',
        '面临卡点': '面临卡点',
        '角色影响的': '角色影响的',
        '暴力的人吗': '暴力的人吗',
        'towlnfax': 'to some extent',
        '估计': '顾忌',
        '保险': '保险',
        '抓得住主要矛盾': '抓得住主要矛盾',
        '高级的位置': '高优先级的位置',
        '立马': '立马',
        '第一代方案': '第一代方案',
        '冒烟测试': '冒烟测试',
        '快速点': '快速迭代',
        '三号': '三号',
        '学会走路之前学会跑': '学会走路之前学会跑',
        '学会跑步之前学会飞': '学会跑步之前学会飞',
        '原地起飞': '原地起飞',
        '轰动加油': '轰动加油',
        '强行逻辑': '强行逻辑',
        'I see': 'I see',
        '教你就是': '跟你',
        '在感受你的过程里面': '在感受你的过程里面',
        '锐利的东西': '锐利的东西',
        'Stay in the game': 'Stay in the game',
        'win的那种ambitious': 'win 的那种 ambition',
        '仔细的很强的人': '好胜心很强的人',
        '打这把拍位赛': '打这把排位赛',
        '哥们儿我说你都有': '哥们儿我说你都有',
        '不要参与': '不要参与',
        '不容易去打匹配': '不容易去打匹配',
        '既然要玩这个游戏': '既然要玩这个游戏',
        '认识我': '认真玩',
        '尊重': '尊重',
        '打的是逆风局': '打的是逆风局',
        '最大的take away': '最大的 take away',
        '怎么打好逆风局': '怎么打好逆风局',
        '反共是': '反共识是',
        'carry逆风局': 'carry 逆风局',
        '你倒知道': '你得知道',
        '最幸运的队友': '最菜的队友',
        '观念点': '关键节点',
        '一场你的失误': '一次你的失误',
        '一边倒的崩盘': '一边倒的崩盘',
        '尊重这个现实': '尊重这个现实',
        '接纳他': '接纳它',
        '认可现在你们是崩盘': '认可现在你们是崩盘',
        '你的队友是失误了': '你的队友是失误了',
        '心态好是什么意思': '心态好是什么意思',
        '携手他们': '携手他们',
        '找机会扭转': '找机会扭转',
        '你的队友会自责': '你的队友会自责',
        '没熟的队友': '不成熟的队友',
        '埋怨': '埋怨',
        '继续去找于目标': '继续去寻找目标',
        '带领他们寻找机会': '带领他们寻找机会',
        '首先发现': '首先发现',
        '与撕开一个口子': '撕开一个口子',
        '抓对方的事物': '抓对方的失误',
        '利用他们的事物': '利用他们的失误',
        '搬回来': '扳回来',
        '私扯': '拉扯',
        '发育起来': '发育起来',
        '足够的私扯': '足够的拉扯',
        '人生到现在打过最大的逆风局势': '人生到现在打过最大的逆风局是',
        '经历过这个逆风局': '经历过这个逆风局',
        '都不算是': '都不算是',
        '原来以前都是青铜族': '原来以前都是青铜局',
        '都是扯头花': '都是扯头花',
        '真正的逆风局还没开始': '真正的逆风局还没开始',
        '创业之后': '创业之后',
        '打了最大的逆风局势': '打了最大的逆风局是',
        '也还没开始': '也还没开始',
        '还在白影': '还在白银',
        'Masco会管着你': 'Musk 会管着你',
        '到黄金了': '到黄金了',
        'New Orleans': 'Neuralink',
        '自己下场了': '自己下场了',
        '到钻石了': '到钻石了',
        '还没有到王者': '还没有到王者',
        '到王者的时候': '到王者的时候',
        '真的代表中国': '真的代表中国',
        '占到那个地方': '站到那个地方',
        '什么主别': '什么组别',
        '竞争对手决定的': '竞争对手决定的',
        '自己的对手很强': '自己的对手很强',
        '玩游戏的人': '玩游戏的人',
        '都有一种冲动': '都有一种冲动',
        '用足够少的资源和时间': '用足够少的资源和时间',
        '拿足够多的经验': '拿足够多的经验',
        '武器装备': '武器装备',
        '属性各方面都拉到满': '属性各方面都拉到满',
        '刷到极致': '刷到极致',
        '你的对手特别强的时候': '你的对手特别强的时候',
        '不允许你失误': '不允许你失误',
        '最有意思的地方': '最有意思的地方',
        '碰到一个比你牛逼得多的对手': '碰到一个比你牛逼得多的对手',
        '被迫在被调打过程中成长': '被迫在被吊打过程中成长',
        '不接受自己的书': '不接受自己输',
        '不接纳': '不接纳',
        '先不接纳他': '先不接纳它',
        '然后不接纳自己': '然后不接纳自己',
        '全自己猜': '全自己扛',
        '但不接受书': '但不接受输',
        '开始的时候也不承认猜': '开始的时候也不承认扛',
        'day one搞specialized': 'day one 搞 SpaceX',
        '才不输自己书': '才不认输',
        '再一点一点的去进化': '再一点一点的去进化',
        '第一天就遇到了这里面': '第一天就遇到了这里面',
        '可能有问题': '可能有问题',
        '刚认识': '刚认识',
        '也算陪你经历了这个过程': '也算陪你经历了这个过程',
        '三四个月的时间': '三四个月的时间',
        '到十月份': '到十月份',
        '对很多创业者而言': '对很多创业者而言',
        '非常非常痛苦的': '非常非常痛苦的',
        '天风开举嘛': '天崩开局嘛',
        '肯定很多人就不干了': '肯定很多人就不干了',
        '回去读书了': '回去读书了',
        '抱怨运气不好': '抱怨运气不好',
        '有人埋怨别人': '有人埋怨别人',
        '有的人埋怨自己': '有的人埋怨自己',
        '做大量的反思之后': '做大量的反思之后',
        '回去上课了': '回去上课了',
        '说可能我没准备好': '说可能我没准备好',
        '等我再过两年': '等我再过两年',
        '等我ready': '等我 ready',
        '我再出来创业': '我再出来创业',
        '但是你没有': '但是你没有',
        '你想了三个月': '你想了三个月',
        '把这个东西处理干净了之后': '把这个东西处理干净了之后',
        '你的结论是这个': '你的结论是这个',
        '我要赢': '我要赢',
        '我要干': '我要干',
        '这个思想是怎么发生变化的呢': '这个思想是怎么发生变化的呢',
        '嗯': '嗯',
        '我说这里面有两个点': '我说这里面有两个点',
        '一个是关于我个人的': '一个是关于我个人的',
        '另外一个也是关于我们刚才讲的': '另外一个也是关于我们刚才讲的',
        'Foundering Gaming': 'Foundering Gaming',
        '我觉得第一个点就是': '我觉得第一个点就是',
        '作为一个学生': '作为一个学生',
        '之前是没有面临过和人的冲突的': '之前是没有面临过和人的冲突的',
        '因为你作为学生': '因为你作为学生',
        '尤其是功课的学生': '尤其是理工科的学生',
        '你面临的都是技术问题': '你面临的都是技术问题',
        '技术问题是一定能够有唯一答案': '技术问题是一定能够有唯一答案',
        '完全的一定会有一个': '完全的一定会有一个',
        'Zilow': 'Zeno',
        'somehow': 'somehow',
        'resist by': 'resist by',
        '你是能讨论清楚的': '你是能讨论清楚的',
        '但是有一个课题': '但是有一个课题',
        '我觉得所有学生都会去面对': '我觉得所有学生都会去面对',
        '人生很复杂': '人生很复杂',
        '他也很难说通过一种方式': '他也很难说通过一种方式',
        '能够让学生意识到这个东西': '能够让学生意识到这个东西',
        '是他们必须补的': '是他们必须补的',
        '或者说通过某种方式': '或者说通过某种方式',
        '让他们稍微有那么一点sense': '让他们稍微有那么一点 sense',
        '其实通通都没有': '其实通通都没有',
        '对于我来讲': '对于我来讲',
        '我最大的这个learning就是': '我最大的这个 learning 就是',
        '你可能不得不把你': '你可能不得不把你',
        '非常纯粹的做这个事情的那个人': '非常纯粹的做这个事情的那个人',
        '和作为一个CEO': '和作为一个 CEO',
        '要有分开': '要分开',
        '一个真正的成熟就是': '一个真正的成熟就是',
        '你能够在对应的场景下': '你能够在对应的场景下',
        '去做好该做的那个角色': '去做好该做的那个角色',
        '哪怕在另外一个场景下': '哪怕在另外一个场景下',
        '你的角色是不一样的': '你的角色是不一样的',
        '但是在那个角色下': '但是在那个角色下',
        '这是你要走的路': '这是你要走的路',
        '而且你要接受自己这样': '而且你要接受自己这样',
        '就是说我不是我': '就是说我不是我',
        '我是当下的这个角色': '我是当下的这个角色',
        '当下的角色': '当下的角色',
        '我是这个CEO': '我是这个 CEO',
        '我的CEO应该做什么': '我的 CEO 应该做什么',
        '我就做什么': '我就做什么',
        '你应该做什么': '你应该做什么',
        '还有第二个点就是': '还有第二个点就是',
        '如果你遇到了一些block': '如果你遇到了一些 block',
        '然后你因此而选择hold on': '然后你因此而选择 hold on',
        '其实老实来讲': '其实老实来讲',
        '非常可惜': '非常可惜',
        '就是为什么你已经做好了': '就是为什么你已经做好了',
        '要打排位的准备': '要打排位的准备',
        '然后因为一些困难就放弃了': '然后因为一些困难就放弃了',
        '我觉得不应该放弃': '我觉得不应该放弃',
        '那你是什么样的场景': '那你是什么样的场景',
        '给自己的这样一个答案呢': '给自己的这样一个答案呢',
        '我中间去了一趟raige': '我中间去了一趟 Rage',
        '那边见到了很多': '那边见到了很多',
        '在哈务达时期': '在哈佛时期',
        '然后因为有师兄师姐在那边读书': '然后因为有师兄师姐在那边读书',
        '见到了他们': '见到了他们',
        '还有很多清华的师兄': '还有很多清华的师兄',
        '然后在和他们交流的过程中': '然后在和他们交流的过程中',
        '你突然感觉到': '你突然感觉到',
        '哎这个是原来你要去的那个地方': '哎这个是原来你要去的那个地方',
        '意思就是说': '意思就是说',
        '有一帮人': '有一帮人',
        '通过一些非常高效的组织': '通过一些非常高效的组织',
        '在一起': '在一起',
        '很纯净的想把一些事情': '很纯净的想把一些事情',
        '变成现实': '变成现实',
        '而这个组织': '而这个组织',
        'Animo Ruo Bao这个组织': 'Humanoid Robot 这个组织',
        '他就推动Local Motion 变革的那帮人': '他就是推动 locomotion 变革的那帮人',
        '然后你在那个Dynamics下': '然后你在那个 Dynamics 下',
        '你说哦有一些事情': '你说哦有一些事情',
        '对那是你当时的起点': '对那是你当时的起点',
        '然后今天走到一半': '然后今天走到一半',
        '然后如果你放下了': '然后如果你放下了',
        '非常非常可惜': '非常非常可惜',
        '因为你会回头去想说': '因为你会回头去想说',
        '你经历了这么多东西': '你经历了这么多东西',
        '那到了这个点': '那到了这个点',
        '一个你可以卖过去': '一个你可以迈过去',
        '也可以不卖过去的Timing下': '也可以不迈过去的 Timing 下',
        '你要怎么选择': '你要怎么选择',
        '对你问自己的': '对你问自己的',
        '真的Fuller 1 Heart': '真的 follow your heart',
        '你能听到你的Calling': '你能听到你的 calling',
        '我如果跟自己说句话': '我如果跟自己说句话',
        '你要说什么': '你要说什么',
        '还是Fuller 1 Calling': '还是 follow your calling',
        '对可以平': '对可以平静',
        '当时你': '当时你',
        '你咱们表现这段话的时候': '你咱们聊这段话的时候',
        '我老在里面的画面': '我老在里面的画面',
        '就是一个英雄回到了泉水': '就是一个英雄回到了泉水',
        '对吧就是只有一丝血了': '对吧就是只有一丝血了',
        '对吧然后那个地方': '对吧然后那个地方',
        '可能那个地方是Local Motion 的发源地': '可能那个地方是 locomotion 的发源地',
        '或者是我们所谓今天': '或者是我们所谓今天',
        '所有的居身智能的发源地': '所有的具身智能的发源地',
        '对吧然后你在那个地方': '对吧然后你在那个地方',
        '可能有一群人': '可能有一群人',
        '那个地方的那些人的心力': '那个地方的那些人的心力',
        '感染了你': '感染了你',
        '就很多时候人生': '就很多时候人生',
        '要不要再出发': '要不要再出发',
        '就是你的心力还有没有': '就是你的心力还有没有',
        '就很多时候有些人放弃了': '就很多时候有些人放弃了',
        '就是因为累了': '就是因为累了',
        '就是你可能': '就是你可能',
        '就那一丝残血的时候': '就那一丝残血的时候',
        '在那个地方': '在那个地方',
        '你被那个Calling 又供证了': '你被那个 calling 又共振了',
        '然后供证了之后': '然后共振了之后',
        '你的血条就满了': '你的血条就满了',
        '满了之后': '满了之后',
        '你就决定再出发了': '你就决定再出发了',
        '对吧然后': '对吧然后',
        '因为其实你是01年': '因为其实你是 01 年',
        '对就你今天在表述这个问题的': '对就你今天在表述这个问题的',
        '层速度和': '成熟度和',
        '稳定性其实是': '稳定性其实是',
        '我想已经有点像一个老兵的感觉了': '我想已经有点像一个老兵的感觉了',
        '我们哪怕从去年7月开始算': '我们哪怕从去年 7 月开始算',
        '你不过创业不到一年': '你不过创业不到一年',
        '如果从人生的月历来算': '如果从人生的阅历来看',
        '那现在才25岁': '那现在才 25 岁',
        '就是你是': '就是你是',
        '怎么让自己发育得这么快的呢': '怎么让自己发育得这么快的呢',
        '你按你的说法': '你按你的说法',
        '你先来别人一个大剑': '你先来别人一个大剑',
        '对吧这个里面的': '对吧这个里面的',
        '方法是什么呢': '方法是什么呢',
        '我觉得非常关键的点就是': '我觉得非常关键的点就是',
        '你知道就是在gaming里面': '你知道就是在 gaming 里面',
        '你做到一个': '你做到一个',
        '之前没有人做到的东西有一个点': '之前没有人做到的东西有一个点',
        '就是你是否相信': '就是你是否相信',
        '在这个times下': '在这个 times 下',
        '做到这个东西是有可能的': '做到这个东西是有可能的',
        '对因为今天刚才这个问题抛出来': '对因为今天刚才这个问题抛出来',
        '就意味着说': '就意味着说',
        '可能在common sense里面': '可能在 common sense 里面',
        '在这个times做到这个东西是很难的': '在这个 times 做到这个东西是很难的',
        '对但今天我们作为gaming': '对但今天我们作为 gamer',
        '我们要聊的是': '我们要聊的是',
        '在这个times下': '在这个 times 下',
        '做到这样的一种状态': '做到这样的一种状态',
        '他有没有可能性': '他有没有可能性',
        '如果有': '如果有',
        '对吧如果他': '对吧如果他',
        '第一性上是ok的': '第一性上是 ok 的',
        '你就believing他': '你就 believing 他',
        '并且你一定要做到他': '并且你一定要做到他',
        '我记得有一个': '我记得有一个',
        '特别有意思的话': '特别有意思的话',
        '可能之前不是特别理解': '可能之前不是特别理解',
        '现在有点懂了': '现在有点懂了',
        '就是没有困难': '就是没有困难',
        '创造困难我们也要上': '创造困难我们也要上',
        '困难本质就是说': '困难本质就是说',
        '你为了让自己在很短的时间内': '你为了让自己在很短的时间内',
        '能够有一些成长': '能够有一些成长',
        '有一些buff的争议': '有一些 buff 的增益',
        '所以就说': '所以就说',
        '你给自己提出了一些': '你给自己提出了一些',
        '看上去不可能的': '看上去不可能的',
        '或者说你认为市场的某种共识': '或者说你认为市场的某种共识',
        '其实都是在你的眼中': '其实都是在你的眼中',
        '都是非共识': '都是非共识',
        '就是我应该提一些': '就是我应该提一些',
        '这东西完全可以更快': '这东西完全可以更快',
        '或者更好': '或者更好',
        '就是我觉得有的时候': '就是我觉得有的时候',
        '人们会给自己射线': '人们会给自己设限',
        '会管你的funder': '不管你是 founder',
        '他会假设自己一定搞不懂AGI': '他会假设自己一定搞不懂 AGI',
        '所以他一定要找一个': '所以他一定要找一个',
        '手机科学家': '首席科学家',
        '或者找很多手机科学家': '或者找很多首席科学家',
        '对吧然后你也会看到': '对吧然后你也会看到',
        '有些科学家给自己射线说': '有些科学家给自己设限说',
        '我没有睁眼': '我没有经验',
        '我没法绕一个公司': '我没法绕一个公司',
        '所以要加入一家公司': '所以要加入一家公司',
        '或者怎么样': '或者怎么样',
        '但这假设我觉得': '但这假设我觉得',
        '他真的低性吗': '他真的低性吗',
        '他真的不可能吗': '他真的不可能吗',
        '在这个里面的边界是什么呢': '在这个里面的边界是什么呢',
        '比如有的人也会去AGI一个店': '比如有的人也会去 AGI 一个点',
        '对吧': '对吧',
        '对就说你可能是这一帮': '对就说你可能是这一帮',
        '零零年前后的这帮': '零零年前后的这帮',
        '优秀的创始人里面': '优秀的创始人里面',
        '大家认为技术背景': '大家认为技术背景',
        '没有那么过硬的': '没有那么过硬的',
        '就说既不是一个教授': '就说既不是一个教授',
        '也不是一个什么citation很高': '也不是一个什么 citation 很高',
        '对吧也不是什么Badest Petper': '对吧也不是什么 best paper',
        '或者这': '或者这',
        '这件事情肯定是有文凯的': '这件事情肯定是有门槛的',
        '那咱们要尊重科学本身': '那咱们要尊重科学本身',
        '好一方面': '好一方面',
        '我们看到很多很优秀的创始': '我们看到很多很优秀的创始人',
        '那真的是靠自己迅速': '那真的是靠自己迅速',
        '成为了某一个领域的专家': '成为了某一个领域的专家',
        '然后带着团队': '然后带着团队',
        '做得很好': '做得很好',
        '那好那发育和学习这件事情': '那好那发育和学习这件事情',
        '这个边界会发展呢': '这个边界会发展呢',
        'New Motor Interface': 'Neural Interface',
        '这个东西': '这个东西',
        '虽然之前有这个名字': '虽然之前有这个名字',
        '可能在学术权正式的出现': '可能在学术界正式的出现',
        '还不足一年的时间': '还不足一年的时间',
        '那在这个运营就意味着没有学生': '那在这个领域就意味着没有学生',
        '也没有教授': '也没有教授',
        '对就好像我记得当时': '对就好像我记得当时',
        '赛尔实验室': 'SAIL 实验室',
        '我们哈统达赛尔实验室': '我们斯坦福 SAIL 实验室',
        '当时': '当时',
        '我特别好的老师': '我特别好的老师',
        'Cian Cian是他教的': '吴恩达教的',
        '然后包括宝宋的时候': '然后包括保研的时候',
        '他也写了推荐信': '他也写了推荐信',
        '他们之前的自然员处理': '他们之前的自然语言处理',
        '就是类似于中国的皇补军校这样': '就是类似于中国的黄埔军校这样',
        '再要要批诀': '再要一批人',
        '但我听过一个非常Hambel的说法': '但我听过一个非常 Humble 的说法',
        '就是在Chad DVD出来之后': '就是在 ChatGPT 出来之后',
        '我们要清空': '我们要清零',
        '如果你这个赛道': '如果你这个赛道',
        '它的结局为零': '它的结局为零',
        '我的意思是': '我的意思是',
        '它被重启了': '它被重启了',
        '以某种方式重启了': '以某种方式重启了',
        '结局为零': '结局为零',
        '就意味着这个领域没有profession': '就意味着这个领域没有 profession',
        '没有权威': '没有权威',
        '对也没有刚才提的situation的bass paper': '对也没有刚才提的 seminal paper',
        '但也意味着有可能不到一年的时间': '但也意味着有可能不到一年的时间',
        '我们也登陵': '我们也能登顶',
        '因为我不觉得你在世俗上': '因为我不觉得你在世俗上',
        '然后按照别人的平台表着': '然后按照别人的平台表',
        '然后你拿到一个分析说非常靠前的东西': '然后你拿到一个排名说非常靠前的东西',
        '就意味着什么': '就意味着什么',
        '然后同样的': '然后同样的',
        '在一个可能你要开创的权权赛道里面': '在一个可能你要开创的全新赛道里面',
        '我觉得': '我觉得',
        '世俗一上想定义的everything': '世俗意义上想定义的 everything',
        '我们也都可以有': '我们也都可以有',
        '对但也不觉得拿到了': '对但也不觉得拿到了',
        '那些东西一定意味着什么': '那些东西一定意味着什么',
        '刚才你说有一个东西': '刚才你说有一个东西',
        '我特别有功名': '我特别有共鸣',
        '就是说其实当年Transformers的那帮人': '就是说其实当年 Transformers 的那帮人',
        '是被主流赛道所排挤的那帮人': '是被主流赛道所排挤的那帮人',
        '就说他们被主流赛道排挤': '就说他们被主流赛道排挤',
        '所以他们才没有去做那些主流认为': '所以他们才没有去做那些主流认为',
        '他们应该做的事情': '他们应该做的事情',
        '反而他们今天开创了一个新的路线': '反而他们今天开创了一个新的路线',
        '就像我们今天在面对一些': '就像我们今天在面对一些',
        '创业者的时候': '创业者的时候',
        '我们也发现': '我们也发现',
        '就是说为什么都是一帮非常厉害的年轻人': '就是说为什么都是一帮非常厉害的年轻人',
        '他是95后': '他是 95 后',
        '甚至是00后': '甚至是 00 后',
        '其实底层的原因就是': '其实底层的原因就是',
        '因为当年他们没有的那些东西': '因为当年他们没有的那些东西',
        '恰恰是他们今天最稀缺的东西': '恰恰是他们今天最稀缺的东西',
        '对是的': '对是的',
        '对吧这就是像': '对吧这就是像',
        '报道经理里面有句话叫': '道德经里面有句话叫',
        '有之以为利': '有之以为利',
        '无之以为用': '无之以为用',
        '他就是因为他是空的': '他就是因为他是空的',
        '才能装东西': '才能装东西',
        '没错': '没错',
        '在内心把它清空是更难的': '在内心把它清空是更难的',
        '我觉得这个东西': '我觉得这个东西',
        '确实是给了新的95年到2000年的': '确实是给了新的 95 年到 2000 年的',
        '这一代创业者': '这一代创业者',
        '我们从在身上看到那种': '我们从在身上看到那种',
        '非常非常非常的不一样的东西': '非常非常非常的不一样的东西',
        '而且': '而且',
        '就是我们交流下来': '就是我们交流下来',
        '就是这种创业者的这种沉思度': '就是这种创业者的这种成熟度',
        '耐心': '耐心',
        '决心': '决心',
        '还真的是非常非常不一样': '还真的是非常非常不一样',
        '因为你一路走过来': '因为你一路走过来',
        '对吧那比如像在生活中': '对吧那比如像在生活中',
        '也会有很多在你很suffer的地方': '也会有很多在你很 suffer 的地方',
        '你是怎么去保持这种生命力的呢': '你是怎么去保持这种生命力的呢',
        '我后来意识到说': '我后来意识到说',
        '我们做的这个事情': '我们做的这个事情',
        '本质是在极致的放大': '本质是在极致的放大',
        '人对生命的感受和体验': '人对生命的感受和体验',
        '对所以': '对所以',
        '生活中': '生活中',
        '我觉得': '我觉得',
        '不管是personal': '不管是 personal',
        '还是说在组织的维度上': '还是说在组织的维度上',
        '你都会遇到': '你都会遇到',
        '可能一些问题': '可能一些问题',
        '但是今天这个问题对我而言': '但是今天这个问题对我而言',
        '它构成了起伏的一部分': '它构成了起伏的一部分',
        '甚至有的时候': '甚至有的时候',
        '咱们好这个起伏大一些': '咱们好这个起伏大一些',
        '你会run something': '你会 run something',
        '有些东西是你必须要交的学费': '有些东西是你必须要交的学费',
        '还有一些东西': '还有一些东西',
        '它可能不一定算学费': '它可能不一定算学费',
        '它可能本身是它精彩的一部分': '它可能本身是它精彩的一部分',
        '那不管它是不是学费': '那不管它是不是学费',
        '因为这是个后宴': '因为这是个后验',
        '在当下你的感受是真实': '在当下你的感受是真实的',
        '对吧': '对吧',
        'suffer是真实': 'suffer 是真实',
        'suffer非常真实': 'suffer 非常真实',
        '痛苦是真实的': '痛苦是真实的',
        '那你怎么recover呢': '那你怎么 recover 呢',
        '说实话': '说实话',
        '直面谈': '直面惨淡',
        '对对': '对对',
        'OK非常暴力': 'OK 非常暴力',
        '被自己也很暴力': '对自己也很暴力',
        '就是咱们见面的时候': '就是咱们见面的时候',
        '那个时候': '那个时候',
        '可能你比现在看起来更智能一些': '可能你比现在看起来更稚嫩一些',
        '对吧因为绿洲也一直以来讲': '对吧因为绿洲也一直以来讲',
        '参战生命力': '生命力',
        '我想吃这个东西': '我想做这个东西',
        '特别是当时': '特别是当时',
        '可能遇到各种各样的挑战': '可能遇到各种各样的挑战',
        '对吧但我觉得你身上的生命力': '对吧但我觉得你身上的生命力',
        '在我们来看是在变强的': '在我们来看是在变强的',
        '就像对你而言': '就像对你而言',
        '你怎么理解生命力': '你怎么理解生命力',
        '你觉得生命力是什么': '你觉得生命力是什么',
        '然后你去保护你的生命力的方法有什么': '然后你去保护你的生命力的方法有什么',
        '我有句话': '我有句话',
        '我觉得可能表达我的一个感受': '我觉得可能表达我的一个感受',
        '就是生命力就是life in gaming': '就是生命力就是 life in gaming',
        'life in gaming': 'life in gaming',
        '对and eventually': '对 and eventually',
        '在过程中': '在过程中',
        '我们have fun': '我们 have fun',
        'inventually': 'eventually',
        'game changer': 'game changer',
        'OK这是一个很酷的结尾': 'OK 这是一个很酷的结尾',
        '那你现在如果给当年刚开始创业了自己': '那你现在如果给当年刚开始创业了自己',
        '也就一年前了自己': '也就一年前了自己',
        '对吧给他一个建议的话': '对吧给他一个建议的话',
        '你会给他什么': '你会给他什么',
        'follow your calling': 'follow your calling',
        'OK但人会因为什么原因': 'OK 但人会因为什么原因',
        '没有follow自己的calling': '没有 follow 自己的 calling',
        '就是我今天回头想': '就是我今天回头想',
        '就是因为有一个问题': '就是因为有一个问题',
        '叫如果再来': '叫如果再来一次',
        '是哪些地方你可能想去改变': '是哪些地方你可能想去改变',
        '对吧我可能觉得我不需要再来一次': '对吧我可能觉得我不需要再来一次',
        '就是我感觉过去七年的': '就是我感觉过去七年的',
        '每一个时间段里面': '每一个时间段里面',
        '我都做到了极致': '我都做到了极致',
        '就做到极致的点': '就做到极致的点',
        '不是说你不可能更好了': '不是说你不可能更好了',
        '而是说follow your heart': '而是说 follow your heart',
        'follow your calling': 'follow your calling',
        '你的每一个decision都是这么完成的': '你的每一个 decision 都是这么完成的',
        '对你没有违背过它': '对你没有违背过它',
        '你没有违背你的calling': '你没有违背你的 calling',
        '去overfitting一些局务罪优': '去 overfitting 一些局部最优',
        '对你从头到尾所有的决策': '对你从头到尾所有的决策',
        '来自于你的calling': '来自于你的 calling',
        '对所以最后面临同样的问题': '对所以最后面临同样的问题',
        '你就问': '你就问',
        '就是这个游戏': '就是这个游戏',
        '对吧必服的': '对吧必服的',
        '或者说你自己的这个决策': '或者说你自己的这个决策',
        '要离开服务器的那一天': '要离开服务器的那一天',
        '对你会不会觉得某一个': '对你会不会觉得某一个',
        '时刻你想再来一遍': '时刻你想再来一遍',
        '如果能像今天一样说': '如果能像今天一样说',
        'OK我不需要': 'OK 我不需要',
        '对因为每一个决策都是follow my calling': '对因为每一个决策都是 follow my calling',
        '嗯就我觉得这个': '嗯就我觉得这个',
        '我不知道最后': '我不知道最后',
        '大家去看到你': '大家去看到你',
        '或者听到今天的播客': '或者听到今天的播客',
        '这是什么感受': '这是什么感受',
        '但是我今天跟你在去': '但是我今天跟你在去',
        '交流的过程里面': '交流的过程里面',
        '我是能感受到': '我是能感受到',
        '我是能感受到那种': '我是能感受到那种',
        '蓬勃的声明力': '蓬勃的生命力',
        '我觉得很多问题': '我觉得很多问题',
        '是大佬思考出来的': '是大脑思考出来的',
        '就像投资一样': '就像投资一样',
        '如果这个东西没有显化': '如果这个东西没有显化',
        '是不是太早了': '是不是太早了',
        '如果它显化了': '如果它显化了',
        '是不是太贵了': '是不是太贵了',
        '这些问题': '这些问题',
        '其实是没有答案': '其实是没有答案',
        '大部分的答案': '大部分的答案',
        '只是因为我们这个': '只是因为我们这个',
        '二元的大佬': '二元的大脑',
        '在寻求一些安全感': '在寻求一些安全感',
        '嗯但是': '嗯但是',
        '体感是真实': '体感是真实',
        '这个体感也很有意思': '这个体感也很有意思',
        '这个体感': '这个体感',
        '其实就是去感受那个体': '其实就是去感受那个体',
        '感受了体就有体感': '感受了体就有体感',
        '所以有的时候你只有在场': '所以有的时候你只有在场',
        '你才有体感': '你才有体感',
        '对你才感受到的体': '对你才感受到的体',
        '对特别喜欢在场这个词': '对特别喜欢在场这个词',
        '这个词太妙': '这个词太妙',
        'gaming的本质也是在场': 'gaming 的本质也是在场',
        '然后最后你就选择了': '然后最后你就选择了',
        '你跟谁在场': '你跟谁在场',
        '对你在什么场': '对你在什么场',
        '对吧然后你就会打出完全不同的': '对吧然后你就会打出完全不同的',
        '对招式': '对招式',
        '对': '对',
        '就像我们这个': '就像我们这个',
        '这个播客也是一样': '这个播客也是一样',
        '你在场去录': '你在场去录',
        '跟我们打个电话录': '跟我们打个电话录',
        '不一样': '不一样',
        '感受是不一样': '感受是不一样',
        '因为还有的时候': '因为还有的时候',
        '会激发出了很多东西': '会激发出了很多东西',
        '这我就就是在场的魅力了': '这我觉得就是在场的魅力了',
        '对这也是生命': '对这也是生命',
        '就我们作为个多摩泰大模型': '就我们作为个多模态大模型',
        '然后当你感受到那种生命力的时候': '然后当你感受到那种生命力的时候',
        '去说的问题': '去说的问题',
        '你会觉得不是问题': '你会觉得不是问题',
        '就是希望那个时候': '就是希望那个时候',
        '你能做到': '你能做到',
        '性知所至': '兴之所至',
        '性敬而归': '兴尽而归',
        '对': '对',
    },
}


def detect_domain(text, title=''):
    """检测文本所属领域，返回领域标签列表

    策略：基于关键词命中次数判断领域
    """
    scores = {}
    combined = title + '\n' + text[:2000]  # 只看前 2000 字符判断

    for domain, terms in DOMAIN_TERMS.items():
        score = 0
        for wrong, right in terms.items():
            if right in combined:
                score += 1
            if wrong in combined and wrong != right:
                score += 2  # 错误形式命中说明确实是这个领域
        if score >= 3:
            scores[domain] = score

    # 按分数降序返回
    return [d for d, _ in sorted(scores.items(), key=lambda x: -x[1])]


def get_domain_correction_dict(domains=None):
    """获取指定领域的校正字典（合并去重）

    Args:
        domains: 领域标签列表，如 ['neural_interface', 'ai_llm']
                 如果为 None，返回所有领域

    Returns:
        {错误形式: 正确形式} 字典
    """
    result = {}
    if domains is None:
        domains = list(DOMAIN_TERMS.keys())

    for domain in domains:
        if domain in DOMAIN_TERMS:
            result.update(DOMAIN_TERMS[domain])

    return result


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

    # 方案 A2：领域术语校正
    domains = detect_domain(text_a, title)
    if domains:
        domain_dict = get_domain_correction_dict(domains)
        text_a2 = text_a
        count_a2 = 0
        # 按错误词长度降序匹配
        sorted_terms = sorted(
            [(w, r) for w, r in domain_dict.items() if w != r],
            key=lambda x: -len(x[0])
        )
        for wrong, right in sorted_terms:
            if wrong in text_a2:
                occurrences = text_a2.count(wrong)
                text_a2 = text_a2.replace(wrong, right)
                count_a2 += occurrences
        if count_a2 > 0:
            details.append(('领域术语校正', f'领域: {", ".join(domains)}', count_a2))
    else:
        text_a2 = text_a
        count_a2 = 0

    # 方案 B：专有名词校正
    text_b, count_b = correct_keywords(text_a2, keywords)
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

    total = count_a + count_a2 + count_b + count_c + count_d
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
    """给片段分配说话者（基于关键段锚定 + 称呼检测 + 问答模式）

    核心思路：
    1. 识别明确的说话者信号作为锚点：
       - 嘉宾自我介绍（"大家好,我是XXX"）→ 嘉宾 XXX
       - 主持人介绍嘉宾（"今天我们...请到了...XXX"）→ 主持人
       - 主持人开场（"大家好,这是XXX播客"）→ 主持人
    2. 称呼检测：提到对方名字 → 当前说话者是另一方
       - 这是最高优先级的信号，因为称呼是明确的语义信号
    3. 基于锚点推断其他段落：问答模式 + 间隔 + 长度对比

    返回: segments 列表，每个增加 speaker 字段
    """
    if not segments:
        return segments

    if not speakers:
        speakers = [
            {'name': 'SPEAKER_01', 'role': '主持人'},
            {'name': 'SPEAKER_02', 'role': '嘉宾'},
        ]

    speaker_names = [s['name'] for s in speakers]
    num_speakers = len(speakers)

    # ============================================================
    # 第一步：识别明确的说话者锚点
    # ============================================================
    # 锚点格式: {segment_index: speaker_index}
    anchors = {}

    for i, seg in enumerate(segments):
        text = seg.get('text', '')

        # 锚点1: 嘉宾自我介绍 "大家好,我是XXX" 或 "我是XXX,这是XXX"
        for j, name in enumerate(speaker_names):
            if '大家好' in text and (f'我是{name}' in text or f'我叫{name}' in text):
                anchors[i] = j
                break

        # 锚点2: 主持人介绍嘉宾 "今天我们...请到了...XXX"
        # 注意：这一段提到嘉宾名字，但不是自我介绍，所以说话者是主持人
        if i not in anchors:
            if any(kw in text for kw in ['今天我们', '请到了', '荣幸', '老朋友']):
                is_self_intro = any(f'我是{name}' in text or f'我叫{name}' in text for name in speaker_names)
                if not is_self_intro:
                    # 找到被介绍的嘉宾
                    for j, name in enumerate(speaker_names):
                        if name in text:
                            # 主持人是除了被介绍人之外的人
                            other_indices = [k for k in range(num_speakers) if k != j]
                            if other_indices:
                                anchors[i] = other_indices[0]
                            break

        # 锚点3: 主持人开场 "大家好,这是XXX播客" "大家好,欢迎"
        if i not in anchors and i == 0:
            if re.search(r'大家好.*这是.*播客', text) or re.search(r'大家好.*欢迎', text):
                anchors[i] = 0  # 主持人

    # ============================================================
    # 第二步：基于称呼检测锚定更多段落
    # ============================================================
    # 提到其他说话者的名字 → 当前说话者是另一方
    # 这是最高优先级的语义信号，因为称呼是明确的
    for i, seg in enumerate(segments):
        if i in anchors:
            continue
        text = seg.get('text', '')

        for j, name in enumerate(speaker_names):
            if name in text:
                # 排除自我介绍
                if f'我是{name}' not in text and f'我叫{name}' not in text:
                    other_indices = [k for k in range(num_speakers) if k != j]
                    if other_indices and num_speakers == 2:
                        anchors[i] = other_indices[0]
                        break

    # ============================================================
    # 第三步：基于锚点推断其他段落
    # ============================================================
    if not anchors:
        anchors[0] = 0  # 默认第一段是主持人

    # 找到最早的锚点
    first_anchor_idx = min(anchors.keys())

    # 填充锚点之前的段落（都设为第一个锚点的说话者）
    for i in range(first_anchor_idx):
        anchors[i] = anchors[first_anchor_idx]

    # 基于锚点推断后续段落
    current_speaker_idx = anchors[first_anchor_idx]
    for i in range(first_anchor_idx + 1, len(segments)):
        if i in anchors:
            # 已知锚点，直接使用
            current_speaker_idx = anchors[i]
        else:
            # 推断
            prev_seg = segments[i-1]
            curr_seg = segments[i]
            gap = curr_seg['start'] - prev_seg['end']
            curr_len = len(curr_seg.get('text', ''))
            prev_len = len(prev_seg.get('text', ''))
            curr_text = curr_seg.get('text', '')
            prev_text = prev_seg.get('text', '')

            should_switch = False

            # 规则1: 间隔超过 4 秒，很可能换人
            if gap > 4.0:
                should_switch = True

            # 规则2: 问答模式
            # 上一段以问号结尾（提问），这一段较长 → 切换（回答）
            if prev_text.rstrip().endswith(('?', '？')) and curr_len > 30:
                should_switch = True
            # 上一段很短（提问），这一段很长（回答）→ 切换
            elif prev_len < 30 and curr_len > 80:
                should_switch = True
            # 上一段很长（回答），这一段很短（提问）→ 切换
            elif prev_len > 80 and curr_len < 30:
                should_switch = True

            if should_switch:
                current_speaker_idx = (current_speaker_idx + 1) % num_speakers

            anchors[i] = current_speaker_idx

    # 设置 speaker 字段
    for i, seg in enumerate(segments):
        seg['speaker'] = speakers[anchors[i]]['name']

    return segments


def split_long_segments(segments, max_duration=300, max_chars=600, speaker_names=None):
    """切分段落，根据问号/句号/自我介绍进行切分

    切分规则：
    1. 说话者切换信号（"大家好""我是XXX"）：总是切分，不管段落长度
    2. 超长段落（> max_duration 或 > max_chars）：按问号/句号切分

    返回新的 segments 列表（保留原 speaker 字段，但后续可重新分配）
    """
    if speaker_names is None:
        speaker_names = []

    result = []
    for seg in segments:
        duration = seg.get('end', 0) - seg.get('start', 0)
        text = seg.get('text', '').strip()
        speaker = seg.get('speaker', '')

        if not text:
            result.append(seg)
            continue

        # 第零轮：检测说话者切换信号（"大家好""我是XXX"）并切分
        # 这是最重要的切分点，因为同一说话者不会说"大家好,我是XXX"
        # 总是切分，不管段落长度
        switch_chunks = [text]
        if speaker_names:
            patterns = ['大家好']
            for name in speaker_names:
                patterns.append(f'我是{name}')
                patterns.append(f'我叫{name}')

            for pattern in patterns:
                new_chunks = []
                for chunk in switch_chunks:
                    # 在模式前切分，保留模式在后面
                    parts = re.split(rf'(?={pattern})', chunk)
                    new_chunks.extend([p for p in parts if p.strip()])
                switch_chunks = new_chunks

        # 如果切分后只有一段，且段落不长，直接保留
        if len(switch_chunks) <= 1 and duration <= max_duration and len(text) <= max_chars:
            result.append(seg)
            continue

        # 第一轮：按问号切分（保留问号在前一段末尾）
        chunks = []
        for chunk in switch_chunks:
            current = ''
            for part in re.split(r'(？|\?)', chunk):
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
            # 但不要合并"大家好""我是XXX"开头的片段到前一段
            is_switch_start = any(chunk.startswith(p) for p in ['大家好', '我是', '我叫'])
            if merged and len(chunk) < 30 and not is_switch_start:
                merged[-1] += chunk
            elif merged and merged[-1].endswith('大家好,') and is_switch_start:
                # 特殊情况：前一段以"大家好,"结尾，当前段以"我是XXX"开头
                # 把"大家好,"从前一段移到当前段
                merged[-1] = merged[-1][:-4]  # 去掉"大家好,"
                if merged[-1]:  # 如果前一段还有内容
                    pass
                else:
                    merged.pop()  # 前一段为空，删除
                chunk = '大家好,' + chunk
                merged.append(chunk)
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
        # 1. 切分超长段落（检测"大家好""我是XXX"等说话者切换信号）
        # 2. 清除原 speaker 字段，根据问答模式重新分配
        print(f"⚠️  检测到原说话者标签不可靠（含 SPEAKER_XX 或超长段落），将忽略原标签重新分配")
        speaker_name_list = [s['name'] for s in speakers]
        segments = split_long_segments(segments, max_duration=300, max_chars=600, speaker_names=speaker_name_list)
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
