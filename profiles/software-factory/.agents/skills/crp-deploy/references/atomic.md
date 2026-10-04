# Atomic Commands

这里列的是 CRP 的底层命令，用于查询、构建、提测和部署。

命令通常在本 skill 主目录执行。
执行原子命令时，运行环境必须能访问 CRP/CMDB 网络接口；如果默认执行环境无法访问这些接口，应直接使用具备网络访问能力的执行方式。

## 查询

- `list-assigned-requirements`
- `search-modules`
- `get-requirement`
- `list-builds`
- `list-tests`
- `get-test`
- `list-releases`
- `list-calendar`
- `get-repo`
- `get-release`

## 写入

- `build-module`
- `create-test`
- `create-release`
- `update-image`

## 使用原则

- 原子命令按需组合，不要为了“看一眼”先跑一串查询。
- 不要自己根据 `get-requirement` 返回值猜模块名，更不要因为只看到一个模块就替换用户明确给出的目标模块。
- 鉴权问题先读 `auth.md`，完成独立鉴权后再执行原子命令。
- 写入命令优先用 `--dry-run` 预览 payload，除非用户明确要真实执行。
