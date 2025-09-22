import os
import queue
import threading
from queue import Queue
from pathlib import Path
import sys
import click
root = Path(__file__).parent
sys.path.append(str(root))
import git
import time

from src.runner import Runner

def handle_dirs(target_path):
    py_files = []
    for root, dirs, files in os.walk(target_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    if len(py_files) > 0:
        def worker(task_queue, input_list, target_repo_path, thread_num):
            while True:
                try:
                    index = task_queue.get_nowait()  # 从队列获取元素的索引
                    print(f"线程 {thread_num} 号获得任务 {index + 1} [{input_list[index].split(os.sep)[-1]}]")
                except queue.Empty:
                    break
                try:
                    runner = Runner(input_list[index], target_repo_path)
                    if runner.is_success:
                        runner.run()

                    task_queue.task_done()
                    print(f"线程 {thread_num} 号任务 {index + 1} 号工作完成 ")
                except Exception as e:
                    print(e, f"线程 {thread_num} 号任务 {index + 1} 号工作失败，已跳过")
                    task_queue.task_done()
                    continue

        max_threads = 5
        task_queue = Queue()
        task_nums = len(py_files)
        for i in range(task_nums):
            task_queue.put(i)
        print(f"检测到 {task_nums} 个python文件，正在生成任务......")
        threads = []
        for index in range(max_threads):
            thread = threading.Thread(target=worker, args=(task_queue, py_files, target_path, index))
            thread.start()
            threads.append(thread)

        task_queue.join()
        print("本次程序代码文档生成已完成，请在根目录下 \"markdown_docs\" 文件夹中查看结果。")

    elif len(py_files) == 0:
        print("无python文件，目前仅支持python文件，请重新输入地址!")

    return 0
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Large language model powered framework for program code documentation generation."""
    if ctx.invoked_subcommand is None:
        repo = git.Repo('.', search_parent_directories=True)
        click.echo(repo.working_tree_dir)
        handle_dirs(str(repo.working_tree_dir))




@cli.command()
@click.option(
    "--target-path",
    "-tp",
    default="",
    show_default=True,
    help="File path of target, including file name with extension",
    type=click.Path(file_okay=True, dir_okay=True),
)
def run(target_path):

    start=time.time()
    if os.path.isfile(target_path):
        target_code_name = target_path.split(os.path.sep)[-1]
        if target_code_name.endswith(".py"):
            target_repo_path=os.path.sep.join(target_path.split(os.path.sep)[0:-1])
            runner = Runner(target_path, target_repo_path)
            if runner.is_success:
                runner.run()
                print("文档生成完成！请在根目录下 \"markdown_docs\" 中查看文档。")
            else:
                return
        else:
            print("目前仅支持python文件，输入正确的地址！")
        return 0
    elif os.path.isdir(target_path):
        handle_dirs(target_path)
    end=time.time()
    elapsed_time=end-start
    with open("E:\\00Egraduationdesign\PcdAgent\pcd_agent\\time.txt","w",encoding="utf-8") as write_file:
        write_file.write(str(elapsed_time))
    print("间隔时间为",elapsed_time)

if __name__ == "__main__":
    cli()