"""账号验证工具

通过登录页面 https://login.live.com/ 验证邮箱是否注册成功。
- 输入邮箱 → 点"下一步"
- 出现密码框 = 账号存在
- 出现"找不到 Microsoft 帐户" = 账号不存在

用法:
  python verify.py                          # 验证 accounts.txt 中所有 [unconfirmed] 的账号
  python verify.py --all                    # 验证 accounts.txt 中所有账号
  python verify.py --email adrienne3509@hotmail.com  # 验证单个邮箱
  python verify.py --file emails.txt       # 验证文件中的邮箱（每行一个）
"""

import os
import re
import argparse
from datetime import datetime

from patchright.sync_api import sync_playwright
from config import load_config
from logger import logger


def parse_accounts_txt(filepath: str, only_unconfirmed: bool = True) -> list[tuple[str, str]]:
    """从 accounts.txt 解析邮箱和密码。

    Returns:
        [(email, password), ...]
    """
    results = []
    if not os.path.exists(filepath):
        logger.error(f"文件不存在: {filepath}")
        return results

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过分割线和批次头
            if not line or line.startswith("=") or line.startswith("-"):
                continue
            if line.startswith("批次") or line.startswith("代理") or line.startswith("成功") or line.startswith("失败"):
                continue

            # 解析格式：2026-07-15 21:37:23  email@hotmail.com  password  [status]
            match = re.match(
                r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+(\S+)\s+(\S+)(?:\s+\[(\w+)\])?",
                line,
            )
            if match:
                email, password, status = match.groups()
                if only_unconfirmed and status == "confirmed":
                    continue  # 跳过已确认的
                if only_unconfirmed and status is None:
                    continue  # 跳过没有状态标记的（旧格式）
                results.append((email, password))

    return results


def verify_email(page, email: str) -> tuple[bool, str]:
    """验证单个邮箱是否存在。

    Returns:
        (exists: bool, message: str)
    """
    try:
        # 进入登录页
        page.goto("https://login.live.com/", timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        # 输入邮箱
        email_input = page.locator('input[type="email"]')
        if email_input.count() == 0:
            # 尝试其他选择器
            email_input = page.get_by_text("电子邮件或电话号码")
            email_input = page.locator('input').first

        email_input.fill(email)
        page.wait_for_timeout(500)

        # 点"下一步"
        page.locator('button[type="submit"]').click(timeout=5000)
        # 也尝试 primaryButton
        # page.locator('[data-testid="primaryButton"]').click(timeout=5000)

        # 等结果：密码框出现 = 存在，"找不到" = 不存在
        try:
            # 等密码框出现（最多 10 秒）
            page.locator('input[type="password"]').wait_for(timeout=10000)
            return True, "账号存在"
        except Exception:
            pass

        # 检查是否显示"找不到"
        if page.get_by_text("找不到 Microsoft 帐户").count() > 0:
            return False, "账号不存在"
        if page.get_by_text("找不到").count() > 0:
            return False, "账号不存在"

        # 其他情况
        return False, "未知状态"

    except Exception as e:
        return False, f"验证异常: {e}"


def verify_batch(
    accounts: list[tuple[str, str]],
    headless: bool = False,
    proxy: str = None,
) -> list[tuple[str, str, bool, str]]:
    """批量验证账号。

    Returns:
        [(email, password, exists, message), ...]
    """
    results = []
    total = len(accounts)

    if total == 0:
        logger.info("没有需要验证的账号")
        return results

    logger.info(f"开始验证 {total} 个账号...")

    p = sync_playwright().start()

    launch_args = [
        "--lang=zh-CN",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    ]

    proxy_settings = None
    if proxy:
        proxy_settings = {"server": proxy, "bypass": "localhost"}

    b = p.chromium.launch(
        headless=headless,
        args=launch_args,
        proxy=proxy_settings,
    )

    context = b.new_context(locale="zh-CN")
    page = context.new_page()

    for i, (email, password) in enumerate(accounts):
        exists, msg = verify_email(page, email)
        status = "存在" if exists else "不存在"
        logger.info(f"[{i+1}/{total}] {email} → {status} ({msg})")
        results.append((email, password, exists, msg))
        page.wait_for_timeout(1000)  # 间隔

    context.close()
    b.close()
    p.stop()

    # 统计
    exists_count = sum(1 for r in results if r[2])
    not_exists_count = total - exists_count
    logger.info(f"\n[Result] 共 {total} 个 | 存在 {exists_count} | 不存在 {not_exists_count}")

    return results


def save_results(results: list[tuple[str, str, bool, str]], filepath: str):
    """保存验证结果到文件。"""
    with open(filepath, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"\n{'='*60}\n")
        f.write(f"验证时间  {timestamp}\n")
        f.write(f"共 {len(results)} 个账号\n")
        f.write(f"{'='*60}\n")
        for email, password, exists, msg in results:
            status = "存在" if exists else "不存在"
            f.write(f"{timestamp}  {email}  {status}  {msg}\n")
        f.write(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="验证 Outlook 邮箱是否注册成功")
    parser.add_argument("--email", type=str, help="验证单个邮箱")
    parser.add_argument("--file", type=str, help="从文件验证（每行一个邮箱）")
    parser.add_argument("--all", action="store_true", help="验证 accounts.txt 中所有账号")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    args = parser.parse_args()

    config = load_config()
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Results")
    accounts_file = os.path.join(results_dir, "accounts.txt")
    verify_result_file = os.path.join(results_dir, "verify_result.txt")

    # 收集要验证的账号
    accounts = []

    if args.email:
        accounts = [(args.email, "")]
    elif args.file:
        with open(args.file, "r") as f:
            accounts = [(line.strip(), "") for line in f if line.strip() and not line.startswith("#")]
    elif args.all:
        accounts = parse_accounts_txt(accounts_file, only_unconfirmed=False)
    else:
        # 默认只验证 unconfirmed 的
        accounts = parse_accounts_txt(accounts_file, only_unconfirmed=True)

    if not accounts:
        logger.info("没有需要验证的账号")
        # 如果没有 unconfirmed 的，尝试验证所有
        accounts = parse_accounts_txt(accounts_file, only_unconfirmed=False)
        if accounts:
            logger.info(f"改为验证所有 {len(accounts)} 个账号")

    if not accounts:
        logger.error("没有找到任何账号")
        raise SystemExit(1)

    # 验证
    proxy = config.get("proxy", None)
    results = verify_batch(accounts, headless=args.headless, proxy=proxy)

    # 保存结果
    save_results(results, verify_result_file)
    logger.info(f"验证结果已保存到 {verify_result_file}")
