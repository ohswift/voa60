import os
import sys
import re
import shutil
import json
from datetime import date, timedelta, datetime

import requests
from tqdm import tqdm
import time

# 从官网抓取某日视频
def download_video(day=None, local_filename=None):
    if day == None:
        day = date.today()
    if os.path.exists(local_filename):
        # print(f"\n{day}视频已下载过...")
        return
    url = f'https://learningenglish.voanews.com/z/3613/{day.year}/{day.month}/{day.day}'
    html1 = requests.get(url).text
    if re.search("Sorry! No content for", html1):
        print(f"\n{day}当日无视频...")
        return    
    #解析出当日视频链接
    ss=re.search(r'''<ul id=.*?<li.*?<a href="(.*?)" ''', html1, re.DOTALL)
    if ss == None:
        return 
    href=ss.groups()[0]
    url = f'https://learningenglish.voanews.com{href}'
    html2 = requests.get(url).text
    #解析视频下载地址
    ss=re.findall(';https:.*?_720p.mp4', html2)
    url = None
    if len(ss) == 0: 
        print(f"re failed:url:{url}")
        return
    url = ss[-1][1:]
    if url == None:
        return
    #下载视频
    if local_filename is None:
        local_filename = re.search('/([^/]*.mp4)', url).groups()[0]
    
    # 发起请求，注意设置stream=True
    # url = "https://voa-video-ns.akamaized.net/pangeavideo/2024/09/2/2c/2c3549d6-28a7-47b6-8048-5605c7948e57_720p.mp4?download=1"
    with requests.get(url, stream=True) as response:
        response.raise_for_status()  # 如果请求返回了错误的状态码，将抛出HTTPError异常
        total_size_in_bytes= int(response.headers.get('content-length', 0))
        # 打开一个新的文件用于写入，使用'wb'模式以支持任何类型的文件
        with open(local_filename, 'wb+') as file:
            # 使用迭代器来逐步读取响应数据
            for chunk in response.iter_content(chunk_size=8192): 
                # 过滤掉空的数据块
                if chunk: 
                    file.write(chunk)
    return local_filename

def work(start_date, wdir):
    delta = date.today() - start_date
    days = delta.days

    items = list(range(days))
    for i in tqdm(items, desc='下载中', ncols=100, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}', colour='green'):
        dt = start_date + timedelta(days=i)
        date_string = dt.strftime('%Y-%m-%d')
        file_path = os.path.join(wdir, f'{date_string}.mp4')
        download_video(dt, file_path)
        # time.sleep(0.05)
    
if __name__ == '__main__':
    dt_input_str = input("输入开始日期(格式:2024-11-01): ")
    if dt_input_str == '':
        dt = date.today() - timedelta(days=7)
    else:
        dt = datetime.strptime(dt_input_str, '%Y-%m-%d')

    work(dt, os.getcwd())



