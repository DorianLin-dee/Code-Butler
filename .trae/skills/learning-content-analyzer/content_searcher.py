#!/usr/bin/env python3
"""
智能文稿搜索工具
先搜索网上是否有现成文稿，再问是否需要转录
"""

import sys
import re
import requests
from pathlib import Path
from urllib.parse import urlparse, quote_plus
from bs4 import BeautifulSoup


def extract_surname_from_title(title):
    """从视频/播客标题中提取受访者姓氏

    支持的标题格式：
      - "翁家翌：OpenAI，GPT..."  → 翁
      - "马斯克最新访谈"          → 马
      - "妹岛和世 & 西泽立卫"     → 妹
      - "嘉宾：翁家翌"            → 翁
      - "专访 Sam Altman"         → altman
      - "Conversation with Elon" → elon（取首词）

    提取不到时返回空字符串。
    """
    if not title:
        return ''

    # 去掉平台后缀（- 小宇宙, | B站, _ YouTube 等）
    clean = re.split(r'\s*[-|_]\s*', title)[0].strip()

    # 规则1: "XXX：/:" 后面跟关键词 → XXX 是受访者
    m = re.match(r'^([^\s：:]{2,8})\s*[：:]', clean)
    if m:
        name = m.group(1)
        # 过滤掉"嘉宾""专访"等引导词
        if name not in ('嘉宾', '专访', '对话', '对谈', '访谈', '完整版', '精华'):
            return _get_surname(name)

    # 规则2: "嘉宾：XXX" / "专访XXX" / "对话XXX" — 支持中英文全名
    m = re.match(r'^(?:嘉宾|专访|对话|对谈|访谈)\s*[：:]?\s*(.+?)(?:\s*(?:谈|聊|说|讲|关于|on|—|$))', clean)
    if m:
        return _get_surname(m.group(1).strip())

    # 规则3: "XXX & YYY" / "XXX × YYY" / "XXX 与 YYY" → 取第一个
    m = re.match(r'^([^\s,&×与]{2,10})\s*[&×与]\s*', clean)
    if m:
        return _get_surname(m.group(1))

    # 规则4: "XXX访谈/专访/对话/对谈" → XXX 是受访者
    m = re.match(r'^([^\s]{2,8})(?:最新)?(?:访谈|专访|对话|对谈|采访)', clean)
    if m:
        name = m.group(1)
        if name not in ('最新', '完整', '完整版'):
            return _get_surname(name)

    # 规则4b: "XXX教授/老师/博士谈..." → XXX 是受访者
    m = re.match(r'^([\u4e00-\u9fff]{2,4})(?:教授|老师|博士|专家|院士)(?:谈|聊|说|讲|论)', clean)
    if m:
        return m.group(1)[0]

    # 规则5: 英文 "Conversation with XXX" / "XXX on YYY" — 匹配完整人名
    m = re.match(r'^Conversation with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', clean, re.IGNORECASE)
    if m:
        return _get_surname(m.group(1))
    m = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+on\s+', clean)
    if m:
        return _get_surname(m.group(1))

    # 规则6: 纯英文标题，尝试取第一个有意义的词（需连续2个大写词，更像人名）
    words = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', clean)
    if words:
        return _get_surname(words[0])

    return ''


def _get_surname(full_name):
    """从完整姓名中提取姓氏

    中文名（2-4字）：取第一个字
    英文名（如 Sam Altman）：取最后一个词
    日文名：取第一个字（与中文相同处理）
    """
    full_name = full_name.strip()

    # 纯中文/日文（2-4个字符）
    if re.match(r'^[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]{2,4}$', full_name):
        return full_name[0]

    # 英文名（含空格，如 "Sam Altman"）
    if ' ' in full_name and re.match(r'^[a-zA-Z\s]+$', full_name):
        parts = full_name.split()
        return parts[-1].lower()

    # 单个英文词（如 "Elon"）
    if re.match(r'^[a-zA-Z]{2,}$', full_name):
        return full_name.lower()

    # 混合名：取第一个中文字符
    m = re.match(r'^([\u4e00-\u9fff])', full_name)
    if m:
        return m.group(1)

    # 混合名：取第一个英文词
    m = re.match(r'^([a-zA-Z]+)', full_name)
    if m:
        return m.group(1).lower()

    return ''


def extract_video_info(url):
    """从URL中提取视频标题等信息"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = ''
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
        
        return {'title': title, 'url': url}
    except Exception as e:
        print(f"⚠️ 提取视频信息失败: {e}")
        return {'title': '', 'url': url}

def search_web_transcript(title, url):
    """在网上搜索文稿"""
    print(f"\n🔍 正在搜索网上文稿...")
    print(f"   标题: {title if title else '未知'}")
    
    search_keywords = []
    
    if title:
        clean_title = re.sub(r'[-|].*$', '', title).strip()
        search_keywords.append(f"{clean_title} 文字稿")
        search_keywords.append(f"{clean_title} 文稿")
        search_keywords.append(f"{clean_title} transcript")
    
    search_keywords.append(f"{url} 文字稿")
    search_keywords.append(f"{url} 文稿")
    
    results = []
    
    for keyword in search_keywords[:3]:
        try:
            search_url = f"https://www.baidu.com/s?wd={quote_plus(keyword)}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for result in soup.find_all('div', class_='result')[:3]:
                try:
                    link = result.find('a')
                    if link and link.get('href'):
                        title_text = link.get_text().strip()
                        href = link.get('href')
                        if title_text and href:
                            results.append({
                                'title': title_text,
                                'url': href,
                                'keyword': keyword
                            })
                except:
                    pass
                    
            if len(results) >= 5:
                break
        except Exception as e:
            print(f"   搜索 '{keyword}' 失败: {e}")
            continue
    
    return results

def extract_content_from_url(url):
    """尝试从URL中提取文稿内容"""
    try:
        print(f"📥 尝试获取内容: {url[:50]}...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        content = '\n'.join(lines)
        
        if len(content) > 500:
            return content
        
        return None
    except Exception as e:
        print(f"   获取失败: {e}")
        return None

def format_transcript_with_timestamps(content):
    """将文稿格式化为带时间戳的格式"""
    if not content:
        return None
    
    lines = content.split('\n')
    
    formatted = []
    time_counter = 0
    
    for line in lines:
        if line.strip():
            minutes = time_counter // 60
            seconds = time_counter % 60
            hours = minutes // 60
            minutes = minutes % 60
            
            timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            formatted.append(f"{timestamp} - {line.strip()}")
            
            time_counter += max(10, len(line) // 20)
    
    if formatted:
        return '\n'.join(formatted)
    
    return None

def generate_transcript_basepath(output_dir='.', surname=''):
    """生成不重复的转录文件路径（不带扩展名）

    格式: transcript_{序号}_{姓}
    例如: transcript_1_xie, transcript_2

    扫描目录中已有的 transcript_* 文件（支持 txt/md/srt/vtt/json 等所有格式），
    序号递增，避免覆盖。返回不带扩展名的完整路径，调用方可自行追加 .txt / .md / .srt 等。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 扫描已有文件（所有转录格式），找到最大序号
    max_num = 0
    for f in output_dir.glob('transcript_*'):
        parts = f.stem.split('_')
        if len(parts) >= 2 and parts[1].isdigit():
            max_num = max(max_num, int(parts[1]))

    next_num = max_num + 1

    # 姓氏只保留字母和中文，转小写
    safe_surname = ''
    if surname:
        cleaned = re.sub(r'[^a-zA-Z\u4e00-\u9fff]', '', surname).lower()
        if cleaned:
            safe_surname = f"_{cleaned}"

    basename = f"transcript_{next_num}{safe_surname}"
    return str(output_dir / basename)


def generate_transcript_filename(output_dir='.', surname=''):
    """生成不重复的转录文件名（.txt）

    格式: transcript_{序号}_{姓}.txt
    例如: transcript_1_xie.txt, transcript_2.txt

    基于 generate_transcript_basepath，固定追加 .txt 扩展名。
    """
    return generate_transcript_basepath(output_dir, surname) + '.txt'


def save_transcript(content, output_dir='.', surname=''):
    """保存文稿，使用不重复的文件名"""
    output_path = generate_transcript_filename(output_dir, surname)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ 文稿已保存: {output_path}")
    return str(output_path)


def extract_speakers_from_shownotes(title='', description=''):
    """从标题和 shownotes（节目简介）中提取说话者姓名列表

    支持的格式：
      - 标题: "翁家翌 & 张潇雨：..." → ["翁家翌", "张潇雨"]
      - 标题: "对话张潇雨" → ["张潇雨"]
      - 简介: "嘉宾：张三、李四" → ["张三", "李四"]
      - 简介: "主持：王五 嘉宾：赵六" → ["王五", "赵六"]
      - 简介: "SPEAKER 01: 张三\nSPEAKER 02: 李四" → ["张三", "李四"]
      - 简介: "【嘉宾】张三 | 【主持】李四" → ["李四", "张三"]

    返回按出现顺序排列的唯一名单，优先主持人在前、嘉宾在后。
    """
    speakers = []

    # 从标题中提取
    if title:
        clean = re.split(r'\s*[-|_]\s*', title)[0].strip()

        # 格式: "XXX & YYY：..." 或 "XXX × YYY：..." 或 "XXX 与 YYY：..."
        m = re.match(r'^([^&×与：:]+)\s*[&×与]\s*([^&×与：:]+?)\s*[：:]', clean)
        if m:
            n1 = m.group(1).strip()
            n2 = m.group(2).strip()
            if 2 <= len(n1) <= 10 and 2 <= len(n2) <= 10:
                speakers.extend([n1, n2])

        # 格式: "对话XXX" / "专访XXX" / "对谈XXX" + "："
        if not speakers:
            m = re.match(r'^(?:对话|专访|对谈|访谈)([\u4e00-\u9fffA-Za-z]{2,10})\s*[：:]', clean)
            if m:
                speakers.append(m.group(1))

        # 格式: "XXX：..." 单人
        if not speakers:
            m = re.match(r'^([^\s：:]{2,8})\s*[：:]', clean)
            if m:
                name = m.group(1)
                if name not in ('嘉宾', '专访', '对话', '对谈', '访谈', '完整版', '精华'):
                    speakers.append(name)

        # 格式: "XXX访谈/专访/对话"
        if not speakers:
            m = re.match(r'^([\u4e00-\u9fff]{2,4})(?:最新)?(?:访谈|专访|对话|对谈)', clean)
            if m:
                speakers.append(m.group(1))

    # 从 description 中提取
    if description:
        lines = description.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 格式: "嘉宾：张三、李四" 或 "嘉宾: 张三, 李四"
            for prefix in ('嘉宾', '主持', '主持人', '主播', '主理人', '对谈嘉宾', '分享嘉宾'):
                m = re.match(rf'[【\[]?{prefix}[】\]]?\s*[：:]\s*(.+)', line)
                if m:
                    names_str = m.group(1)
                    # 拆分：顿号、中文逗号、英文逗号、|、/、和、与、及
                    # 注意：英文人名的空格不拆（"Sam Altman" 是一个人）
                    names = re.split(r'[、,，|/；;]|\s+(?:和|与|及)\s+', names_str)
                    for n in names:
                        n = n.strip()
                        # 去掉"·""-""_"等中间连接符（保留为名字的一部分，不拆）
                        # 如 "埃隆·马斯克" → 保留为一个名字
                        if n and n not in speakers:
                            speakers.append(n)

            # 格式: "SPEAKER 01: 张三" 或 "S01: 张三"
            m = re.match(r'(?:SPEAKER|S)\s*\d+\s*[：:]\s*(.+)', line, re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                if name and name not in speakers:
                    speakers.append(name)

            # 格式: "张三（嘉宾）" 或 "李四 - 主持人"
            m = re.match(r'([\u4e00-\u9fffA-Za-z·\s]{2,15})\s*[（(]\s*(?:嘉宾|主持|主持人|主播)[）)]', line)
            if m:
                name = m.group(1).strip()
                if name not in speakers:
                    speakers.append(name)

    # 过滤和清洗
    temp = []
    for s in speakers:
        s = s.strip()
        # 去除括号及括号内内容（"杨立昆（Yann LeCun）" → "杨立昆"）
        s = re.sub(r'[（(].*?[）)]', '', s).strip()
        # 去除头衔后缀
        s = re.sub(r'(?:老师|博士|教授|先生|女士|同学|老师|老师)$', '', s)
        s = s.strip()
        # 太短/纯数字跳过
        if not s or re.match(r'^[\d\s]+$', s) or len(s) < 2:
            continue
        # 英文人名（含空格，如 "Sam Altman"）- 3-25 字符
        if re.match(r'^[A-Za-z\s·\.\-]+$', s):
            if len(s) <= 25:
                temp.append(s)
            continue
        # 中文名（含"·"，如"埃隆·马斯克"）- 2-8 字
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', s)
        if 2 <= len(chinese_chars) <= 8:
            temp.append(s)
            continue
        # 其他混合情况，总长度合理也保留
        if len(s) <= 15:
            temp.append(s)

    # 去重：同一人可能有简称和全称（如 "马斯克" 和 "埃隆·马斯克"）
    # 策略：如果短名是长名的结尾部分（中文姓氏在后），则去重保留长名
    filtered = []
    for name in temp:
        is_dup = False
        for i, existing in enumerate(filtered):
            # 去掉"·"" "等连接符后比较
            name_clean = re.sub(r'[·\s\-]', '', name)
            existing_clean = re.sub(r'[·\s\-]', '', existing)
            # 一个是另一个的子串 → 保留更长的那个
            if name_clean == existing_clean:
                is_dup = True
                break
            if name_clean in existing_clean:
                # name 是 existing 的子串，保留 existing
                is_dup = True
                break
            if existing_clean in name_clean:
                # existing 是 name 的子串，用 name 替换 existing
                filtered[i] = name
                is_dup = True
                break
        if not is_dup:
            filtered.append(name)

    return filtered


def assign_speaker_names(speaker_list, num_speakers=2):
    """根据提取到的说话者列表，生成 SPEAKER_XX → 真名 的映射

    规则：
    - 第一个人（通常是主持人）→ SPEAKER_00
    - 第二个人（通常是嘉宾）→ SPEAKER_01
    - 以此类推

    返回字典，如 {"SPEAKER_00": "张潇雨", "SPEAKER_01": "翁家翌"}
    """
    mapping = {}
    for i, name in enumerate(speaker_list[:num_speakers]):
        mapping[f"SPEAKER_{i:02d}"] = name
    return mapping


def generate_initial_prompt(title='', description='', speakers=None, language='zh'):
    """从标题、简介、说话者列表生成 Whisper initial_prompt

    作用：告诉 Whisper 上下文和专有名词，显著提高专有名词识别准确率
    策略：
    - 提取标题中的关键信息（人名、公司名、术语）
    - 从 shownotes 提取嘉宾、主题关键词
    - 拼接成自然的中文句子，符合 Whisper prompt 格式
    - 控制在 200 字符以内（太长反而可能干扰）

    示例输出：
    "这是一档科技播客，讨论人工智能、OpenAI、GPT 等话题。
     主持人张潇雨，嘉宾翁家翌。"
    """
    if speakers is None:
        speakers = []

    parts = []

    # 1. 从标题提取主题关键词
    if title:
        clean = re.split(r'\s*[-|_]\s*', title)[0].strip()
        # 提取英文专有名词
        en_terms = re.findall(r'\b[A-Z][a-zA-Z]+(?:[-\s][A-Z0-9][a-zA-Z0-9]*)*\b', clean)
        # 提取英文缩写
        abbrs = re.findall(r'\b[A-Z]{2,6}\b', clean)
        # 提取中文人名（标题开头）
        name_match = re.match(r'^([^\s：:]{2,8})\s*[：:]', clean)
        title_name = name_match.group(1) if name_match and name_match.group(1) not in ('嘉宾', '专访', '对话', '对谈', '访谈') else ''

        keywords = en_terms + abbrs
        if title_name and title_name not in speakers:
            keywords.insert(0, title_name)

        if keywords:
            # 去重，保留前 8 个
            seen = set()
            unique_kw = []
            for kw in keywords:
                if kw not in seen and len(kw) >= 2:
                    seen.add(kw)
                    unique_kw.append(kw)
                    if len(unique_kw) >= 8:
                        break
            parts.append(f"本期关键词：{'、'.join(unique_kw)}。")

    # 2. 说话者信息
    if speakers:
        # 区分主持人和嘉宾（如果有）
        hosts = []
        guests = []
        # 简单处理：第一个是主持人，后面的是嘉宾
        if len(speakers) == 1:
            parts.append(f"主讲人：{speakers[0]}。")
        else:
            parts.append(f"对话参与者：{'、'.join(speakers[:4])}。")

    # 3. 从 description 提取主题关键词（前几句）
    if description:
        lines = [l.strip() for l in description.split('\n') if l.strip()]
        # 取前 2 行非空行，提取关键词
        for line in lines[:2]:
            # 提取英文术语
            en_terms = re.findall(r'\b[A-Z][a-zA-Z]+(?:[-\s][A-Z0-9][a-zA-Z0-9]*)*\b', line)
            if en_terms and len(parts) < 3:
                unique = []
                seen = set()
                for t in en_terms[:5]:
                    if t not in seen:
                        seen.add(t)
                        unique.append(t)
                if unique:
                    parts.append(f"涉及技术：{'、'.join(unique)}。")
                break

    # 4. 语言和风格提示
    if language == 'zh':
        parts.insert(0, "这是一段中文播客访谈。")
    elif language == 'en':
        parts.insert(0, "This is a podcast interview.")

    # 拼接并控制长度
    prompt = ''.join(parts)
    if len(prompt) > 220:
        prompt = prompt[:220] + '。'

    return prompt if prompt else ''


def main():
    print("=" * 70)
    print("🔍 智能文稿搜索工具")
    print("=" * 70)
    
    if len(sys.argv) < 2:
        print("\n用法: python3 content_searcher.py <视频链接>")
        print("示例: python3 content_searcher.py https://www.bilibili.com/video/BV1Z9QABeEgf")
        sys.exit(1)
    
    url = sys.argv[1]
    current_dir = Path.cwd()
    
    print(f"\n📹 分析链接: {url}")
    
    video_info = extract_video_info(url)
    
    search_results = search_web_transcript(video_info['title'], video_info['url'])
    
    if search_results:
        print(f"\n✅ 找到 {len(search_results)} 个可能的文稿来源:")
        print("-" * 70)
        for i, result in enumerate(search_results, 1):
            print(f"{i}. {result['title'][:60]}...")
            print(f"   {result['url'][:60]}...")
            print()
        
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
                output_file = save_transcript(formatted, current_dir)
                
                print("\n" + "=" * 70)
                print("✅ 文稿准备就绪!")
                print(f"📄 文件: {output_file}")
                print("=" * 70)
                print("\n文稿预览:")
                print("-" * 70)
                preview_lines = formatted.split('\n')[:20]
                print('\n'.join(preview_lines))
                if len(preview_lines) < len(formatted.split('\n')):
                    print("... (更多内容请查看 transcript.txt)")
                
                return {
                    'found': True,
                    'file': output_file,
                    'content': formatted
                }
        else:
            print("\n⚠️ 找到一些链接，但未能提取到可用的文稿内容")
    else:
        print("\n❌ 未找到现成文稿")
    
    print("\n💡 建议: 使用转录功能获取文稿")
    return {
        'found': False,
        'message': '未找到现成文稿，请使用转录功能'
    }

if __name__ == '__main__':
    result = main()
    if result and not result.get('found'):
        sys.exit(1)

