import json
import time

from llama_index.llms.deepseek import DeepSeek
from .target_info import TargetItem
from .structure_handler import MetaInfo
from .prompt import  chat_template


class ChatEngine(object):

    def __init__(self):

        self.llm=DeepSeek(
            api_key='sk-fbd6284d67a24d73bf7ebdd2be25b91e',
            api_base='https://api.deepseek.com/',
            model='deepseek-chat',
            timeout=1000,
            max_retries=1,
            is_chat_mode=True,
        )

    def assemble_prompt(self,target_item:TargetItem):

        formatted_messages:str

        code_info = target_item.content
        referenced = len(target_item.who_reference_me) > 0

        code_type = code_info["type"]
        code_name = code_info["name"]
        code_content = code_info["code_content"]
        have_return = code_info["have_return"]

        code_type_tell = "Class" if code_type == "ClassDef" else "Function"
        parameters_or_attribute = (
            "属性(atributes)" if code_type == "ClassDef" else "参数(parameters)"
        )
        have_return_tell = (
            "**输出示例**: 模拟出代码段可能的输出情况."
            if have_return
            else ""
        )
        combine_ref_situation = (
            "同时解释其在项目中的调用与被调用状况,"
            if referenced
            else ""
        )
        def get_referenced_prompt(target_item: target_item) -> str:
            if len(target_item.reference_who) == 0:
                return ""
            prompt = [
                """请注意，该代码段调用了以下对象，其相关代码与对应文档如下:"""
            ]
            for reference_item in target_item.reference_who:
                instance_prompt = (
                    f"""对象名: {reference_item.get_full_name()}\n文档: \n{reference_item.md_content[-1] if len(reference_item.md_content) > 0 else 'None'}\n源代码:```\n{reference_item.content['code_content'] if 'code_content' in reference_item.content.keys() else ''}\n```"""
                    + "=" * 10
                )
                prompt.append(instance_prompt)
            return "\n".join(prompt)

        def get_referencer_prompt(target_item: target_item) -> str:
            if len(target_item.who_reference_me) == 0:
                return ""
            prompt = [
                """同时，该代码段被以下代码调用,其相关代码与对应文档如下:"""
            ]
            for referencer_item in target_item.who_reference_me:
                instance_prompt = (
                    f"""对象名: {referencer_item.get_full_name()}\n文档: \n{referencer_item.md_content[-1] if len(referencer_item.md_content) > 0 else 'None'}\n源代码:```\n{referencer_item.content['code_content'] if 'code_content' in referencer_item.content.keys() else 'None'}\n```"""
                    + "=" * 10
                )
                prompt.append(instance_prompt)
            return "\n".join(prompt)

        def get_relationship_description(referencer_content, reference_letter):
            if referencer_content and reference_letter:
                return "并且请从功能角度在项目中包含与其调用者与被调用者之间的引用关系"
            #
            elif referencer_content:
                return "并且请从功能角度在项目中包含与其调用者之间的引用关系"
            elif reference_letter:
                return "并且请从功能角度在项目中包含与其被调用者之间的引用关系"
            else:
                return ""

        referencer_content = get_referencer_prompt(target_item)
        reference_letter = get_referenced_prompt(target_item)
        has_relationship = get_relationship_description(
            referencer_content, reference_letter
        )

        formatted_messages= chat_template.format_messages(
            combine_ref_situation=combine_ref_situation,
            code_type_tell=code_type_tell,
            code_name=code_name,
            code_content=code_content,
            have_return_tell=have_return_tell,
            has_relationship=has_relationship,
            reference_letter=reference_letter,
            referencer_content=referencer_content,
            parameters_or_attribute=parameters_or_attribute,
        )
        return formatted_messages

    def generate_doc(self, target_item: TargetItem):
        """Generates documentation for a given DocItem."""
        messages = self.assemble_prompt(target_item)
        for attempt in range(3):
            try:
                response = self.llm.chat(messages)
                return response.message.content
            except Exception as e:
                print(e,f"{target_item.obj_name} 第 {attempt + 1}/3 次连接失败，正在尝试重新重新连接。")
                time.sleep(3)


if __name__ == "__main__":


    chat=ChatEngine()
    with open("E:/00Egraduationdesign/.project_doc_record0/project_hierarchy.json","r",encoding="utf-8") as reader:
        target_info = json.load(reader)
        for target_name, target_content in target_info.items():
            info_list=MetaInfo.from_target_info_json(target_content)

    for  info_item in info_list:

        chat.generate_doc(info_item)
