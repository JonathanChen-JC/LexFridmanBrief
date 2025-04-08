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
            
            # 确保段落之间有空行
            paragraphs = content.split('\n\n')
            formatted_content = '\n\n'.join(p.strip() for p in paragraphs if p.strip())
            
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
        fe.pubDate(entry['pub_date'])
    
    # 保存feed
    fg.rss_file(feed_path)
    
    # 推送更新到Git仓库
    try:
        git_sync.push_feed()
    except Exception as e:
        print(f"Failed to push feed to Git repository: {e}")

if __name__ == '__main__':
    update_feed()