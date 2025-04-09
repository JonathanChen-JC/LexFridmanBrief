#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from git_sync import GitSync
from lex_transcript_scraper import LexFridmanTranscriptScraper
from gemini_summarizer import load_articles, call_gemini_api, save_brief, DEFAULT_PROMPT
from rss_generator import update_feed
from flask import Flask, send_file, Response
from threading import Thread
import aiohttp

# 设置日志
log_format = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
log_datefmt = '%Y-%m-%d %H:%M:%S %z'

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt=log_datefmt,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 设置模块日志记录器
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)

# 创建Flask应用
app = Flask(__name__)

@app.route('/feed.xml')
def serve_feed():
    try:
        return send_file('feed.xml', mimetype='application/rss+xml')
    except Exception as e:
        logger.error(f"提供feed.xml失败: {e}")
        return Response(status=500)

def run_flask():
    app.run(host='0.0.0.0', port=5000)

class PodcastUpdater:
    def __init__(self):
        self.scraper = LexFridmanTranscriptScraper()
        self.last_check_time = datetime.now(ZoneInfo('Asia/Shanghai'))
        try:
            self.git_sync = GitSync()
        except Exception as e:
            logger.warning(f"Git同步功能初始化失败: {e}")
            self.git_sync = None
    
    async def init_feed(self):
        """初始化feed.xml，对比本地和远程版本"""
        try:
            if self.git_sync:
                # 获取并对比远程feed.xml，自动选择最新版本
                logger.info("正在对比本地和远程feed.xml版本...")
                self.git_sync.pull_feed()
                
                # 如果本地feed.xml不存在，则创建新的feed
                if not os.path.exists('feed.xml'):
                    update_feed()
            else:
                # 如果Git同步不可用，直接更新feed
                update_feed()
            
            logger.info("Feed初始化完成")
        except Exception as e:
            logger.error(f"Feed初始化失败: {e}")
    
    async def check_and_update(self):
        """检查播客更新并处理新内容"""
        try:
            # 检查新的播客内容
            new_episodes = await self.scraper.check_new_episodes()
            if not new_episodes:
                logger.info("没有新的播客内容")
                return
            
            # 处理每个新的播客
            for episode in new_episodes:
                # 获取完整的逐字稿
                if not self.scraper.process_entry(episode):
                    logger.error(f"获取逐字稿失败: {episode['title']}")
                    continue
                
                # 加载最新的逐字稿
                articles = load_articles()
                if not articles:
                    logger.error("无法加载逐字稿")
                    continue
                
                # 生成综述
                summary = call_gemini_api(prompt=DEFAULT_PROMPT, articles=articles)
                if not summary:
                    logger.error("生成综述失败")
                    continue
                
                # 保存综述
                save_brief(summary, articles[0]['title'])
                
                # 更新feed
                update_feed()
                
                # 如果Git同步可用，将更新后的feed推送到仓库
                if self.git_sync:
                    try:
                        self.git_sync.commit_and_push_feed()
                        logger.info("成功将更新后的feed.xml推送到Git仓库")
                    except Exception as e:
                        logger.error(f"推送feed.xml到Git仓库失败: {e}")
                
                logger.info(f"成功处理新的播客: {articles[0]['title']}")
            
            self.last_check_time = datetime.now(ZoneInfo('Asia/Shanghai'))
        except Exception as e:
            logger.error(f"检查和更新播客失败: {e}")
    
    async def self_ping(self):
        """自检功能，每5分钟ping一次服务地址以保持活跃"""
        service_url = os.getenv('RENDER_SERVICE_URL')
        if not service_url:
            logger.warning("未设置RENDER_SERVICE_URL环境变量，无法执行自检保活")
            return

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(service_url) as response:
                        if response.status == 200:
                            logger.info(f"服务保活ping成功: {service_url}")
                        else:
                            logger.warning(f"服务保活ping返回非200状态码: {response.status}")
                except Exception as e:
                    logger.error(f"服务保活ping失败: {e}")
                await asyncio.sleep(300)  # 5分钟

    async def periodic_check(self):
        """定期检查播客更新"""
        while True:
            try:
                await self.check_and_update()
                await asyncio.sleep(21600)  # 6小时
            except Exception as e:
                logger.error(f"定期检查失败: {e}")
                await asyncio.sleep(300)  # 发生错误时等待5分钟后重试

async def main():
    updater = PodcastUpdater()
    
    # 启动Flask服务器
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 初始化feed
    try:
        await updater.init_feed()
    except Exception as e:
        logger.warning(f"Feed初始化失败，但不影响服务器运行: {e}")
    
    # 创建任务
    tasks = [
        updater.periodic_check(),
        updater.self_ping()
    ]
    
    # 运行所有任务
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已停止")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")