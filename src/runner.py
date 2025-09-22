import json
import os
from typing import List
from queue import Queue, Empty
from .structure_handler import FileHandler, MetaInfo
from .chat_engine import ChatEngine
from .target_info import TargetItem, TargetItemStatus

import threading


class Runner:

    def __init__(self, target_file_dir, target_repo_path):

        self.max_threads = 5
        self.is_success = True
        self.target_file_dir = target_file_dir
        self.target_repo_path = target_repo_path
        self.target_code_name = target_file_dir.split(os.path.sep)[-1]
        self.target_code_dirs = os.path.sep.join(target_file_dir.split(os.path.sep)[0:-1])

        self.target_code_json = os.path.join(self.target_repo_path, "target_doc_record",
                                             self.target_code_name.replace(".py", ".json"))
        self.target_file = FileHandler(target_file_dir=self.target_file_dir, target_repo_path=self.target_repo_path)
        if len(self.target_file.target_info_list) == 0:
            print(f"文件 {self.target_code_name} 无可生成文档.")
            self.is_success = False
            return

        self.target_meta = MetaInfo()

        self.target_meta.init_meta_info(repo_path=self.target_code_dirs, target_path=self.target_code_name,
                                        target_info_list=self.target_file.target_info_list)

        print(f"[{self.target_code_name}]初始化完成 开始运行")

    def save_into_json(self):
        target_info_dict = self.target_meta.from_target_to_dictlist()
        # 保存至json文件
        self.target_file.to_target_json_file(target_info_dict)

    @staticmethod
    def generate_for_single_item(target_obj_item: TargetItem, lock):
        chat = ChatEngine()
        message = chat.generate_doc(target_obj_item)
        #             先把message存到mdcontent里，后面可能需要转化后存储

        if message:
            target_obj_item.save_md_content(message)
            target_obj_item.update_item_status(TargetItemStatus.doc_up_to_date)
        else:
            target_obj_item.save_md_content()
            target_obj_item.update_item_status(TargetItemStatus.doc_has_not_been_generated)
            raise ValueError

    def generate_docs(self, target_obj_list: List[TargetItem]):

        def worker(task_queue, lock, input_list):
            while True:
                try:

                    index = task_queue.get_nowait()  # 从队列获取元素的索引
                except Empty:
                    break

                try:
                    print(f" {self.target_code_name} 第 {index + 1}/{len(input_list)} 个询问任务正在进行。")
                    self.generate_for_single_item(input_list[index], lock)
                    task_queue.task_done()
                    print(f" {self.target_code_name} 第 {index + 1}/{len(input_list)} 个询问任务已完成。")

                except ValueError as ve:
                    print(f" {self.target_code_name} 第 {index + 1}/{len(input_list)} 个询问任务询问失败")
                    task_queue.task_done()
                    continue

                except Exception as e:
                    print(f"error from {self.target_code_name} ", e)
                    break  # 队列为空时退出

        max_threads = self.max_threads
        task_queue = Queue()
        lock = threading.Lock()
        task_num = len(target_obj_list)
        for index in range(task_num):
            task_queue.put(index)
        print(f"检测到 {self.target_code_name} 共计任务 {task_num} 个。")
        threads = []
        for _ in range(max_threads):
            thread = threading.Thread(target=worker, args=(task_queue, lock, target_obj_list), )
            thread.start()
            threads.append(thread)

        task_queue.join()

    def first_generation(self):
        self.save_into_json()

        self.generate_docs(self.target_meta.target_obj_list)

        self.save_into_json()
        self.target_file.convert_to_markdown(self.target_meta.target_obj_list)


    def docs_update(self):
        '''
                   若为文档更新则需要考虑源代码的增删改，
                   维护一个待更新dict，存储在原list中的index和value
                    按照dict去chat，返回值按照index存储
                   重新parse代码文件，与现有info比较,获取item——status：

                    先处理增删改情况
                   对于增加：直接询问所有新增的代码的doc，
                    对于修改，代码内容改变并重新分析引用情况，然后询问doc
                    如何定义修改：type name相同则认为为已存在item，比较code_content who_reference_me
                    对于删除的情况，若存在则最后重新生成一下文档文件即可
                    然后对于无变化的item直接赋值到新的list中
                    检查是否都有mdcontent，无mdcontent则进入dict

                    chat

                   '''

        need_refresh = False  # 需要重新生成md文档
        updating_dict = {}  # key= name, v= TargetItem
        # k: 在newlist的index v: 对应index的value
        updating_mapping_dict = {}

        # 获取旧obj_list
        with open(self.target_code_json, "r", encoding="utf-8") as reader:
            older_info_dict = json.load(reader)
            older_info_list = older_info_dict.get(self.target_code_name)
            older_obj_list = self.target_meta.from_target_info_json(older_info_list)

        # 新obj_list在self中
        new_obj_list = self.target_meta.target_obj_list
        # 获取比较信息 key为带层级关系的name和对应list中的index
        older_key_set = {MetaInfo.find_obj_with_lineno(meta.code_start_line, older_obj_list) for meta in older_obj_list}
        older_key_dict = dict(older_key_set)

        new_key_set = {MetaInfo.find_obj_with_lineno(meta.code_start_line, new_obj_list) for meta in
                       self.target_meta.target_obj_list}
        new_key_dict = dict(new_key_set)

        # 处理删除
        for name, index in older_key_dict.items():
            try:
                new_key = new_key_dict[name]

            except KeyError as e:
                need_refresh = True
                break

        # 处理新增
        # 处理修改
        for name, index in new_key_dict.items():
            try:
                old_key = older_key_dict[name]  # 在old obj list 中的index
                new_key = index  # 在new obj list中的index
                #     找得到就是修改或不变
                temp_new = new_obj_list[new_key]  # type==TargetItem
                temp_old = older_obj_list[old_key]
                # 本身未生成文档，则一定要生成文档
                if temp_old.content["item_status"] != "doc_up_to_date":
                    raise KeyError
                #     如果代码发生变化
                if temp_new.content["code_content"] != temp_old.content["code_content"]:
                    raise KeyError
                # 如果引用发生变化
                if temp_new.content["who_reference_me"] != temp_old.content["who_reference_me"]:
                    raise KeyError
                #     如果没有变化
                new_obj_list[new_key].md_content = temp_old.md_content
                new_obj_list[new_key].item_status = temp_old.item_status
                new_obj_list[new_key].content["md_content"] = temp_old.content["md_content"]
                new_obj_list[new_key].content["item_status"] = temp_old.content["item_status"]

            except KeyError as e:
                updating_mapping_dict[name] = index  # 找不到就是新增
                updating_dict[name] = new_obj_list[index]  # 待生成字典 存储 映射关系和节点
                continue

        #     分析完成，可以存储一下json信息
        self.save_into_json()
        #         按照updating dict存储的节点进行询问，所有消息存储至new obj list中
        if updating_dict:
            need_refresh = True

            self.generate_docs(list(updating_dict.values()))
            # self.batch_processing(list(updating_dict.values()))
            for name, item in updating_dict.items():
                new_obj_list[updating_mapping_dict[name]] = item

            print("完成文档更新，正在写入json")
            self.save_into_json()

        if need_refresh:
            print("完成json更新，正在更新md")
            self.target_file.convert_to_markdown(new_obj_list)
            return

        else:
            print(f"{self.target_code_name} 所属文档为最新，无需更新")
            return

    def run(self):

        # 检查生成模式为首次生成还是文档更新
        # 首次生成：无json路径，或json中无mdcontent
        if not os.path.exists(self.target_code_json):
            print(f"检测到 {self.target_code_name} 第一次生成文档，正在生成中......")
            self.first_generation()

        else:
            print(f"检测到 {self.target_code_name} 已存在生成的文档记录，正在检查更新中......")
            self.docs_update()

        return
