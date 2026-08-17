# Thinking Lab — Daily Update Edition

这是一个不需要 OpenAI API 的个人阅读与思考网页。

## 它如何每天更新

GitHub Actions 每天 00:00 UTC（东八区约 08:00）运行 `scripts/update_news.py`，
从公开 RSS 搜索源抓取三个主题的新内容，并写入 `data/news.json`。
GitHub Pages 托管 `index.html`，网页打开时直接读取这个 JSON。

因此：
- 不需要额外购买 OpenAI API；
- 抓取发生在 GitHub 云端，不受本地浏览器 CORS 限制；
- 个人 Ideas / Reading Notes 保存在浏览器 localStorage，不上传到公开仓库。

## 5 分钟部署

1. 注册/登录 GitHub。
2. 新建一个 **Public** repository，例如 `thinking-lab`。
3. 把本项目所有文件上传到仓库根目录。
4. 在仓库进入 **Settings → Pages**。
5. 在 Build and deployment 中选择 **Deploy from a branch**，
   Branch 选择 `main`，目录选择 `/ (root)`，保存。
6. 进入 **Actions**，确认 `Update Thinking Lab` workflow 已启用。
   可先点 `Run workflow` 手动运行一次。
7. 几分钟后 Pages 页面会给出你的固定网址。

## 文件结构

- `index.html`：网页
- `scripts/update_news.py`：抓取新闻
- `data/news.json`：每天更新的数据
- `.github/workflows/update.yml`：每日自动任务

## 隐私提示

仓库是公开的，所以不要把私人笔记写入仓库文件。
网页中的个人笔记默认只存在你电脑浏览器的 localStorage。
