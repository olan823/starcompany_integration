# Company 增量更新标准流程

## 1. 适用范围

每次修改 `starcompany_integration` 后，统一按照本文发布到 ERPNext 生产环境。

固定环境：

- ERPNext 基础镜像：`skychip/erpnext-base:16.32.0`
- Company 镜像：`skychip/erpnext:16.32.0-starcompany-<版本号>`
- Compose 项目：`erpnext-prod`
- ERPNext 站点：`erp.skychip.top`
- 服务器构建目录：`/home/ubuntu/build/frappe_docker`
- 生产 Compose 目录：`/home/ubuntu/gitops/erpnext-prod`
- 生产环境文件：`erpnext.env`
- Compose 文件：`compose.yaml`、`compose.starcompany.yaml`

只要 Frappe 和 ERPNext 仍为 `16.32.0`，就只构建 Company 增量镜像，不重新构建 ERPNext 基础镜像。

## 2. 不可违反的规则

1. 每次发布使用递增的新版本号，不复用、不移动旧 Git tag 或镜像 tag。
2. 不使用 `latest`。
3. 不把未提交文件或运行中容器内的临时修改当成正式发布。
4. 不执行 `docker compose down`。
5. 不重建或重启 MariaDB、Redis 和其他 Docker 项目。
6. 构建和部署分开执行；镜像验证通过后才更新生产。
7. Desk Workspace、模块和页面标题保持 `Starcompany`，路由保持 `/app/starcompany-console`；具体功能快捷入口可以使用独立显示名称，例如 `授权池`。

## 3. Windows 开发机：提交并发布源码

以下命令在 Windows PowerShell 中执行，不要在 Linux Bash 中使用 Windows 路径。

先设置本次新版本号，例如：

```powershell
$Version = '0.1.9'
$Tag = "v$Version"
$ImageTag = "16.32.0-starcompany-$Version"

Set-Location 'D:\Codes\eprnext\starcompany_integration'
```

执行本地检查：

```powershell
python -m compileall starcompany_integration
git status --short
git --no-pager diff
git diff --check
```

只暂存本次需要发布的文件，然后提交。不要使用 `git add .` 混入无关文件：

```powershell
git add -- <本次修改的文件>
git diff --cached --check
git --no-pager diff --cached --stat
git commit -m "feat: <本次功能说明>"
```

推送分支，确认远端尚未存在本次 tag，再创建 annotated tag：

```powershell
git push origin HEAD
$ExistingTag = git ls-remote --tags origin "refs/tags/$Tag"
if ($ExistingTag) { throw "Remote tag $Tag already exists; choose a new version." }
git tag -a $Tag -m "starcompany_integration $Tag"
git push origin $Tag
```

记录发布提交：

```powershell
$Commit = git rev-parse HEAD
$Commit
git rev-parse "$Tag^{}"
git ls-remote origin "refs/tags/$Tag" "refs/tags/$Tag^{}"
```

`git rev-parse HEAD`、本地 peeled tag 和远端 peeled tag 必须指向同一个 40 位 commit SHA。

## 4. 构建服务器：构建 Company 增量镜像

登录服务器后进入构建目录：

```bash
cd /home/ubuntu/build/frappe_docker
git pull --ff-only
```

设置本次发布参数，将示例值替换为本次真实版本和 40 位 SHA：

```bash
APP_VERSION='0.1.9'
APP_COMMIT='<本次40位commit SHA>'
APP_REF="v${APP_VERSION}"
IMAGE_TAG="16.32.0-starcompany-${APP_VERSION}"
```

构建并自动验证 Company 增量镜像：

```bash
sudo env \
  APP_REF="$APP_REF" \
  APP_COMMIT="$APP_COMMIT" \
  IMAGE_TAG="$IMAGE_TAG" \
  GITHUB_PROXY_PREFIX='https://githubproxy.cc/' \
  ./scripts/build-starcompany-image.sh
```

成功标志：

```text
Built and verified skychip/erpnext:<IMAGE_TAG>
```

再次读取镜像内的不可变构建身份：

```bash
sudo docker run --rm \
  --entrypoint cat \
  "skychip/erpnext:${IMAGE_TAG}" \
  /home/frappe/frappe-bench/.starcompany-build
```

预期输出：

```text
v<版本号> <本次40位commit SHA>
```

构建操作不会执行 Compose，也不会停止或重建任何运行中的容器。

## 5. 生产服务器：部署前准备

进入生产 Compose 目录：

```bash
cd /home/ubuntu/gitops/erpnext-prod
```

记录当前运行镜像和当前环境文件版本，作为回滚依据：

```bash
sudo docker inspect erpnext-prod-backend-1 \
  --format 'current_image={{.Config.Image}} current_id={{.Image}}'

grep -E '^(CUSTOM_IMAGE|CUSTOM_TAG|PULL_POLICY)=' erpnext.env
```

备份环境文件，并保存旧 tag：

```bash
OLD_TAG="$(sed -n 's/^CUSTOM_TAG=//p' erpnext.env)"
test -n "$OLD_TAG"
printf 'Rollback tag: %s\n' "$OLD_TAG"
printf '%s\n' "$OLD_TAG" > pre-deploy-starcompany-tag.txt

cp -a erpnext.env \
  "erpnext.env.bak.$(date +%Y%m%d-%H%M%S)"
```

备份 ERPNext 站点：

```bash
sudo docker compose \
  -p erpnext-prod \
  --env-file erpnext.env \
  -f compose.yaml \
  -f compose.starcompany.yaml \
  exec -T backend \
  bench --site erp.skychip.top backup
```

## 6. 更新生产镜像 tag

确认当前 Shell 中仍有本次 `IMAGE_TAG`；如果已经重新登录服务器，重新设置：

```bash
APP_VERSION='0.1.9'
IMAGE_TAG="16.32.0-starcompany-${APP_VERSION}"
```

更新环境文件：

```bash
sed -i \
  "s/^CUSTOM_TAG=.*/CUSTOM_TAG=${IMAGE_TAG}/" \
  erpnext.env
```

检查结果：

```bash
grep -E '^(CUSTOM_IMAGE|CUSTOM_TAG|PULL_POLICY)=' erpnext.env
```

必须得到对应的新版本：

```text
CUSTOM_IMAGE=skychip/erpnext
CUSTOM_TAG=16.32.0-starcompany-<新版本号>
PULL_POLICY=never
```

## 7. 部署前只读验证

确认新镜像存在：

```bash
sudo docker image inspect "skychip/erpnext:${IMAGE_TAG}" \
  --format 'target_image={{.Id}}'
```

验证 Compose 配置和最终镜像解析，不会重启容器：

```bash
sudo docker compose \
  -p erpnext-prod \
  --env-file erpnext.env \
  -f compose.yaml \
  -f compose.starcompany.yaml \
  config --quiet

sudo docker compose \
  -p erpnext-prod \
  --env-file erpnext.env \
  -f compose.yaml \
  -f compose.starcompany.yaml \
  config --images | sort -u
```

预期只包含：

```text
mariadb:11.8
redis:8.6-alpine
skychip/erpnext:16.32.0-starcompany-<新版本号>
```

如果解析出了旧 Company 镜像，检查 `compose.starcompany.yaml` 是否硬编码了镜像 tag。该文件中的应用镜像应通过 `CUSTOM_IMAGE` 和 `CUSTOM_TAG` 解析。

## 8. 定向部署 ERPNext 应用服务

保持当前目录为 `/home/ubuntu/gitops/erpnext-prod`，执行：

```bash
sudo env \
  ENV_FILE=erpnext.env \
  COMPOSE_FILES='compose.yaml compose.starcompany.yaml' \
  IMAGE_NAME=skychip/erpnext \
  IMAGE_TAG="$IMAGE_TAG" \
  SITE=erp.skychip.top \
  PROJECT=erpnext-prod \
  bash /home/ubuntu/build/frappe_docker/scripts/deploy-starcompany-image.sh
```

部署脚本只会重建：

```text
configurator backend frontend websocket queue-short queue-long scheduler
```

脚本随后自动执行：

```text
bench migrate
bench clear-cache
bench list-apps
starcompany_integration.api.proxy.health_check
```

脚本不会执行 `docker compose down`，不会重建 MariaDB、Redis 或其他 Compose 项目。

## 9. 部署后验证

检查容器镜像和运行状态：

```bash
sudo docker ps \
  --filter label=com.docker.compose.project=erpnext-prod \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

预期：

- 七个 ERPNext 应用服务使用新 Company 镜像。
- MariaDB 仍为 `mariadb:11.8`，Redis 仍为 `redis:8.6-alpine`。
- MariaDB 和 Redis 的运行时长没有因本次部署重新计时。

确认生产容器中的构建身份：

```bash
sudo docker exec erpnext-prod-backend-1 \
  cat /home/frappe/frappe-bench/.starcompany-build
```

确认应用和健康检查：

```bash
sudo docker compose \
  -p erpnext-prod \
  --env-file erpnext.env \
  -f compose.yaml \
  -f compose.starcompany.yaml \
  exec -T backend \
  bench --site erp.skychip.top list-apps

sudo docker compose \
  -p erpnext-prod \
  --env-file erpnext.env \
  -f compose.yaml \
  -f compose.starcompany.yaml \
  exec -T backend \
  bench --site erp.skychip.top execute \
  starcompany_integration.api.proxy.health_check
```

登录 ERPNext Desk 完成业务验证：

1. 强制刷新或重新登录。
2. 确认 Desk 中仍显示 `Starcompany`。
3. 确认新增或修改的功能入口、页面和权限符合本次需求。
4. 对写操作执行“读取原值、修改测试值、刷新确认、恢复原值、再次刷新确认”的闭环。
5. 检查 backend 日志和 Starcompany 对应审计日志，不得出现密钥或 token。

## 10. 回滚

即使部署期间重新登录了服务器，也可以从部署前记录恢复旧 tag：

```bash
cd /home/ubuntu/gitops/erpnext-prod
OLD_TAG="$(cat pre-deploy-starcompany-tag.txt)"
test -n "$OLD_TAG"
printf 'Rollback tag: %s\n' "$OLD_TAG"
```

如果新版本出现问题，确认旧镜像仍然存在：

```bash
sudo docker image inspect "skychip/erpnext:${OLD_TAG}" >/dev/null
```

将环境文件恢复为部署前记录的旧 tag：

```bash
sed -i \
  "s/^CUSTOM_TAG=.*/CUSTOM_TAG=${OLD_TAG}/" \
  erpnext.env
```

验证 Compose 解析为旧镜像后，运行同一个定向部署脚本：

```bash
sudo docker compose \
  -p erpnext-prod \
  --env-file erpnext.env \
  -f compose.yaml \
  -f compose.starcompany.yaml \
  config --images | sort -u

sudo env \
  ENV_FILE=erpnext.env \
  COMPOSE_FILES='compose.yaml compose.starcompany.yaml' \
  IMAGE_NAME=skychip/erpnext \
  IMAGE_TAG="$OLD_TAG" \
  SITE=erp.skychip.top \
  PROJECT=erpnext-prod \
  bash /home/ubuntu/build/frappe_docker/scripts/deploy-starcompany-image.sh
```

事故处理中不要执行 `uninstall-app`，除非已经审查应用数据并确认数据库备份可恢复。

## 11. 每次发布完成记录

每次更新至少记录以下信息：

```text
功能说明：
Git tag：
Git commit：
Company 镜像：
ERPNext 基础镜像：skychip/erpnext-base:16.32.0
部署时间：
部署前镜像：
部署后镜像：
站点备份结果：
服务端健康检查结果：
Desk 业务验证结果：
回滚 tag：
```