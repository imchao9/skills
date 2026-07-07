# Basketball Profile

篮球视频专用 profile。适合在篮球素材处理项目里安装，不放进默认 `core`，避免普通项目加载领域专用流程。

当前包含：

- `basketball-pure-cut`：篮球全场录像纯享版剪辑，删除热身、等待、黑屏、暂停和非比赛片段。
- `basketball-highlight-builder`：基于事件片段和全场录像生成个人集锦或整场集锦。

安装：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/basketball \
  --agent codex --skill '*' --yes --copy --full-depth
```
