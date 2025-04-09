import requests
import os
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
import time
import logging
import email.utils  # 用于解析RFC822日期格式

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

class LexFridmanTranscriptScraper:
    def __init__(self, rss_url="https://lexfridman.com/feed/podcast/", output_dir="Transcripts"):
        self.rss_url = rss_url
        self.output_dir = output_dir
        
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"创建输出目录: {output_dir}")
    
    def parse_rss_feed(self, limit=None):
        """解析RSS源并返回播客条目列表"""
        logging.info(f"开始解析RSS源: {self.rss_url}")
        try:
            response = requests.get(self.rss_url)
            response.raise_for_status()
            
            # 解析XML
            root = ET.fromstring(response.content)
            
            # 查找所有item元素（播客条目）
            # 使用XML命名空间
            namespaces = {'': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
            channel = root.find('channel', namespaces) if namespaces else root.find('channel')
            items = channel.findall('item', namespaces) if channel else []
            
            # 创建条目列表
            entries = []
            for item in items:
                # 提取标题
                title_elem = item.find('title', namespaces)
                title = title_elem.text if title_elem is not None else '无标题'
                
                # 提取链接
                link_elem = item.find('link', namespaces)
                link = link_elem.text if link_elem is not None else ''
                
                # 提取发布日期
                pub_date_elem = item.find('pubDate', namespaces)
                pub_date_str = pub_date_elem.text if pub_date_elem is not None else ''
                pub_date_tuple = email.utils.parsedate(pub_date_str) if pub_date_str else None
                
                # 创建条目对象
                entry = {
                    'title': title,
                    'link': link,
                    'published_parsed': pub_date_tuple
                }
                entries.append(entry)
            
            # 限制条目数量
            if limit and len(entries) > limit:
                entries = entries[:limit]
                
            logging.info(f"成功解析RSS源，获取到{len(entries)}个条目")
            return entries
        except Exception as e:
            logging.error(f"解析RSS源时出错: {e}")
            return []
    
    def find_transcript_url(self, podcast_url):
        """在播客页面中查找Transcript链接，仅在当前播客的<item>标签内搜索"""
        logging.info(f"查找Transcript链接: {podcast_url}")
        try:
            response = requests.get(self.rss_url)
            response.raise_for_status()
            
            # 解析XML
            root = ET.fromstring(response.content)
            
            # 使用XML命名空间
            namespaces = {'': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
            channel = root.find('channel', namespaces) if namespaces else root.find('channel')
            items = channel.findall('item', namespaces) if channel else []
            
            # 在items中查找当前播客的<item>标签
            current_item = None
            for item in items:
                link_elem = item.find('link', namespaces)
                if link_elem is not None and link_elem.text == podcast_url:
                    current_item = item
                    break
            
            if current_item is None:
                logging.warning(f"在RSS源中未找到当前播客: {podcast_url}")
                return None
            
            # 在当前播客的<item>标签内容中查找Transcript链接
            description_elem = current_item.find('description', namespaces)
            if description_elem is None or not description_elem.text:
                logging.warning(f"当前播客没有描述内容: {podcast_url}")
                return None
            
            # 解析描述内容中的HTML
            soup = BeautifulSoup(description_elem.text, 'html.parser')
            
            # 方法1: 查找包含"Transcript:"文本的元素及其后的链接
            for element in soup.find_all(['p', 'div', 'span']):
                if element.text and "Transcript:" in element.text:
                    # 提取文本中的URL
                    text = element.text
                    transcript_text_part = text.split("Transcript:", 1)[1].strip()
                    url_match = re.search(r'https?://[\w.-]+(?:/[\w.-]*)*/?(?:-transcript)?', transcript_text_part)
                    if url_match:
                        return url_match.group(0)
                    
                    # 查找该元素后的链接
                    next_element = element.find_next('a')
                    if next_element and next_element.get('href'):
                        return next_element.get('href')
            
            # 方法2: 直接查找URL中包含transcript的链接
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and "transcript" in href.lower():
                    return href
            
            logging.warning(f"暂未找到这集播客的逐字稿: {podcast_url}")
            return None
            
        except Exception as e:
            logging.error(f"查找Transcript链接时出错: {e}")
            return None
    
    def get_transcript_content(self, transcript_url):
        """获取Transcript页面的内容"""
        logging.info(f"获取Transcript内容: {transcript_url}")
        try:
            response = requests.get(transcript_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尝试找到主要内容区域
            main_content = None
            
            # 方法1: 查找article标签
            article = soup.find('article')
            if article:
                main_content = article
            
            # 方法2: 查找主要内容div
            if not main_content:
                for div in soup.find_all('div', class_=re.compile(r'content|main|transcript|entry')):
                    main_content = div
                    break
            
            # 方法3: 如果以上方法都失败，使用body
            if not main_content:
                main_content = soup.find('body')
            
            if main_content:
                # 移除不需要的元素
                for element in main_content.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    element.decompose()
                
                # 获取文本并清理
                text = main_content.get_text(separator='\n')
                # 移除多余的空行
                text = re.sub(r'\n{3,}', '\n\n', text)
                # 移除开头和结尾的空白
                text = text.strip()
                
                return text
            else:
                logging.warning(f"无法找到Transcript内容: {transcript_url}")
                return None
        except Exception as e:
            logging.error(f"获取Transcript内容时出错: {e}")
            return None
    
    async def check_new_episodes(self):
        """检查RSS源中是否有新的播客内容，通过比较标题中的三位数字编号"""
        logging.info("检查新的播客内容")
        try:
            # 获取RSS源中的播客条目
            entries = self.parse_rss_feed()
            if not entries:
                return []
            
            # 读取feed.xml文件
            try:
                with open('feed.xml', 'r', encoding='utf-8') as f:
                    feed_content = f.read()
                feed_root = ET.fromstring(feed_content)
                feed_items = feed_root.findall('.//item')
                feed_titles = [item.find('title').text for item in feed_items if item.find('title') is not None]
            except (FileNotFoundError, ET.ParseError) as e:
                logging.warning(f"读取feed.xml失败: {e}")
                feed_titles = []
            
            # 从feed.xml中获取最大的播客编号
            feed_max_number = 0
            for title in feed_titles:
                match = re.search(r'#(\d+)', title)
                if match:
                    number = int(match.group(1))
                    feed_max_number = max(feed_max_number, number)
            
            # 找出新的播客内容
            new_episodes = []
            for entry in entries:
                # 从标题中提取播客编号
                match = re.search(r'#(\d+)', entry['title'])
                if match:
                    number = int(match.group(1))
                    # 如果播客编号大于feed.xml中的最大编号，则为新内容
                    if number > feed_max_number:
                        new_episodes.append(entry)
            
            logging.info(f"发现{len(new_episodes)}个新的播客内容")
            return new_episodes
        except Exception as e:
            logging.error(f"检查新播客内容时出错: {e}")
            return []
    
    def get_podcast_content(self, podcast_url):
        """获取播客页面的内容（当没有Transcript时使用）"""
        logging.info(f"获取播客页面内容: {podcast_url}")
        try:
            response = requests.get(podcast_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尝试找到主要内容区域
            main_content = None
            
            # 方法1: 查找article标签
            article = soup.find('article')
            if article:
                main_content = article
            
            # 方法2: 查找主要内容div
            if not main_content:
                for div in soup.find_all('div', class_=re.compile(r'content|main|entry')):
                    main_content = div
                    break
            
            # 方法3: 如果以上方法都失败，使用body
            if not main_content:
                main_content = soup.find('body')
            
            if main_content:
                # 移除不需要的元素
                for element in main_content.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    element.decompose()
                
                # 获取文本并清理
                text = main_content.get_text(separator='\n')
                # 移除多余的空行
                text = re.sub(r'\n{3,}', '\n\n', text)
                # 移除开头和结尾的空白
                text = text.strip()
                
                return text
            else:
                logging.warning(f"无法找到播客页面内容: {podcast_url}")
                return None
        except Exception as e:
            logging.error(f"获取播客页面内容时出错: {e}")
            return None
    
    def format_filename(self, title, date):
        """格式化文件名为 YYYYMMDD - [播客标题].md"""
        # 清理标题，移除不允许在文件名中使用的字符
        clean_title = re.sub(r'[\\/*?:"<>|]', '', title)
        # 限制标题长度
        if len(clean_title) > 100:
            clean_title = clean_title[:97] + '...'
        
        # 格式化日期
        date_str = date.strftime("%Y%m%d")
        
        return f"{date_str} - {clean_title}.md"
    
    def save_transcript(self, content, filename):
        """将内容保存为Markdown文件"""
        file_path = os.path.join(self.output_dir, filename)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"成功保存文件: {file_path}")
            return True
        except Exception as e:
            logging.error(f"保存文件时出错: {e}")
            return False
    
    def process_entry(self, entry):
        """处理单个播客条目"""
        title = entry['title']
        link = entry['link']
        date = datetime(*entry['published_parsed'][:6]) if entry['published_parsed'] else datetime.now()
        
        logging.info(f"处理播客: {title}")
        
        # 查找Transcript链接
        transcript_url = self.find_transcript_url(link)
        
        content = None
        source_type = "transcript"
        
        if transcript_url:
            # 获取Transcript内容
            content = self.get_transcript_content(transcript_url)
        
        if not content:
            # 如果没有找到Transcript或获取失败，使用原始播客页面内容
            content = self.get_podcast_content(link)
            source_type = "podcast page"
        
        if content:
            # 添加元数据到内容顶部
            metadata = f"# {title}\n\n"
            metadata += f"- **日期**: {date.strftime('%Y-%m-%d')}\n"
            metadata += f"- **链接**: {link}\n"
            if transcript_url:
                metadata += f"- **Transcript链接**: {transcript_url}\n"
            metadata += f"- **来源**: {source_type}\n\n"
            metadata += "---\n\n"
            
            content = metadata + content
            
            # 保存内容
            filename = self.format_filename(title, date)
            return self.save_transcript(content, filename)
        else:
            logging.error(f"无法获取内容: {link}")
            return False
    
    def run(self, limit=None):
        """运行爬虫"""
        entries = self.parse_rss_feed(limit)
        success_count = 0
        
        for entry in entries:
            # 添加延迟以避免请求过于频繁
            time.sleep(1)
            if self.process_entry(entry):
                success_count += 1
        
        logging.info(f"爬取完成，成功处理{success_count}/{len(entries)}个播客")
        return success_count

# 如果直接运行此脚本
if __name__ == "__main__":
    scraper = LexFridmanTranscriptScraper()
    scraper.run()