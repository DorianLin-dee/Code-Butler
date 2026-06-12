# 📚 Related Work 分析工具使用指南

## 🚀 一句话搞定

```
"帮我分析论文 /path/to/paper.pdf 的 Related Work"
```

工具会自动完成：
1. 📄 提取 PDF 文本
2. 🔍 识别 Related Work 部分
3. 📋 提取引用论文列表
4. 🔗 搜索免费链接
5. 🧠 生成思维导图
6. 💡 总结创新点

---

## 📋 输出内容

### 1. 引用论文表格
| 论文 | 年份 | DOI | 免费链接 | 研究方向 |
|------|------|-----|----------|----------|
| Author | 2020 | 10.xxx | ACM | 主题 |

### 2. 研究脉络思维导图
```
├─ 主题1
│   ├─ Author [2020]
│   └─ ...
├─ 主题2
│   ├─ Author [2019]
│   └─ ...
```

### 3. 核心论文标注
- ⭐ 标注里程碑论文
- 提供 DOI 链接
- 总结创新点

---

## 🛠️ 命令行使用

```bash
# 基本用法
python3 related_work_analyzer.py paper.pdf

# 指定输出路径
python3 related_work_analyzer.py "/Users/xxx/paper.pdf"
```

---

## 📖 示例

### 输入
```
"帮我分析论文 /Users/dorian/thesis/paper.pdf 的 Related Work"
```

### 输出
```
✅ 识别 31 篇引用论文
✅ 研究主题: Deployable Structures, Gridshells, Auxetics, etc.

🧠 研究脉络思维导图
├─ Deployable Structures
│   ├─ Pottmann [2015] ⭐
│   ├─ Dudte [2016]
│   └─ ...
├─ Gridshells
│   ├─ Lienhard [2013]
│   └─ ...
```

---

## 💡 泛化能力

✅ **任何学术论文** - 计算机、机械、建筑等  
✅ **任何引用格式** - ACM、IEEE、Springer 等  
✅ **任何章节名** - Related Work, Background, Prior Work 等  
✅ **任何 PDF** - 文本型 PDF（非扫描版）

---

## ⚠️ 注意事项

1. PDF 必须是文本型（可复制文字）
2. 扫描版 PDF 需要 OCR 处理
3. 免费链接尽力搜索，可能部分论文无免费版本

---

## 🔗 相关资源

- ACM DL: https://dl.acm.org
- IEEE: https://ieeexplore.ieee.org
- arXiv: https://arxiv.org
- Google Scholar: https://scholar.google.com
