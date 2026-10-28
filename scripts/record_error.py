#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
record_error.py - 考研英语完形填空错题记录脚本
将错题以 YAML frontmatter + 正文格式只追加写入错题本.md
支持单条与批量 (JSON 数组) 追加、ID 自动去重递增与 12 类错误枚举/能力短板校验。
归档成功后默认自动删除输入 JSON 临时文件（--keep-json 可保留），并尝试清理因此变空的临时父目录（最多向上两级，仅删空目录），无需调用方手动清理。
"""

import sys
import os
import re
import json
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# 12 类完形填空错误类型封闭枚举
ERROR_TYPES = [
    "宇宙定级错误",
    "直觉先入为主",
    "逻辑关系误判",
    "态度极性倒错",
    "动宾/主谓不配",
    "修饰限定背离",
    "及物/不及物违背",
    "词义/僻义误解",
    "虚词同义通斥误选",
    "细节背离主旨",
    "时序与时态悖论",
    "选项误读"
]

# 能力短板封闭集合
ABILITY_SHORTBOARDS = ["词汇", "语法", "主旨"]

DEFAULT_FILE_NAME = "错题本.md"

def sanitize_notebook_path(raw_path: str) -> str:
    """
    对错题本路径进行安全净化与自愈：
    1. 若因环境编码剥离等原因导致文件名退化为 '.md'，自动纠偏至 '<parent>/考研英语/错题本.md'；
    2. 若路径指向已存在的目录或以斜杠结尾，自动在该目录下追加 '考研英语/错题本.md'（若目录已是 '考研英语' 则追加 '错题本.md'）；
    3. 保证返回绝对路径。
    """
    if not raw_path:
        return ""
    p = os.path.expanduser(raw_path.strip())
    base = os.path.basename(p)
    parent = os.path.dirname(p)

    if base == ".md":
        if os.path.basename(parent) == "考研英语":
            return os.path.abspath(os.path.join(parent, DEFAULT_FILE_NAME))
        return os.path.abspath(os.path.join(parent, "考研英语", DEFAULT_FILE_NAME))

    if os.path.isdir(p) or p.endswith("/") or p.endswith("\\"):
        clean_p = p.rstrip("/\\")
        if os.path.basename(clean_p) == "考研英语":
            return os.path.abspath(os.path.join(clean_p, DEFAULT_FILE_NAME))
        return os.path.abspath(os.path.join(clean_p, "考研英语", DEFAULT_FILE_NAME))

    return os.path.abspath(p)


def get_default_notebook_path() -> str:
    """
    智能解析错题本安全持久化存储路径，彻底与 Skill 目录解耦（保障更新/重装 Skill 绝不丢失）：
    1. 环境变量优先：KAOYAN_ERROR_NOTEBOOK 或 ERROR_NOTEBOOK_PATH（带自动路径自愈）
    2. Open Minis 外部挂载 Documents 优先（/var/minis/mounts/Documents/考研英语/错题本.md）
    3. Android 手机公共文档目录原生探测：
       - /storage/emulated/0/Documents/考研英语/错题本.md
       - /sdcard/Documents/考研英语/错题本.md
       - /storage/emulated/0/Download/考研英语/错题本.md
       - /sdcard/Download/考研英语/错题本.md
    4. Open Minis 沙盒持久工作区降级：
       - /var/minis/workspace/错题本.md
    5. PC / 常规环境（Windows / macOS / Linux）公共文档目录：
       - ~/Documents/考研英语/错题本.md
    6. 全局用户主目录安全兜底：
       - ~/.free-kaoyan-cloze/错题本.md
    """
    # 1. 环境变量优先（进行路径自愈净化）
    env_path = os.environ.get("KAOYAN_ERROR_NOTEBOOK") or os.environ.get("ERROR_NOTEBOOK_PATH")
    if env_path:
        return sanitize_notebook_path(env_path)

    # 2. Open Minis 外部挂载目录与 Android 沙盒优先
    is_android_or_minis = (os.name != 'nt') or os.path.exists("/var/minis")
    if is_android_or_minis:
        # 优先检测 Open Minis 挂载的外部目录
        minis_mount_candidates = [
            "/var/minis/mounts/Documents/考研英语/错题本.md",
            "/var/minis/mounts/documents/考研英语/错题本.md",
            "/var/minis/mounts/Documents/错题本.md",
            "/var/minis/mounts/documents/错题本.md",
        ]
        if os.path.isdir("/var/minis/mounts"):
            try:
                for entry in os.listdir("/var/minis/mounts"):
                    sub = os.path.join("/var/minis/mounts", entry)
                    if os.path.isdir(sub) and entry.lower() in ["documents", "document", "docs"]:
                        cand = os.path.join(sub, "考研英语", DEFAULT_FILE_NAME)
                        if cand not in minis_mount_candidates:
                            minis_mount_candidates.insert(0, cand)
            except Exception:
                pass

        for cand in minis_mount_candidates:
            try:
                parent = os.path.dirname(cand)
                mount_root = parent
                while mount_root and not os.path.exists(mount_root) and mount_root != "/":
                    mount_root = os.path.dirname(mount_root)
                if mount_root and mount_root != "/" and os.path.exists(mount_root):
                    os.makedirs(parent, exist_ok=True)
                    test_file = os.path.join(parent, ".perm_test")
                    with open(test_file, "w", encoding="utf-8") as f:
                        f.write("1")
                    os.remove(test_file)
                    return cand
            except Exception:
                continue

        # 3. Android 原生公共存储路径探测
        android_candidates = [
            "/storage/emulated/0/Documents/考研英语/错题本.md",
            "/sdcard/Documents/考研英语/错题本.md",
            "/storage/emulated/0/Download/考研英语/错题本.md",
            "/sdcard/Download/考研英语/错题本.md",
        ]
        for cand in android_candidates:
            try:
                parent = os.path.dirname(cand)
                if os.path.exists(parent) or os.path.exists("/storage/emulated/0") or os.path.exists("/sdcard"):
                    os.makedirs(parent, exist_ok=True)
                    test_file = os.path.join(parent, ".perm_test")
                    with open(test_file, "w", encoding="utf-8") as f:
                        f.write("1")
                    os.remove(test_file)
                    return cand
            except Exception:
                continue

        # 4. Open Minis 官方 workspace 降级
        minis_ws = "/var/minis/workspace"
        if os.path.exists(minis_ws):
            try:
                os.makedirs(minis_ws, exist_ok=True)
                cand = os.path.join(minis_ws, DEFAULT_FILE_NAME)
                test_file = os.path.join(minis_ws, ".perm_test")
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write("1")
                os.remove(test_file)
                return cand
            except Exception:
                pass

    # 5. PC / 常规系统（Windows / macOS / Linux）用户文档目录
    try:
        home = os.path.expanduser("~")
        docs_dir = os.path.join(home, "Documents", "考研英语")
        if os.path.exists(os.path.join(home, "Documents")):
            os.makedirs(docs_dir, exist_ok=True)
            return os.path.join(docs_dir, DEFAULT_FILE_NAME)
    except Exception:
        pass

    # 6. 全局用户主目录安全兜底
    try:
        home_fallback = os.path.join(os.path.expanduser("~"), ".free-kaoyan-cloze")
        os.makedirs(home_fallback, exist_ok=True)
        return os.path.join(home_fallback, DEFAULT_FILE_NAME)
    except Exception:
        return os.path.abspath(DEFAULT_FILE_NAME)


def migrate_legacy_notebook_if_needed(target_path: str):
    """
    检查旧 Skill 目录下是否存在历史遗留错题数据。
    若存在且目标文件与旧文件不同，将旧文件中的有效条目无损合并至新目标持久化路径，并备份旧文件。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)
    legacy_candidates = [
        os.path.join(skill_dir, DEFAULT_FILE_NAME),
        os.path.join(os.path.dirname(skill_dir), "free", DEFAULT_FILE_NAME),
        os.path.abspath(DEFAULT_FILE_NAME),
    ]
    target_abs = os.path.abspath(target_path)

    for leg_path in legacy_candidates:
        leg_abs = os.path.abspath(leg_path)
        if leg_abs == target_abs or not os.path.isfile(leg_abs):
            continue

        try:
            with open(leg_abs, "r", encoding="utf-8") as f:
                legacy_text = f.read()

            if not re.search(r"^id:\s*.+$", legacy_text, re.MULTILINE):
                continue

            target_ids = get_existing_ids(target_abs)
            if not os.path.exists(target_abs) or os.path.getsize(target_abs) == 0:
                parent_dir = os.path.dirname(target_abs)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                with open(target_abs, "w", encoding="utf-8") as f:
                    f.write(legacy_text)
                print(f"[MIGRATION] 已将旧错题本完整迁移至持久化路径: {target_abs}")
            else:
                raw_entries = re.split(r"(?=\n---\nid:)", "\n" + legacy_text)
                to_append = []
                for entry in raw_entries:
                    m = re.search(r"^id:\s*(.+)$", entry.strip(), re.MULTILINE)
                    if m and m.group(1).strip() not in target_ids:
                        to_append.append(entry.strip() + "\n\n")
                if to_append:
                    with open(target_abs, "a", encoding="utf-8") as f:
                        f.write("\n" + "".join(to_append))
                    print(f"[MIGRATION] 已将旧错题本中的历史条目合并至持久化路径: {target_abs}")

            bak_path = leg_abs + ".migrated.bak"
            if os.path.exists(bak_path):
                os.remove(bak_path)
            os.rename(leg_abs, bak_path)
        except Exception as e:
            print(f"[WARNING] 旧错题迁移提示 (跳过): {e}", file=sys.stderr)


def get_existing_ids(file_path):
    if not os.path.exists(file_path):
        return set()
    ids = set()
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^id:\s*(.+)$", line.strip())
            if m:
                ids.add(m.group(1).strip())
    return ids


def normalize_standard_id(raw_id: str) -> str:
    """
    规范完形填空标准 ID 命名规则: YYYY-[E1-|E2-]Cloze-Q[01-20]
    自动纠偏 '2015-完形-5', '2015-Cloze-Q5', '2015-英一-完形-Q05', '2015-E2-Cloze-5', '2015-Q3' 等格式
    """
    if not raw_id:
        return "UNKNOWN-Cloze-Q00"
    raw_id = raw_id.strip()

    # 1. 提取 4 位年份
    year_match = re.search(r"(\d{4})", raw_id)
    year = year_match.group(1) if year_match else "UNKNOWN"

    # 将年份从临时查找串中移除，防止题号误匹配到年份末尾数字
    id_without_year = re.sub(r"\b\d{4}\b", "", raw_id)

    # 2. 提取英语一 / 英语二标签（若有）
    exam_tag = ""
    if re.search(r"(?:英一|英语一|E1|English\s*1|I\b)", raw_id, re.IGNORECASE):
        exam_tag = "E1-"
    elif re.search(r"(?:英二|英语二|E2|English\s*2|II\b)", raw_id, re.IGNORECASE):
        exam_tag = "E2-"

    # 3. 提取题号 1-20
    q_match = re.search(r"(?:Q|第|空|题|[-_/\s])\s*0*([1-9]|1\d|20)(?!\d)", id_without_year, re.IGNORECASE)
    if not q_match:
        q_match = re.search(r"0*([1-9]|1\d|20)(?!\d)", id_without_year)

    if q_match:
        q_num = int(q_match.group(1))
        return f"{year}-{exam_tag}Cloze-Q{q_num:02d}"

    return raw_id


def generate_unique_id(base_id, existing_ids):
    if base_id not in existing_ids:
        return base_id
    index = 2
    while f"{base_id}-{index}" in existing_ids:
        index += 1
    return f"{base_id}-{index}"


def _get_field(data, keys, default=""):
    for k in keys:
        if k in data and data[k] is not None:
            val = str(data[k]).strip()
            if val:
                return val
    return default


def format_error_entry(data, existing_ids):
    # 校验错误类型（支持多种常见别名）
    error_type = _get_field(data, ["error_type", "error", "type_of_error", "错误类型"])
    if error_type not in ERROR_TYPES:
        print(f"[ERROR] 非法错误类型: '{error_type}'。必须严格属于 12 类封闭枚举之一：\n{', '.join(ERROR_TYPES)}", file=sys.stderr)
        sys.exit(1)

    # 校验能力短板（支持多种常见别名）
    shortboard = _get_field(data, ["ability_shortboard", "shortboard", "ability", "能力短板"])
    if shortboard not in ABILITY_SHORTBOARDS:
        print(f"[ERROR] 非法能力短板: '{shortboard}'。必须属于 {ABILITY_SHORTBOARDS} 之一", file=sys.stderr)
        sys.exit(1)

    base_id = _get_field(data, ["id", "ID", "item_id"], "UNKNOWN-Cloze-Q00")
    base_id = normalize_standard_id(base_id)
    entry_id = generate_unique_id(base_id, existing_ids)
    existing_ids.add(entry_id)

    # 刷次标签（默认“一刷”）
    round_val = _get_field(data, ["round", "刷次", "review_round", "round_tag"], "一刷")

    # 用户选项与正确选项（可选）
    user_answer = _get_field(data, ["user_answer", "user_choice", "my_answer", "用户选项"])
    correct_answer = _get_field(data, ["correct_answer", "answer", "standard_answer", "正确答案"])

    # secondary_error_types（副错误类型列表，可选）
    sec_errs_raw = data.get("secondary_error_types") or data.get("secondary_errors") or data.get("副错误类型") or []
    if isinstance(sec_errs_raw, str):
        sec_errs_raw = [s.strip() for s in re.split(r"[,，、]", sec_errs_raw) if s.strip()]
    valid_sec_errors = []
    if isinstance(sec_errs_raw, list):
        for se in sec_errs_raw:
            se_str = str(se).strip()
            if se_str in ERROR_TYPES and se_str != error_type and se_str not in valid_sec_errors:
                valid_sec_errors.append(se_str)

    q_type = _get_field(data, ["question_type", "type", "q_type", "题型"], "动词题")
    keyword = _get_field(data, ["keyword", "keywords", "key", "解题关键词"])
    location = _get_field(data, ["location", "loc", "原文定位"])
    restore = _get_field(data, ["restore", "thought", "错误还原"])
    attribution = _get_field(data, ["attribution", "attr", "方法论归因"])
    lesson = _get_field(data, ["lesson", "takeaway", "教训金句"])
    analysis = _get_field(data, ["analysis", "body", "content", "正文"])
    if not analysis:
        analysis = f"错误还原：{restore}\n方法论归因：{attribution}\n教训金句：{lesson}"

    frontmatter_lines = [
        "---",
        f"id: {entry_id}",
        f"刷次: {round_val}",
        f"题型: {q_type}",
        f"error_type: {error_type}",
    ]
    if valid_sec_errors:
        frontmatter_lines.append(f"secondary_error_types: [{', '.join(valid_sec_errors)}]")
    if user_answer:
        frontmatter_lines.append(f"user_answer: {user_answer}")
    if correct_answer:
        frontmatter_lines.append(f"correct_answer: {correct_answer}")
    frontmatter_lines.extend([
        f"能力短板: {shortboard}",
        f"解题关键词: {keyword}",
        f"原文定位: {location}",
        f"错误还原: {restore}",
        f"方法论归因: {attribution}",
        f"教训金句: {lesson}",
        "---"
    ])
    fm_block = "\n".join(frontmatter_lines)

    entry_content = f"""
{fm_block}

### {entry_id}

{analysis}
"""
    return entry_id, entry_content


def append_errors(file_path, items):
    if not items:
        print("[WARNING] 没有待追加的错题条目。", file=sys.stderr)
        return []

    # 首次归档前，若存在旧 Skill 目录遗留数据，自动安全合并迁移
    migrate_legacy_notebook_if_needed(file_path)

    existing_ids = get_existing_ids(file_path)
    added_ids = []
    contents = []

    for item in items:
        if not isinstance(item, dict):
            continue
        entry_id, content = format_error_entry(item, existing_ids)
        added_ids.append(entry_id)
        contents.append(content)

    if not added_ids:
        print("[ERROR] 未解析到有效错题数据。", file=sys.stderr)
        sys.exit(1)

    parent_dir = os.path.dirname(os.path.abspath(file_path))
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    if not os.path.exists(file_path):
        header = "# 错题本\n\n本文件存放考研英语错题，由 FREE 考研英语系列 (free-kaoyan-cloze) skill 维护。\n\n## 错题列表\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(header)
    else:
        # 若存在初始模板占位符“（暂无）”，自动清理剔除
        with open(file_path, "r", encoding="utf-8") as f:
            content_str = f.read()
        if "（暂无）" in content_str or "(暂无)" in content_str:
            cleaned_str = re.sub(r"[（(]暂无[）)]\s*", "", content_str)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cleaned_str)

    with open(file_path, "a", encoding="utf-8") as f:
        f.write("".join(contents))

    return added_ids


def auto_cleanup_temp_file(file_path: str):
    """
    成功归档后，自动删除输入的临时 JSON 文件，并尝试清理因此变空的临时父目录（最多向上追溯两级）。
    仅删除因移除该文件而变空的目录，绝不触碰非空目录与当前工作目录及根目录。
    """
    if not file_path or not os.path.isfile(file_path):
        return

    abs_file = os.path.abspath(file_path)
    cwd = os.path.abspath(os.getcwd())

    try:
        os.remove(abs_file)
        print(f"🧹 已自动清理临时输入文件: {abs_file}")
    except Exception as e:
        print(f"[DEBUG] 临时文件清理提示 (可忽略): {e}", file=sys.stderr)
        return

    # 尝试递归向上清理变空的目录（最多 2 级）
    curr_dir = os.path.dirname(abs_file)
    for _ in range(2):
        if not curr_dir or curr_dir == cwd or curr_dir == os.path.dirname(cwd):
            break
        # 保护重要系统根目录
        if curr_dir in ["/", "\\", "C:\\", "C:/", os.path.expanduser("~")]:
            break
        try:
            if os.path.isdir(curr_dir) and not os.listdir(curr_dir):
                os.rmdir(curr_dir)
                curr_dir = os.path.dirname(curr_dir)
            else:
                break
        except Exception:
            break


def main():
    parser = argparse.ArgumentParser(description="考研英语完形填空错题本记录工具")
    parser.add_argument("--file", "-f", help="错题本目标路径 (可选，默认使用系统持久化路径)")
    parser.add_argument("--json", "-j", help="包含错题数据的 JSON 字符串或 JSON 文件路径")
    parser.add_argument("--info", "--status", action="store_true", help="显示当前解析到的错题本持久化存储路径与状态")
    parser.add_argument("--keep-json", action="store_true", help="保留输入的临时 JSON 文件，不执行自动删除")

    # 单条命令行参数（兼顾极简排查）
    parser.add_argument("--id", help="题目 ID (如 2015-Cloze-Q05)")
    parser.add_argument("--round", default="一刷", help="刷次标签 (默认 一刷)")
    parser.add_argument("--type", "--question-type", default="动词题", help="题型")
    parser.add_argument("--error", "--error-type", help="错误类型 (12 类枚举之一)")
    parser.add_argument("--shortboard", "--ability-shortboard", help="能力短板 (词汇/语法/主旨)")
    parser.add_argument("--keyword", help="解题关键词")
    parser.add_argument("--location", help="原文定位")
    parser.add_argument("--restore", help="错误还原")
    parser.add_argument("--attribution", help="方法论归因")
    parser.add_argument("--lesson", help="教训金句")
    parser.add_argument("--analysis", help="正文复盘分析")

    args = parser.parse_args()

    # 路径解析与自愈
    if args.file:
        notebook_path = sanitize_notebook_path(args.file)
    else:
        notebook_path = get_default_notebook_path()

    if args.info:
        print("=== 错题本持久化存储状态诊断 ===")
        print(f"解析路径: {notebook_path}")
        print(f"文件存在: {os.path.isfile(notebook_path)}")
        if os.path.isfile(notebook_path):
            size_kb = os.path.getsize(notebook_path) / 1024
            existing = get_existing_ids(notebook_path)
            print(f"文件大小: {size_kb:.2f} KB")
            print(f"已录错题: {len(existing)} 题")
        parent = os.path.dirname(notebook_path)
        print(f"父级目录: {parent} (存在: {os.path.exists(parent)})")
        return

    items_to_add = []
    temp_json_to_clean = None

    if args.json:
        raw_json_str = args.json.strip()
        if os.path.isfile(raw_json_str):
            temp_json_to_clean = os.path.abspath(raw_json_str)
            with open(raw_json_str, "r", encoding="utf-8") as f:
                raw_json_str = f.read().strip()
        try:
            parsed = json.loads(raw_json_str)
            if isinstance(parsed, list):
                items_to_add.extend(parsed)
            elif isinstance(parsed, dict):
                items_to_add.append(parsed)
            else:
                print("[ERROR] --json 内容必须是 JSON 对象或对象数组", file=sys.stderr)
                sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON 解析失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            try:
                parsed = json.loads(stdin_content)
                if isinstance(parsed, list):
                    items_to_add.extend(parsed)
                elif isinstance(parsed, dict):
                    items_to_add.append(parsed)
            except json.JSONDecodeError as e:
                print(f"[ERROR] stdin JSON 解析失败: {e}", file=sys.stderr)
                sys.exit(1)

    # 兜底：若无 JSON，检查是否通过单条命令行参数传入
    if not items_to_add and args.id and args.error and args.shortboard:
        single_item = {
            "id": args.id,
            "round": args.round,
            "question_type": args.type,
            "error_type": args.error,
            "ability_shortboard": args.shortboard,
            "keyword": args.keyword or "（无）",
            "location": args.location or "（无）",
            "restore": args.restore or "（无）",
            "attribution": args.attribution or "（无）",
            "lesson": args.lesson or "（无）",
            "analysis": args.analysis or "",
        }
        items_to_add.append(single_item)

    if not items_to_add:
        print("[ERROR] 未提供任何待归档错题。请使用 --json 传入数据或使用 --info 诊断。", file=sys.stderr)
        sys.exit(1)

    added_ids = append_errors(notebook_path, items_to_add)

    print(f"✅ 成功归档 {len(added_ids)} 道错题至持久化错题本：")
    for aid in added_ids:
        print(f"  - {aid}")
    print(f"📁 存储文件: {notebook_path}")

    # 成功后自动清理临时文件（若有且未开启 --keep-json）
    if temp_json_to_clean and not args.keep_json:
        auto_cleanup_temp_file(temp_json_to_clean)


if __name__ == "__main__":
    main()
