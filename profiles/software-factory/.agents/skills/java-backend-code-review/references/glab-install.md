# glab 安装引导

仅在以下场景读取本文件：

- 用户要按 MR 模式审查，但当前机器缺少 `glab`
- 用户明确说要安装 `glab`
- 用户问为什么 MR review 不能直接运行

## 处理原则

1. 先明确说明：
   - MR 模式依赖 `glab`
   - 如果不想安装 `glab`，可以改用“源分支对比目标分支”模式
2. 如果用户愿意安装，再继续下一步；不要默认直接安装。
3. 安装前要先征求明确确认：
   - `当前机器没有 glab。你可以改用分支对比模式，或者我帮你安装 glab。要安装的话，我会临时使用清华 Homebrew 镜像执行 brew install glab。要我现在安装吗？`
4. 只有在用户明确回答“要安装 / 是 / Yes”后，才运行安装脚本。

## 推荐安装方式

优先使用 Homebrew 安装：

```bash
bash "$SKILL_DIR/scripts/install_glab.sh"
```

安装完成后，引导用户继续完成认证：

```bash
glab auth login
```

如果是自建 GitLab，必要时提示用户按实例域名登录，例如：

```bash
glab auth login --hostname gitlab.codemao.cn
```

## 国内镜像策略

默认使用“临时镜像”方式执行安装，不默认持久修改 Homebrew 配置：

- `HOMEBREW_API_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles/api`
- `HOMEBREW_BOTTLE_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles`

这样能减少安装时对海外源的依赖，但不会直接改写用户的 shell profile。

## 降级方案

如果用户不想安装 `glab`，直接改为分支对比模式：

- `请告诉我源分支和目标分支，例如 feature/xxx 对比 master。`

## 参考

- GitLab CLI 文档：`glab auth login` 是官方推荐的登录方式
- 清华 TUNA Homebrew 镜像文档：Homebrew 4 之后，大部分场景可以通过 `HOMEBREW_API_DOMAIN` 和 `HOMEBREW_BOTTLE_DOMAIN` 进行镜像加速
