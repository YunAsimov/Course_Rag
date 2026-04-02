# 1Panel 部署说明

这个目录提供了可直接用于 1Panel 的容器编排文件。

## 准备

1. 将整个项目上传到 1Panel 服务器，例如 `/opt/course-rag`
2. 在服务器上进入 `deploy/1panel/`
3. 复制 `.env.example` 为 `.env`
4. 修改 `.env` 中至少这几个值：

```env
OPENAI_API_KEY=你的 DashScope / OpenAI 兼容接口密钥
MYSQL_PASSWORD=应用数据库密码
MYSQL_ROOT_PASSWORD=MySQL root 密码
```

## 在 1Panel 中启动

1. 打开 `容器 -> 编排 -> 创建编排`
2. 选择 `路径选择`
3. 选中本文件夹里的 `docker-compose.yml`
4. 启动编排

启动成功后，应用会监听主机本地端口 `127.0.0.1:${APP_HOST_PORT}`，默认是 `127.0.0.1:17860`。

## 绑定域名

推荐再通过 1Panel 创建一个反向代理网站：

1. 打开 `网站 -> 创建网站`
2. 选择 `反向代理`
3. 代理地址填写 `http://127.0.0.1:17860`
4. 绑定你的域名
5. 在网站设置里开启 HTTPS

## 持久化目录

当前编排会持久化这些内容：

- `storage/`：用户上传资料、会话密钥等
- `logs/`：应用日志
- MySQL 数据卷：账号、历史记录、资料元数据

## 说明

- 编排里使用 `PROJECT_ROOT` 指向项目根目录，适合 1Panel 在临时目录中执行 compose 的场景
- 如果你要改端口，修改 `.env` 中的 `APP_HOST_PORT`
- 如果你已经在 1Panel 中单独安装了 MySQL，也可以去掉 compose 里的 `mysql` 服务，并把 `.env` 里的 `MYSQL_HOST` 改成实际地址

