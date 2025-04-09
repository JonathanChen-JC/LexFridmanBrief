#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import base64
import requests
from datetime import datetime
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

class GitSync:
    def __init__(self):
        """初始化GitSync类，设置Git仓库配置"""
        self.repo_url = os.getenv('GIT_REPO_URL')
        self.branch = os.getenv('GIT_BRANCH', 'main')
        self.username = os.getenv('GIT_USERNAME')
        self.token = os.getenv('GIT_TOKEN')
        
        if not all([self.repo_url, self.username, self.token]):
            raise ValueError('缺少必要的Git配置环境变量')
        
        # 解析仓库信息
        if self.repo_url.startswith('https://github.com/'):
            self.repo_info = self.repo_url.replace('https://github.com/', '').strip('/')
            self.repo_owner, self.repo_name = self.repo_info.split('/')
        else:
            raise ValueError('仓库URL必须是GitHub HTTPS URL格式')
        
        self.work_dir = os.path.dirname(os.path.abspath(__file__))
    
    def _get_github_file_content(self, file_path: str) -> str:
        """从GitHub获取文件内容"""
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}?ref={self.branch}"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {self.token}"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                content_data = response.json()
                if content_data.get("encoding") == "base64":
                    content = base64.b64decode(content_data["content"]).decode("utf-8")
                    logger.info(f"成功从GitHub获取文件: {file_path}")
                    return content
                else:
                    logger.error(f"不支持的编码: {content_data.get('encoding')}")
            elif response.status_code == 404:
                logger.warning(f"GitHub上未找到文件: {file_path}")
            else:
                logger.error(f"获取GitHub文件失败，状态码: {response.status_code}")
            
            return None
        except Exception as e:
            logger.error(f"从GitHub获取文件时出错: {str(e)}")
            return None
    
    def _update_github_file(self, file_path: str, content: str, commit_message: str) -> bool:
        """更新GitHub上的文件"""
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {self.token}"
            }
            
            # 获取文件的SHA
            response = requests.get(url, headers=headers)
            file_sha = None
            if response.status_code == 200:
                file_sha = response.json()["sha"]
            elif response.status_code != 404:
                logger.error(f"获取文件信息失败，状态码: {response.status_code}")
                return False
            
            # 准备更新数据
            update_data = {
                "message": commit_message,
                "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
                "branch": self.branch
            }
            if file_sha:
                update_data["sha"] = file_sha
            
            # 发送更新请求
            response = requests.put(url, headers=headers, json=update_data)
            
            if response.status_code in [200, 201]:
                logger.info(f"成功更新GitHub文件: {file_path}")
                return True
            else:
                logger.error(f"更新GitHub文件失败，状态码: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"更新GitHub文件时出错: {str(e)}")
            return False
    
    def _get_feed_date(self, feed_content: str) -> datetime:
        """从XML内容中解析lastBuildDate"""
        try:
            if not feed_content:
                return None
            
            root = ET.fromstring(feed_content)
            
            # 首先尝试获取lastBuildDate
            last_build_date = root.find("./channel/lastBuildDate")
            if last_build_date is not None and last_build_date.text:
                try:
                    return parsedate_to_datetime(last_build_date.text)
                except ValueError:
                    pass
            
            # 如果没有lastBuildDate，尝试获取最新的pubDate
            items = root.findall("./channel/item")
            if items:
                pub_date = items[0].find("pubDate")
                if pub_date is not None and pub_date.text:
                    try:
                        return parsedate_to_datetime(pub_date.text)
                    except ValueError:
                        pass
            
            return None
        except Exception as e:
            logger.error(f"解析lastBuildDate时出错: {str(e)}")
            return None
    
    def pull_feed(self):
        """从远程仓库获取feed.xml文件"""
        try:
            # 获取GitHub上的feed.xml内容
            github_content = self._get_github_file_content('feed.xml')
            
            # 读取本地feed.xml内容
            local_feed_path = os.path.join(self.work_dir, 'feed.xml')
            local_content = None
            if os.path.exists(local_feed_path):
                with open(local_feed_path, 'r', encoding='utf-8') as f:
                    local_content = f.read()
            
            # 解析日期
            local_date = self._get_feed_date(local_content) if local_content else None
            github_date = self._get_feed_date(github_content) if github_content else None
            
            # 根据日期选择使用哪个版本
            if github_date and (not local_date or github_date > local_date):
                # 使用GitHub版本
                with open(local_feed_path, 'w', encoding='utf-8') as f:
                    f.write(github_content)
                logger.info('已更新为远程feed.xml版本')
            else:
                logger.info('保留本地feed.xml版本')
        
        except Exception as e:
            logger.error(f"获取feed.xml失败: {str(e)}")
    
    def commit_and_push_feed(self):
        """提交并推送feed.xml到远程仓库"""
        try:
            local_feed_path = os.path.join(self.work_dir, 'feed.xml')
            if not os.path.exists(local_feed_path):
                raise FileNotFoundError('feed.xml文件不存在')
            
            # 读取本地文件内容
            with open(local_feed_path, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            # 更新GitHub文件
            commit_message = f'更新feed.xml - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            success = self._update_github_file('feed.xml', local_content, commit_message)
            
            if success:
                logger.info('成功将feed.xml推送到GitHub')
            else:
                logger.error('推送feed.xml到GitHub失败')
        
        except Exception as e:
            logger.error(f"推送feed.xml失败: {str(e)}")