from __future__ import annotations

import json
import os
import ast
import time

import jedi
from typing import Any, Callable, Dict, List, Optional

from dataclasses import dataclass, field
from .target_info import TargetItem, TargetItemType, TargetItemStatus
# from settings import SettingsManager
import threading


def find_all_referencer(
        repo_path, variable_name, file_path, line_number, column_number, in_file_only=False
):
    """复制过来的之前的实现"""
    script = jedi.Script(path=os.path.join(repo_path, file_path))

    for attempt in range(3):
        try:
            if in_file_only:
                references = script.get_references(
                    line=line_number, column=column_number, scope="file"
                )
            else:
                references = script.get_references(line=line_number, column=column_number)
            # 过滤出变量名为 variable_name 的引用，并返回它们的位置
            variable_references = [ref for ref in references if ref.name == variable_name]

            return [
                (os.path.relpath(ref.module_path, repo_path), ref.line, ref.column)
                for ref in variable_references
                if not (ref.line == line_number and ref.column == column_number)
            ]
        except Exception as e:
            print("jedi error", type(e), e)
            time.sleep(1.5)
            continue
    return []


@dataclass
class MetaInfo:
    repo_path: Path = ""  # type: ignore
    target_path = ""
    document_version: str = (
        ""  # 随时间变化，""代表没完成，否则对应一个目标仓库的commit hash
    )
    # target_repo_hierarchical_tree: "TargetItem" = field(
    #     default_factory=lambda: TargetItem()
    # )  # 整个repo的文件结构
    target_obj_list = []
    white_list: Any[List] = None

    fake_file_reflection: Dict[str, str] = field(default_factory=dict)
    jump_files: List[str] = field(default_factory=list)
    deleted_items_from_older_meta: List[List] = field(default_factory=list)

    in_generation_process: bool = False

    checkpoint_lock: threading.Lock = threading.Lock()

    def init_meta_info(self, repo_path, target_path, target_info_list):
        self.target_path = target_path
        self.repo_path = repo_path
        self.parse_target_reference(target_info_list,self.checkpoint_lock)

    @staticmethod
    def find_obj_with_lineno(start_line, target_obj_list) -> (str, int):

        referencer_index_list = []
        for index, now_obj in enumerate(target_obj_list):
            # 找所有包含的节点
            if now_obj.code_start_line <= start_line <= now_obj.code_end_line:
                referencer_index_list.append(index)

        if len(referencer_index_list) == 0:
            return None, None

        if len(referencer_index_list) >= 1:
            #     叠加多层，需要处理

            start_line_dict = {index: target_obj_list[index].code_start_line for index in referencer_index_list}
            hierarchy_tuple_list = sorted(start_line_dict.items(), key=lambda item: item[1], reverse=False)
            # hierarchy_path = [str(hierarchy_path_tuple[index][-1]) for index, val in hierarchy_path_tuple]

            referencer_hierarchy = "/".join(
                target_obj_list[now_tuple[0]].obj_name for now_tuple in hierarchy_tuple_list)
            # 被谁引用

            # print(referencer_hierarchy,hierarchy_tuple_list[-1][1])
            return referencer_hierarchy, hierarchy_tuple_list[-1][0]

    def parse_target_reference(self, target_info_list,lock):
        target_obj_list = self.from_target_info_json(target_info_list)
        # List[TargetItem]                          List[Dict]
        count = 0
        try:
            for index, now_obj in enumerate(target_obj_list):
                count += 1
                referencer_index_list = []
                """在文件内遍历所有变量"""

                in_file_only = False
                rel_file_path = self.target_path
                with lock:
                    reference_list = find_all_referencer(
                        repo_path=self.repo_path,
                        variable_name=now_obj.obj_name,
                        file_path=rel_file_path,
                        line_number=now_obj.content["code_start_line"],
                        column_number=now_obj.content["name_column"],
                        in_file_only=in_file_only,
                    )

                for referencer_pos in reference_list:  # 对于每个引用

                    # 是不是自己的引用， 是则跳过不是则入参
                    if now_obj.code_start_line <= referencer_pos[1] <= now_obj.code_end_line:
                        continue

                    # 引用者下标列表，若=1则被函数引用，若》=1则可能被某类的函数或函数内部定义函数引用。
                    referencer_name, referencer_index = self.find_obj_with_lineno(referencer_pos[1], target_obj_list)
                    now_obj_path, now_obj_index = self.find_obj_with_lineno(now_obj.code_start_line, target_obj_list)
                    # 写入引用信息，需要将targetitem节点写入，需要去重
                    if referencer_name is not None:
                        if referencer_index not in referencer_index_list:
                            target_obj_list[index].who_reference_me_name_list.append(referencer_name)
                            target_obj_list[referencer_index].reference_who_name_list.append(now_obj_path)

                            temp_referencer = target_obj_list[referencer_index]

                            target_obj_list[index].who_reference_me.append(temp_referencer)
                            target_obj_list[referencer_index].reference_who.append(now_obj)
                            referencer_index_list.append(referencer_index)

            # 同步content中的引用信息
            def refresh_item_content(target_obj_list):
                for index, now_obj in enumerate(target_obj_list):
                    target_obj_list[index].content["who_reference_me"] = now_obj.who_reference_me_name_list
                    target_obj_list[index].content["reference_who"] = now_obj.reference_who_name_list
                    target_obj_list[index].content["item_status"] = now_obj.item_status.to_str()

                return target_obj_list

            self.target_obj_list = refresh_item_content(target_obj_list)
        except Exception as e:
            print(e)
            raise e

    def from_target_to_dictlist(self):
        target_obj_list = self.target_obj_list
        target_path = self.target_path

        target_info_list = []
        target_dict = {}
        for item in target_obj_list:
            target_info_list.append(item.content)

        target_dict[target_path] = target_info_list
        return target_dict


    @staticmethod
    def get_item_list(target_info_list):

        obj_item_list: List[TargetItem] = []
        for value in target_info_list:

            obj_doc_item = TargetItem(
                obj_name=value["name"],
                content=value,
                md_content=value["md_content"],
                code_start_line=value["code_start_line"],
                code_end_line=value["code_end_line"],
                item_type=TargetItemType.to_target_item_type(value["type"])
            )

            # 处理引用节点，将引用者节点加入当前节点
            if "item_status" in value.keys():
                obj_doc_item.item_status = TargetItemStatus[value["item_status"]]
            if "reference_who" in value.keys():
                obj_doc_item.reference_who_name_list = value["reference_who"]
            if "special_reference_type" in value.keys():
                obj_doc_item.special_reference_type = value[
                    "special_reference_type"
                ]
            if "who_reference_me" in value.keys():
                obj_doc_item.who_reference_me_name_list = value["who_reference_me"]
            obj_item_list.append(obj_doc_item)
        # print(obj_item_list)
        return obj_item_list

    def from_target_info_json(self, target_info_list):

        # print(target_info_list)
        if len(target_info_list) > 0:
            return self.get_item_list(target_info_list)
        else:
            json_path = os.path.join(self.repo_path, "target_doc_record", self.target_path.replace(".py", ".json"))
            if not os.path.exists(json_path):
                return None
            else:
                with open(json_path, "r", encoding="utf-8") as reader:
                    obj_dict = json.load(reader)
                    info_list = obj_dict.get(self.target_path)
                    return self.get_item_list(info_list)


class FileHandler:
    """
    历变更后的文件的循环中，为每个变更后文件（也就是当前文件）创建一个实例
    """
    target_info_list: "List" = field(
        default_factory=List
    )

    def __init__(self, target_file_dir, target_repo_path):

        self.file_name = target_file_dir.split(os.path.sep)[-1]  # 这里的file_path是文件名
        self.file_dirs = os.path.sep.join(target_file_dir.split(os.path.sep)[0:-1])
        self.repo_path = target_repo_path

        self.target_json_path = os.path.join(self.repo_path, "target_doc_record")
        self.target_json_file = os.path.join(self.target_json_path, self.file_name.split(".")[0] + ".json")

        self.target_markdown_path = os.path.join(self.repo_path,"markdown_docs","src")
        self.target_markdown_file = os.path.join(self.target_markdown_path, self.file_name.replace(".py", ".md"))

        self.generate_file_structure()

    def get_end_lineno(self, node):
        """
        Get the end line number of a given node.

        Args:
            node: The node for which to find the end line number.

        Returns:
            int: The end line number of the node. Returns -1 if the node does not have a line number.
        """
        if not hasattr(node, "lineno"):
            return -1  # 返回-1表示此节点没有行号

        end_lineno = node.lineno
        for child in ast.iter_child_nodes(node):
            child_end = getattr(child, "end_lineno", None) or self.get_end_lineno(child)
            if child_end > -1:  # 只更新当子节点有有效行号时
                end_lineno = max(end_lineno, child_end)
        return end_lineno

    def add_parent_references(self, node, parent=None):
        """
        Adds a parent reference to each node in the AST.

        Args:
            node: The current node in the AST.

        Returns:
            None
        """
        for child in ast.iter_child_nodes(node):
            child.parent = node
            self.add_parent_references(child, node)

    def get_functions_and_classes(self, code_content):
        """
        Retrieves all functions, classes, their parameters (if any), and their hierarchical relationships.
        Output Examples: [('FunctionDef', 'AI_give_params', 86, 95, None, ['param1', 'param2']), ('ClassDef', 'PipelineEngine', 97, 104, None, []), ('FunctionDef', 'get_all_pys', 99, 104, 'PipelineEngine', ['param1'])]
        On the example above, PipelineEngine is the Father structure for get_all_pys.

        Args:
            code_content: The code content of the whole file to be parsed.

        Returns:
            A list of tuples containing the type of the node (FunctionDef, ClassDef, AsyncFunctionDef),
            the name of the node, the starting line number, the ending line number, the name of the parent node, and a list of parameters (if any).
        """
        tree = ast.parse(code_content)
        self.add_parent_references(tree) #定义与分析抽象语法树
        functions_and_classes = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                start_line = node.lineno
                end_line = self.get_end_lineno(node)#获取代码段结束行
                parameters = (
                    [arg.arg for arg in node.args.args] if "args" in dir(node) else []
                )
                functions_and_classes.append(
                    (type(node).__name__, node.name, start_line, end_line, parameters)
                )
                # 获取源代码中所有类与函数信息
        return functions_and_classes

    def get_obj_code_info(
            self, code_type, code_name, start_line, end_line, params, file_path=None
    ):
        """
        Get the code information for a given object.

        Args:
            code_type (str): The type of the code.
            code_name (str): The name of the code.
            start_line (int): The starting line number of the code.
            end_line (int): The ending line number of the code.
            parent (str): The parent of the code.
            file_path (str, optional): The file path. Defaults to None.

        Returns:
            dict: A dictionary containing the code information.
        """

        code_info = {}
        code_info["type"] = code_type
        code_info["name"] = code_name
        code_info["md_content"] = []
        code_info["code_start_line"] = start_line
        code_info["code_end_line"] = end_line
        code_info["params"] = params

        with open(
                os.path.join(
                    self.file_dirs, file_path if file_path != None else self.file_name
                ),
                "r",
                encoding="utf-8",
        ) as code_file:
            lines = code_file.readlines()
            code_content = "".join(lines[start_line - 1: end_line])
            # 获取对象名称在第一行代码中的位置
            name_column = lines[start_line - 1].find(code_name)
            # 判断代码中是否有return字样
            if "return" in code_content:
                have_return = True
            else:
                have_return = False

            code_info["have_return"] = have_return
            # # 使用 json.dumps 来转义字符串，并去掉首尾的引号
            code_info["code_content"] = code_content
            code_info["name_column"] = name_column

        return code_info

    def generate_file_structure(self):
        """
        Generates the file structure for the given file path.

        Args:
            file_path (str): The relative path of the file.

        Returns:
            dict: A dictionary containing the file path and the generated file structure.

        Output example:
        {
            "function_name": {
                "type": "function",
                "start_line": 10,
                ··· ···
                "end_line": 20,
                "parent": "class_name"
            },
            "class_name": {
                "type": "class",
                "start_line": 5,
                ··· ···
                "end_line": 25,
                "parent": None
            }
        }
        """
        list_obj = {}
        file_path = self.file_name
        with open(os.path.join(self.file_dirs, self.file_name), "r", encoding="utf-8") as f:
            content = f.read()
            structures = self.get_functions_and_classes(content)
            file_objects = []  # 以列表的形式存储
            for struct in structures:
                structure_type, name, start_line, end_line, params = struct
                code_info = self.get_obj_code_info(
                    structure_type, name, start_line, end_line, params, file_path
                )
                file_objects.append(code_info)
        # 按照定义顺序排序，符合代码层级关系
        file_objects = sorted(file_objects, key=lambda item: item["code_start_line"])
        # 假定可以获取到文件名
        list_obj[file_path] = file_objects
        self.target_info_list = file_objects
        return list_obj

    def to_target_json_file(self, target_info_dict):
        lock = threading.Lock()
        with lock:
            if not os.path.exists(self.target_json_path):
                os.makedirs(self.target_json_path)

        json_str = json.dumps(target_info_dict, indent=4)

        with open(self.target_json_file, "w", encoding="utf-8") as writer:
            writer.write(json_str)

    def convert_to_markdown(self, target_obj_list):
        markdown_list = []
        lock = threading.Lock()
        with lock:
            if not os.path.exists(self.target_markdown_path):
                os.makedirs(self.target_markdown_path)

        if len(target_obj_list) > 0:
            for obj in target_obj_list:
                markdown_list.append(obj.to_markdown() + "***\n")
        else:
            markdown_list.append("文档待生成......\n***\n")

        with open(self.target_markdown_file, "w", encoding="utf-8") as writer:
            writer.writelines(markdown_list)


if __name__ == "__main__":
    f = FileHandler(repo_path="E:/00Egraduationdesign/yolov5", file_path="yolo.py")
    # file_json = f.generate_file_structure()
    m = MetaInfo()
    m.init_meta_info(repo_path="E:/00Egraduationdesign/yolov5", target_path="yolo.py")
    # m.parse_target_reference(f.target_info_list)
    m.target_obj_list = m.from_target_info_json([])
    f.convert_to_markdown(m.target_obj_list)
    # new_dict = m.from_target_to_dictlist()
    # f.to_target_json_file(new_dict)
    # print(f.target_info_list)
    # for _,obj in file_json.items():
    #     print(type(obj))
    # with open("E:/00Egraduationdesign/.project_doc_record0/project_hierarchy.json","r",encoding="utf-8") as reader:
    #     target_info = json.load(reader)
    #     for target_name, target_content in target_info.items():
    #         print(target_name,target_content)
    #         MetaInfo.from_target_info_json(target_content)
