# Lex Fridman 播客简述生成器

## 项目简介

本项目是一个自动化工具，用于获取 Lex Fridman 播客的内容，并生成中文简述和 RSS 订阅源。它能够自动抓取最新的播客内容，使用 Gemini AI 生成中文综述，并将内容同步到 Git 仓库中。

## 核心功能

### 1. 播客内容抓取 (lex_transcript_scraper.py)
- 自动解析 Lex Fridman 播客的 RSS 源
- 智能查找每个播客条目的 Transcript 链接
- 抓取播客文字记录内容
- 将内容保存为 Markdown 格式，文件名格式：`YYYYMMDD - [播客标题].md`
- 提供完整的日志记录功能

### 2. AI 内容综述 (gemini_summarizer.py)
- 使用 Google Gemini AI 模型生成中文综述
- 智能分析播客内容的核心论点和关键信息
- 保持专业的编辑视角，突出新闻价值
- 使用 Markdown 格式输出，保持良好的结构性
- 支持自定义提示词模板

### 3. RSS 订阅源生成 (rss_generator.py)
- 创建包含中文简述的 RSS Feed
- 自动维护最新的 50 条播客记录
- 支持现有 Feed 的解析和更新
- 确保内容格式规范，适合订阅阅读

### 4. Git 同步管理 (git_sync.py)
- 自动化 Git 仓库操作
- 支持配置远程仓库信息
- 自动拉取和推送更新
- 异常处理和错误日志记录

## 项目结构

```
├── Transcripts/          # 存放原始播客文字记录
├── brief/               # 存放生成的中文简述
├── lex_transcript_scraper.py   # 播客内容抓取模块
├── gemini_summarizer.py        # AI 内容综述模块
├── rss_generator.py           # RSS 生成模块
├── git_sync.py               # Git 同步模块
├── main.py                   # 主程序入口
├── feed.xml                  # 生成的 RSS Feed 文件
└── requirements.txt          # 项目依赖
```

## 环境配置

### 必需的环境变量

1. Gemini API 配置：
```
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-2.5-pro-exp-03-25  # 可选，默认使用最新模型
```

2. Git 仓库配置：
```
GIT_REPO_URL=your_repo_url   # 支持HTTPS格式(https://github.com/username/repo.git)或SSH格式(git@github.com:username/repo.git)
GIT_BRANCH=main              # 可选，默认为 main
GIT_USERNAME=your_username
GIT_TOKEN=your_token
```

## 部署说明

1. 克隆项目并安装依赖：
```bash
git clone <repository_url>
cd LexFridmanBrief
pip install -r requirements.txt
```

2. 配置环境变量：
- 在系统中设置上述必需的环境变量
- 或创建 `.env` 文件并填入配置信息

3. 运行项目：
```bash
python main.py
```

## 使用说明

- 项目会自动获取最新的播客内容并生成中文简述
- 生成的内容会自动同步到 Git 仓库
- 可以通过 RSS 阅读器订阅 `feed.xml` 获取更新
- 查看 `scraper.log` 了解运行状态和错误信息

## 注意事项

- 确保 Gemini API 密钥有足够的配额
- Git 令牌需要有仓库的读写权限
- 建议定期检查日志文件了解运行状态
- 可以根据需要调整 RSS Feed 的条目数量限制