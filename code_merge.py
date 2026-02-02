import os
import json

def build_dir_tree(root_dir, exclude_dirs, allowed_exts):
    dir_tree = {}
    root_name = os.path.basename(root_dir)
    exclude_dirs = {d.lower() for d in exclude_dirs}
    
    for root, dirs, files in os.walk(root_dir):
        # 过滤目录和文件
        dirs[:] = [d for d in dirs if d.lower() not in exclude_dirs]
        files = [f for f in files if os.path.splitext(f)[1].lower() in allowed_exts]
        if not files and not dirs:  # 跳过空目录
            continue
        
        # 构建相对路径层级
        rel_path = os.path.relpath(root, root_dir).replace('\\', '/')
        path_parts = [p for p in rel_path.split('/') if p != '.']
        
        # 插入到目录树
        current = dir_tree
        for part in path_parts:
            current = current.setdefault(part, {})
        
        # 添加文件列表
        if files:
            current['_files'] = files
    
    return {root_name: dir_tree}

def merge_project_code(root_dir, output_file='code.merge.txt'):
    # 配置参数
    code_config = {
        'C++': {'.cpp', '.h', '.c'},
        'C#': {'.cs', '.xaml', '.axaml'},
        'python': {'.py'}
    }
    allowed_exts = {ext for exts in code_config.values() for ext in exts}
    exclude_dirs = ['.vs', '.git', 'bin', 'obj', '.venv']
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # 生成目录树JSON
        dir_tree = build_dir_tree(root_dir, exclude_dirs, allowed_exts)
        f.write(f"//DIR_TREE_START\n{json.dumps(dir_tree, indent=2)}\n//DIR_TREE_END\n\n")
        
        # 合并文件内容
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d.lower() not in exclude_dirs]
            
            for file in files:
                if os.path.splitext(file)[1].lower() in allowed_exts:
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, root_dir).replace('\\', '/')
                    
                    with open(path, 'r', encoding='utf-8', errors='ignore') as src:
                        content = src.read()
                        f.write(f"//{rel_path}\n{content}\n\n")

if __name__ == "__main__":
    project_dir = input("Project path: ").strip()
    if os.path.isdir(project_dir):
        merge_project_code(project_dir)
        print("Done: code.merge.txt")
    else:
        print("Invalid path")