import os

def get_project_root()->str:

    current_root=os.path.abspath(__file__)

    current_dir_root=os.path.dirname(current_root)

    project_root=os.path.dirname(current_dir_root)

    return project_root

def get_abs_path(relative_path:str)->str:
#相对路径转绝对路径
    project_root=get_project_root()
    return os.path.join(project_root,relative_path)

if __name__=="__main__":
    print(get_abs_path("co"))


