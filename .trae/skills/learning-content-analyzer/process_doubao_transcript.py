#!/usr/bin/env python3
"""
豆包转录稿处理工具
将豆包语音识别的转录稿转换为 skill 标准格式，并进行词语校正

豆包转录稿格式：
    Speaker 1 00:00:00.260
    大家好，我是张金建...

    Speaker 2 00:00:17.220
    大家好，我是秦声涛...

转换为标准格式：
    [00:00:00 - 00:00:17] [张金建]
    大家好，我是张金建...

功能：
    - 自动识别说话者姓名（自我介绍 / 嘉宾介绍）
    - 合并同一说话者的连续发言
    - 专有名词自动校正（复用 transcript_corrector 术语字典）
    - 口语化表达清理

用法：
    python3 process_doubao_transcript.py <豆包转录稿.txt> [--speakers 张津剑,秦深涛] [--output output.md]
"""

import re
import sys
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


def load_term_dict():
    """加载术语校正字典（从 transcript_corrector 复用）

    Returns:
        dict: {错误词: 正确词}
    """
    try:
        from transcript_corrector import DOMAIN_TERMS

        all_terms = {}
        for domain, terms in DOMAIN_TERMS.items():
            all_terms.update(terms)
        return all_terms
    except Exception:
        return {}


COMMON_FIXES = {
    '开炉': '开颅',
    '开颅之后': '开颅之后',
    '金建哥': '津剑哥',
    '金建': '津剑',
    '张金建': '张津剑',
    '秦声涛': '秦深涛',
    'OriginFlow': 'Orange Flow',
    'Origin Flow': 'Orange Flow',
    'origin flow': 'Orange Flow',
    'Motion Unite Active Potential': 'Motor Unit Action Potential',
    'motion unit active potential': 'Motor Unit Action Potential',
    '阿维塔': 'avatar',
    '方电': '放电',
    '方电神经': '放电神经',
    '机原蛋白': '肌球蛋白',
    '机动肌原蛋白': '肌动蛋白和肌球蛋白',
    '神驱': '神经驱动',
    '微人': '肉眼',
    '天审': '筛选',
    'b 进来': '电极进来',
    '思路环路': '伺服环路',
    '低要求': '第一课',
    '勒坤': 'LeCun',
    '勒空': 'LeCun',
    'Java 的': 'JEPA 的',
    'jepa': 'JEPA',
    '咵叽': '咔嚓',
    'scenery': 'scenario',
    '放的心态': '佛系的心态',
    '林德': '黄仁勋',
    'Siri 回过头': 'Cerebras 回过头',
    '机座电流': '肌电信号',
    '运动声音接口': '运动神经接口',
    '运动声纹接口': '运动神经接口',
    'neural mis-matching': 'neural mismatching',
    'neural mis matching': 'neural mismatching',
    'neural mismatch': 'neural mismatching',
    'brain to text': 'brain-to-text',
    'brain-text': 'brain-to-text',
    'POS': 'fascia',
    '筋膜': 'fascia',
    'POR': 'PoR',
    'hyper 秀': 'HyperX',
    '极鞘': '机械外骨骼',
    'Figger': 'Figure',
    'Figma': 'Figure',
    'Federico': 'Figure',
    'fetcher': 'Figure',
    'Anthropic': 'Anthropic',
    'anthropic': 'Anthropic',
    'op us': 'opus',
    'codex': 'Claude Code',
    'Labs 被': 'Labs 被',
    'ctrl lab': 'CTRL-Labs',
    'Ctrl Lab': 'CTRL-Labs',
    'control lab': 'CTRL-Labs',
    'Control Lab': 'CTRL-Labs',
    'meta': 'Meta',
    'neuralink': 'Neuralink',
    'Neuralink': 'Neuralink',
    '具神智能': '具身智能',
    '居神智能': '具身智能',
    '人机共容': '人机共融',
    '人际共融': '人机共融',
    '人际共容': '人机共融',
    '哈工达': '哈工大',
    '哈工大大': '哈工大',
    '机点工程学院': '机电工程学院',
    '航空宇航制造': '航空宇航制造',
}


def parse_doubao_transcript(text):
    """解析豆包转录稿

    Returns:
        list of dict: [{speaker, start, text}, ...]
    """
    lines = text.strip().split('\n')
    segments = []
    current_speaker = None
    current_start = None
    current_text = []

    speaker_pattern = re.compile(
        r'^Speaker\s+(\d+)\s+(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s*$',
        re.IGNORECASE
    )

    skip_prefixes = [
        '202', '201', '200',
        'Keywords:', 'Keywords：', 'keywords:',
        'Summary:', 'Summary：', 'summary:',
        'Transcript:', 'Transcript：', 'transcript:',
        '对话时间', '时长', '总时长',
    ]

    for line in lines:
        line_stripped = line.strip()

        if not line_stripped:
            if current_speaker is not None and current_text:
                segments.append({
                    'speaker': current_speaker,
                    'start': current_start,
                    'text': '\n'.join(current_text).strip()
                })
                current_text = []
            continue

        skip = False
        for prefix in skip_prefixes:
            if line_stripped.startswith(prefix):
                skip = True
                break
        if skip:
            continue

        m = speaker_pattern.match(line_stripped)
        if m:
            if current_speaker is not None and current_text:
                segments.append({
                    'speaker': current_speaker,
                    'start': current_start,
                    'text': '\n'.join(current_text).strip()
                })

            current_speaker = f"Speaker {m.group(1)}"
            current_start = m.group(2)
            current_text = []
            continue

        if current_speaker is not None:
            current_text.append(line_stripped)

    if current_speaker is not None and current_text:
        segments.append({
            'speaker': current_speaker,
            'start': current_start,
            'text': '\n'.join(current_text).strip()
        })

    return segments


def extract_speaker_names(segments):
    """从转录内容中自动提取说话者姓名

    策略：
    1. 自我介绍："我是XXX"、"大家好我是XXX"
    2. 嘉宾介绍："我们请到了XXX"、"嘉宾XXX"
    3. 称呼对方：提到对方名字的是主持人
    """
    names = {}

    intro_patterns = [
        r'大家好[，,。.]?\s*我是([\u4e00-\u9fa5]{2,4})',
        r'^我是([\u4e00-\u9fa5]{2,4})[，,。.！!?？]',
        r'我是([\u4e00-\u9fa5]{2,4})[，,。.！!?？\s]',
        r'我叫([\u4e00-\u9fa5]{2,4})[，,。.！!?？]',
    ]

    for seg in segments:
        if seg['speaker'] in names:
            continue
        for pattern in intro_patterns:
            m = re.search(pattern, seg['text'])
            if m:
                name = m.group(1)
                if name not in ('不是', '谁', '哪个', '怎么', '什么', '觉得', '认为', '因为', '所以', '但是', '而且', '然后'):
                    names[seg['speaker']] = name
                    break

    if len(names) < 2:
        intro_patterns_guest = [
            r'请到了[^，。]*?([\u4e00-\u9fa5]{2,4})[，。同学老师先生]',
            r'嘉宾[是：]*([\u4e00-\u9fa5]{2,4})',
            r'老朋友[，,]*也是[^的]*?的[^，。]*?([\u4e00-\u9fa5]{2,4})[，。]',
        ]
        for seg in segments:
            if seg['speaker'] in names:
                continue
            for pattern in intro_patterns_guest:
                m = re.search(pattern, seg['text'])
                if m:
                    name = m.group(1)
                    if name not in names.values() and len(name) >= 2 and len(name) <= 4:
                        names[seg['speaker']] = name
                        break
            if len(names) >= 2:
                break

    return names


def time_to_seconds(time_str):
    time_str = time_str.split('.')[0]
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + int(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + int(s)
    return 0


def seconds_to_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def add_end_times(segments):
    for i in range(len(segments)):
        if i + 1 < len(segments):
            segments[i]['end'] = segments[i + 1]['start']
        else:
            segments[i]['end'] = segments[i]['start']
    return segments


def merge_same_speaker(segments, max_gap_sec=60):
    """合并同一说话者的连续发言

    Args:
        max_gap_sec: 最大间隔秒数，超过则不合并（防止跨度过大）
    """
    if not segments:
        return segments

    merged = [dict(segments[0])]
    for seg in segments[1:]:
        prev = merged[-1]
        if seg['speaker'] == prev['speaker']:
            gap = time_to_seconds(seg['start']) - time_to_seconds(prev['start'])
            if gap <= max_gap_sec:
                prev['text'] += '\n' + seg['text']
                prev['end'] = seg.get('end', seg['start'])
                continue
        merged.append(dict(seg))

    return merged


def correct_terms(text, term_dict=None):
    """词语校正

    Args:
        text: 原始文本
        term_dict: 术语字典 {错误: 正确}

    Returns:
        str: 校正后的文本
        dict: 校正统计 {正确词: 次数}
    """
    if term_dict is None:
        term_dict = {}

    corrections = {}
    result = text

    sorted_terms = sorted(term_dict.items(), key=lambda x: len(x[0]), reverse=True)

    for wrong, right in sorted_terms:
        if wrong == right:
            continue
        if wrong in result:
            count = result.count(wrong)
            result = result.replace(wrong, right)
            if right not in corrections:
                corrections[right] = 0
            corrections[right] += count

    return result, corrections


def clean_oral_style(text):
    """口语化清理"""
    result = text

    result = re.sub(r'[，,]+\s*对[，,]+\s*', '，', result)
    result = re.sub(r'对对对[，,.。]?', '对。', result)
    result = re.sub(r'嗯嗯[，,.。]?', '嗯，', result)
    result = re.sub(r'哈哈哈[，,.。]?', '（笑）', result)
    result = re.sub(r'哈哈[，,.。]?', '（笑）', result)
    result = re.sub(r'对吧？[，,]?\s*对吧？', '对吧？', result)
    result = re.sub(r'就是说[，,]', '就是', result)
    result = re.sub(r'就是就是[，,]', '就是', result)
    result = re.sub(r'然后然后[，,]', '然后', result)
    result = re.sub(r'因为因为[，,]', '因为', result)
    result = re.sub(r'所以所以[，,]', '所以', result)

    return result


def format_transcript(segments, speaker_names=None):
    if speaker_names is None:
        speaker_names = {}

    lines = []
    for seg in segments:
        start = seg['start'].split('.')[0] if '.' in seg['start'] else seg['start']
        end = seg.get('end', seg['start'])
        end = end.split('.')[0] if '.' in end else end

        speaker = speaker_names.get(seg['speaker'], seg['speaker'])

        lines.append(f"[{start} - {end}] [{speaker}]")
        lines.append(seg['text'])
        lines.append("")

    return '\n'.join(lines).strip()


def main():
    parser = argparse.ArgumentParser(
        description='处理豆包转录稿，转换为 skill 标准格式并校正词语'
    )
    parser.add_argument('input', help='豆包转录稿文件路径')
    parser.add_argument('--speakers', help='手动指定说话者姓名，逗号分隔（按 Speaker 1, 2 顺序）')
    parser.add_argument('--output', '-o', help='输出文件路径（默认：输入文件名_processed.md）')
    parser.add_argument('--no-merge', action='store_true', help='不合并同一说话者的连续发言')
    parser.add_argument('--no-correct', action='store_true', help='不进行词语校正')
    parser.add_argument('--no-clean', action='store_true', help='不清理口语化表达')
    parser.add_argument('--max-gap', type=int, default=60,
                        help='合并同一说话者的最大间隔秒数（默认 60 秒）')
    parser.add_argument('--term-file', help='自定义术语校正文件（JSON 格式，{错误:正确}）')

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    text = input_path.read_text(encoding='utf-8')
    print(f"📖 读取豆包转录稿: {args.input}")

    segments = parse_doubao_transcript(text)
    print(f"✅ 解析完成，共 {len(segments)} 段")

    segments = add_end_times(segments)

    speaker_names = {}
    if args.speakers:
        names = args.speakers.split(',')
        for i, name in enumerate(names, 1):
            speaker_names[f"Speaker {i}"] = name.strip()
        print(f"👤 使用手动指定的说话者: {speaker_names}")
    else:
        speaker_names = extract_speaker_names(segments)
        if speaker_names:
            print(f"👤 自动识别说话者: {speaker_names}")
        else:
            print("⚠️ 未能自动识别说话者姓名（可用 --speakers 手动指定）")

    if not args.no_merge:
        before = len(segments)
        segments = merge_same_speaker(segments, max_gap_sec=args.max_gap)
        print(f"🔗 合并连续发言: {before} 段 → {len(segments)} 段")

    total_corrections = {}
    if not args.no_correct:
        term_dict = load_term_dict()
        term_dict.update(COMMON_FIXES)

        if args.term_file:
            try:
                import json
                with open(args.term_file, 'r', encoding='utf-8') as f:
                    custom_terms = json.load(f)
                term_dict.update(custom_terms)
                print(f"📚 加载自定义术语: {len(custom_terms)} 条")
            except Exception as e:
                print(f"⚠️ 自定义术语加载失败: {e}")

        print(f"📚 术语校正字典: {len(term_dict)} 条")

        for seg in segments:
            seg['text'], corrs = correct_terms(seg['text'], term_dict)
            for right, count in corrs.items():
                if right not in total_corrections:
                    total_corrections[right] = 0
                total_corrections[right] += count

        if total_corrections:
            print(f"🔧 词语校正: {sum(total_corrections.values())} 处")
            for right, count in sorted(total_corrections.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"   {right}: {count} 处")
        else:
            print("🔧 词语校正: 无需校正")

    if not args.no_clean:
        for seg in segments:
            seg['text'] = clean_oral_style(seg['text'])
        print("🧹 已清理口语化表达")

    output = format_transcript(segments, speaker_names)

    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.with_suffix('.md')).replace('.txt', '_processed.md')
        if output_path == str(input_path):
            output_path = str(input_path.with_suffix('.md'))

    Path(output_path).write_text(output, encoding='utf-8')
    total_chars = sum(len(s['text']) for s in segments)
    print(f"\n💾 已保存: {output_path}")
    print(f"📊 共 {len(segments)} 段，{total_chars} 字")


if __name__ == '__main__':
    main()
