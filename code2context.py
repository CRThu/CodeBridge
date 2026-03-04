# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pathspec"
# ]
# ///

import os
import json
import pathspec
import sys
import re
import argparse

# --- 配置常量 ---
CONFIG_FILE = "config.json"
IGNORE_FILE = ".agentignore"

def load_config():
    """从脚本所在目录加载基础配置 config.json"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, CONFIG_FILE)
    
    # 默认配置（如果找不到 config.json）
    default_config = {
        "allowed_exts":
        [
            ".cpp", ".h", ".c",
            ".cs", ".xaml", ".axaml",
            ".py",
            ".css", ".js", ".html",
            ".md",
            ".json", ".yaml", ".yml",
            ".sh", ".bat", ".ps1"
        ],
        "default_exclude":
        [
            ".git", ".vs", ".venv", ".idea", "__pycache__",
            "bin", "obj",
            "vendor", "build", "dist"]
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取 config.json 失败，使用默认配置: {e}")
    
    return default_config

def get_path_spec(project_dir, default_exclude):
    """优先解析项目目录下的 .agentignore，不存在则使用 config.json 中的排除列表"""
    ignore_path = os.path.join(project_dir, IGNORE_FILE)
    
    if os.path.exists(ignore_path):
        print(f"检测到 {IGNORE_FILE}，正在应用规则...")
        with open(ignore_path, 'r', encoding='utf-8') as f:
            return pathspec.PathSpec.from_lines('gitwildmatch', f)
    else:
        print(f"未找到 {IGNORE_FILE}，使用 config.json 中的默认排除列表...")
        # 将简单的目录列表转换为 pathspec 规则
        return pathspec.PathSpec.from_lines('gitwildmatch', default_exclude)

def build_dir_tree(root_dir, spec, allowed_exts, target_files=None):
    """构建 JSON 格式目录树"""
    dir_tree = {}
    root_name = os.path.basename(root_dir)
    
    for root, dirs, files in os.walk(root_dir):
        rel_root = os.path.relpath(root, root_dir)
        if rel_root == ".": rel_root = ""

        # 过滤目录
        dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(rel_root, d))]
        
        # 过滤文件
        valid_files = []
        for f in files:
            rel_path = os.path.join(rel_root, f).replace('\\', '/')
            if target_files is not None:
                if rel_path in target_files:
                    valid_files.append(f)
            else:
                if os.path.splitext(f)[1].lower() in allowed_exts and not spec.match_file(rel_path):
                    valid_files.append(f)
        
        if not valid_files and not dirs:
            continue
        
        # 构建 JSON 层级
        path_parts = [p for p in rel_root.replace('\\', '/').split('/') if p]
        current = dir_tree
        for part in path_parts:
            current = current.setdefault(part, {})
        
        if valid_files:
            current['_files'] = valid_files
            
    return {root_name: dir_tree}

def smart_read(full_path):
    """自动识别编码并读取文件内容"""
    # 按照优先级尝试：UTF-8 (标准) -> GB18030 (中文) -> Latin-1 (西欧)
    for enc in ['utf-8', 'gb18030', 'latin-1']:
        try:
            with open(full_path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    
    # 最终保底方案：使用 UTF-8 并忽略错误字符
    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def pack_project_code(root_dir, output_file, delta_files=None):
    """打包文件内容 (全量或增量)"""
    config = load_config()
    allowed_exts = set(config.get("allowed_exts", []))
    
    # 2. 获取匹配器 (优先 .agentignore)
    spec = get_path_spec(root_dir, config.get("default_exclude", []))
    
    print(f"正在生成打包文件: {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # 1. 目录树
        print("正在生成目录结构...")
        dir_tree = build_dir_tree(root_dir, spec, allowed_exts, target_files=delta_files)
        f.write(f"//DIR_TREE_START\n{json.dumps(dir_tree, indent=2, ensure_ascii=False)}\n//DIR_TREE_END\n\n")
        
        # 2. 文件内容
        print("正在打包文件内容...")
        for root, dirs, files in os.walk(root_dir):
            rel_root = os.path.relpath(root, root_dir)
            if rel_root == ".": rel_root = ""

            dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(rel_root, d))]
            
            for file in files:
                rel_path = os.path.join(rel_root, file).replace('\\', '/')
                
                # 确定是否需要包含该文件
                should_include = False
                if delta_files is not None:
                    if rel_path in delta_files:
                        should_include = True
                else:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in allowed_exts and not spec.match_file(rel_path):
                        should_include = True
                
                if should_include:
                    full_path = os.path.join(root, file)
                    try:
                        content = smart_read(full_path)
                        f.write(f"--- START OF FILE: {rel_path} ---\n")
                        f.write(content)
                        f.write(f"\n--- END OF FILE: {rel_path} ---\n\n")
                    except Exception as e:
                        print(f"跳过文件 {rel_path}: {e}")

def apply_ai_changes(root_dir, ai_res_file, force=False):
    """解析并安全应用 AI 修改"""
    if not os.path.exists(ai_res_file):
        print(f"错误: 找不到文件 {ai_res_file}")
        return

    config = load_config()
    spec = get_path_spec(root_dir, config.get("default_exclude", []))
    allowed_exts = set(config.get("allowed_exts", []))

    # AI 响应通常是 UTF-8
    content = smart_read(ai_res_file)

    # 解析协议
    file_blocks = re.findall(r'--- START OF FILE: (.*?) ---\n(.*?)\n--- END OF FILE: \1 ---', content, re.DOTALL)
    deletions = re.findall(r'--- DELETE FILE: (.*?) ---', content)

    plan = []
    
    def is_safe(rel_path):
        """三层安全检查"""
        norm_path = os.path.normpath(rel_path).replace('\\', '/')
        if norm_path.startswith("..") or os.path.isabs(norm_path):
            return False, "路径越界攻击"
        if spec.match_file(norm_path):
            return False, "被 .agentignore 或默认规则忽略"
        # 允许创建新文件，但如果是已有文件，检查后缀
        ext = os.path.splitext(norm_path)[1].lower()
        if ext and ext not in allowed_exts:
             return False, "不支持的文件后缀"
        return True, norm_path

    for path, body in file_blocks:
        safe, result = is_safe(path)
        if not safe:
            print(f"跳过非法路径 {path}: {result}")
            continue
        action = "UPDATE" if os.path.exists(os.path.join(root_dir, result)) else "NEW"
        plan.append((action, result, body))

    for path in deletions:
        safe, result = is_safe(path)
        if not safe:
            print(f"跳过非法删除请求 {path}: {result}")
            continue
        if os.path.exists(os.path.join(root_dir, result)):
            plan.append(("DELETE", result, None))

    if not plan:
        print("未发现有效修改清单。")
        return

    print("\n--- 待应用修改清单 ---")
    for action, path, _ in plan:
        print(f"{action:6} | {path}")
    print("----------------------")

    if not force:
        if input("\n确认执行上述修改？(y/N): ").strip().lower() != 'y':
            print("操作取消。")
            return

    for action, path, body in plan:
        full_path = os.path.join(root_dir, path)
        try:
            if action == "DELETE":
                os.remove(full_path)
                print(f"[已删除] {path}")
            else:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(body)
                print(f"[已写入] {path}")
        except Exception as e:
            print(f"处理 {path} 失败: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="code2context")
    parser.add_argument("path", nargs="?", help="项目根路径")
    parser.add_argument("--delta", help="增量列表 (JSON 数组或文件路径)")
    parser.add_argument("--apply", help="解析并应用 AI 结果文件")
    parser.add_argument("--force", action="store_true", help="强制执行 Apply 无需确认")
    
    args = parser.parse_args()

    # 交互式菜单逻辑
    project_path = args.path
    mode = "pack" # 默认全量
    delta_list = None
    apply_file = args.apply
    force = args.force

    if not project_path:
        print("=== code2context 交互模式 ===")
        project_path = input("1. 请输入项目根路径: ").strip()
        if not project_path or not os.path.isdir(project_path):
            print("错误: 路径无效")
            sys.exit(1)
        
        print("\n2. 请选择操作模式:")
        print("   [1] 全量打包 (Full Pack)")
        print("   [2] 增量提取 (Delta Pack)")
        print("   [3] 应用 AI 修改 (Apply)")
        print("   [4] 退出")
        choice = input("请输入编号 [1]: ").strip() or "1"
        
        if choice == "2":
            mode = "delta"
            delta_input = input("请输入增量列表 (JSON 数组或 .json 文件): ").strip()
            if os.path.exists(delta_input):
                with open(delta_input, 'r', encoding='utf-8') as f:
                    delta_list = json.load(f)
            else:
                delta_list = json.loads(delta_input.replace("'", '"'))
        elif choice == "3":
            mode = "apply"
            apply_file = input("请输入 AI 结果文件名 (txt): ").strip()
        elif choice == "4":
            sys.exit(0)
    else:
        # 命令行模式下的逻辑判断
        if args.apply:
            mode = "apply"
        elif args.delta:
            mode = "delta"
            if os.path.exists(args.delta):
                with open(args.delta, 'r', encoding='utf-8') as f:
                    delta_list = json.load(f)
            else:
                delta_list = json.loads(args.delta.replace("'", '"'))

    # 执行核心逻辑
    abs_project_path = os.path.abspath(project_path)
    project_name = os.path.basename(os.path.normpath(abs_project_path))
    parent_dir = os.path.dirname(os.path.normpath(abs_project_path))

    if mode == "apply":
        apply_ai_changes(abs_project_path, apply_file, force=force)
    else:
        output_suffix = "context" if mode == "pack" else "delta"
        output_file = os.path.join(parent_dir, f"{project_name}.{output_suffix}.txt")
        pack_project_code(abs_project_path, output_file, delta_files=delta_list)
        print(f"\n[+] 成功！打包文件已生成: {output_file}")
        
    # 为了 EXE 运行不闪退，在交互模式下最后加个 pause
    if not args.path:
        input("\n任务结束，按回车退出...")