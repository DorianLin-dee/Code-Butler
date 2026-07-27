
#!/usr/bin/env python3
"""
学习内容分析器 - 分析书籍、播客、视频内容，生成思维导图框架和时间轴
"""

import re
from typing import List, Dict, Any, Tuple, Optional


class ContentAnalyzer:
    def __init__(self):
        self.content = ""
        self.sections = []
        self.key_points = []
        self.timeline_events = []
        self.screenshots = []
    
    def load_content(self, content: str):
        """加载学习内容"""
        self.content = content
        self._parse_structure()
        self._extract_timeline()
        self._extract_screenshots()
    
    def _parse_structure(self):
        """解析内容结构，支持中文内容和多级标题"""
        lines = self.content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 匹配标题格式：数字编号（1. / 1.1. / 2.1 等）或 Markdown 标题
            is_title = False
            if re.match(r'^#{1,6}\s+', line):
                is_title = True
            elif re.match(r'^\d+(\.\d+)*\.?\s+', line):
                is_title = True
            
            if is_title:
                if current_section:
                    self.sections.append(current_section)
                current_section = {
                    'title': line,
                    'content': [],
                    'subsections': [],
                    'screenshots': []
                }
            elif current_section:
                # 检查是否是截图标记
                screenshot_match = re.match(r'\[screenshot:\s*(.+?)\s*\]', line, re.IGNORECASE)
                if screenshot_match:
                    screenshot_path = screenshot_match.group(1).strip()
                    current_section['screenshots'].append(screenshot_path)
                else:
                    current_section['content'].append(line)
        
        if current_section:
            self.sections.append(current_section)
    
    def _extract_timeline(self):
        """从内容中提取音频/视频时间戳事件"""
        self.timeline_events = []
        
        timestamp_pattern = r'(\d{1,2}:\d{2}(?::\d{2})?)'
        
        matches = re.finditer(timestamp_pattern, self.content)
        
        for match in matches:
            timestamp = match.group(1)
            timestamp = self._normalize_timestamp(timestamp)
            
            start_pos = max(0, match.start() - 100)
            end_pos = min(len(self.content), match.end() + 200)
            context = self.content[start_pos:end_pos]
            context = re.sub(r'\s+', ' ', context).strip()
            
            sentences = re.split(r'[。！？.!?\n]', context)
            event_desc = ""
            for sentence in sentences:
                if timestamp in sentence or len(sentence) > 10:
                    event_desc = sentence.strip()
                    if len(event_desc) > 5:
                        break
            
            if not event_desc:
                event_desc = context[:100]
            
            exists = any(ts[0] == timestamp for ts in self.timeline_events)
            if not exists and event_desc:
                self.timeline_events.append((timestamp, event_desc))
        
        self.timeline_events.sort(key=lambda x: self._timestamp_to_seconds(x[0]))
    
    def _extract_screenshots(self):
        """从内容中提取所有截图"""
        self.screenshots = []
        screenshot_pattern = r'\[screenshot:\s*(.+?)\s*\]'
        
        matches = re.finditer(screenshot_pattern, self.content, re.IGNORECASE)
        for match in matches:
            screenshot_path = match.group(1).strip()
            if screenshot_path not in self.screenshots:
                self.screenshots.append(screenshot_path)
    
    def _normalize_timestamp(self, timestamp: str) -> str:
        """标准化时间戳格式为 HH:MM:SS"""
        parts = timestamp.split(':')
        if len(parts) == 2:
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return timestamp
    
    def _timestamp_to_seconds(self, timestamp: str) -> int:
        """将时间戳转换为秒数用于排序"""
        parts = list(map(int, timestamp.split(':')))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return 0
    
    def _find_timestamp_for_section(self, section: Dict) -> str:
        """为章节找到对应的时间戳"""
        section_text = section['title'] + ' ' + ' '.join(section['content'])
        
        for timestamp, event in self.timeline_events:
            if section['title'] and (section['title'] in event or event in section['title']):
                return timestamp
            section_words = set(re.findall(r'[\w\u4e00-\u9fff]+', section_text))
            event_words = set(re.findall(r'[\w\u4e00-\u9fff]+', event))
            if len(section_words & event_words) >= 2:
                return timestamp
        return ""
    
    def _is_image_url(self, path: str) -> bool:
        """判断是否为URL"""
        return path.startswith('http://') or path.startswith('https://')
    
    def _generate_screenshot_markdown(self, screenshot_path: str) -> str:
        """生成截图的Markdown格式"""
        if self._is_image_url(screenshot_path):
            return f'![screenshot]({screenshot_path})'
        else:
            return f'![screenshot](file:///{screenshot_path})'
    
    def extract_key_points(self) -> List[str]:
        """提取核心要点"""
        key_points = []
        
        for section in self.sections:
            content = ' '.join(section['content'])
            
            sentences = re.split(r'[。！？.!?]', content)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 10:
                    if any(keyword in sentence for keyword in 
                           ['重要', '关键', '核心', '主要', '首先', '其次', '最后',
                            'important', 'key', 'core', 'main', 'first', 'second', 'finally']):
                        key_points.append(sentence)
        
        return key_points
    
    def generate_mind_map(self) -> str:
        """生成完整的思维导图，在二级标题后附上时间戳和截图"""
        if not self.sections:
            return "请先提供学习内容"
        
        mind_map = ["📚 内容框架"]
        
        for i, section in enumerate(self.sections, 1):
            prefix = "├── " if i < len(self.sections) else "└── "
            
            timestamp = self._find_timestamp_for_section(section)
            title_display = section['title']
            if timestamp:
                title_display += f" [{timestamp}]"
            
            mind_map.append(f"{prefix}{title_display}")
            
            # 显示所有内容要点，而不是只显示前3个
            if section['content']:
                content_lines = [line for line in section['content'] if line.strip()]
                if content_lines:
                    # 判断是否是详细的时间戳内容行
                    has_timestamps = any(re.search(r'\d{1,2}:\d{2}(?::\d{2})?', line) for line in content_lines)
                    
                    if has_timestamps:
                        # 如果有时间戳内容，分层次显示
                        current_sub_point = []
                        for line in content_lines:
                            # 如果行包含时间戳或编号，作为新要点
                            if re.search(r'^\s*[-*+•]', line) or re.search(r'\d{1,2}:\d{2}', line):
                                if current_sub_point:
                                    self._add_sub_point(mind_map, current_sub_point, i, len(section['content']))
                                    current_sub_point = []
                                current_sub_point.append(line)
                            else:
                                current_sub_point.append(line)
                        
                        if current_sub_point:
                            self._add_sub_point(mind_map, current_sub_point, i, len(section['content']))
                    else:
                        # 普通内容逐行显示
                        for j, point in enumerate(content_lines, 1):
                            sub_prefix = "│   ├── " if i < len(self.sections) else "    ├── "
                            if j == len(content_lines):
                                sub_prefix = "│   └── " if i < len(self.sections) else "    └── "
                            
                            # 显示完整内容，不截断
                            mind_map.append(f"{sub_prefix}{point}")
            
            if section['screenshots']:
                for screenshot in section['screenshots']:
                    screenshot_markdown = self._generate_screenshot_markdown(screenshot)
                    indent = "│   " if i < len(self.sections) else "    "
                    mind_map.append(f"{indent}{screenshot_markdown}")
        
        return '\n'.join(mind_map)
    
    def _add_sub_point(self, mind_map: List[str], lines: List[str], section_index: int, total_sections: int):
        """添加子要点到思维导图"""
        if not lines:
            return
        
        # 合并多行内容为一条
        full_text = ' '.join([line.strip() for line in lines if line.strip()])
        
        # 为二级标题内容添加前缀
        sub_prefix = "│   ├── " if section_index < total_sections else "    ├── "
        
        # 只显示一条完整内容
        mind_map.append(f"{sub_prefix}{full_text}")
    
    def generate_timeline(self) -> str:
        """生成音频/视频时间轴"""
        if not self.timeline_events:
            return "没有找到时间戳信息。请确保内容包含音频/视频时间戳（如 00:05:12 或 30:25）"
        
        timeline = ["⏱️ 音频/视频时间轴"]
        
        for i, (timestamp, event) in enumerate(self.timeline_events, 1):
            prefix = "├── " if i < len(self.timeline_events) else "└── "
            timeline.append(f"{prefix}{timestamp}")
            timeline.append(f"    {event}")
        
        return '\n'.join(timeline)
    
    def answer_question(self, question: str) -> str:
        """回答用户问题"""
        keywords = question.split()
        
        timestamp_match = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', question)
        if timestamp_match:
            timestamp = self._normalize_timestamp(timestamp_match.group(1))
            for ts, event in self.timeline_events:
                if ts == timestamp:
                    return f"在 {timestamp} 这个时间点，内容是：\n\n{event}"
        
        relevant_content = []
        for section in self.sections:
            section_text = section['title'] + ' ' + ' '.join(section['content'])
            for keyword in keywords:
                if keyword.lower() in section_text.lower():
                    relevant_content.append(section)
                    break
        
        if not relevant_content:
            return "抱歉，我在内容中没有找到相关信息。你可以换个方式提问，或者提供更多上下文。"
        
        answer = f"关于 '{question}' 的相关内容：\n\n"
        for section in relevant_content:
            answer += f"📌 {section['title']}\n"
            answer += '\n'.join(section['content']) + '\n\n'
            
            if section['screenshots']:
                answer += "📷 相关截图：\n"
                for screenshot in section['screenshots']:
                    answer += f"{self._generate_screenshot_markdown(screenshot)}\n"
                answer += "\n"
        
        return answer


def main():
    print("学习内容分析助手")
    print("=" * 50)
    
    analyzer = ContentAnalyzer()
    
    while True:
        print("\n请选择操作：")
        print("1. 输入学习内容")
        print("2. 生成思维导图")
        print("3. 生成时间轴")
        print("4. 提取核心要点")
        print("5. 提问")
        print("6. 退出")
        
        choice = input("\n请输入选项 (1-6): ").strip()
        
        if choice == '1':
            print("\n请输入学习内容（包含音频/视频时间戳和截图标记）：")
            print("截图格式：[screenshot: 文件路径或URL]")
            print("输入 'END' 结束输入")
            content_lines = []
            while True:
                line = input()
                if line.strip() == 'END':
                    break
                content_lines.append(line)
            content = '\n'.join(content_lines)
            analyzer.load_content(content)
            print("✓ 内容已加载")
        
        elif choice == '2':
            mind_map = analyzer.generate_mind_map()
            print("\n" + mind_map)
        
        elif choice == '3':
            timeline = analyzer.generate_timeline()
            print("\n" + timeline)
        
        elif choice == '4':
            key_points = analyzer.extract_key_points()
            print("\n📋 核心要点：")
            for i, point in enumerate(key_points, 1):
                print(f"{i}. {point}")
        
        elif choice == '5':
            question = input("\n请输入你的问题：").strip()
            answer = analyzer.answer_question(question)
            print("\n" + answer)
        
        elif choice == '6':
            print("再见！")
            break
        
        else:
            print("无效选项，请重新选择")


if __name__ == "__main__":
    main()

