# 批量与搜索命令

仅在用户明确提出批量、搜索或下载意图时读取本文件。所有命令都需要先通过 `command -v feedgrab`，并在执行后回读 Markdown/CSV 产物。

## X/Twitter

```bash
feedgrab x-so "关键词" --days 7
feedgrab x-so "关键词1,关键词2" --merge
feedgrab "https://x.com/i/history"
feedgrab "https://x.com/<user>"
```

通常需要 `feedgrab login twitter`，并按版本要求设置 `X_BOOKMARKS_ENABLED` 或 `X_USER_TWEETS_ENABLED`。

## 小红书

```bash
feedgrab xhs-so "关键词" --sort popular --limit 20
feedgrab "https://www.xiaohongshu.com/user/profile/<id>"
feedgrab "https://www.xiaohongshu.com/search_result?keyword=<关键词>"
```

作者/搜索批量通常需要 `feedgrab login xhs` 及对应 `XHS_*_ENABLED` 开关；`xhs-so` 是否可用以当前版本诊断为准。

## 微信公众号

```bash
feedgrab mpweixin-so "关键词" --limit 20
feedgrab mpweixin-id "公众号名称"
feedgrab mpweixin-zhuanji "<专辑 URL>"
```

按账号批量需要微信后台登录；公开专辑通常不需要登录。

## Reddit、知乎、YouTube、飞书

```bash
feedgrab reddit-so "关键词" --limit 20
feedgrab zhihu-so "关键词" --limit 20
feedgrab ytb-so "关键词" --limit 10
feedgrab feishu-wiki "<知识库 URL>"
```

YouTube 搜索可能需要 `YOUTUBE_API_KEY`；飞书知识库通常需要 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 或已保存登录态。

## 下载与媒体

只有用户明确要求下载时使用：

```bash
feedgrab ytb-dlv "<YouTube URL>"
feedgrab ytb-dla "<YouTube URL>"
feedgrab ytb-dlz "<YouTube URL>"
```

下载完成后回读实际文件路径、大小和退出码；不要把“下载命令启动”当作下载完成。
