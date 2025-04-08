import os
import subprocess
from datetime import datetime
from typing import Optional
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

class GitSync:
    def __init__(self):
        # 从环境变量获取Git配置
        self.repo_url = os.getenv('GIT_REPO_URL')
        self.branch = os.getenv('GIT_BRANCH', 'main')
        self.username = os.getenv('GIT_USERNAME')
        self.token = os.getenv('GIT_TOKEN')
        
        if not all([self.repo_url, self.username, self.token]):
            raise ValueError('Missing required Git configuration in environment variables')
        
        # 构建带有认证信息的仓库URL
        repo_parts = self.repo_url.split('://')
        if len(repo_parts) == 2:
            self.auth_repo_url = f'https://{self.username}:{self.token}@{repo_parts[1]}'
        else:
            self.auth_repo_url = self.repo_url
        
        # 确保工作目录存在
        self.work_dir = os.path.dirname(os.path.abspath(__file__))
        
    def _run_git_command(self, command: list[str], check: bool = True, input: str = None) -> Optional[str]:
        """执行Git命令并返回输出"""
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
            print(f'Git command failed: {e.stderr}')
            if check:
                raise
            return None
    
    def setup_git_config(self):
        """配置Git用户信息和凭证"""
        self._run_git_command(['git', 'config', 'user.name', self.username])
        self._run_git_command(['git', 'config', 'user.email', f'{self.username}@users.noreply.github.com'])
        # 配置凭证存储
        self._run_git_command(['git', 'config', 'credential.helper', 'store'])
        # 设置远程仓库认证信息
        credential_input = f'url={self.repo_url}\nusername={self.username}\npassword={self.token}\n'
        self._run_git_command(['git', 'credential', 'approve'], input=credential_input)
    
    def init_repo(self):
        """初始化Git仓库并添加远程仓库"""
        try:
            # 先配置Git凭证
            self.setup_git_config()
            
            # 检查是否已经是Git仓库
            if not os.path.exists(os.path.join(self.work_dir, '.git')):
                self._run_git_command(['git', 'init'])
                self._run_git_command(['git', 'remote', 'add', 'origin', self.auth_repo_url], check=False)
            else:
                # 更新远程仓库URL
                self._run_git_command(['git', 'remote', 'set-url', 'origin', self.auth_repo_url], check=False)
                
            # 验证远程仓库连接
            self._run_git_command(['git', 'ls-remote', '--exit-code', self.auth_repo_url, self.branch])
        except Exception as e:
            print(f'Failed to initialize repository: {e}')
            raise
    
    def get_last_build_date(self, feed_path: str) -> Optional[datetime]:
        """从feed.xml文件中获取lastBuildDate"""
        try:
            if not os.path.exists(feed_path):
                return None
            tree = ET.parse(feed_path)
            root = tree.getroot()
            last_build_date = root.find('./channel/lastBuildDate')
            if last_build_date is not None and last_build_date.text:
                return parsedate_to_datetime(last_build_date.text)
            return None
        except Exception as e:
            print(f'Failed to get lastBuildDate: {e}')
            return None

    def pull_feed(self):
        """从远程仓库拉取feed.xml并与本地版本对比"""
        try:
            # 获取本地feed.xml的lastBuildDate
            local_feed_path = os.path.join(self.work_dir, 'feed.xml')
            local_date = self.get_last_build_date(local_feed_path)

            # 拉取远程仓库
            self._run_git_command(['git', 'fetch', 'origin', self.branch])
            self._run_git_command(['git', 'checkout', self.branch], check=False)
            
            # 获取远程feed.xml的lastBuildDate
            remote_feed_path = os.path.join(self.work_dir, 'feed.xml')
            self._run_git_command(['git', 'checkout', 'origin/' + self.branch, '--', 'feed.xml'], check=False)
            remote_date = self.get_last_build_date(remote_feed_path)

            # 如果远程版本较新，保留远程版本
            if remote_date and (not local_date or remote_date > local_date):
                self._run_git_command(['git', 'checkout', 'origin/' + self.branch, '--', 'feed.xml'])
            else:
                # 否则恢复本地版本（如果存在）
                if os.path.exists(local_feed_path):
                    self._run_git_command(['git', 'checkout', self.branch, '--', 'feed.xml'])

        except subprocess.CalledProcessError as e:
            print(f'Failed to pull from remote repository: {e}')
        except Exception as e:
            print(f'Error during feed comparison: {e}')
    
    def push_feed(self):
        """将更新后的feed.xml推送到远程仓库"""
        try:
            feed_path = os.path.join(self.work_dir, 'feed.xml')
            if not os.path.exists(feed_path):
                print('feed.xml not found')
                return
            
            # 添加并提交更改
            self._run_git_command(['git', 'add', 'feed.xml'])
            commit_message = f'Update feed.xml - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            self._run_git_command(['git', 'commit', '-m', commit_message], check=False)
            
            # 推送到远程仓库
            self._run_git_command(['git', 'push', 'origin', self.branch])
        except subprocess.CalledProcessError as e:
            print(f'Failed to push feed.xml: {e}')