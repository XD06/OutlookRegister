# OutlookRegister

基于 **Python + Patchright / Playwright** 的 Outlook / Hotmail 自动化批量注册机与辅助邮箱绑定系统。

> 📖 **深入了解架构设计与全文件技术实现细节，请参阅** 👉 **[ARCHITECTURE.md (系统架构与技术实现规范)](file:///c:/Users/dsk/Desktop/OutlookRegister/ARCHITECTURE.md)**

---

## 快速概览

1. **拟人化批量注册**：模拟真人键鼠行为轨迹（贝塞尔曲线、打字延迟、防风控策略），自动破解按压/图形验证码，支持 `@outlook.com` 与 `@hotmail.com`。
2. **时区与语言对齐**：通过代理出口 IP 自动查询 GeoIP，并将浏览器 Context 的时区与语言动态对齐，大幅降低风控拦截率。
3. **同会话辅助邮箱绑定（Post-Register Binder）**：注册成功后在同浏览器会话中直接进入安全设置，绑定 1~2 个备用辅助邮箱（支持 Cloudflare Mail Worker 临时邮箱与自建 API，内置三级跳板降级机制）。
4. **认证凭据落盘**：支持 Session Cookies 提取（`outlook_session.jsonl`）与 Microsoft OAuth2 Token 授权提取（`outlook_token.jsonl`）。
5. **代理池灵活管理**：支持单代理（`single`）、文件轮换（`file`）、本地端口池（`pool`）、独享代理及自动模式（`auto`），状态自动持久化保存。

---

## 快速开始

### 1. 环境准备

```bat
cd C:\Users\dsk\Desktop\OutlookRegister

:: 1. 安装依赖包
pip install -r requirements.txt

:: 2. 安装 Patchright 专用的 Chromium 浏览器内核
patchright install chromium
```

### 2. 启动运行

```bat
:: 直接通过 Python 运行
python main.py

:: 或通过批处理脚本启动
run_batch.bat
```

---

## 常用配置（`config.json`）

系统核心参数通过 `config.json` 配置，常用设置如下：

```json
{
  "choose_browser": "patchright",
  "email_suffix": "@hotmail.com",
  "proxy_mode": "pool",
  "proxy": "http://127.0.0.1:10808",
  "headless": false,
  "concurrent_flows": 1,
  "max_tasks": 30,
  "bot_protection_wait": 11,
  "bind_enabled": true,
  "bind_target_count": [1, 2],
  "bind_mail_source": "random",
  "bind_cf_enabled": true
}
```

### 核心参数速查

| 配置项 | 默认值 | 作用说明 |
|---|---|---|
| `choose_browser` | `"patchright"` | 浏览器内核（推荐 `patchright` 自带反检测补丁） |
| `proxy_mode` | `"pool"` | 代理模式：`"single"`（单代理） / `"file"`（文件轮换） / `"pool"`（端口池） / `"auto"` |
| `headless` | `false` | 是否无头运行（调试建议设为 `false` 可视化查看） |
| `concurrent_flows`| `1` | 并发线程数 |
| `max_tasks` | `30` | 任务总数（设为 `0` 则自动根据代理数/端口数匹配） |
| `bind_enabled` | `true` | 是否在注册成功后自动绑定辅助安全邮箱 |
| `bind_target_count`| `[1, 2]` | 绑定数量：数字、区间数组（如 `[1, 2]`）或字符串（`"1-2"`） |
| `bind_mail_source` | `"random"`| 辅助邮箱生成源：`"cf"`（Cloudflare 临时邮箱） / `"legacy"`（自建 API） / `"random"` |

---

## 结果文件（`Results/`）

所有运行产物均保存在 `Results/` 目录中：

| 产物文件 | 说明 |
|---|---|
| `Results/accounts.txt` | 批次运行汇总、成功/失败明细与国家 IP 成功率排行榜 |
| `Results/success_log.txt` | 成功账号明细（包含密码、代理、时区、验证码耗时指标等） |
| `Results/outlook_session.jsonl` | Session 模式提取的有效 Microsoft 认证 Cookies |
| `Results/outlook_token.jsonl` | OAuth2 模式换取的 Access / Refresh Token |
| `Results/bind-status.csv` | 辅助邮箱绑定明细流水记录 |
| `Results/bind-recovery-map.json` | 注册主账号 $\to$ 已绑辅助邮箱全量映射字典 |

---

## 常用工具

- **账号存活批量检测**：
  ```bat
  python verify.py --all --headless
  ```
- **代理连通性检测**：
  ```bat
  test.bat
  ```
- **绑定模块单元测试**：
  ```bat
  python -m unittest discover -s recovery_binder\tests -v
  ```

---

## 深入技术文档

关于系统分层架构、状态机模型、反检测算法与全文件职责明细，请直接查阅：
👉 **[ARCHITECTURE.md (系统架构与技术实现规范)](file:///c:/Users/dsk/Desktop/OutlookRegister/ARCHITECTURE.md)**

---

## 鸣谢与上游仓库 (Upstream & Acknowledgements)

- **上游项目 (Upstream)**: 本项目基于 [LainsNL/OutlookRegister](https://github.com/LainsNL/OutlookRegister) 演进重构，在此对原作者的开源贡献表示衷心感谢。
- **扩展与优化**: 在原项目基础上重构了代理池机制、增强了反爬风控对抗与 GeoIP 动态对齐、新增了 Post-Register 安全辅助邮箱自动绑定框架（支持 Cloudflare Mail Worker 与自建 API 双通道）、修复了多处异步会话与错误处理逻辑。

---

## 开源协议 (License)

本项目采用 [MIT License](LICENSE) 许可协议。使用者需遵循相关法律法规，仅限用于合法测试与研究学习目的。

