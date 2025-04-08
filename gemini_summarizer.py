#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import datetime
import pytz
import requests
import logging
import sys
import argparse

# 设置日志
log_format = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
log_datefmt = '%Y-%m-%d %H:%M:%S %z'

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt=log_datefmt,
    handlers=[
        # 标准输出处理器，确保日志在Render平台上可见
        logging.StreamHandler(sys.stdout)
    ]
)

# 设置模块日志记录器
logger = logging.getLogger("gemini_summarizer")
logger.setLevel(logging.INFO)

# 常量定义
TRANSCRIPTS_DIR = "Transcripts"
BRIEF_DIR = "brief"

# 从环境变量获取Gemini模型名称，如果未设置则使用默认值
DEFAULT_MODEL = "gemini-2.5-pro-exp-03-25"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def ensure_dir_exists(directory):
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"创建目录: {directory}")


# 默认提示词模板
DEFAULT_PROMPT = """你是一位资深新闻编辑，请对这份 Lex Fridman 播客单集的逐字稿脚本，进行专业综述。请遵循以下要求：

# 综述格式
1. 综述文本为简体中文
2. 使用Markdown格式输出
3. 每篇综述请参照逐字稿脚本 Table of Contents 中的时间码标题，设置综述文章的各个小标题，并使用二级标题(##)

# 内容要求
1. 准确提炼逐字稿脚本的核心论点和关键信息
2. 突出重要的数据、引用和具体事实
3. 保持客观中立的叙述语气
4. 按照文章在原文中的顺序进行综述
5. 确保对每篇文章都进行完整的总结
6. 综述的文字量，可以比较长

# 注意事项
1. 直接输出综述内容，不要加入任何与综述无关的回应性语句
2. 保持专业的编辑视角，注重新闻价值的提炼
3. 适当保留原文的叙事结构和重要细节"""


def load_articles(file_path=None):
    """加载指定路径的播客逐字稿，如果未指定路径则加载最新的逐字稿"""
    try:
        # 如果未提供文件路径，获取最新的逐字稿文件
        if not file_path:
            # 获取Transcripts目录下的所有文件
            ensure_dir_exists(TRANSCRIPTS_DIR)
            transcript_files = [f for f in os.listdir(TRANSCRIPTS_DIR) if f.endswith('.md')]
            
            if not transcript_files:
                logger.error(f"在 {TRANSCRIPTS_DIR} 目录下未找到任何逐字稿文件")
                return None
                
            # 按文件名排序（文件名格式为：YYYYMMDD - #XXX – 标题.md）
            transcript_files.sort(reverse=True)
            file_path = os.path.join(TRANSCRIPTS_DIR, transcript_files[0])
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None
        
        # 加载并解析markdown文件
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 从文件名中提取播客标题
        podcast_title = os.path.basename(file_path).split('.')[0]
        
        # 解析逐字稿内容
        # 创建一个包含所有必要信息的字典
        transcript_data = {
            'title': podcast_title,
            'content': content,
            'file_path': file_path
        }
        
        # 提取元数据（如日期、链接等）
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('- **日期**:'):
                transcript_data['date'] = line.split(':')[1].strip()
            elif line.startswith('- **链接**:'):
                transcript_data['url'] = line.split(':')[1].strip()
            elif line.startswith('Table of Contents'):
                # 记录目录位置，可能对生成摘要有用
                transcript_data['toc_index'] = i
        
        logger.info(f"成功加载逐字稿: {podcast_title}")
        return [transcript_data]  # 返回包含单个逐字稿数据的列表
    except Exception as e:
        logger.error(f"加载逐字稿失败: {str(e)}")
        return None


def call_gemini_api(api_key=None, prompt=None, articles=None):
    """调用Gemini API生成摘要"""
    try:
        # 如果未提供API密钥，从环境变量获取
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                logger.error("未提供API密钥且环境变量GEMINI_API_KEY未设置")
                return None
        
        # 构建请求数据
        # 修改API请求参数
        request_data = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"text": json.dumps(articles, ensure_ascii=False)}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 1.0,  # 降低温度以获得更稳定的输出
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1000000
            }
        }
        
        # 发送请求
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        
        # 获取当前的API URL（可能已被环境变量更新）
        current_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{os.environ.get('GEMINI_MODEL', GEMINI_MODEL)}:generateContent"
        
        response = requests.post(
            current_api_url,
            headers=headers,
            json=request_data
        )
        
        # 检查响应
        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and len(result["candidates"]) > 0:
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                logger.info("成功生成摘要")
                return text
            else:
                logger.error(f"API响应中没有找到候选结果: {result}")
        else:
            logger.error(f"API请求失败，状态码: {response.status_code}, 响应: {response.text}")
        
        return None
    except Exception as e:
        logger.error(f"调用Gemini API失败: {str(e)}")
        return None


def save_brief(content, podcast_title):
    """保存播客综述"""
    try:
        # 确保目录存在
        ensure_dir_exists(BRIEF_DIR)
        
        # 构建文件路径，使用播客标题作为文件名
        # 移除文件名中可能导致问题的字符
        safe_title = podcast_title.replace('/', '_').replace('\\', '_')
        filepath = os.path.join(BRIEF_DIR, f"{safe_title}.md")
        
        # 保存综述
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"播客综述已保存到 {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"保存综述失败: {str(e)}")
        return None


def generate_podcast_brief(api_key=None, file_path=None):
    """生成播客综述"""
    # 使用默认提示词
    prompt = DEFAULT_PROMPT
    logger.info("使用默认提示词模板")
    
    # 如果未提供API密钥，尝试从环境变量获取
    if api_key is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("未提供API密钥且环境变量GEMINI_API_KEY未设置，无法生成综述")
            return False
        logger.info("使用环境变量中的GEMINI_API_KEY")
    
    # 加载逐字稿
    logger.info(f"开始加载逐字稿: {file_path if file_path else '最新'}")
    transcript_data = load_articles(file_path)
    if not transcript_data:
        logger.error(f"逐字稿加载失败，无法继续生成综述")
        return False
    logger.info(f"成功加载逐字稿")
    
    # 调用Gemini API
    logger.info(f"开始调用Gemini API生成摘要")
    summary = call_gemini_api(api_key, prompt, transcript_data)
    if not summary:
        logger.error("Gemini API调用失败，无法生成摘要")
        return False
    logger.info("Gemini API调用成功，已获取摘要")
    
    # 保存综述
    logger.info(f"开始保存综述")
    podcast_title = transcript_data[0]['title']
    filepath = save_brief(summary, podcast_title)
    if not filepath:
        logger.error("综述保存失败")
        return False
    logger.info(f"综述已成功保存到: {filepath}")
    
    return True


def main(target_file=None):
    """主函数，处理指定的转录文件或所有转录文件
    Args:
        target_file: 指定要处理的转录文件名，如果为None则处理最新的转录文件
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="使用Gemini API生成Lex Fridman播客综述")
    parser.add_argument("--api-key", help="Gemini API密钥，如果未提供则使用环境变量GEMINI_API_KEY")
    parser.add_argument("--file", help="指定逐字稿文件路径，默认使用最新的逐字稿")
    parser.add_argument("--model", help="指定Gemini模型名称，如果未提供则使用环境变量GEMINI_MODEL或默认值")
    args = parser.parse_args()
    
    # 如果提供了模型名称，设置环境变量
    if args.model:
        os.environ["GEMINI_MODEL"] = args.model
        logger.info(f"使用命令行指定的模型: {args.model}")
    
    # 如果提供了API密钥，设置环境变量
    if args.api_key:
        os.environ["GEMINI_API_KEY"] = args.api_key
        logger.info("使用命令行提供的API密钥")
    
    # 确保目录存在
    ensure_dir_exists(BRIEF_DIR)
    ensure_dir_exists(TRANSCRIPTS_DIR)
    
    # 如果提供了目标文件，构建完整的文件路径
    if target_file:
        file_path = os.path.join(TRANSCRIPTS_DIR, target_file)
    else:
        file_path = args.file

    # 生成播客综述
    success = generate_podcast_brief(file_path=file_path)
    
    if success:
        logger.info("播客综述生成成功")
    else:
        logger.error("播客综述生成失败")


if __name__ == "__main__":
    main()