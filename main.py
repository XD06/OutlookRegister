"""OutlookRegister 主入口

负责配置加载、控制器选择、并发任务调度。
"""

import os
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future

from config import load_config, get_results_dir
from logger import logger
from get_token import get_access_token
from utils import random_email, generate_strong_password
from controllers.patchright_controller import PatchrightController
from controllers.playwright_controller import PlaywrightController


def process_single_flow(controller, config: dict) -> tuple:
    """执行单次注册流程。

    Returns:
        (success: bool, country: str)
    """
    page = None

    try:
        controller.thread_local.deadline = time.monotonic() + 300
        page = controller.get_thread_page()
        if page is None:
            logger.error("[Error: Browser] - 无法获取页面，浏览器启动可能失败")
            return False, _get_country(controller)

        email = random_email()
        password = generate_strong_password()

        # 调用 controller 特定的注册方法
        result = controller.outlook_register(page, email, password)

        if not result:
            return False, _get_country(controller)

        # Post-register recovery bind (same page/session). Failures do not flip register success.
        if config.get("bind_enabled", True):
            try:
                from recovery_binder import bind_recovery_emails

                actual_email = getattr(controller.thread_local, "used_email", email)
                full_email = f"{actual_email}{controller.email_suffix}"
                bind_cfg = dict(config)
                bind_cfg["bind_session_proxy"] = controller.get_current_proxy()
                br = bind_recovery_emails(
                    page,
                    full_email,
                    password,
                    bind_cfg,
                    results_dir=controller.results_dir,
                )
                logger.info(
                    f"[Bind: Result] status={br.status} emails={br.emails} note={br.note}"
                )
            except Exception as bind_err:
                logger.error(f"[Bind: Error] {bind_err}")

        if not controller.enable_oauth2:
            actual_email = getattr(controller.thread_local, 'used_email', email)
            session_verified = False
            try:
                all_cookies = page.context.cookies()
                ms_cookies = [c for c in all_cookies
                              if "live.com" in c.get("domain", "") or "microsoftonline" in c.get("domain", "")]
                auth_names = [c["name"] for c in ms_cookies
                              if any(k in c["name"].lower() for k in ("auth", "msp", "rps", "secure", "token"))]
                logger.info(f"[Verify: Session] - {len(ms_cookies)} Microsoft cookies, 认证: {auth_names}")
                if auth_names:
                    session_path = os.path.join(controller.results_dir, "outlook_session.jsonl")
                    record = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "email": f"{actual_email}{controller.email_suffix}",
                        "password": password,
                        "auth_cookies": auth_names,
                        "cookies": ms_cookies,
                    }
                    with open(session_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    logger.info(f"[Success: Session] - {actual_email}{controller.email_suffix}")
                    session_verified = True
                else:
                    logger.warning(f"[Unverified: Session] - {actual_email}{controller.email_suffix} 无认证 cookies")
            except Exception as e:
                logger.error(f"[Verify: Session] - 获取失败: {e}")

            if not session_verified:
                unverified_path = os.path.join(controller.results_dir, "unverified_session.txt")
                with open(unverified_path, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  "
                            f"{actual_email}{controller.email_suffix}  {password}  [no_session]\n")
            _log_success(controller, config, actual_email, password)
            return True, _get_country(controller)

        # OAuth2 保险：等待会话稳定，能拿到 token 才算真正注册成功
        actual_email = getattr(controller.thread_local, 'used_email', email)
        logger.info(f"[Verify: TokenAuth] - 等待 5 秒会话稳定后验证 token...")
        page.wait_for_timeout(5000)
        proxy = controller.get_current_proxy()
        token_result = get_access_token(page, actual_email, config, proxy)
        if token_result[0]:
            refresh_token, access_token, expire_at = token_result
            token_path = os.path.join(controller.results_dir, "outlook_token.jsonl")
            record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "email": f"{actual_email}{controller.email_suffix}",
                "password": password,
                "refresh_token": refresh_token,
                "access_token": access_token,
                "expire_at": expire_at,
            }
            with open(token_path, "a", encoding="utf-8") as f2:
                f2.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.info(f"[Success: TokenAuth] - {actual_email}{controller.email_suffix}")
            _log_success(controller, config, actual_email, password)
            return True, _get_country(controller)
        else:
            logger.warning(f"[Fail: TokenAuth] - {actual_email}{controller.email_suffix} 注册成功但未拿到 token，判定为失败")
            return False, _get_country(controller)

    except Exception as e:
        logger.error(f"[Error: Flow] - 单次注册流程异常: {e}", exc_info=True)
        return False, _get_country(controller)

    finally:
        controller.clean_up(page, "done_browser")


def _get_country(controller) -> str:
    """从控制器的线程局部变量获取当前代理 IP 的国家。"""
    geo = getattr(controller.thread_local, 'geo', None)
    if geo:
        return geo.get('country', 'Unknown')
    return 'Unknown'


def _log_success(controller, config, email, password) -> None:
    """记录成功注册的详细信息到 success_log.txt，用于分析规律。"""
    from datetime import datetime
    # 用实际使用的邮箱（可能被页面建议替换过）
    actual_email = getattr(controller.thread_local, 'used_email', email)
    geo = getattr(controller.thread_local, 'geo', {}) or {}
    proxy = getattr(controller.thread_local, 'current_proxy', 'Unknown')
    captcha = getattr(controller.thread_local, 'captcha_data', {}) or {}
    log_file = os.path.join(controller.results_dir, "success_log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (
        f"{timestamp}\t"
        f"{actual_email}{controller.email_suffix}\t"
        f"{password}\t"
        f"proxy={proxy}\t"
        f"country={geo.get('country', '?')}\t"
        f"countryCode={geo.get('countryCode', '?')}\t"
        f"timezone={geo.get('timezone', '?')}\t"
        f"browser={config.get('choose_browser', '?')}\t"
        f"suffix={controller.email_suffix}\t"
        f"wait={controller.wait_time}\t"
        f"captcha_attempt={captcha.get('attempt', '?')}\t"
        f"first_hold={captcha.get('first_hold', '?')}ms\t"
        f"gap={captcha.get('gap', '?')}ms\t"
        f"second_react={captcha.get('second_react', '?')}ms\t"
        f"second_hold={captcha.get('second_hold', '?')}ms"
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_concurrent_flows(
    controller, config: dict, concurrent_flows: int = 10, max_tasks: int = 100
) -> None:
    """并发执行注册任务。"""
    from datetime import datetime

    task_counter = 0
    succeeded_tasks = 0
    failed_tasks = 0
    country_stats = {}  # country -> {"success": 0, "fail": 0}
    result_file = os.path.join(controller.results_dir, "accounts.txt")
    batch_start_time = datetime.now()
    batch_start = batch_start_time.strftime("%Y-%m-%d %H:%M:%S")

    # 写批次头
    pool = config.get("proxy_pool", {})
    proxy_file = config.get("proxy_file", "")
    proxy_info = f"文件 {proxy_file}" if proxy_file else f"端口 {pool.get('start', '?')}-{pool.get('end', '?')}"
    with open(result_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"批次开始  {batch_start}\n")
        f.write(f"代理: {proxy_info} | 任务: {max_tasks} | 并发: {concurrent_flows}\n")
        f.write(f"{'='*60}\n")

    with ThreadPoolExecutor(max_workers=concurrent_flows) as executor:
        running_futures: set[Future] = set()

        while task_counter < max_tasks or len(running_futures) > 0:
            done_futures = {f for f in running_futures if f.done()}
            for future in done_futures:
                try:
                    success, country = future.result()
                    if success:
                        succeeded_tasks += 1
                    else:
                        failed_tasks += 1
                    # 国家统计
                    if country not in country_stats:
                        country_stats[country] = {"success": 0, "fail": 0}
                    if success:
                        country_stats[country]["success"] += 1
                    else:
                        country_stats[country]["fail"] += 1
                except Exception as e:
                    failed_tasks += 1
                    logger.error(f"[Error: Future] - 任务异常: {e}")
                running_futures.remove(future)

                # 实时进度
                total_done = succeeded_tasks + failed_tasks
                logger.info(
                    f"[Progress] {total_done}/{max_tasks} | "
                    f"成功 {succeeded_tasks} | 失败 {failed_tasks}"
                )

            while len(running_futures) < concurrent_flows and task_counter < max_tasks:
                new_future = executor.submit(process_single_flow, controller, config)
                running_futures.add(new_future)
                task_counter += 1
                if max_tasks > 1 and task_counter % (max_tasks // 2) == 0:
                    logger.info(f"已提交 {task_counter}/{max_tasks} 任务.")
                elif max_tasks == 1:
                    logger.info(f"已提交 {task_counter}/{max_tasks} 任务.")

            time.sleep(0.5)

    # 写批次尾（含统计）
    batch_end_time = datetime.now()
    batch_end = batch_end_time.strftime("%Y-%m-%d %H:%M:%S")
    duration = batch_end_time - batch_start_time
    minutes, seconds = divmod(duration.total_seconds(), 60)
    total = succeeded_tasks + failed_tasks
    success_rate = (succeeded_tasks / total * 100) if total > 0 else 0
    fail_rate = (failed_tasks / total * 100) if total > 0 else 0

    with open(result_file, "a", encoding="utf-8") as f:
        f.write(f"{'-'*60}\n")
        f.write(f"批次结束  {batch_end}\n")
        f.write(f"成功 {succeeded_tasks}/{total} ({success_rate:.1f}%)  "
                f"失败 {failed_tasks}/{total} ({fail_rate:.1f}%)  "
                f"耗时 {int(minutes)}分{int(seconds)}秒\n")

        # 国家 IP 通过率排行
        if country_stats:
            f.write(f"\n--- 国家 IP 通过率排行 ---\n")
            ranked = sorted(country_stats.items(),
                           key=lambda x: x[1]["success"] / max(sum(x[1].values()), 1),
                           reverse=True)
            for country, stats in ranked:
                c_total = stats["success"] + stats["fail"]
                c_rate = stats["success"] / c_total * 100 if c_total > 0 else 0
                f.write(f"  {country}: {stats['success']}/{c_total} ({c_rate:.0f}%)\n")

        f.write(f"{'='*60}\n")

    logger.info(
        f"\n[Result] 共 {total}, 成功 {succeeded_tasks} ({success_rate:.1f}%), "
        f"失败 {failed_tasks} ({fail_rate:.1f}%)"
    )

    # 控制台也输出国家排行
    if country_stats:
        ranked = sorted(country_stats.items(),
                       key=lambda x: x[1]["success"] / max(sum(x[1].values()), 1),
                       reverse=True)
        logger.info("[Country] 国家 IP 通过率排行:")
        for country, stats in ranked:
            c_total = stats["success"] + stats["fail"]
            c_rate = stats["success"] / c_total * 100 if c_total > 0 else 0
            logger.info(f"  {country}: {stats['success']}/{c_total} ({c_rate:.0f}%)")


def create_controller(config: dict):
    """根据配置选择浏览器控制器。

    Args:
        config: 配置字典

    Returns:
        控制器实例

    Raises:
        ValueError: 不支持的浏览器类型
    """
    browser_type = config["choose_browser"]
    if browser_type == "patchright":
        return PatchrightController(config)
    elif browser_type == "playwright":
        return PlaywrightController(config)
    else:
        raise ValueError(
            f"不支持的浏览器类型: '{browser_type}'，请填写 'patchright' 或 'playwright'"
        )


if __name__ == "__main__":
    # 1. 加载并校验配置
    config = load_config()
    get_results_dir()

    concurrent_flows = config["concurrent_flows"]

    # 2. 创建控制器（如果配置了 proxy_file 会在此加载代理列表）
    try:
        selected_controller = create_controller(config)
    except ValueError as e:
        logger.error(str(e))
        raise SystemExit(1)

    # 3. 计算任务数：max_tasks=0 时自动判断
    max_tasks = config["max_tasks"]
    api_config = config.get("proxy_api", {})
    if max_tasks == 0:
        if api_config.get("enable"):
            # API 模式：无限循环，代理用完自动提取新的
            max_tasks = 99999
            logger.info("[Config] max_tasks=0, API 模式，持续运行直到 Ctrl+C")
        else:
            # 文件代理池或端口代理池：按数量跑一轮
            rotator = getattr(selected_controller, '_rotator', None)
            if rotator and len(rotator) > 0:
                max_tasks = len(rotator)
                logger.info(f"[Config] max_tasks=0, 文件代理池共 {max_tasks} 个代理")
            else:
                pool = config.get("proxy_pool")
                if pool:
                    max_tasks = pool["end"] - pool["start"] + 1
                    logger.info(f"[Config] max_tasks=0, 端口代理池 {pool['start']}-{pool['end']} = {max_tasks}")
                else:
                    max_tasks = 1
                    logger.info("[Config] max_tasks=0, 无代理池，设为 1")

    # 3. 运行并发注册（Ctrl+C 可随时终止）
    try:
        run_concurrent_flows(selected_controller, config, concurrent_flows, max_tasks)
    except KeyboardInterrupt:
        logger.info("[Manual] 收到 Ctrl+C，正在停止...")
    finally:
        selected_controller.clean_up(cleanup_type="all_browser")
