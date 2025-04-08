import os
import subprocess
from datetime import datetime
from typing import Optional

class GitSync:
    def __init__(self):
        # 从环境变量获取Git配置
        self.repo_url = os.getenv('GIT_REPO_URL')
        self.branch = os.getenv('GIT_BRANCH', 'main')
        self.username = os.getenv('GIT_USERNAME')
        self.token = os.getenv('GIT_TOKEN')
        
        if not all([self.repo_url, self.username, self.token]):
            raise ValueError('Missing required Git configuration in environment variables')
        
        # 构建带认证的仓库URL
        self.auth_repo_url = f'https://{self.username}:{self.token}@{self.repo_url.split("://")[1]}'
        
        # 确保工作目录存在
        self.work_dir = os.path.dirname(os.path.abspath(__file__))
        
    def _run_git_command(self, command: list[str], check: bool = True) -> Optional[str]:
        """执行Git命令并返回输出"""
        try:
            result = subprocess.run(
                command,
                cwd=self.work_dir,
                check=check,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f'Git command failed: {e.stderr}')
            if check:
                raise
            return None
    
    def setup_git_config(self):
        """配置Git用户信息"""
        self._run_git_command(['git', 'config', 'user.name', self.username])
        self._run_git_command(['git', 'config', 'user.email', f'{self.username}@users.noreply.github.com'])
    
    def init_repo(self):
        """初始化Git仓库并添加远程仓库"""
        # 检查是否已经是Git仓库
        if not os.path.exists(os.path.join(self.work_dir, '.git')):
            self._run_git_command(['git', 'init'])
            self._run_git_command(['git', 'remote', 'add', 'origin', self.auth_repo_url])
        else:
            # 更新远程仓库URL
            self._run_git_command(['git', 'remote', 'set-url', 'origin', self.auth_repo_url])
    
    def pull_feed(self):
        """从远程仓库拉取feed.xml"""
        try:
            self._run_git_command(['git', 'fetch', 'origin', self.branch])
            self._run_git_command(['git', 'checkout', self.branch], check=False)
            self._run_git_command(['git', 'pull', 'origin', self.branch], check=False)
        except subprocess.CalledProcessError:
            print('Failed to pull from remote repository')
    
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