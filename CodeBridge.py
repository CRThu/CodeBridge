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
import subprocess
from datetime import datetime

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

def run_git_diff(root_dir, staged=False):
    """导出 Git Diff 到项目父目录"""
    abs_project_path = os.path.abspath(root_dir)
    project_name = os.path.basename(os.path.normpath(abs_project_path))
    parent_dir = os.path.dirname(os.path.normpath(abs_project_path))
    output_file = os.path.join(parent_dir, f"{project_name}.gitdiff.txt")
    
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--cached")
    
    try:
        # 验证仓库
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root_dir, check=True, capture_output=True)
        # 获取 Diff
        result = subprocess.run(cmd, cwd=root_dir, check=True, capture_output=True, text=True, encoding='utf-8')
        
        header = f"\n{'='*20} GIT DIFF ({'STAGED' if staged else 'CHANGES'}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {'='*20}\n"
        
        # 写入文件 (覆盖写入以保持纯净，符合 Spec 要求)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(header)
            f.write(result.stdout)
            
        print(f"[+] Git Diff 已导出: {output_file}")
    except FileNotFoundError:
        print("错误: 系统未安装 Git。")
    except subprocess.CalledProcessError:
        print("错误: 该目录不是有效的 Git 仓库。")
    except Exception as e:
        print(f"导出 Git Diff 失败: {e}")

def apply_ai_changes(root_dir, ai_res_file, force=False):
    """解析并安全应用 AI 修改"""
    if not os.path.exists(ai_res_file):
        print(f"错误: 找不到文件 {ai_res_file}")
        return

    config = load_config()
    spec = get_path_spec(root_dir, config.get("default_exclude", []))
    allowed_exts = set(config.get("allowed_exts", []))

    content = smart_read(ai_res_file)

    # 协议解析 (START/END FILE)
    file_blocks = re.findall(r'--- START OF FILE: (.*?) ---\n(.*?)\n--- END OF FILE: \1 ---', content, re.DOTALL)
    deletions = re.findall(r'--- DELETE FILE: (.*?) ---', content)

    plan = []
    
    def is_safe(rel_path):
        """安全沙箱校验"""
        norm_path = os.path.normpath(rel_path).replace('\\', '/')
        if norm_path.startswith("..") or os.path.isabs(norm_path):
            return False, "路径越界"
        if spec.match_file(norm_path):
            return False, "规则屏蔽"
        ext = os.path.splitext(norm_path)[1].lower()
        if ext and ext not in allowed_exts:
             return False, "后缀非法"
        return True, norm_path

    for path, body in file_blocks:
        safe, result = is_safe(path)
        if not safe:
            print(f"跳过路径 {path}: {result}")
            continue
        action = "UPDATE" if os.path.exists(os.path.join(root_dir, result)) else "NEW"
        plan.append((action, result, body))

    for path in deletions:
        safe, result = is_safe(path)
        if not safe:
            print(f"跳过删除 {path}: {result}")
            continue
        if os.path.exists(os.path.join(root_dir, result)):
            plan.append(("DELETE", result, None))

    if not plan:
        print("无有效修改。")
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
                if os.path.exists(full_path):
                    os.remove(full_path)
                    print(f"[已删除] {path}")
            else:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(body)
                print(f"[已写入] {path}")
        except Exception as e:
            print(f"处理 {path} 失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="CodeBridge - 让本地代码与 AI 上下文无缝连接")
    parser.add_argument("path", nargs="?", help="项目根路径")
    parser.add_argument("--delta", help="增量列表 (JSON 数组或文件路径)")
    parser.add_argument("--apply", help="解析并应用 AI 结果文件")
    parser.add_argument("--force", action="store_true", help="强制执行 Apply 无需确认")
    parser.add_argument("--diff", action="store_true", help="导出 Git 修改区 Diff (Changes)")
    parser.add_argument("--diff-staged", action="store_true", help="导出 Git 暂存区 Diff (Staged)")
    
    args = parser.parse_args()

    # 命令行直达逻辑
    if args.path:
        abs_project_path = os.path.abspath(args.path)
        if not os.path.isdir(abs_project_path):
            print(f"错误: 路径 {abs_project_path} 不存在")
            sys.exit(1)
            
        project_name = os.path.basename(os.path.normpath(abs_project_path))
        parent_dir = os.path.dirname(os.path.normpath(abs_project_path))

        if args.apply:
            apply_ai_changes(abs_project_path, args.apply, force=args.force)
        elif args.diff:
            run_git_diff(abs_project_path, staged=False)
        elif args.diff_staged:
            run_git_diff(abs_project_path, staged=True)
        else:
            delta_list = None
            if args.delta:
                if os.path.exists(args.delta):
                    with open(args.delta, 'r', encoding='utf-8') as f:
                        delta_list = json.load(f)
                else:
                    delta_list = json.loads(args.delta.replace("'", '"'))
            
            output_suffix = "delta" if delta_list else "context"
            output_file = os.path.join(parent_dir, f"{project_name}.{output_suffix}.txt")
            pack_project_code(abs_project_path, output_file, delta_files=delta_list)
            print(f"\n[+] 成功！打包文件已生成: {output_file}")
        return

    # 循环交互模式
    print("=== CodeBridge 交互模式 ===")
    while True:
        project_path = input("\n1. 请输入项目根路径 (输入 'exit' 退出): ").strip()
        if not project_path or project_path.lower() == 'exit':
            break
            
        if not os.path.isdir(project_path):
            print("错误: 路径无效，请重新输入")
            continue
        
        abs_project_path = os.path.abspath(project_path)
        
        # 功能菜单循环
        while True:
            print(f"\n当前项目: {abs_project_path}")
            print("--- 功能菜单 ---")
            print("   [1] 全量打包 (Full Pack)")
            print("   [2] 增量提取 (Delta Pack)")
            print("   [3] 导出 Git 暂存区 Diff (Staged)")
            print("   [4] 导出 Git 修改区 Diff (Changes)")
            print("   [5] 应用 AI 修改 (Apply)")
            print("   [6] 切换项目路径")
            print("   [7] 退出程序")
            
            choice = input("\n请选择编号 [1-7]: ").strip()
            
            if choice == "1":
                project_name = os.path.basename(os.path.normpath(abs_project_path))
                parent_dir = os.path.dirname(os.path.normpath(abs_project_path))
                output_file = os.path.join(parent_dir, f"{project_name}.context.txt")
                pack_project_code(abs_project_path, output_file)
                print(f"\n[+] 全量打包完成: {output_file}")
                
            elif choice == "2":
                delta_input = input("请输入增量列表 (JSON 数组或 .json 文件): ").strip()
                try:
                    if os.path.exists(delta_input):
                        with open(delta_input, 'r', encoding='utf-8') as f:
                            delta_list = json.load(f)
                    else:
                        delta_list = json.loads(delta_input.replace("'", '"'))
                    
                    project_name = os.path.basename(os.path.normpath(abs_project_path))
                    parent_dir = os.path.dirname(os.path.normpath(abs_project_path))
                    output_file = os.path.join(parent_dir, f"{project_name}.delta.txt")
                    pack_project_code(abs_project_path, output_file, delta_files=delta_list)
                    print(f"\n[+] 增量提取完成: {output_file}")
                except Exception as e:
                    print(f"错误: 增量列表解析失败: {e}")
                    
            elif choice == "3":
                run_git_diff(abs_project_path, staged=True)
                
            elif choice == "4":
                run_git_diff(abs_project_path, staged=False)
                
            elif choice == "5":
                apply_file = input("请输入 AI 结果文件名 (txt): ").strip()
                apply_ai_changes(abs_project_path, apply_file)
                
            elif choice == "6":
                break # 直接返回上层输入路径
                
            elif choice == "7":
                print("程序已退出。")
                sys.exit(0)
            else:
                print("无效选项，请重新尝试。")

if __name__ == "__main__":
    main()