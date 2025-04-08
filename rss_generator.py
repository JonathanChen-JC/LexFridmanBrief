import os
from datetime import datetime
from zoneinfo import ZoneInfo
from feedgen.feed import FeedGenerator
from collections import deque
import xml.etree.ElementTree as ET
from git_sync import GitSync

def create_rss_feed():
    fg = FeedGenerator()
    fg.title('Lex Fridman Podcast Brief')
    fg.link(href='https://lexfridman.com/')
    fg.description('Brief summaries of Lex Fridman Podcast episodes')
    fg.language('zh-CN')
    return fg

def parse_existing_feed(feed_path):
    if not os.path.exists(feed_path):
        return deque(maxlen=50)
    
    try:
        tree = ET.parse(feed_path)
        root = tree.getroot()
        entries = deque(maxlen=50)
        
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            description = item.find('description').text
            pub_date = item.find('pubDate').text
            entries.append({
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date
            })
        return entries
    except Exception as e:
        print(f"Error parsing existing feed: {e}")
        return deque(maxlen=50)

def format_content(content):
    # 按照多个换行符分割段落，使用HTML标签格式化
    lines = content.split('\n')
    formatted_lines = []
    current_paragraph = []
    
    for line in lines:
        line = line.rstrip()
        
        # 处理标题行（以#开头）
        if line.lstrip().startswith('#'):
            # 如果有待处理的段落，先添加它
            if current_paragraph:
                formatted_lines.append(f"<p>{' '.join(current_paragraph)}</p>")
                current_paragraph = []
            
            formatted_lines.append(line)
            formatted_lines.append('')  # 标题后添加一个空行
        # 处理空行：表示段落结束
        elif not line.strip():
            if current_paragraph:
                formatted_lines.append(f"<p>{' '.join(current_paragraph)}</p>")
                current_paragraph = []
        # 处理普通文本行
        else:
            current_paragraph.append(line)
    
    # 处理最后一个段落
    if current_paragraph:
        formatted_lines.append(f"<p>{' '.join(current_paragraph)}</p>")
    
    # 使用单个换行符连接所有行
    return '\n'.join(formatted_lines)

def update_feed():
    brief_dir = os.path.join(os.path.dirname(__file__), 'brief')
    feed_path = os.path.join(os.path.dirname(__file__), 'feed.xml')
    
    # 初始化Git同步
    try:
        git_sync = GitSync()
        git_sync.init_repo()
        git_sync.setup_git_config()
        git_sync.pull_feed()
    except Exception as e:
        print(f"Git sync initialization failed: {e}")
    
    # 获取现有条目
    existing_entries = parse_existing_feed(feed_path)
    
    # 创建新的feed
    fg = create_rss_feed()
    
    # 读取brief目录下的所有md文件
    for filename in os.listdir(brief_dir):
        if filename.endswith('.md'):
            file_path = os.path.join(brief_dir, filename)
            
            # 从文件名中提取标题
            title = filename[:-3]  # 移除.md后缀
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 格式化内容，保持原有段落格式
            formatted_content = format_content(content)
            
            # 创建新条目
            fe = fg.add_entry()
            fe.title(title)
            fe.link(href='https://lexfridman.com/')
            fe.description(formatted_content)
            current_time = datetime.now(ZoneInfo('Asia/Shanghai'))
            fe.pubDate(current_time)
            
            # 将新条目添加到现有条目队列
            existing_entries.append({
                'title': title,
                'link': 'https://lexfridman.com/',
                'description': formatted_content,
                'pub_date': current_time.strftime('%a, %d %b %Y %H:%M:%S %z')
            })
    
    # 将所有条目写入feed
    for entry in existing_entries:
        fe = fg.add_entry()
        fe.title(entry['title'])
        fe.link(href=entry['link'])
        fe.description(entry['description'])
        fe.pubDate(datetime.strptime(entry['pub_date'], '%a, %d %b %Y %H:%M:%S %z'))
    
    # 生成feed并写入文件
    fg.rss_file(feed_path, pretty=True)
    
    # 提交更新到Git
    try:
        git_sync.commit_and_push_feed()
    except Exception as e:
        print(f"Git sync failed: {e}")