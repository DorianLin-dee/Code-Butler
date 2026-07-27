#!/usr/bin/env python3
"""
对话内容提炼工具（Dialogue Content Extractor）

从播客/访谈/讲座等对话转录文本中提取核心观点，
生成思维导图、标注来源、输出精美HTML阅读页。

功能：
1. 解析带说话者的转录稿（支持多种格式）
2. 按主题模块拆分内容（启发式：基于说话者切换、话题关键词）
3. 提取核心观点 + 金句采集
4. 生成 Mermaid 思维导图
5. 生成 Tailwind 风格 HTML 阅读页

用法：
    from dialogue_extractor import extract_dialogue_content
    result = extract_dialogue_content('transcript.txt', title='播客标题')

    # 或命令行
    python3 dialogue_extractor.py transcript.txt --title "对谈李想"
"""

import re
import sys
import json
from pathlib import Path
from collections import Counter, defaultdict


# ============================================================
# 五色分区系统（与 learning-with-ai 设计系统一致）
# ============================================================
MODULE_COLORS = [
    {'name': '基础概念', 'main': 'indigo', 'bg': 'bg-indigo-50', 'text': 'text-indigo-600', 'border': 'border-indigo-200'},
    {'name': '方法框架', 'main': 'teal', 'bg': 'bg-teal-50', 'text': 'text-teal-600', 'border': 'border-teal-200'},
    {'name': '技术实践', 'main': 'amber', 'bg': 'bg-amber-50', 'text': 'text-amber-600', 'border': 'border-amber-200'},
    {'name': '应用案例', 'main': 'sky', 'bg': 'bg-sky-50', 'text': 'text-sky-600', 'border': 'border-sky-200'},
    {'name': '核心洞察', 'main': 'rose', 'bg': 'bg-rose-50', 'text': 'text-rose-600', 'border': 'border-rose-200'},
]

# 观点标签语义约定
TAG_STYLES = {
    '核心': 'bg-rose-50 text-rose-600',
    '关键': 'bg-rose-50 text-rose-600',
    '金句': 'bg-teal-50 text-teal-600',
    '引用': 'bg-teal-50 text-teal-600',
    '框架': 'bg-indigo-50 text-indigo-600',
    '方法论': 'bg-indigo-50 text-indigo-600',
    '案例': 'bg-amber-50 text-amber-600',
    '实践': 'bg-amber-50 text-amber-600',
}

# 金句候选触发词（宽松匹配，找到包含这些词的句子作为金句候选）
QUOTE_TRIGGER_WORDS = [
    '本质', '核心', '关键', '根本', '最重要', '最关键',
    '我觉得', '我认为', '我坚信', '我一直认为', '我的观点是',
    '其实', '事实上', '实际上', '本质上', '从根本上讲',
    '真正的', '不是...而是', '与其...不如',
    '千万不要', '一定要', '必须', '应该',
    '最好的方式', '最好的办法', '一个好的',
    '如果你想', '要想...就要', '秘诀', '秘密',
    '感悟', '体会', '经验', '教训', '总结',
    '第一', '第二', '第三', '最重要的是',
]

# 更精准的金句模式（用于高质量金句）
QUOTE_PATTERNS = [
    r'我觉得.{2,30}的本质是',
    r'核心是.{2,30}',
    r'最关键的是.{2,30}',
    r'最重要的是.{2,30}',
    r'本质上.{2,30}',
    r'我的观点是.{2,30}',
    r'我一直认为.{2,30}',
    r'我坚信.{2,30}',
    r'一个好的.{2,15}应该',
    r'.{2,15}不是.{2,30}，而是',
    r'真正的.{2,15}是',
    r'.{2,15}的核心在于',
    r'如果你想.{2,20}，就要',
    r'千万不要.{2,20}，要',
    r'与其.{2,15}，不如',
    r'最好的方式.{2,15}是',
]

# 主题关键词分类（用于自动归类模块）
TOPIC_KEYWORDS = {
    '基础概念': ['什么是', '定义', '概念', '原理', '底层逻辑', '首先要理解', '我们先看', '背景'],
    '方法框架': ['方法', '方法论', '框架', '步骤', '流程', '怎么做到', '如何做', '技巧', '策略', '原则', '规律', '方式', '路径'],
    '技术实践': ['技术', '实践', '具体怎么做', '操作', '执行', '落地', '工具', '产品', '研发', '工程', '做出来', '实现'],
    '应用案例': ['案例', '例子', '比如', '举个', '当时', '我们做了', '经历', '故事', '经验分享', '举个例子'],
    '核心洞察': ['我觉得', '我认为', '本质', '核心', '关键', '根本', '洞察', '感悟', '反思', '总结', '最重要', '最关键'],
}


# ============================================================
# 第一步：解析转录文件
# ============================================================

def parse_dialogue_transcript(text):
    """解析对话转录文本，提取段落列表

    支持格式：
    - [时间 - 时间] [说话者]
      文本内容
    - [时间 - 时间] 说话者: 文本
    - 说话者: 文本

    返回列表: [{
        'start': '00:01:23',
        'end': '00:02:34',
        'speaker': '罗永浩',
        'text': '...',
        'length': 123,
    }]
    """
    paragraphs = []
    lines = text.strip().split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # 格式1: [00:00:00 - 00:00:49] [罗永浩]
        m = re.match(r'^\[(\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})\]\s*\[([^\]]+)\]', line)
        if m:
            start = m.group(1)
            end = m.group(2)
            speaker = m.group(3).strip()
            # 文本可能在同一行或下一行
            text_content = line[m.end():].strip()
            if not text_content and i + 1 < len(lines):
                i += 1
                text_content = lines[i].strip()
            paragraphs.append({
                'start': start,
                'end': end,
                'speaker': speaker,
                'text': text_content,
                'length': len(text_content),
            })
            i += 1
            continue

        # 格式2: [时间 - 时间] 说话者: 文本
        m = re.match(r'^\[(\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})\]\s*([^:：]+)[:：]\s*(.+)', line)
        if m:
            paragraphs.append({
                'start': m.group(1),
                'end': m.group(2),
                'speaker': m.group(3).strip(),
                'text': m.group(4).strip(),
                'length': len(m.group(4).strip()),
            })
            i += 1
            continue

        # 格式3: 说话者: 文本
        m = re.match(r'^([^\[][^:：]{1,10})[:：]\s*(.+)', line)
        if m and len(m.group(1)) <= 10:
            paragraphs.append({
                'start': '',
                'end': '',
                'speaker': m.group(1).strip(),
                'text': m.group(2).strip(),
                'length': len(m.group(2).strip()),
            })
            i += 1
            continue

        # 普通文本行（如果是上一段的延续）
        if paragraphs and line and not line.startswith('[') and not re.match(r'^\d{2}:\d{2}', line):
            paragraphs[-1]['text'] += '，' + line
            paragraphs[-1]['length'] += len(line) + 1
            i += 1
            continue

        i += 1

    return paragraphs


# ============================================================
# 第二步：识别说话者角色
# ============================================================

def identify_roles(paragraphs):
    """识别说话者角色（主持人/嘉宾）

    基于启发式：
    - 说话最多的通常是嘉宾
    - 提问多的（问号多）通常是主持人
    - 第一段说话的通常是主持人
    """
    if not paragraphs:
        return {}

    speaker_stats = defaultdict(lambda: {'lines': 0, 'chars': 0, 'questions': 0})
    for p in paragraphs:
        spk = p['speaker']
        speaker_stats[spk]['lines'] += 1
        speaker_stats[spk]['chars'] += p['length']
        speaker_stats[spk]['questions'] += p['text'].count('?') + p['text'].count('？')

    speakers = list(speaker_stats.keys())
    roles = {}

    if len(speakers) == 1:
        roles[speakers[0]] = '主讲人'
    elif len(speakers) >= 2:
        # 主持人：问号多 / 话少
        # 嘉宾：话多
        sorted_by_chars = sorted(speakers, key=lambda s: -speaker_stats[s]['chars'])
        sorted_by_questions = sorted(speakers, key=lambda s: -speaker_stats[s]['questions'])

        # 第一个说话的是主持人
        first_speaker = paragraphs[0]['speaker']

        # 话最少且问号最多的是主持人
        host_candidates = set()
        if speaker_stats[sorted_by_chars[-1]]['chars'] < speaker_stats[sorted_by_chars[0]]['chars'] * 0.6:
            host_candidates.add(sorted_by_chars[-1])
        if sorted_by_questions:
            host_candidates.add(sorted_by_questions[0])

        host = first_speaker if first_speaker in host_candidates else sorted_by_questions[0]
        roles[host] = '主持人'

        for spk in speakers:
            if spk not in roles:
                roles[spk] = '嘉宾'

    return roles


# ============================================================
# 第三步：提取核心观点 + 金句
# ============================================================

def _split_sentences(text):
    """智能拆分句子（处理中文标点）"""
    sentences = re.split(r'[。！？.!?；;]', text)
    return [s.strip() for s in sentences if s.strip()]


def _find_key_sentence(text):
    """找到段落中最核心的句子（作为观点摘要）

    策略：
    1. 含核心词（本质/核心/关键/我觉得/我认为）的优先
    2. 第一句优先（很多人习惯开门见山）
    3. 长度适中（20-60字）
    """
    sentences = _split_sentences(text)
    if not sentences:
        return text[:50]

    # 评分找最佳句子
    best_sent = sentences[0]
    best_score = 0

    for i, sent in enumerate(sentences):
        score = 0

        # 核心词加分
        core_words = ['本质', '核心', '关键', '根本', '最重要', '最关键',
                      '我觉得', '我认为', '我坚信', '我的观点',
                      '其实', '事实上', '实际上', '总结一下']
        for w in core_words:
            if w in sent:
                score += 3
                break

        # 数字/数据加分
        if re.search(r'\d+%|\d+倍|\d+个亿|\d+万', sent):
            score += 1

        # 位置：第一句和最后一句加分
        if i == 0:
            score += 2
        elif i == len(sentences) - 1:
            score += 1

        # 长度适中加分（20-80字）
        if 20 <= len(sent) <= 80:
            score += 1

        if score > best_score:
            best_score = score
            best_sent = sent

    return best_sent


def _detect_quotes(text):
    """检测金句（宽松模式 + 精准模式结合）

    返回：(is_quote, quote_text)
    """
    sentences = _split_sentences(text)
    if not sentences:
        return False, ''

    best_quote = ''
    best_score = 0

    for sent in sentences:
        score = 0

        # 触发词检测（宽松）
        trigger_count = sum(1 for w in QUOTE_TRIGGER_WORDS if w in sent)
        score += trigger_count

        # 精准模式检测（高质量）
        for pat in QUOTE_PATTERNS:
            if re.search(pat, sent):
                score += 3
                break

        # 长度合适（15-80字，太短不像金句，太长不像）
        if 15 <= len(sent) <= 80:
            score += 1
        elif len(sent) > 80 or len(sent) < 10:
            score -= 1

        # 有"我"开头更像金句
        if sent.startswith('我'):
            score += 1

        # 是金句（分数够高）
        if score >= 2 and len(sent) >= 12:
            if score > best_score:
                best_score = score
                best_quote = sent.strip()

    return best_quote != '', best_quote


def extract_key_points(paragraphs, min_length=50):
    """提取核心观点（启发式：长段落 + 观点性表达）

    评分规则：
    - 长度分：越长越可能是核心观点（嘉宾的长回答）
    - 核心词加分：含"本质/核心/关键/我觉得"等
    - 模式分：包含金句模式的加分
    - 位置分：开头结尾的内容更重要
    - 嘉宾说的比主持人说的分量重
    """
    points = []
    total_paragraphs = len(paragraphs)

    # 先识别谁是主持人/嘉宾，嘉宾的话权重更高
    roles = identify_roles(paragraphs)

    for idx, p in enumerate(paragraphs):
        score = 0
        tags = []
        text = p['text']

        # 长度分
        if p['length'] > 500:
            score += 4
        elif p['length'] > 300:
            score += 3
        elif p['length'] > 150:
            score += 2
        elif p['length'] > 80:
            score += 1

        # 嘉宾/主持人权重：嘉宾的话更可能是核心观点
        role = roles.get(p['speaker'], '')
        if role == '嘉宾':
            score += 2
        elif role == '主持人':
            score -= 1  # 主持人的话通常是提问，不算核心观点

        # 核心词检测
        core_words = ['核心', '关键', '本质', '根本', '最重要', '最关键',
                      '我觉得', '我认为', '我坚信', '其实', '事实上',
                      '总结', '感悟', '经验', '教训']
        core_count = sum(1 for w in core_words if w in text)
        if core_count >= 3:
            score += 3
            tags.append('核心')
        elif core_count >= 1:
            score += 2
            tags.append('核心')

        # 方法框架词
        method_words = ['方法', '框架', '步骤', '流程', '策略', '原则', '方式', '路径', '规律']
        method_count = sum(1 for w in method_words if w in text)
        if method_count >= 2:
            score += 2
            tags.append('框架')
        elif method_count >= 1:
            score += 1
            tags.append('框架')

        # 案例/故事词
        case_words = ['比如', '例子', '案例', '当时', '经历', '故事', '举个']
        case_count = sum(1 for w in case_words if w in text)
        if case_count >= 2:
            score += 2
            tags.append('案例')
        elif case_count >= 1:
            score += 1
            tags.append('案例')

        # 含数字/具体数据的
        if re.search(r'\d+%|\d+倍|\d+个亿|\d+万|\d+千|\d+人', text):
            score += 1
            tags.append('数据')

        # 位置分：中间部分（20%-80%）是主要内容区
        position = idx / total_paragraphs if total_paragraphs > 0 else 0.5
        if 0.2 <= position <= 0.8:
            score += 1

        # 金句检测
        is_quote, quote_text = _detect_quotes(text)
        if is_quote:
            score += 2
            tags.append('金句')

        if score >= 3 and p['length'] >= min_length:
            # 生成观点摘要（找核心句）
            summary = _find_key_sentence(text)

            # 归类到主题模块
            module = classify_to_module(text, idx, total_paragraphs)

            points.append({
                'id': len(points) + 1,
                'module': module,
                'summary': summary[:60] + ('...' if len(summary) > 60 else ''),
                'full_text': text,
                'speaker': p['speaker'],
                'start': p['start'],
                'end': p['end'],
                'score': score,
                'tags': list(set(tags)),
                'is_quote': is_quote,
                'quote_text': quote_text,
                'index': idx,
            })

    # 按分数排序
    points.sort(key=lambda x: -x['score'])
    return points


def classify_to_module(text, idx, total):
    """将观点归类到主题模块（启发式）

    基于关键词匹配 + 位置推断
    """
    scores = {m: 0 for m in TOPIC_KEYWORDS.keys()}

    for module, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[module] += 1

    # 位置推断：
    # - 前 20% 通常是基础概念/背景介绍
    # - 中间是方法/实践/案例
    # - 后 20% 是核心洞察/总结
    position = idx / total if total > 0 else 0.5

    if position < 0.2:
        scores['基础概念'] += 2
    elif position > 0.8:
        scores['核心洞察'] += 2
    elif 0.3 <= position <= 0.7:
        scores['方法框架'] += 1
        scores['技术实践'] += 1

    # 返回分数最高的模块
    best_module = max(scores, key=scores.get)
    return best_module if scores[best_module] > 0 else '核心洞察'


def collect_quotes(points, max_quotes=10):
    """从观点中采集金句"""
    quotes = [p for p in points if p['is_quote'] and p['quote_text']]
    quotes.sort(key=lambda x: -x['score'])
    return quotes[:max_quotes]


# ============================================================
# 第四步：生成思维导图（Mermaid mindmap）
# ============================================================

def generate_mindmap(title, points, modules):
    """生成 Mermaid 思维导图"""
    lines = ['```mermaid', 'mindmap', f'  root(({title}))']

    for i, module in enumerate(modules):
        color_class = f'm{i+1}'
        lines.append(f'    {module}:::{color_class}')

        module_points = [p for p in points if p['module'] == module]
        module_points.sort(key=lambda x: -x['score'])

        for p in module_points[:5]:
            summary = p['summary'][:30].replace('"', "'")
            lines.append(f'      {summary}')

    # 添加配色样式
    lines.append('')
    lines.append('    classDef m1 fill:#e0e7ff,stroke:#6366f1,color:#4338ca')
    lines.append('    classDef m2 fill:#ccfbf1,stroke:#14b8a6,color:#0f766e')
    lines.append('    classDef m3 fill:#fef3c7,stroke:#f59e0b,color:#b45309')
    lines.append('    classDef m4 fill:#e0f2fe,stroke:#0ea5e9,color:#0369a1')
    lines.append('    classDef m5 fill:#ffe4e6,stroke:#f43f5e,color:#be123c')
    lines.append('```')

    return '\n'.join(lines)


# ============================================================
# 第五步：生成 HTML 页面
# ============================================================

def generate_html(title, paragraphs, points, modules, quotes, roles, output_file=None):
    """生成精美 HTML 阅读页（Tailwind 风格）

    使用内联样式和 CDN，确保离线也能看（字体用系统字体回退）
    """
    # 统计数据
    total_chars = sum(p['length'] for p in paragraphs)
    total_minutes = 0
    if paragraphs and paragraphs[-1]['end']:
        h, m, s = map(int, paragraphs[-1]['end'].split(':'))
        total_minutes = h * 60 + m + s // 60

    speakers = list(set(p['speaker'] for p in paragraphs))
    num_modules = len(modules)

    # 按模块分组观点
    modules_data = []
    for i, module in enumerate(modules):
        color = MODULE_COLORS[i % len(MODULE_COLORS)]
        module_points = [p for p in points if p['module'] == module]
        module_points.sort(key=lambda x: -x['score'])
        modules_data.append({
            'name': module,
            'color': color,
            'points': module_points[:15],  # 每模块最多 15 个观点
            'count': len(module_points),
        })

    # 生成观点卡片 HTML
    point_cards_html = ''
    for mod_data in modules_data:
        color = mod_data['color']
        point_cards_html += f'''
    <section id="module-{mod_data['name']}" class="py-16">
      <div class="max-w-4xl mx-auto px-6">
        <div class="flex items-end justify-between mb-8">
          <div>
            <span class="inline-block px-3 py-1 text-xs font-medium rounded-full {color['bg']} {color['text']} mb-3">
              模块 {modules_data.index(mod_data) + 1}
            </span>
            <h2 class="text-3xl font-bold text-gray-900" style="font-family: Georgia, 'Noto Serif SC', serif;">
              {mod_data['name']}
            </h2>
          </div>
          <div class="text-right">
            <div class="text-4xl font-bold text-gray-200" style="font-family: Georgia, serif;">
              {mod_data['count']}
            </div>
            <div class="text-xs text-gray-400">个观点</div>
          </div>
        </div>

        <div class="space-y-4">
'''
        for p in mod_data['points']:
            tags_html = ''
            for tag in p['tags'][:3]:
                tag_style = TAG_STYLES.get(tag, 'bg-gray-100 text-gray-600')
                tags_html += f'<span class="inline-block px-2 py-0.5 text-xs rounded {tag_style} mr-1">{tag}</span>'

            source_html = ''
            if p['speaker']:
                role = roles.get(p['speaker'], p['speaker'])
                source_html += f'<span class="text-xs text-gray-500">{p["speaker"]}（{role}）</span>'
            if p['start']:
                source_html += f'<span class="text-xs text-gray-400 mx-2">·</span>'
                source_html += f'<span class="text-xs text-gray-400">{p["start"]}</span>'

            quote_block = ''
            if p['is_quote'] and p['quote_text']:
                quote_block = f'''
            <blockquote class="mt-3 pl-4 border-l-2 {color['border']} italic text-gray-700">
              「{p['quote_text']}」
            </blockquote>
'''

            point_cards_html += f'''
          <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
            <div class="flex items-start justify-between mb-2">
              <h3 class="text-lg font-semibold text-gray-800">
                {p['summary']}
              </h3>
            </div>
            <p class="text-gray-600 text-sm leading-relaxed mb-3">
              {p['full_text'][:200]}{'...' if len(p['full_text']) > 200 else ''}
            </p>
{quote_block}
            <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-50">
              <div>{tags_html}</div>
              <div>{source_html}</div>
            </div>
          </div>
'''

        point_cards_html += '''
        </div>
      </div>
    </section>
'''

    # 生成金句墙 HTML
    quotes_html = ''
    if quotes:
        quotes_html = '''
    <section class="py-16 bg-gradient-to-b from-gray-50 to-white">
      <div class="max-w-4xl mx-auto px-6">
        <div class="text-center mb-12">
          <span class="inline-block px-3 py-1 text-xs font-medium rounded-full bg-teal-50 text-teal-600 mb-3">
            金句墙
          </span>
          <h2 class="text-3xl font-bold text-gray-900" style="font-family: Georgia, 'Noto Serif SC', serif;">
            精彩语录
          </h2>
        </div>
        <div class="grid md:grid-cols-2 gap-4">
'''
        for i, q in enumerate(quotes[:8]):
            color = MODULE_COLORS[i % len(MODULE_COLORS)]
            quotes_html += f'''
          <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div class="text-3xl text-{color['main']}-200 mb-2">"</div>
            <p class="text-gray-700 leading-relaxed mb-4" style="font-family: Georgia, 'Noto Serif SC', serif;">
              {q['quote_text']}
            </p>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500">— {q['speaker']}</span>
              <span class="text-gray-400">{q['start']}</span>
            </div>
          </div>
'''
        quotes_html += '''
        </div>
      </div>
    </section>
'''

    # 快速导航卡片
    nav_cards = ''
    for i, mod_data in enumerate(modules_data):
        color = mod_data['color']
        nav_cards += f'''
        <a href="#module-{mod_data['name']}" class="block">
          <div class="{color['bg']} rounded-xl p-5 hover:scale-105 transition-transform cursor-pointer">
            <div class="text-2xl font-bold {color['text']}" style="font-family: Georgia, serif;">
              {mod_data['count']}
            </div>
            <div class="text-sm font-medium text-gray-700 mt-1">{mod_data['name']}</div>
          </div>
        </a>
'''

    # 完整 HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - 核心观点提炼</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@300;400;500;600&display=swap');
    body {{
      font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    h1, h2, h3, .serif {{
      font-family: 'Noto Serif SC', Georgia, serif;
    }}
    .progress-bar {{
      position: fixed;
      top: 0;
      left: 0;
      height: 2px;
      background: linear-gradient(90deg, #6366f1, #ec4899);
      z-index: 100;
      transition: width 0.1s;
    }}
    .fade-in {{
      opacity: 0;
      transform: translateY(20px);
      transition: opacity 0.6s, transform 0.6s;
    }}
    .fade-in.visible {{
      opacity: 1;
      transform: translateY(0);
    }}
    .back-to-top {{
      position: fixed;
      bottom: 30px;
      right: 30px;
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: white;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      opacity: 0;
      transition: opacity 0.3s;
      z-index: 50;
    }}
    .back-to-top.show {{ opacity: 1; }}
  </style>
</head>
<body class="bg-gray-50 text-gray-800">
  <div class="progress-bar" id="progressBar"></div>

  <!-- Hero 区域 -->
  <header class="bg-gradient-to-br from-indigo-50 via-white to-rose-50 pt-20 pb-16">
    <div class="max-w-4xl mx-auto px-6 text-center">
      <div class="inline-block px-4 py-1.5 bg-white/60 backdrop-blur rounded-full text-sm text-gray-500 mb-6">
        对话内容提炼 · Dialogue Content Extractor
      </div>
      <h1 class="text-4xl md:text-5xl font-bold text-gray-900 mb-4 leading-tight">
        {title}
      </h1>
      <p class="text-gray-500 mb-10 text-lg">
        核心观点提炼 · 思维导图 · 金句采集
      </p>

      <!-- 数据概览 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-2xl mx-auto mb-12">
        <div class="bg-white/80 backdrop-blur rounded-xl p-4">
          <div class="text-3xl font-bold text-indigo-500" style="font-family: Georgia, serif;">{total_minutes}</div>
          <div class="text-xs text-gray-500">分钟</div>
        </div>
        <div class="bg-white/80 backdrop-blur rounded-xl p-4">
          <div class="text-3xl font-bold text-teal-500" style="font-family: Georgia, serif;">{len(points)}</div>
          <div class="text-xs text-gray-500">核心观点</div>
        </div>
        <div class="bg-white/80 backdrop-blur rounded-xl p-4">
          <div class="text-3xl font-bold text-amber-500" style="font-family: Georgia, serif;">{num_modules}</div>
          <div class="text-xs text-gray-500">主题模块</div>
        </div>
        <div class="bg-white/80 backdrop-blur rounded-xl p-4">
          <div class="text-3xl font-bold text-rose-500" style="font-family: Georgia, serif;">{len(quotes)}</div>
          <div class="text-xs text-gray-500">条金句</div>
        </div>
      </div>

      <!-- 模块快速导航 -->
      <div class="grid grid-cols-2 md:grid-cols-{num_modules} gap-3 max-w-3xl mx-auto">
        {nav_cards}
      </div>
    </div>
  </header>

  <!-- 主体内容 -->
  <main>
    {point_cards_html}
    {quotes_html}
  </main>

  <!-- 页脚 -->
  <footer class="py-12 text-center text-gray-400 text-sm">
    <p>由 learning-content-analyzer Skill 自动生成</p>
    <p class="mt-1">对话内容提炼 · 观点提取 · 思维导图</p>
  </footer>

  <!-- 回到顶部 -->
  <div class="back-to-top" id="backToTop" onclick="window.scrollTo({{top:0, behavior:'smooth'}})">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M18 15l-6-6-6 6"/>
    </svg>
  </div>

  <script>
    // 进度条
    window.addEventListener('scroll', () => {{
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress = (scrollTop / docHeight) * 100;
      document.getElementById('progressBar').style.width = progress + '%';

      // 回到顶部按钮
      const btn = document.getElementById('backToTop');
      if (scrollTop > 300) btn.classList.add('show');
      else btn.classList.remove('show');
    }});

    // 渐入动画
    const observer = new IntersectionObserver((entries) => {{
      entries.forEach(entry => {{
        if (entry.isIntersecting) {{
          entry.target.classList.add('visible');
        }}
      }});
    }}, {{ threshold: 0.1 }});

    document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

    // Mermaid
    if (window.mermaid) {{
      mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    }}
  </script>
</body>
</html>'''

    if output_file:
        Path(output_file).write_text(html, encoding='utf-8')

    return html


# ============================================================
# 第六步：生成 Markdown 版本
# ============================================================

def generate_markdown(title, points, modules, quotes):
    """生成 Markdown 版本的核心观点"""
    lines = [f'# {title}', '']
    lines.append('> 核心观点提炼 · 由 learning-content-analyzer 自动生成')
    lines.append('')

    # 思维导图
    lines.append('## 🧠 思维导图')
    lines.append('')
    lines.append(generate_mindmap(title, points, modules))
    lines.append('')

    # 按模块列出观点
    lines.append('---')
    lines.append('')

    for module in modules:
        module_points = [p for p in points if p['module'] == module]
        module_points.sort(key=lambda x: -x['score'])

        lines.append(f'## 📌 {module}')
        lines.append('')

        for i, p in enumerate(module_points[:10], 1):
            tags_str = ' '.join([f'`{tag}`' for tag in p['tags'][:3]])
            lines.append(f'### {i}. {p["summary"]}')
            lines.append('')
            lines.append(f'- **说话人**: {p["speaker"]}')
            if p['start']:
                lines.append(f'- **时间戳**: {p["start"]}')
            if tags_str:
                lines.append(f'- **标签**: {tags_str}')
            lines.append('')
            lines.append(f'> {p["full_text"][:200]}{"..." if len(p["full_text"]) > 200 else ""}')
            lines.append('')
            if p['is_quote'] and p['quote_text']:
                lines.append(f'> **金句**: 「{p["quote_text"]}」')
                lines.append('')

    # 金句
    if quotes:
        lines.append('---')
        lines.append('')
        lines.append('## 💎 金句墙')
        lines.append('')
        for i, q in enumerate(quotes[:10], 1):
            lines.append(f'{i}. 「{q["quote_text"]}」—— {q["speaker"]} ({q["start"]})')
            lines.append('')

    return '\n'.join(lines)


# ============================================================
# 主入口
# ============================================================

def extract_dialogue_content(input_file, title='对话内容提炼', output_dir='.'):
    """完整的对话内容提炼流程

    Args:
        input_file: 转录文件路径
        title: 内容标题
        output_dir: 输出目录

    Returns:
        dict: 包含 html_file, md_file, mindmap_file, points, modules, quotes
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 读取文件
    text = Path(input_file).read_text(encoding='utf-8')

    # 2. 解析对话
    paragraphs = parse_dialogue_transcript(text)
    if not paragraphs:
        print(f"⚠️ 未能解析出对话段落，请检查文件格式")
        return None

    print(f"📝 解析到 {len(paragraphs)} 个对话段落")

    # 3. 识别角色
    roles = identify_roles(paragraphs)
    print(f"🎤 说话者: {list(roles.keys())}")
    for spk, role in roles.items():
        print(f"   - {spk}: {role}")

    # 4. 提取核心观点
    points = extract_key_points(paragraphs)
    print(f"💡 提取到 {len(points)} 个核心观点")

    # 5. 按模块分组
    modules = []
    seen_modules = set()
    for p in points:
        if p['module'] not in seen_modules:
            modules.append(p['module'])
            seen_modules.add(p['module'])
    print(f"📚 主题模块: {modules}")

    # 6. 采集金句
    quotes = collect_quotes(points)
    print(f"💎 采集到 {len(quotes)} 条金句")

    # 7. 生成文件名
    base_name = Path(input_file).stem

    # 8. 生成 HTML
    html_file = output_dir / f'{base_name}_analysis.html'
    generate_html(title, paragraphs, points, modules, quotes, roles, str(html_file))
    print(f"🌐 HTML 已生成: {html_file}")

    # 9. 生成 Markdown
    md_file = output_dir / f'{base_name}_key_points.md'
    md_content = generate_markdown(title, points, modules, quotes)
    md_file.write_text(md_content, encoding='utf-8')
    print(f"📝 Markdown 已生成: {md_file}")

    # 10. 生成思维导图（单独文件）
    mindmap_file = output_dir / f'{base_name}_mindmap.md'
    mindmap_content = generate_mindmap(title, points, modules)
    mindmap_file.write_text(mindmap_content, encoding='utf-8')
    print(f"🧠 思维导图已生成: {mindmap_file}")

    return {
        'html_file': str(html_file),
        'md_file': str(md_file),
        'mindmap_file': str(mindmap_file),
        'points': points,
        'modules': modules,
        'quotes': quotes,
        'paragraphs': paragraphs,
        'roles': roles,
    }


# ============================================================
# 命令行入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("用法: python3 dialogue_extractor.py <transcript.txt> [--title '标题'] [--output-dir ./output]")
        print("示例:")
        print("  python3 dialogue_extractor.py transcript_1_lixiang.txt --title '罗永浩对谈李想'")
        sys.exit(1)

    input_file = sys.argv[1]
    title = '对话内容提炼'
    output_dir = '.'

    if '--title' in sys.argv:
        idx = sys.argv.index('--title')
        if idx + 1 < len(sys.argv):
            title = sys.argv[idx + 1]

    if '--output-dir' in sys.argv:
        idx = sys.argv.index('--output-dir')
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]

    print(f"📄 输入文件: {input_file}")
    print(f"📝 标题: {title}")
    print("=" * 60)

    result = extract_dialogue_content(input_file, title, output_dir)

    if result:
        print("")
        print("=" * 60)
        print("✅ 提炼完成！")
        print(f"   HTML: {result['html_file']}")
        print(f"   Markdown: {result['md_file']}")
        print(f"   思维导图: {result['mindmap_file']}")


if __name__ == '__main__':
    main()
