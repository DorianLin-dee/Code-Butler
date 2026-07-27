
#!/usr/bin/env python3
"""
Podwise 完整工作流程实现
输入 → 转录 → 抽取Highlights → 关键词提取 → 全文总结 → 思维导图生成 → 存储
"""

import os
import json
import yt_dlp
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️ Whisper未安装，仅支持预转录的内容")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ OpenAI未安装，仅支持基础功能")


class InputProcessor:
    """阶段1: 输入处理模块"""
    
    def __init__(self, output_dir="./audio_downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process(self, input_source: str) -&gt; str:
        """处理输入源"""
        if os.path.isfile(input_source):
            return self.process_file(input_source)
        elif input_source.startswith(('http://', 'https://')):
            return self.process_url(input_source)
        else:
            raise ValueError(f"不支持的输入类型: {input_source}")
    
    def process_file(self, file_path: str) -&gt; str:
        """处理本地文件"""
        print(f"📁 使用本地文件: {file_path}")
        return file_path
    
    def process_url(self, url: str) -&gt; str:
        """处理网络URL，下载音频"""
        print(f"📥 正在下载音频: {url}")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.output_dir / '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            audio_path = self.output_dir / f"{info['id']}.mp3"
            
            print(f"✅ 下载完成: {audio_path}")
            return str(audio_path)


class WhisperTranscriber:
    """阶段2: 音频转录模块"""
    
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None
        if WHISPER_AVAILABLE:
            print(f"🎤 加载Whisper模型: {model_size}")
            self.model = whisper.load_model(model_size)
    
    def transcribe(self, audio_path: str) -&gt; Dict[str, Any]:
        """转录音频"""
        if not self.model:
            raise RuntimeError("Whisper模型未加载，请先安装: pip install openai-whisper")
        
        print(f"🎙️ 正在转录...")
        result = self.model.transcribe(
            audio_path,
            language="zh",
            word_timestamps=True
        )
        
        transcript_data = self._format_result(result)
        print(f"✅ 转录完成，共 {len(transcript_data['segments'])} 个片段")
        return transcript_data
    
    def _format_result(self, result: Dict[str, Any]) -&gt; Dict[str, Any]:
        """格式化转录结果"""
        segments = []
        for seg in result['segments']:
            segments.append({
                'start': seg['start'],
                'end': seg['end'],
                'text': seg['text'].strip(),
                'start_formatted': self._format_time(seg['start']),
                'end_formatted': self._format_time(seg['end'])
            })
        
        return {
            'full_text': result['text'],
            'segments': segments,
            'language': result.get('language', 'zh')
        }
    
    @staticmethod
    def _format_time(seconds: float) -&gt; str:
        """格式化时间为 HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class ContentAnalyzer:
    """阶段3 &amp; 4: 内容分析模块"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.client = None
        if openai_api_key and OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=openai_api_key)
    
    def analyze(self, transcript: str) -&gt; Dict[str, Any]:
        """完整内容分析"""
        print("🔍 分析内容中...")
        
        if self.client:
            highlights = self._extract_highlights_llm(transcript)
            keywords = self._extract_keywords_llm(transcript)
        else:
            highlights = self._extract_highlights_simple(transcript)
            keywords = self._extract_keywords_simple(transcript)
        
        return {
            'highlights': highlights,
            'keywords': keywords
        }
    
    def _extract_highlights_llm(self, text: str) -&gt; List[Dict]:
        """使用LLM提取Highlights"""
        prompt = f"""
        请从以下播客转录稿中提取最精彩的5-10个片段。
        
        转录稿：
        {text[:8000]}
        
        请输出JSON格式：
        {{
            "highlights": [
                {{
                    "content": "精彩内容片段",
                    "reason": "为什么这段精彩（内容重要/观点独特/幽默风趣等）"
                }}
            ]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return result.get('highlights', [])
        except Exception as e:
            print(f"⚠️ LLM提取失败: {e}")
            return self._extract_highlights_simple(text)
    
    def _extract_highlights_simple(self, text: str) -&gt; List[Dict]:
        """简单规则提取Highlights"""
        sentences = text.split('。')
        highlights = []
        for sentence in sentences[:10]:
            if len(sentence) &gt; 20:
                highlights.append({
                    'content': sentence.strip() + '。',
                    'reason': '自动识别的重点句子'
                })
        return highlights
    
    def _extract_keywords_llm(self, text: str) -&gt; List[str]:
        """使用LLM提取关键词"""
        prompt = f"""
        从以下文本中提取20个最重要的关键词，按重要性排序：
        
        {text[:4000]}
        
        请输出JSON格式：
        {{
            "keywords": ["keyword1", "keyword2", ...]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return result.get('keywords', [])
        except Exception as e:
            print(f"⚠️ LLM提取关键词失败: {e}")
            return self._extract_keywords_simple(text)
    
    def _extract_keywords_simple(self, text: str) -&gt; List[str]:
        """简单规则提取关键词"""
        import re
        words = re.findall(r'[\u4e00-\u9fff]+', text)
        word_counts = {}
        for word in words:
            if len(word) &gt; 1:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:20]]
    
    def generate_summary(self, text: str) -&gt; str:
        """生成全文总结"""
        print("📝 生成总结...")
        
        if self.client:
            return self._generate_summary_llm(text)
        return self._generate_summary_simple(text)
    
    def _generate_summary_llm(self, text: str) -&gt; str:
        """使用LLM生成总结"""
        prompt = f"""
        请为以下播客转录稿生成详细总结。
        
        要求：
        1. 先写一个简短的总览（100字）
        2. 然后按段落分段总结
        3. 最后列出3-5个核心要点
        
        转录稿：
        {text[:12000]}
        """
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    
    def _generate_summary_simple(self, text: str) -&gt; str:
        """简单摘要"""
        sentences = text.split('。')
        summary = "播客内容总结：\n\n"
        summary += "内容要点：\n"
        for i, sentence in enumerate(sentences[:5]):
            summary += f"{i+1}. {sentence.strip()}。\n"
        return summary
    
    def generate_mindmap(self, text: str) -&gt; Dict[str, Any]:
        """生成思维导图数据"""
        print("🧠 生成思维导图...")
        
        if self.client:
            return self._generate_mindmap_llm(text)
        return self._generate_mindmap_simple(text)
    
    def _generate_mindmap_llm(self, text: str) -&gt; Dict[str, Any]:
        """使用LLM生成思维导图"""
        prompt = f"""
        请分析以下内容，生成结构化的思维导图数据。
        
        输出JSON格式：
        {{
            "title": "主标题",
            "children": [
                {{
                    "title": "二级节点",
                    "children": [
                        {{
                            "title": "三级节点",
                            "content": "详细内容"
                        }}
                    ]
                }}
            ]
        }}
        
        内容：
        {text[:8000]}
        """
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    
    def _generate_mindmap_simple(self, text: str) -&gt; Dict[str, Any]:
        """简单思维导图"""
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        return {
            'title': '播客内容',
            'children': [
                {
                    'title': '段落1',
                    'children': [{'title': '内容', 'content': p}]
                }
                for p in paragraphs[:5]
            ]
        }


class DataStorage:
    """阶段5: 数据存储模块"""
    
    def __init__(self, output_dir="./podwise_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, result: Dict[str, Any], id: Optional[str] = None) -&gt; str:
        """保存分析结果"""
        if id is None:
            id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        file_path = self.output_dir / f"{id}_analysis.json"
        
        result['id'] = id
        result['created_at'] = datetime.now().isoformat()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"💾 结果已保存: {file_path}")
        
        self._save_markdown(result, id)
        return id
    
    def _save_markdown(self, result: Dict[str, Any], id: str):
        """保存为Markdown格式"""
        md_path = self.output_dir / f"{id}_report.md"
        
        md = f"# 播客分析报告\n\n"
        md += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if 'summary' in result:
            md += "## 总结\n\n"
            md += f"{result['summary']}\n\n"
        
        if 'analysis' in result:
            if 'highlights' in result['analysis']:
                md += "## 精彩片段\n\n"
                for i, highlight in enumerate(result['analysis']['highlights'], 1):
                    md += f"### {i}. {highlight.get('content', '')}\n"
                    if 'reason' in highlight:
                        md += f"_{highlight['reason']}_\n"
                    md += "\n"
            
            if 'keywords' in result['analysis']:
                md += "## 关键词\n\n"
                keywords = result['analysis']['keywords']
                md += ', '.join(keywords) + "\n\n"
        
        if 'mindmap' in result:
            md += "## 思维导图\n\n"
            md += self._render_mindmap_markdown(result['mindmap'])
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md)
        
        print(f"📄 Markdown报告已保存: {md_path}")
    
    def _render_mindmap_markdown(self, mindmap: Dict[str, Any]) -&gt; str:
        """渲染思维导图为Markdown"""
        md = ""
        def render(node, level=1):
            nonlocal md
            indent = "  " * level
            md += f"{indent}- {node.get('title', '')}\n"
            if 'content' in node:
                md += f"{indent}  {node['content']}\n"
            if 'children' in node:
                for child in node['children']:
                    render(child, level + 1)
        
        render(mindmap)
        return md


class PodwisePipeline:
    """Podwise完整处理流程"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.input_processor = InputProcessor()
        self.transcriber = WhisperTranscriber()
        self.analyzer = ContentAnalyzer(openai_api_key)
        self.storage = DataStorage()
    
    def process(self, input_source: str, use_existing_transcript: Optional[str] = None) -&gt; Dict[str, Any]:
        """完整流程处理"""
        print("\n" + "=" * 60)
        print("🚀 Podwise 分析开始")
        print("=" * 60)
        
        transcript_data = None
        
        if use_existing_transcript:
            print(f"📄 使用现有转录: {use_existing_transcript}")
            with open(use_existing_transcript, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
        else:
            print("\n📥 阶段1: 输入处理...")
            audio_path = self.input_processor.process(input_source)
            
            print("\n🎤 阶段2: 音频转录...")
            transcript_data = self.transcriber.transcribe(audio_path)
        
        print("\n🔍 阶段3: 内容分析...")
        analysis = self.analyzer.analyze(transcript_data['full_text'])
        
        print("\n🧠 阶段4: 生成总结和思维导图...")
        summary = self.analyzer.generate_summary(transcript_data['full_text'])
        mindmap = self.analyzer.generate_mindmap(transcript_data['full_text'])
        
        print("\n💾 阶段5: 数据存储...")
        result = {
            'transcript': transcript_data,
            'analysis': analysis,
            'summary': summary,
            'mindmap': mindmap
        }
        
        id = self.storage.save(result)
        
        print("\n" + "=" * 60)
        print("✅ 全部完成！")
        print(f"🆔 任务ID: {id}")
        print("=" * 60)
        
        return result


def main():
    """主函数演示"""
    import sys
    
    if len(sys.argv) &lt; 2:
        print("用法: python podwise_pipeline.py &lt;播客链接或本地文件&gt;")
        print("示例: python podwise_pipeline.py https://www.xiaoyuzhoufm.com/episode/xxx")
        print("      python podwise_pipeline.py ./audio.mp3")
        print("      python podwise_pipeline.py --transcript transcript.txt")
        sys.exit(1)
    
    source = sys.argv[1]
    api_key = os.environ.get('OPENAI_API_KEY')
    
    pipeline = PodwisePipeline(api_key)
    
    use_transcript = None
    if source == '--transcript' and len(sys.argv) &gt; 2:
        use_transcript = sys.argv[2]
        pipeline.process(source, use_existing_transcript=use_transcript)
    else:
        pipeline.process(source)


if __name__ == "__main__":
    main()

