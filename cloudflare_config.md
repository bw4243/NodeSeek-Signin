# 解决 NodeSeek Cloudflare 防护问题

## 问题分析
您遇到的 HTTP 403 错误是由于 NodeSeek 使用了 Cloudflare 防护，主要问题：
1. **缺少有效的 Cookie** - 需要通过浏览器获取登录后的 Cookie
2. **Cloudflare 检测** - 需要模拟真实浏览器行为

## 解决步骤

### 1. 获取有效的 Cookie
1. 在浏览器中登录 NodeSeek (https://www.nodeseek.com)
2. 按 F12 打开开发者工具
3. 切换到 Network (网络) 标签页
4. 刷新页面或点击任意链接
5. 找到任意请求，点击查看请求头 (Request Headers)
6. 复制完整的 Cookie 值

### 2. 配置环境变量
创建或编辑 `.env` 文件，添加以下配置：

```bash
# 必需配置
NS_COOKIE=你的完整Cookie值
GOOGLE_API_KEY=你的Google_AI_Studio_API_Key

# Cloudflare 绕过配置
NS_COMMENT_DRY_RUN=true
NS_UA=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36
```

### 3. 或者使用 Cookie 文件方式
创建 `./cookie/NS_COOKIE.txt` 文件，将 Cookie 值放入其中：

```bash
mkdir cookie
echo "你的Cookie值" > cookie/NS_COOKIE.txt
```

## 高级配置选项

如果仍然遇到问题，可以尝试以下额外配置：

```bash
# 更详细的浏览器伪装
NS_ACCEPT=text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8
NS_ACCEPT_LANGUAGE=zh-CN,zh;q=0.9,en;q=0.8
NS_ACCEPT_ENCODING=gzip, deflate, br
NS_SEC_CH_UA="Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"
NS_SEC_CH_UA_MOBILE=?0
NS_SEC_CH_UA_PLATFORM="Windows"

# 设置 Referer
NS_REFERER=https://www.nodeseek.com/

# 如果分类页仍然被拦截，可以直接指定帖子 URL
NS_THREAD_URLS=https://www.nodeseek.com/post-123456-1,https://www.nodeseek.com/post-789012-1
```

## 测试步骤

1. 配置完成后，先运行干跑模式测试：
```bash
python commenter.py
```

2. 如果成功，会看到类似输出：
```
[账号1] 目标1: 帖子标题 -> 帖子URL
------ DRY RUN 生成评论（未发布） ------
生成的评论内容
------------------------------------
```
