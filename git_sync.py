import os
import subprocess
import tempfile
import shutil
from datetime import datetime
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
        if self.repo_url.startswith('https://'):
            self.auth_repo_url = self.repo_url.replace(
                'https://',
                f'https://{self.username}:{self.token}@'
            )
        else:
            self.auth_repo_url = self.repo_url
        
        self.work_dir = os.path.dirname(os.path.abspath(__file__))
    
    def _run_git_command(self, command: list[str], cwd: str = None, check: bool = True, input: str = None) -> str:
        """执行Git命令并返回输出结果"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.work_dir,
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
    
    def _setup_repo(self, repo_dir: str):
        """设置Git仓库的基本配置"""
        # 设置Git用户信息
        self._run_git_command(['git', 'config', 'user.name', self.username], cwd=repo_dir)
        self._run_git_command(['git', 'config', 'user.email', f'{self.username}@users.noreply.github.com'], cwd=repo_dir)
        self._run_git_command(['git', 'config', 'pull.rebase', 'false'], cwd=repo_dir)
    
    def _clone_repository(self) -> str:
        """克隆仓库到临时目录"""
        temp_dir = tempfile.mkdtemp(prefix="git_repo_")
        logger.info(f'克隆仓库到临时目录: {temp_dir}')
        
        try:
            self._run_git_command(['git', 'clone', self.auth_repo_url, temp_dir])
            self._setup_repo(temp_dir)
            return temp_dir
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.error(f'克隆仓库失败: {str(e)}')
            raise
    
    def _get_feed_date(self, feed_path: str) -> datetime:
        """获取feed.xml的最后更新时间"""
        if not os.path.exists(feed_path):
            return None
        try:
            tree = ET.parse(feed_path)
            root = tree.getroot()
            # 首先尝试获取lastBuildDate
            last_build_date = root.find('./channel/lastBuildDate')
            if last_build_date is not None and last_build_date.text:
                return parsedate_to_datetime(last_build_date.text)
            # 如果没有lastBuildDate，尝试获取最新的pubDate
            items = root.findall('./channel/item')
            if items:
                pub_date = items[0].find('pubDate')
                if pub_date is not None and pub_date.text:
                    return parsedate_to_datetime(pub_date.text)
            return None
        except Exception as e:
            logger.error(f'获取feed.xml最后更新时间失败: {e}')
            return None
    
    def pull_feed(self):
        """从远程仓库获取feed.xml文件"""
        repo_dir = None
        try:
            # 克隆仓库到临时目录
            repo_dir = self._clone_repository()
            
            # 切换到指定分支
            self._run_git_command(['git', 'checkout', self.branch], cwd=repo_dir)
            
            # 比较本地和远程feed.xml的日期
            local_feed_path = os.path.join(self.work_dir, 'feed.xml')
            repo_feed_path = os.path.join(repo_dir, 'feed.xml')
            
            local_date = self._get_feed_date(local_feed_path)
            remote_date = self._get_feed_date(repo_feed_path)
            
            if remote_date and (not local_date or remote_date > local_date):
                # 使用远程版本
                shutil.copy2(repo_feed_path, local_feed_path)
                logger.info('已更新为远程feed.xml版本')
            else:
                logger.info('保留本地feed.xml版本')
        
        finally:
            # 清理临时目录
            if repo_dir:
                shutil.rmtree(repo_dir, ignore_errors=True)
    
    def commit_and_push_feed(self):
        """提交并推送feed.xml到远程仓库"""
        repo_dir = None
        try:
            local_feed_path = os.path.join(self.work_dir, 'feed.xml')
            if not os.path.exists(local_feed_path):
                raise FileNotFoundError('feed.xml文件不存在')
            
            # 克隆仓库到临时目录
            repo_dir = self._clone_repository()
            
            # 切换到指定分支
            self._run_git_command(['git', 'checkout', self.branch], cwd=repo_dir)
            
            # 复制本地feed.xml到仓库
            repo_feed_path = os.path.join(repo_dir, 'feed.xml')
            shutil.copy2(local_feed_path, repo_feed_path)
            
            # 提交更改
            commit_message = f'更新feed.xml - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            self._run_git_command(['git', 'add', 'feed.xml'], cwd=repo_dir)
            
            # 检查是否有更改需要提交
            status = self._run_git_command(['git', 'status', '--porcelain'], cwd=repo_dir)
            if not status:
                logger.info('没有需要提交的更改')
                return
            
            self._run_git_command(['git', 'commit', '-m', commit_message], cwd=repo_dir)
            
            # 推送到远程仓库
            try:
                self._run_git_command(['git', 'push', 'origin', self.branch], cwd=repo_dir)
                logger.info('成功推送到远程仓库')
            except subprocess.CalledProcessError as e:
                if 'non-fast-forward' in str(e.stderr):
                    logger.warning('推送被拒绝，正在尝试同步并重试...')
                    self._run_git_command(['git', 'pull', '--no-rebase', 'origin', self.branch], cwd=repo_dir)
                    self._run_git_command(['git', 'push', 'origin', self.branch], cwd=repo_dir)
                    logger.info('同步后推送成功')
                else:
                    raise
        
        finally:
            # 清理临时目录
            if repo_dir:
                shutil.rmtree(repo_dir, ignore_errors=True)