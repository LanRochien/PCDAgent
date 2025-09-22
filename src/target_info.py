from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto, unique
from typing import Any, Callable, Dict, List, Optional


@unique
class EdgeType(Enum):
    reference_edge = auto()  # 一个obj引用另一个obj
    subfile_edge = auto()  # 一个 文件/文件夹 属于一个文件夹
    file_item_edge = auto()  # 一个 obj 属于一个文件


@unique
class TargetItemType(Enum):
    # 对可能的对象文档类型进行定义（分不同细粒度）
    _repo = auto()  # 根节点，需要生成readme
    _dir = auto()
    _file = auto()
    _class = auto()
    _class_function = auto()
    _function = auto()  # 文件内的常规function
    _sub_function = auto()  # function内的定义的subfunction
    _global_var = auto()

    def to_target_item_type(item_type):
        if item_type == "ClassDef":
            return TargetItemType._class
        elif item_type == "FunctionDef":
            return TargetItemType._function

    def to_str(self):
        if self == TargetItemType._class:
            return "ClassDef"
        elif self == TargetItemType._function:
            return "FunctionDef"
        elif self == TargetItemType._class_function:
            return "FunctionDef"
        elif self == TargetItemType._sub_function:
            return "FunctionDef"
        # assert False, f"{self.name}"
        return self.name


@unique
class TargetItemStatus(Enum):
    doc_up_to_date = auto()  # 无需生成文档
    doc_has_not_been_generated = auto()  # 文档还未生成，需要生成
    code_changed = auto()  # 源码被修改了，需要改文档
    add_new_referencer = auto()  # 添加了新的引用者
    referencer_not_exist = auto()  # 曾经引用他的obj被删除了，或者不再引用他了

    def to_str(self):
        if self == TargetItemStatus.doc_up_to_date:
            return "doc_up_to_date"
        elif self == TargetItemStatus.doc_has_not_been_generated:
            return "doc_has_not_been_generated"
        elif self == TargetItemStatus.code_changed:
            return "code_changed"
        elif self == TargetItemStatus.add_new_referencer:
            return "add_new_referencer"
        elif self == TargetItemStatus.referencer_not_exist:
            return "referencer not_exist"


@dataclass
class TargetItem:
    item_type: TargetItemType = TargetItemType._class_function
    item_status: TargetItemStatus = TargetItemStatus.doc_has_not_been_generated

    obj_name: str = ""  # 对象的名字
    code_start_line: int = -1
    code_end_line: int = -1
    md_content: List[str] = field(default_factory=list)  # 存储不同版本的doc
    content: Dict[Any, Any] = field(default_factory=dict)  # 原本存储的信息

    children: Dict[str, TargetItem] = field(default_factory=dict)  # 子对象
    father: Any[TargetItem] = None

    reference_who: List[TargetItem] = field(default_factory=list)  # 他引用了谁
    who_reference_me: List[TargetItem] = field(default_factory=list)  # 谁引用了他
    special_reference_type: List[bool] = field(default_factory=list)

    reference_who_name_list: List[str] = field(
        default_factory=list
    )  # 他引用了谁，这个可能是老版本
    who_reference_me_name_list: List[str] = field(
        default_factory=list
    )  # 谁引用了他，这个可能是老版本的

    has_task: bool = False

    multithread_task_id: int = -1  # 在多线程中的task_id

    def get_full_name(self, strict=False):
        """获取从下到上所有的obj名字

        Returns:
            str: 从下到上所有的obj名字，以斜杠分隔
        """
        if self.father == None:
            return self.obj_name
        name_list = []
        now = self
        while now != None:
            self_name = now.obj_name
            if strict:
                for name, item in self.father.children.items():
                    if item == now:
                        self_name = name
                        break
                if self_name != now.obj_name:
                    self_name = self_name + "(name_duplicate_version)"
            name_list = [self_name] + name_list
            now = now.father

        name_list = name_list[1:]
        return "/".join(name_list)

    def get_file_name(self):
        full_name = self.get_full_name()
        return full_name.split(".py")[0] + ".py"

    def get_travel_list(self):
        """按照先序遍历的顺序，根节点在第一个"""
        now_list = [self]
        for _, child in self.children.items():
            now_list = now_list + child.get_travel_list()
        return now_list

    def update_item_status(self, item_status):
        self.item_status = item_status
        self.content["item_status"] = item_status.to_str()

    def save_md_content(self, md_content: str = None):
        if md_content == None:
            self.md_content = []
        else:
            self.md_content.append(md_content)

    def to_markdown(self) -> str:
        """将文件内容转化为 markdown 格式的文本"""
        level = 2 if self.item_type.to_str() == "ClassDef" else 3
        markdown_content = (
                "#" * level + f" {self.item_type.to_str()} {self.obj_name}"
        )
        if "params" in self.content.keys() and self.content["params"]:
            markdown_content += f"({', '.join(self.content['params'])})"
        markdown_content += "\n"
        if self.md_content:
            markdown_content += f"{self.md_content[-1]}\n"
        else:
            markdown_content += "文档施工中……\n"

        return markdown_content
