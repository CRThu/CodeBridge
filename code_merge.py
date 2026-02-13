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

# --- 配置常量 ---
CONFIG_FILE = "config.json"
IGNORE_FILE = ".agentignore"

def load_config():
    """
    从脚本所在目录加载基础配置 config.json
    """
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
            ".md"
        ],
        "default_exclude":
        [
            ".git", ".vs", ".venv", ".idea",
            "bin", "obj",
            "vendor"]
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取 config.json 失败，使用默认配置: {e}")
    
    return default_config

def get_path_spec(project_dir, default_exclude):
    """
    优先解析项目目录下的 .agentignore，不存在则使用 config.json 中的排除列表
    """
    ignore_path = os.path.join(project_dir, IGNORE_FILE)
    
    if os.path.exists(ignore_path):
        print(f"检测到 {IGNORE_FILE}，正在应用规则...")
        with open(ignore_path, 'r', encoding='utf-8') as f:
            return pathspec.PathSpec.from_lines('gitwildmatch', f)
    else:
        print(f"未找到 {IGNORE_FILE}，使用 config.json 中的默认排除列表...")
        # 将简单的目录列表转换为 pathspec 规则
        return pathspec.PathSpec.from_lines('gitwildmatch', default_exclude)

def build_dir_tree(root_dir, spec, allowed_exts):
    dir_tree = {}
    root_name = os.path.basename(root_dir)
    
    for root, dirs, files in os.walk(root_dir):
        rel_root = os.path.relpath(root, root_dir)
        if rel_root == ".":
            rel_root = ""

        # 过滤目录
        dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(rel_root, d))]
        
        # 过滤文件
        valid_files = [
            f for f in files 
            if os.path.splitext(f)[1].lower() in allowed_exts 
            and not spec.match_file(os.path.join(rel_root, f))
        ]
        
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

def merge_project_code(root_dir, output_file='code.merge.txt'):
    # 1. 加载配置
    config = load_config()
    allowed_exts = set(config.get("allowed_exts", []))
    
    # 2. 获取匹配器 (优先 .agentignore)
    spec = get_path_spec(root_dir, config.get("default_exclude", []))
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # 3. 生成并写入目录树
        print("正在生成目录结构...")
        dir_tree = build_dir_tree(root_dir, spec, allowed_exts)
        f.write(f"//DIR_TREE_START\n{json.dumps(dir_tree, indent=2, ensure_ascii=False)}\n//DIR_TREE_END\n\n")
        
        # 4. 合并文件内容
        print("正在合并文件内容...")
        for root, dirs, files in os.walk(root_dir):
            rel_root = os.path.relpath(root, root_dir)
            if rel_root == ".": rel_root = ""

            dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(rel_root, d))]
            
            for file in files:
                rel_path = os.path.join(rel_root, file).replace('\\', '/')
                ext = os.path.splitext(file)[1].lower()
                
                if ext in allowed_exts and not spec.match_file(rel_path):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as src:
                            f.write(f"//{rel_path}\n{src.read()}\n\n")
                    except Exception as e:
                        print(f"跳过文件 {rel_path}: {e}")

if __name__ == "__main__":
    # 1. 支持命令行参数：执行 python code_merge.py C:/path/to/project
    # 如果没有参数，则回退到手动输入模式
    if len(sys.argv) > 1:
        project_path = sys.argv[1].strip()
    else:
        project_path = input("请输入项目路径: ").strip()

    if os.path.isdir(project_path):
        # 1. 规范化并获取绝对路径
        abs_project_path = os.path.abspath(project_path)
        
        # 2. 获取工程目录的名字 (如: MyProject)
        project_name = os.path.basename(os.path.normpath(abs_project_path))
        
        # 3. 获取工程目录的父目录 (即“上一层”)
        parent_dir = os.path.dirname(os.path.normpath(abs_project_path))
        
        # 4. 构造输出路径：工程目录名 + .merge.txt，放在父目录下
        output_filename = f"{project_name}.merge.txt"
        final_output_path = os.path.join(parent_dir, output_filename)
        
        # 5. 调用合并函数
        merge_project_code(abs_project_path, output_file=final_output_path)
        
        print(f"\n成功！合并文件已生成在工程目录同级（并排）: \n{final_output_path}")
    else:
        print("错误: 路径不存在")