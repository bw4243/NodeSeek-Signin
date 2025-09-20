#!/usr/bin/env python3
# 检查temp-script中的配置数据

from curl_cffi import requests
from bs4 import BeautifulSoup
import base64
import json

cookie = open('./cookie/NS_COOKIE.txt').read().strip()
headers = {'Cookie': cookie, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print('获取帖子页面...')
resp = requests.get('https://www.nodeseek.com/post-456178-1', headers=headers, impersonate='chrome110', timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')

# 查找temp-script标签
temp_script = soup.find('script', id='temp-script')
if temp_script and temp_script.string:
    print('找到temp-script标签')
    try:
        # base64解码
        decoded = base64.b64decode(temp_script.string).decode('utf-8')
        print(f'解码后长度: {len(decoded)} 字符')
        
        # 解析JSON
        data = json.loads(decoded)
        print(f'JSON解析成功，顶层键: {list(data.keys())}')
        
        # 递归查找所有包含token或csrf的字段
        def find_tokens(obj, path="root"):
            results = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    current_path = f"{path}.{k}"
                    if 'token' in k.lower() or 'csrf' in k.lower():
                        results.append((current_path, v))
                    results.extend(find_tokens(v, current_path))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    results.extend(find_tokens(item, f"{path}[{i}]"))
            return results
        
        tokens = find_tokens(data)
        if tokens:
            print('找到的token字段:')
            for path, value in tokens:
                print(f'  {path}: {str(value)[:50]}...')
        else:
            print('未找到token相关字段')
            
        # 检查是否有user相关信息
        if 'user' in data:
            user_data = data['user']
            print(f'用户数据键: {list(user_data.keys()) if isinstance(user_data, dict) else type(user_data)}')
            
    except Exception as e:
        print(f'处理temp-script失败: {e}')
else:
    print('未找到temp-script标签')

print('\n完成分析')
