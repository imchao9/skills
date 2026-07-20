# Basketball Profile

篮球视频专用 profile。适合在篮球素材处理项目里安装，不放进默认 `core`，避免普通项目加载领域专用流程。

当前包含：

- `basketball-video-delivery`：从小球迷全场回放到本地剪辑、验收和百度网盘交付的可恢复编排工作流。
- `basketball-pure-cut`：篮球全场录像纯享版剪辑，删除热身、等待、黑屏、暂停和非比赛片段。
- `basketball-highlight-builder`：基于事件片段和全场录像生成个人集锦或整场集锦。
- `xiaoqiumi-match-review`：抓取小球迷篮球比赛数据，生成中文球评，并输出 5 种风格的赛后海报 HTML。

安装：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/basketball \
  --agent codex --skill '*' --yes --copy --full-depth
```
