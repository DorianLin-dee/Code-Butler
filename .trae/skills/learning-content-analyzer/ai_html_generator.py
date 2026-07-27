#!/usr/bin/env python3
"""
AI 深度分析 HTML 生成器

接收结构化的深度分析数据（由 AI/LLM 提炼），生成高质量 HTML 页面。
与 dialogue_extractor.py 的区别：
  - dialogue_extractor.py：基于规则的启发式快速预览，秒级生成，适合粗略浏览
  - ai_html_generator.py：AI 深度分析版本，经过提炼总结，质量更高，需要 AI 参与

数据结构（传递给 generate_html 的 analysis dict）：
{
    "title": "标题",
    "subtitle": "副标题/简介",
    "speakers": ["张津剑", "秦深涛"],
    "duration": "77分钟",
    "source": "B站 BV1j3VA6zECQ",

    "mindmap": {
        "root": "神经接口的下一个十年",
        "nodes": [
            {
                "label": "核心概念",
                "children": [
                    {"label": "MUAP 运动单位动作电位", "detail": "..."},
                    {"label": "Neural Mismatch 神经失配", "detail": "..."},
                    ...
                ]
            },
            ...
        ]
    },

    "tech_concepts": [
        {
            "name": "MUAP",
            "full_name": "Motor Unit Action Potential（运动单位动作电位）",
            "category": "神经生理学",
            "explanation": "深度解释...",
            "importance": "高",
            "related": ["Neural Mismatch", "肌肉募集"]
        },
        ...
    ],

    "modules": [
        {
            "title": "技术路径",
            "color": "indigo",
            "key_points": [
                {
                    "title": "为什么从肌电切入",
                    "content": "深度分析...",
                    "evidence": ["原文段落1", "原文段落2"]
                },
                ...
            ]
        },
        ...
    ],

    "golden_quotes": [
        {
            "text": "生命力就是 life in gaming",
            "speaker": "秦深涛",
            "context": "关于生命力的理解"
        },
        ...
    ],

    "core_insights": [
        {
            "title": "非侵入式运动神经接口是人机交互的下一个变量",
            "content": "深度解读...",
            "impact": "高"
        },
        ...
    ],

    "transcript_path": "原始转录稿路径（可选）"
}
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any


# ============================================================
# 五色分区系统（与 learning-with-ai 设计系统一致）
# ============================================================
COLOR_MAP = {
    'indigo': {
        'bg': 'bg-indigo-50', 'text': 'text-indigo-600',
        'border': 'border-indigo-200', 'ring': 'ring-indigo-200',
        'dot': 'bg-indigo-500', 'gradient': 'from-indigo-500 to-indigo-600',
        'soft': 'bg-indigo-100/50',
    },
    'teal': {
        'bg': 'bg-teal-50', 'text': 'text-teal-600',
        'border': 'border-teal-200', 'ring': 'ring-teal-200',
        'dot': 'bg-teal-500', 'gradient': 'from-teal-500 to-teal-600',
        'soft': 'bg-teal-100/50',
    },
    'amber': {
        'bg': 'bg-amber-50', 'text': 'text-amber-600',
        'border': 'border-amber-200', 'ring': 'ring-amber-200',
        'dot': 'bg-amber-500', 'gradient': 'from-amber-500 to-amber-600',
        'soft': 'bg-amber-100/50',
    },
    'sky': {
        'bg': 'bg-sky-50', 'text': 'text-sky-600',
        'border': 'border-sky-200', 'ring': 'ring-sky-200',
        'dot': 'bg-sky-500', 'gradient': 'from-sky-500 to-sky-600',
        'soft': 'bg-sky-100/50',
    },
    'rose': {
        'bg': 'bg-rose-50', 'text': 'text-rose-600',
        'border': 'border-rose-200', 'ring': 'ring-rose-200',
        'dot': 'bg-rose-500', 'gradient': 'from-rose-500 to-rose-600',
        'soft': 'bg-rose-100/50',
    },
    'purple': {
        'bg': 'bg-purple-50', 'text': 'text-purple-600',
        'border': 'border-purple-200', 'ring': 'ring-purple-200',
        'dot': 'bg-purple-500', 'gradient': 'from-purple-500 to-purple-600',
        'soft': 'bg-purple-100/50',
    },
    'emerald': {
        'bg': 'bg-emerald-50', 'text': 'text-emerald-600',
        'border': 'border-emerald-200', 'ring': 'ring-emerald-200',
        'dot': 'bg-emerald-500', 'gradient': 'from-emerald-500 to-emerald-600',
        'soft': 'bg-emerald-100/50',
    },
}


def get_color(color_name):
    """获取颜色配置，默认 indigo"""
    return COLOR_MAP.get(color_name, COLOR_MAP['indigo'])


def render_mindmap_mermaid(mindmap):
    """渲染 Mermaid 思维导图（经过 AI 提炼的节点）

    支持最多 3 层：根节点 → 一级分支 → 二级节点
    """
    root = mindmap.get('root', '思维导图')
    nodes = mindmap.get('nodes', [])

    lines = ['mindmap', f'  root((("{root}"))']

    for i, node in enumerate(nodes):
        label = node.get('label', '')
        children = node.get('children', [])

        icon = ':::icon'
        lines.append(f'    {label}{icon}')

        for child in children:
            child_label = child.get('label', '')
            detail = child.get('detail', '')
            if detail:
                lines.append(f'      {child_label}')
                lines.append(f'        {detail[:60]}')
            else:
                lines.append(f'      {child_label}')

    return '\n'.join(lines)


def render_tech_concepts(tech_concepts):
    """渲染技术概念深度解析卡片"""
    if not tech_concepts:
        return ''

    html_parts = []
    html_parts.append('''
    <div class="mb-12">
        <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
            <span class="w-1 h-6 bg-gradient-to-b from-purple-500 to-indigo-500 rounded-full"></span>
            技术概念深度解析
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    ''')

    for concept in tech_concepts:
        name = concept.get('name', '')
        full_name = concept.get('full_name', '')
        category = concept.get('category', '')
        explanation = concept.get('explanation', '')
        importance = concept.get('importance', '中')
        related = concept.get('related', [])

        imp_colors = {
            '高': 'bg-rose-100 text-rose-700',
            '中': 'bg-amber-100 text-amber-700',
            '低': 'bg-gray-100 text-gray-600',
        }
        imp_class = imp_colors.get(importance, imp_colors['中'])

        related_html = ''
        if related:
            related_html = '<div class="mt-3 flex flex-wrap gap-2">'
            for r in related:
                related_html += f'<span class="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">#{r}</span>'
            related_html += '</div>'

        card = f'''
            <div class="p-5 bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div class="flex items-start justify-between mb-2">
                    <div>
                        <h3 class="text-lg font-bold text-gray-800">{name}</h3>
                        {f'<p class="text-sm text-gray-500 mt-0.5">{full_name}</p>' if full_name else ''}
                    </div>
                    <span class="text-xs px-2 py-1 rounded-full {imp_class} font-medium">重要性: {importance}</span>
                </div>
                {f'<span class="inline-block text-xs px-2 py-0.5 bg-purple-50 text-purple-600 rounded mb-2">{category}</span>' if category else ''}
                <p class="text-gray-600 text-sm leading-relaxed">{explanation}</p>
                {related_html}
            </div>
        '''
        html_parts.append(card)

    html_parts.append('''
        </div>
    </div>
    ''')

    return '\n'.join(html_parts)


def render_modules(modules):
    """渲染主题模块（AI 深度分析版）"""
    if not modules:
        return ''

    html_parts = []

    for module in modules:
        title = module.get('title', '')
        color_name = module.get('color', 'indigo')
        key_points = module.get('key_points', [])
        color = get_color(color_name)

        html_parts.append(f'''
        <div class="mb-10">
            <div class="flex items-center gap-3 mb-5">
                <span class="w-1 h-7 bg-gradient-to-b {color['gradient']} rounded-full"></span>
                <h2 class="text-xl font-bold text-gray-800">{title}</h2>
                <span class="text-xs px-2 py-1 {color['bg']} {color['text']} rounded-full font-medium">
                    {len(key_points)} 个核心观点
                </span>
            </div>
            <div class="space-y-4">
        ''')

        for j, kp in enumerate(key_points):
            kp_title = kp.get('title', '')
            kp_content = kp.get('content', '')
            evidence = kp.get('evidence', [])

            evidence_html = ''
            if evidence:
                evidence_html = '<div class="mt-3 pl-4 border-l-2 ' + color['border'] + ' ' + color['bg'] + '/30 py-2 rounded-r">'
                evidence_html += '<p class="text-xs font-medium ' + color['text'] + ' mb-1">📝 原文依据</p>'
                for ev in evidence:
                    evidence_html += f'<p class="text-xs text-gray-600 italic">"{ev[:100]}{"..." if len(ev) > 100 else ""}</p>'
                evidence_html += '</div>'

            card = f'''
                <div class="p-4 bg-white rounded-xl border border-gray-100 shadow-sm">
                    <h3 class="font-semibold text-gray-800 mb-2 flex items-start gap-2">
                        <span class="flex-shrink-0 w-5 h-5 {color['bg']} {color['text']} rounded-full flex items-center justify-center text-xs font-bold mt-0.5">
                            {j+1}
                        </span>
                        {kp_title}
                    </h3>
                    <div class="pl-7 text-gray-600 text-sm leading-relaxed">
                        {kp_content}
                    </div>
                    {evidence_html}
                </div>
            '''
            html_parts.append(card)

        html_parts.append('''
            </div>
        </div>
        ''')

    return '\n'.join(html_parts)


def render_golden_quotes(quotes):
    """渲染金句卡片（AI 精选）"""
    if not quotes:
        return ''

    html_parts = []
    html_parts.append('''
    <div class="mb-12">
        <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
            <span class="w-1 h-6 bg-gradient-to-b from-amber-500 to-rose-500 rounded-full"></span>
            金句精选
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    ''')

    for i, quote in enumerate(quotes):
        text = quote.get('text', '')
        speaker = quote.get('speaker', '')
        context = quote.get('context', '')

        card = f'''
            <div class="p-5 bg-gradient-to-br from-amber-50 to-rose-50 rounded-xl border border-amber-100 relative overflow-hidden">
                <div class="absolute top-2 right-3 text-4xl text-amber-200 font-serif">"</div>
                <p class="text-gray-700 font-medium leading-relaxed relative z-10">
                    {text}
                </p>
                <div class="mt-3 flex items-center justify-between">
                    <span class="text-sm text-amber-700 font-medium">—— {speaker}</span>
                    {f'<span class="text-xs text-gray-500">{context}</span>' if context else ''}
                </div>
            </div>
        '''
        html_parts.append(card)

    html_parts.append('''
        </div>
    </div>
    ''')

    return '\n'.join(html_parts)


def render_core_insights(insights):
    """渲染核心洞察（AI 提炼的最有价值的洞察）"""
    if not insights:
        return ''

    html_parts = []
    html_parts.append('''
    <div class="mb-12">
        <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
            <span class="w-1 h-6 bg-gradient-to-b from-rose-500 to-purple-500 rounded-full"></span>
            核心洞察
        </h2>
        <div class="space-y-4">
    ''')

    for insight in insights:
        title = insight.get('title', '')
        content = insight.get('content', '')
        impact = insight.get('impact', '中')

        imp_colors = {
            '高': {'dot': 'bg-rose-500', 'text': 'text-rose-600', 'bg': 'bg-rose-50'},
            '中': {'dot': 'bg-amber-500', 'text': 'text-amber-600', 'bg': 'bg-amber-50'},
            '低': {'dot': 'bg-gray-400', 'text': 'text-gray-600', 'bg': 'bg-gray-50'},
        }
        ic = imp_colors.get(impact, imp_colors['中'])

        card = f'''
            <div class="p-5 {ic['bg']} rounded-xl border border-gray-100">
                <div class="flex items-start gap-3">
                    <div class="flex-shrink-0 w-2 h-2 {ic['dot']} rounded-full mt-2"></div>
                    <div>
                        <h3 class="font-bold text-gray-800 mb-2">{title}</h3>
                        <p class="text-gray-600 text-sm leading-relaxed">{content}</p>
                    </div>
                </div>
            </div>
        '''
        html_parts.append(card)

    html_parts.append('''
        </div>
    </div>
    ''')

    return '\n'.join(html_parts)


def render_header(analysis):
    """渲染页头"""
    title = analysis.get('title', '深度分析')
    subtitle = analysis.get('subtitle', '')
    speakers = analysis.get('speakers', [])
    duration = analysis.get('duration', '')
    source = analysis.get('source', '')

    speakers_html = ''
    if speakers:
        speakers_html = '<div class="flex flex-wrap gap-2 mt-3">'
        for spk in speakers:
            speakers_html += f'<span class="px-3 py-1 bg-white/60 backdrop-blur-sm text-indigo-700 rounded-full text-sm font-medium">{spk}</span>'
        speakers_html += '</div>'

    meta_html = ''
    meta_items = []
    if duration:
        meta_items.append(f'⏱️ {duration}')
    if source:
        meta_items.append(f'📺 {source}')
    if meta_items:
        meta_html = '<div class="flex flex-wrap gap-4 mt-3 text-sm text-indigo-200">'
        meta_html += ' · '.join(meta_items)
        meta_html += '</div>'

    return f'''
    <header class="relative overflow-hidden mb-12">
        <div class="absolute inset-0 bg-gradient-to-br from-indigo-600 via-purple-600 to-rose-500">
            <div class="absolute inset-0 opacity-10">
                <svg class="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                    <defs>
                        <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
                            <path d="M 10 0 L 0 0 0 10" fill="none" stroke="white" stroke-width="0.5" opacity="0.3"/>
                        </pattern>
                    </defs>
                    <rect width="100" height="100" fill="url(#grid)"/>
                </svg>
            </div>
        </div>
        <div class="relative px-8 py-16 md:py-20">
            <div class="max-w-4xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 bg-white/10 backdrop-blur-sm rounded-full text-white/80 text-sm mb-4">
                    <span>AI 深度分析版</span>
                    <span class="w-1 h-1 bg-white/40 rounded-full"></span>
                    <span>豆包模型生成</span>
                </div>
                <h1 class="text-3xl md:text-4xl font-bold text-white leading-tight">
                    {title}
                </h1>
                {f'<p class="mt-3 text-lg text-indigo-100">{subtitle}</p>' if subtitle else ''}
                {speakers_html}
                {meta_html}
            </div>
        </div>
        <div class="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-gray-50 to-transparent"></div>
    </header>
    '''


def render_mindmap_section(mindmap):
    """渲染思维导图区域"""
    mermaid_code = render_mindmap_mermaid(mindmap)

    return f'''
    <div class="mb-12">
        <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
            <span class="w-1 h-6 bg-gradient-to-b from-teal-500 to-emerald-500 rounded-full"></span>
            思维导图
            <span class="text-xs font-normal text-gray-500 ml-2">（AI 提炼版）</span>
        </h2>
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <div class="mermaid-wrap overflow-x-auto">
                <pre class="mermaid! hidden">{mermaid_code}</pre>
                <div id="mindmap-container" class="min-h-[400px] flex items-center justify-center">
                    <div class="text-gray-400 text-sm">加载思维导图中...</div>
                </div>
            </div>
        </div>
    </div>
    '''


def generate_html(analysis: Dict[str, Any], output_path: str = None) -> str:
    """生成 AI 深度分析 HTML

    Args:
        analysis: 结构化分析数据
        output_path: 输出文件路径（可选）

    Returns:
        str: HTML 内容
    """

    page_title = analysis.get('title', '深度分析')
    header = render_header(analysis)
    mindmap_section = render_mindmap_section(analysis.get('mindmap', {}))
    tech_section = render_tech_concepts(analysis.get('tech_concepts', []))
    modules_html = render_modules(analysis.get('modules', []))
    quotes_html = render_golden_quotes(analysis.get('golden_quotes', []))
    insights_html = render_core_insights(analysis.get('core_insights', []))

    html_parts = []
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="zh-CN">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'    <title>{page_title}</title>')
    html_parts.append('    <script src="https://cdn.tailwindcss.com"></script>')
    html_parts.append('    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>')
    html_parts.append('    <style>')
    html_parts.append('        body {')
    html_parts.append('            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",')
    html_parts.append('                         "Hiragino Sans GB", "Microsoft YaHei", sans-serif;')
    html_parts.append('            background: #f9fafb;')
    html_parts.append('        }')
    html_parts.append('        .mermaid {')
    html_parts.append('            display: flex;')
    html_parts.append('            justify-content: center;')
    html_parts.append('        }')
    html_parts.append('        .mermaid svg {')
    html_parts.append('            max-width: 100%;')
    html_parts.append('            height: auto;')
    html_parts.append('        }')
    html_parts.append('        ::-webkit-scrollbar {')
    html_parts.append('            width: 6px;')
    html_parts.append('            height: 6px;')
    html_parts.append('        }')
    html_parts.append('        ::-webkit-scrollbar-track {')
    html_parts.append('            background: #f1f5f9;')
    html_parts.append('        }')
    html_parts.append('        ::-webkit-scrollbar-thumb {')
    html_parts.append('            background: #cbd5e1;')
    html_parts.append('            border-radius: 3px;')
    html_parts.append('        }')
    html_parts.append('        ::-webkit-scrollbar-thumb:hover {')
    html_parts.append('            background: #94a3b8;')
    html_parts.append('        }')
    html_parts.append('    </style>')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append(header)
    html_parts.append('')
    html_parts.append('    <main class="max-w-5xl mx-auto px-4 pb-20">')
    html_parts.append('        ' + mindmap_section.strip())
    html_parts.append('        ' + insights_html.strip())
    html_parts.append('        ' + tech_section.strip())
    html_parts.append('        ' + modules_html.strip())
    html_parts.append('        ' + quotes_html.strip())
    html_parts.append('    </main>')
    html_parts.append('')
    html_parts.append('    <footer class="border-t border-gray-200 bg-white py-8 mt-12">')
    html_parts.append('        <div class="max-w-5xl mx-auto px-4 text-center text-gray-500 text-sm">')
    html_parts.append('            <p>AI 深度分析 · 豆包模型生成 · 仅供学习参考</p>')
    html_parts.append('            <p class="mt-1 text-gray-400 text-xs">本分析由 AI 自动生成，可能存在偏差，请结合原文理解</p>')
    html_parts.append('        </div>')
    html_parts.append('    </footer>')
    html_parts.append('')
    html_parts.append('    <script>')
    html_parts.append('        mermaid.initialize({')
    html_parts.append('            startOnLoad: false,')
    html_parts.append('            theme: "default",')
    html_parts.append('            mindmap: {')
    html_parts.append('                padding: 20,')
    html_parts.append('                maxNodeWidth: 200')
    html_parts.append('            }')
    html_parts.append('        });')
    html_parts.append('')
    html_parts.append('        async function renderMindmap() {')
    html_parts.append('            try {')
    html_parts.append('                const pre = document.querySelector(".mermaid!");')
    html_parts.append('                if (!pre) return;')
    html_parts.append('                const code = pre.textContent;')
    html_parts.append('                const container = document.getElementById("mindmap-container");')
    html_parts.append('                const { svg } = await mermaid.render("mindmap-svg", code);')
    html_parts.append('                container.innerHTML = svg;')
    html_parts.append('            } catch (e) {')
    html_parts.append('                console.error("Mermaid 渲染失败:", e);')
    html_parts.append('                document.getElementById("mindmap-container").innerHTML =')
    html_parts.append('                    \'<div class="text-gray-500 text-sm">思维导图渲染失败，请刷新重试</div>\';')
    html_parts.append('            }')
    html_parts.append('        }')
    html_parts.append('')
    html_parts.append('        renderMindmap();')
    html_parts.append('    </script>')
    html_parts.append('</body>')
    html_parts.append('</html>')

    html = '\n'.join(html_parts)

    if output_path:
        Path(output_path).write_text(html, encoding='utf-8')

    return html


def save_analysis_json(analysis: Dict[str, Any], output_path: str):
    """保存分析数据为 JSON，方便后续复用"""
    Path(output_path).write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def load_analysis_json(input_path: str) -> Dict[str, Any]:
    """从 JSON 加载分析数据"""
    return json.loads(Path(input_path).read_text(encoding='utf-8'))


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("用法: python3 ai_html_generator.py <analysis.json> <output.html>")
        print()
        print("从 JSON 格式的深度分析数据生成 HTML 页面")
        print("JSON 结构请参考文件顶部注释")
        sys.exit(0)

    analysis = load_analysis_json(sys.argv[1])
    generate_html(analysis, sys.argv[2])
    print(f"✅ HTML 已生成: {sys.argv[2]}")
