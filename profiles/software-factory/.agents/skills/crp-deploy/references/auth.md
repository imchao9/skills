# Auth

鉴权命令会维护这两个文件：

- `output/auth-storage-state.json`
- `output/auth-cookie.txt`

## 方法一: Browser Login

依赖：

- `node`
- Playwright Node 包：优先按 Node 规则 `require('playwright')`，找不到再 fallback 到 `~/.npm/_npx` 缓存
- 本机安装 `Google Chrome`

执行时必须能启动本机浏览器并访问 CRP；如果默认执行环境不具备这些能力，应直接使用具备浏览器和网络访问能力的执行方式。

```bash
node scripts/auth-login.js
```

浏览器登录固定使用 Node 入口。实测 Python 外层包装启动时页面加载明显变慢，Node 入口更接近已验证可用的浏览器链路。

`node scripts/auth-login.js` 会打开一个临时的专用浏览器上下文，等待登录完成后写入上面的鉴权文件。
成功时脚本已经校验过 CRP 登录态，直接重新执行原命令即可。
它不会长期保留浏览器 profile。正常流程会在成功、失败或取消后关闭浏览器并清理临时 profile。
脚本自带登录超时，默认 3 分钟，可用 `--login-timeout <seconds>` 调整；执行后等待命令返回，不要频繁轮询 stdout，除非命令进程已等待至少 30 秒仍未返回。

## 异常清理

仅在怀疑浏览器异常残留、并且明确需要关闭残留时使用。先定位只属于本鉴权流程的进程：

```bash
pgrep -af 'crp-deploy-auth-login-.*/profile'
```

确认输出里的 `--user-data-dir` 包含 `crp-deploy-auth-login-.../profile` 后，再关闭对应 PID：

```bash
kill <PID>
```

不要用宽泛的 Chrome 进程名批量关闭。

## 方法二: Manual Cookie Paste

如果不想安装浏览器依赖，直接把浏览器里的完整 Cookie 粘贴到 `output/auth-cookie.txt` 最后一行。
然后执行校验：

```bash
scripts/auth validate
```
