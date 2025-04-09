import os
import subprocess
from datetime import datetime
from typing import Optional
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import logging

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
        
        # 构建带认证的仓库URL
        repo_parts = self.repo_url.split('://')
        self.auth_repo_url = f'https://{self.username}:{self.token}@{repo_parts[1]}' if len(repo_parts) == 2 else self.repo_url
        self.work_dir = os.path.dirname(os.path.abspath(__file__))
    
    def init_repo(self):
        """初始化或更新Git仓库配置"""
        try:
            if not os.path.exists(os.path.join(self.work_dir, '.git')):
                self._execute_git_command(['git', 'init'])
                self._execute_git_command(['git', 'remote', 'add', 'origin', self.auth_repo_url])
            else:
                remote_exists = self._execute_git_command(['git', 'remote'], check=False)
                if 'origin' not in (remote_exists or ''):
                    self._execute_git_command(['git', 'remote', 'add', 'origin', self.auth_repo_url])
                self._execute_git_command(['git', 'remote', 'set-url', 'origin', self.auth_repo_url])
            
            # 验证远程仓库连接
            self._execute_git_command(['git', 'ls-remote', '--exit-code', self.auth_repo_url, self.branch])
            logger.info('Git仓库初始化成功')
        except Exception as e:
            logger.error(f'Git仓库初始化失败: {e}')
            raise
    
    def setup_git_config(self):
        """设置Git配置信息"""
        try:
            self._execute_git_command(['git', 'config', 'user.name', self.username])
            self._execute_git_command(['git', 'config', 'user.email', f'{self.username}@users.noreply.github.com'])
            self._execute_git_command(['git', 'config', 'credential.helper', 'store'])
            self._execute_git_command(['git', 'config', 'pull.rebase', 'false'])
            
            # 配置Git凭证
            credential_input = f'url={self.repo_url}\nusername={self.username}\npassword={self.token}\n'
            self._execute_git_command(['git', 'credential', 'approve'], input=credential_input)
            logger.info('Git配置设置成功')
        except Exception as e:
            logger.error(f'Git配置设置失败: {e}')
            raise
    
    def pull_feed(self):
        """拉取并同步feed.xml文件"""
        try:
            local_feed_path = os.path.join(self.work_dir, 'feed.xml')
            local_date = self._get_feed_date(local_feed_path)

            # 获取远程分支
            self._execute_git_command(['git', 'fetch', 'origin', self.branch])
            self._execute_git_command(['git', 'checkout', self.branch], check=False)
            
            # 检出远程feed.xml
            self._execute_git_command(['git', 'checkout', f'origin/{self.branch}', '--', 'feed.xml'], check=False)
            remote_date = self._get_feed_date(local_feed_path)

            # 根据日期选择最新版本
            if remote_date and (not local_date or remote_date > local_date):
                self._execute_git_command(['git', 'checkout', f'origin/{self.branch}', '--', 'feed.xml'])
                logger.info('已更新为远程feed.xml版本')
            elif os.path.exists(local_feed_path):
                self._execute_git_command(['git', 'checkout', self.branch, '--', 'feed.xml'])
                logger.info('保留本地feed.xml版本')
        except Exception as e:
            logger.error(f'拉取feed.xml失败: {e}')
            raise
    
    def commit_and_push_feed(self):
        """提交并推送feed.xml到远程仓库"""
        try:
            feed_path = os.path.join(self.work_dir, 'feed.xml')
            if not os.path.exists(feed_path):
                raise FileNotFoundError('feed.xml文件不存在')
            
            # 添加并提交更改
            commit_message = f'更新feed.xml - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            self._execute_git_command(['git', 'add', 'feed.xml'])
            
            if not self._execute_git_command(['git', 'commit', '-m', commit_message], check=False):
                logger.info('没有需要提交的更改')
                return
            
            # 推送到远程仓库
            try:
                self._execute_git_command(['git', 'push', 'origin', self.branch])
                logger.info('成功推送到远程仓库')
            except subprocess.CalledProcessError as e:
                if 'non-fast-forward' in str(e.stderr):
                    logger.warning('推送被拒绝，正在尝试同步并重试...')
                    self._execute_git_command(['git', 'pull', '--rebase', 'origin', self.branch])
                    self._execute_git_command(['git', 'push', 'origin', self.branch])
                    logger.info('同步后推送成功')
                else:
                    raise
        except Exception as e:
            logger.error(f'推送feed.xml失败: {e}')
            raise
    
    def _execute_git_command(self, command: list[str], check: bool = True, input: str = None) -> Optional[str]:
        """执行Git命令并返回输出结果"""
        try:
            result = subprocess.run(
                command,
                cwd=self.work_dir,
                check=check,
                capture_output=True,
                text=True,
                input=input
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f'Git命令执行失败: {e.stderr}')
            if check:
                raise
            return None
    
    def _get_feed_date(self, feed_path: str) -> Optional[datetime]:
        """获取feed.xml的最后更新时间"""
        if not os.path.exists(feed_path):
            return None
        try:
            tree = ET.parse(feed_path)
            last_build_date = tree.getroot().find('./channel/lastBuildDate')
            return parsedate_to_datetime(last_build_date.text) if last_build_date is not None and last_build_date.text else None
        except Exception as e:
            logger.error(f'获取feed.xml最后更新时间失败: {e}')
            return None