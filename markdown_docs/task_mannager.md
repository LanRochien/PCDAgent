## ClassDef Task
**Task**: Task 类的功能是描述和管理单个任务单元及其依赖关系与状态。

**属性(atributes)**:  
· task_id (int): 任务的唯一标识符。  
· dependencies (List[Task]): 当前任务所依赖的其他 Task 对象的列表。  
· extra_info (Any): 与任务关联的额外信息，默认为 None。  
· status (int): 任务状态，取值范围为 0（未开始）、1（进行中）、2（已完成）、3（出错），初始化时默认为 0。

**代码描述**:  
Task 类用于封装任务的基本元数据及其执行上下文。其核心作用是定义任务之间的依赖关系（通过 dependencies 属性），跟踪任务执行状态（通过 status 属性），并存储任务相关扩展信息（通过 extra_info 属性）。在项目中，Task 对象由 MultiTaskDispatch 类的 add_task 方法创建并管理。当调用 add_task 时，MultiTaskDispatch 会根据 dependency_task_id 参数从 task_dict 中提取依赖的 Task 对象，构造新的 Task 实例并注册到 task_dict 中。任务状态的变化（如 get_next_task 方法中将 status 设为 1）直接影响 MultiTaskDispatch 的任务调度逻辑，例如仅当依赖任务全部完成且自身状态为 0 时才会被分配执行。

**注意事项**:  
1. status 属性应严格遵循预定义状态值（0-3），错误的状态值可能导致调度逻辑异常。  
2. dependencies 列表中的 Task 对象必须已存在于 MultiTaskDispatch 的 task_dict 中，否则 add_task 方法会因 KeyError 中断。  
3. 修改 dependencies 或 status 属性时应确保线程安全（如通过 task_lock），因其在 MultiTaskDispatch 中可能被多线程并发访问。  
4. extra_info 字段的解析逻辑需由调用方自行实现，其类型和内容不受 Task 类约束。
***
### FunctionDef __init__(self, task_id, dependencies, extra_info)
**__init__**:  __init__ 函数的功能是初始化一个 Task 类的实例对象。

**参数(parameters)**:这个Function所包含的 参数(parameters) 有 .
· task_id: 任务的唯一标识符，类型为 int。
· dependencies: 当前任务依赖的其他任务列表，类型为 List[Task]。
· extra_info: 可选参数，用于存储与任务相关的额外信息，类型为 Any，默认值为 None。

**代码描述**: 该 Function的作用是为 Task 类的实例对象进行初始化操作。具体行为包括：
1. 将参数 task_id 赋值给实例变量 self.task_id，用于唯一标识任务实例。
2. 将参数 extra_info 赋值给实例变量 self.extra_info，用于保存任务的扩展信息字段。
3. 将参数 dependencies 赋值给实例变量 self.dependencies，用于记录当前任务的前置依赖任务列表。
4. 初始化 self.status 属性并赋值为 0，该属性用于跟踪任务状态，数值对应关系为：0（未开始）、1（正在进行）、2（已完成）、3（出错）。

**注意事项**:
1. dependencies 参数必须是由 Task 类型元素组成的列表，传入其他类型可能导致后续逻辑异常。
2. status 属性采用硬编码初始化值 0，其状态变迁需通过其他方法显式修改，直接修改该属性值可能导致状态跟踪错误。
3. extra_info 参数具有高度灵活性，可存储任意类型数据，但使用者需自行保证其数据结构的有效性和解析逻辑的健壮性。
4. 该构造函数未包含参数校验逻辑，调用者需确保传入的 task_id 唯一且 dependencies 列表内容有效。
***
## ClassDef TaskManager
**TaskManager**: TaskManager 的功能是实现多任务调度与管理，处理任务依赖关系及状态追踪。

**属性(atributes)**: 这个Class所包含的属性有  
· task_dict (Dict[int, Task]): 存储任务ID与Task对象的映射关系  
· task_lock (threading.Lock): 线程锁，用于保证多线程环境下对task_dict的安全访问  
· now_id (int): 自增计数器，用于生成唯一的新任务ID  
· query_id (int): 自增计数器，记录任务查询次数  

**代码描述**:  
TaskManager 是一个线程安全的多任务调度器，核心功能包括：  
1. **任务注册**：通过`add_task`方法创建新任务，支持指定依赖任务列表（dependency_task_id）。新任务被封装为Task对象，其状态初始化为0（未开始），依赖关系指向具体的Task实例。每个新任务的ID由now_id自增生成。  
2. **任务分配**：`get_next_task`遍历task_dict，筛选出无依赖（dependencies为空）且状态为0的任务，将其状态更新为1（进行中），供外部处理器调用。  
3. **完成状态检测**：`all_success`属性通过判断task_dict是否为空，快速检测是否所有任务均已完成（假设任务完成后会从字典中移除）。  
4. **线程安全**：所有对task_dict的修改和遍历操作均通过with self.task_lock上下文管理器保护，确保多线程环境下的数据一致性。  

**注意事项**:  
1. 依赖任务必须在调用`add_task`时已存在于task_dict中，否则会触发KeyError  
2. 任务状态由内部维护（0=未开始，1=进行中），外部调用者不应直接修改Task对象的状态字段  
3. `get_next_task`返回的任务需由调用方处理完成后手动从task_dict移除，否则all_success将始终返回False  
4. query_id字段仅记录查询次数，不参与核心逻辑，主要用于调试或监控  

**输出示例**:  
```python
manager = TaskManager()
task1_id = manager.add_task(dependency_task_id=[])
task2_id = manager.add_task(dependency_task_id=[task1_id])
task, tid = manager.get_next_task(process_id=1)  # 返回(task1对象, task1_id)
```
***
### FunctionDef __init__(self)
**__init__**:  __init__ 函数的功能是初始化 MultiTaskDispatch 类的实例对象。

**参数(parameters)**: 该 Function 无显式外部参数，仅包含隐式 self 参数用于实例绑定。

**代码描述**:  该 Function 是 MultiTaskDispatch 类的构造函数，负责初始化任务调度核心组件。具体实现以下功能：
1. 创建 thread-safe 的 task_dict 字典结构，用于存储以 int 型 task_id 为键、Task 对象为值的映射关系
2. 初始化 threading.Lock 对象 task_lock，保障多线程环境下对共享资源 task_dict 的安全访问
3. 设置 now_id 和 query_id 计数器，分别用于生成唯一任务ID和记录查询次数
4. 定义嵌套属性 all_success，通过 @property 装饰器实现动态计算任务完成状态
5. 在类实例化过程中直接定义 add_task() 和 get_next_task() 方法，形成完整的任务管理闭环

与 Task 类的交互体现在：
- add_task() 方法通过 dependency_task_id 参数接收依赖的 Task 对象列表
- 新创建的 Task 对象会被存入 task_dict，其状态字段 status 将影响 get_next_task() 的任务调度逻辑

**注意事项**:
1. task_lock 的 with 语句使用是保障线程安全的关键，任何直接操作 task_dict 的代码必须通过该锁进行同步
2. now_id 的递增逻辑保证每个新任务的 ID 唯一性，但需要注意其作用域限定于 add_task() 方法内
3. query_id 的递增操作位于 get_next_task() 的锁保护范围内，但该字段未参与核心业务逻辑
4. Task 对象的 status 字段应严格遵循定义的状态机规则：0=未开始，1=进行中，2=已完成，3=错误

**输出示例**: 该构造方法无直接输出，实例化后对象初始状态为：
- task_dict = {}
- task_lock = <locked _thread.lock object>
- now_id = 0
- query_id = 0
***
### FunctionDef all_success(self)
**all_success**: all_success 函数的功能是判断当前对象的所有任务是否全部成功完成。

**参数(parameters)**: 该 Function 无显式定义的参数，仅包含隐式类实例参数 `self`（通过类方法调用时自动传递）。

**代码描述**: 该 Function 通过检查当前对象的 `task_dict` 属性是否为空字典来实现功能。具体逻辑为：若 `self.task_dict` 的长度等于 0（即字典中无任何键值对），则返回布尔值 `True`，表示所有任务已成功完成；反之返回 `False`，表示存在未完成或失败的任务。

**注意事项**:
1. 该方法的判定结果完全依赖于 `self.task_dict` 的实时状态，若该属性被其他方法动态修改，返回值会同步变化
2. 需要确保 `task_dict` 的设计逻辑符合"任务成功完成后被移出字典"的约定，否则可能导致误判
3. 返回值为严格的布尔类型（`bool`），可直接用于条件判断语句中

**输出示例**: 
- 当 `self.task_dict` 为空时返回：`True`
- 当 `self.task_dict` 包含元素时返回：`False`
***
### FunctionDef add_task(self, dependency_task_id, extra)
**add_task**:  add_task 函数的功能是向任务字典中添加新任务并返回新任务的唯一ID。

**参数(parameters)**:  
· dependency_task_id: 新任务所依赖的父任务ID列表，类型为整数列表。每个ID必须已在task_dict中存在。  
· extra: 与新任务关联的附加信息，类型不限，默认值为None。  

**代码描述**:  
该函数通过线程安全的方式向task_dict插入新任务。具体流程为：  
1. 使用task_lock保证多线程环境下字典操作的原子性。  
2. 通过dependency_task_id遍历task_dict，获取所有依赖的Task对象集合depend_tasks。  
3. 以当前now_id作为新任务的唯一标识，创建Task实例。该实例包含任务ID、依赖对象集合和附加信息，其中status字段由Task类初始化为0（未开始状态）。  
4. 将新Task实例存入task_dict后，now_id自增以实现ID连续分配。  
5. 返回新任务的ID（now_id自增前的值）。  

与Task类的交互体现在：通过Task构造函数创建任务实例时，将依赖的父任务对象列表作为dependencies参数传递，实现任务间的依赖关系绑定。该函数是构建任务依赖图的核心方法。

**注意事项**:  
· 传入的dependency_task_id中的每个ID必须对应task_dict中已存在的任务，否则会触发KeyError  
· 线程安全性由task_lock保证，调用方无需额外同步  
· 返回值是任务创建瞬间的now_id快照，后续调用add_task会改变now_id的值  
· Task对象的状态管理（如status字段更新）需通过其他方法实现，本函数仅负责初始化  

**输出示例**:  
假设最后一次返回的ID是2，再次调用后将返回3。示例返回值格式为：  
3
***
### FunctionDef get_next_task(self, process_id)
**get_next_task**: get_next_task 函数的功能是为指定进程ID获取下一个可执行的任务对象及其ID。

**参数(parameters)**:  
· self: 类实例方法隐含参数，用于访问类内部属性如task_lock、task_dict等。  
· process_id (int): 进程标识符，用于关联操作来源（当前版本代码中未在核心逻辑中使用，仅保留于注释的调试输出部分）。  

**代码描述**:  
该函数通过线程锁（task_lock）保证线程安全，首先递增内部计数器query_id。随后遍历任务字典（task_dict）中的所有任务ID，筛选符合以下条件的任务：  
1. 无依赖项（dependencies长度为0）  
2. 任务状态为0（未开始状态）  

当找到首个符合条件的任务时，立即将其状态标记为1（进行中状态），并返回该任务对象与其ID组成的元组。若遍历后无可用任务，则返回(None, -1)。  

**注意事项**:  
1. 线程安全依赖task_lock实现，调用方需避免在外部直接操作task_dict造成锁竞争或状态不一致。  
2. 任务状态变更（0→1）具有原子性，调用方需确保任务执行完成后自行更新状态，否则可能导致任务重复执行。  
3. task_dict的遍历顺序取决于字典键的存储结构（Python默认无序），实际任务获取顺序可能与插入顺序不一致。  
4. process_id参数在现有代码版本中未参与核心逻辑，仅保留于注释的调试语句，可能用于未来扩展或日志追踪。  

**输出示例**:  
· 存在可用任务时返回: (<TaskObject instance at 0x...>, 5)  
· 无可用任务时返回: (None, -1)
***
