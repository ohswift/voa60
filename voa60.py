#!/opt/miniconda3/envs/paddle/bin/python
import os
import sys
import re
import subprocess
import requests
import shutil
import random
import json
from hashlib import md5
from datetime import date, timedelta, datetime
import multiprocessing

from dotenv import load_dotenv
load_dotenv()
BAIDU_APPID = os.getenv('BAIDU_APPID')
BAIDU_APP_KEY = os.getenv('BAIDU_APP_KEY')

# WORK_DIR= f'{os.getcwd()}'
WORK_DIR = f'/Users/vincent/work/media'
SUBTITLE_LIB_DIR = r'/Users/vincent/work/github/video-subtitle-extractor/backend'

VIDEO_FILE='1.mp4'
SRT_FILE='1.srt'
SRT_TXT_FILE='1.txt'
SRT_ORI_FILE='1.eng.srt'
BANNER_SRT_FILE='../0.srt'
OUTPUT_FILE = 'output2.mp4'

'''
过滤掉视频的32~43, 92~104秒...
ffmpeg -i output2.mp4 -vf "select='not(between(t,32,43)+between(t,92,104))',setpts=N/FRAME_RATE/TB" -af "aselect='not(between(t,32,43)+between(t,92,104))',asetpts=N/SR/TB" -y output2.2.mp4
'''

# 从官网抓取某日视频
def download_video(day=None, local_filename=None):
    if day == None:
        day = date.today()
    if os.path.exists(local_filename):
        return local_filename
    url = f'https://learningenglish.voanews.com/z/3613/{day.year}/{day.month}/{day.day}'
    html1 = requests.get(url).text
    if re.search("Sorry! No content for", html1):
        print("当日无视频...")
        return
    
    #解析出当日视频链接
    ss=re.search(r'''<ul id=.*?<li.*?<a href="(.*?)" ''', html1, re.DOTALL)
    if ss == None:
        return 
    href=ss.groups()[0]
    url = f'https://learningenglish.voanews.com{href}'
    html2 = requests.get(url).text
    #解析视频下载地址
    # ss=re.findall('<li class="subitem">.*?<a.*?href="(.*?)".*?title="(.*?) ', html2, re.DOTALL)
    # for s in ss:
    # if s[1].find('720p') != -1:
    #     url = s[0]
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

# 使用开源video-subtitle-extractor从视频中提取英文字幕
def extracte_caption_from_video(video_path):
    if not os.path.exists(video_path):
        return
    sys.path.insert(0, os.path.abspath(SUBTITLE_LIB_DIR))
    import main
    multiprocessing.set_start_method("spawn")
    subtitle_area = (633, 710, 18, 1261)
    se = main.SubtitleExtractor(video_path, subtitle_area)
    # 开始提取字幕
    se.run()

# 用百度翻译API
def translate_text(query, dest_language="zh-cn"):

    appid = BAIDU_APPID
    appkey = BAIDU_APP_KEY

    from_lang = 'en'
    to_lang =  'zh'
    endpoint = 'http://api.fanyi.baidu.com'
    path = '/api/trans/vip/translate'
    url = endpoint + path

    # Generate salt and sign
    def make_md5(s, encoding='utf-8'):
        return md5(s.encode(encoding)).hexdigest()

    salt = random.randint(32768, 65536)
    sign = make_md5(appid + query + str(salt) + appkey)

    # Build request
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    payload = {'appid': appid, 'q': query, 'from': from_lang, 'to': to_lang, 'salt': salt, 'sign': sign}

    # Send request
    r = requests.post(url, params=payload, headers=headers)
    result = r.json()['trans_result']
    return result

# 用百度翻译字幕
def translate_srt(wdir):
    sub_txt_file = f'{wdir}/{SRT_TXT_FILE}'
    sub_srt_file = f'{wdir}/{SRT_FILE}'
    sub_srt_trans_file = f'{wdir}/tmp'
    sub_srt_ori_file = f'{wdir}/{SRT_ORI_FILE}'
    if not os.path.exists(sub_txt_file) or not os.path.exists(sub_srt_file):
        return

    with open(sub_srt_file, 'r') as file:
        srt_ct = file.read()

    with open(sub_txt_file, 'r') as file:
        english_text = file.read()
        
    rs = translate_text(english_text)
    for s in rs:
        srt_ct = srt_ct.replace(s['src'], s['dst'])

    with open(sub_srt_trans_file, 'w') as file:
        file.write(srt_ct)
        os.rename(sub_srt_file, sub_srt_ori_file)
        os.rename(sub_srt_trans_file, sub_srt_file)

# 压制字幕
def compress_video(wdir, genCN):
    mp4_file = f'{wdir}/{VIDEO_FILE}'
    sub_srt_file = f'{wdir}/{SRT_FILE}'
    banner_srt_file = f'{wdir}/{BANNER_SRT_FILE}'
    out_file = f'{wdir}/{OUTPUT_FILE}'

    if not os.path.exists(sub_srt_file):
        return

    if genCN:
        ff_cmd = f'''ffmpeg -hide_banner -nostats -i {mp4_file} -filter_complex "[0:v]split=2[v1][v2];[v1]drawbox=x=0:y=ih-96:w=iw:h=96:color=white:t=fill,subtitles={banner_srt_file}:force_style='FontName=SourceHanSansCN-Bold,FontSize=20,PrimaryColour=&H0000FFFF,OutlineColour=&H00222222,Outline=1,MarginV=10'[v11];[v2]subtitles={sub_srt_file}:force_style='FontName=SourceHanSansCN-Bold,FontSize=20,PrimaryColour=&H0000FFFF,OutlineColour=&H00222222,Outline=1,MarginV=40'[v21];[v21][0:a][v11][0:a]concat=n=2:v=1:a=1[ov][oa]" -map "[ov]" -map "[oa]" -y {out_file}'''
    else:
        ff_cmd = f'''ffmpeg -hide_banner -nostats -i {mp4_file} -filter_complex "[0:v]split=2[v1][v2];[v1]drawbox=x=0:y=ih-96:w=iw:h=96:color=white:t=fill,subtitles={banner_srt_file}:force_style='FontName=SourceHanSansCN-Bold,FontSize=20,PrimaryColour=&H0000FFFF,OutlineColour=&H00222222,Outline=1,MarginV=10'[v11];[v11][0:a][v2][0:a]concat=n=2:v=1:a=1[ov][oa]" -map "[ov]" -map "[oa]" -y {out_file}'''

    p = subprocess.Popen(ff_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) 
    for line in p.stderr:
        if line.startswith("frame="):
            print(line[:-1], end='\r')
        else:
            # pass
            print(line, end='')
    print("\n")

# 获取封面图片
def captureCoverImg(video_path):
    ff_cmd = f'ffmpeg -i {video_path} -ss 00:00:01.720 -frames:v 1 -y cover.jpg'
    print(f'cmd: {ff_cmd}')
    output = subprocess.run(ff_cmd, shell=True, capture_output=True, text=True)
    print(f'cover: {output.stderr}')

def work(genCN=True):
    dt_input_str = input("input date(fmt 2024-11-01): ")
    if dt_input_str == '':
        dt = date.today() - timedelta(days=1)
    else:
        dt = datetime.strptime(dt_input_str, '%Y-%m-%d')
    
    dstr = f'{dt.year}-{dt.month:02d}-{dt.day:02d}'
    print(dstr)

    wdir = f'{WORK_DIR}/{dstr}'
    if os.path.exists(wdir) and os.path.isdir(wdir):
        print("already done...")
        # shutil.rmtree(wdir)  
        # return
    else:
        os.makedirs(wdir, exist_ok=True)  
    os.chdir(wdir)

    fn = f'{wdir}/{VIDEO_FILE}'
    fn = download_video(dt, fn)
    if fn == None:
        return    
    
    captureCoverImg(fn)  
  
    if genCN:
        #提取字幕,翻译...
        extracte_caption_from_video(fn)
        os.system(f"open '{wdir}'")
        input("extract ok?")
        translate_srt(wdir)
        input("translate ok?")
    else:
        os.system(f"open '{wdir}'")
    compress_video(wdir, genCN)

if __name__ == '__main__':
    work()
