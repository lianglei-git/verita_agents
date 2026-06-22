
Lab-ConstructingSpiralSyntax - 输出基于 EGP 语法点的“螺旋学习路径”工作流



       

用户画像 Agent
→ [人生推演]
→ 路线规划 Agent
→ 故事场景 Agent
→ 知识点映射 Agent
→ 课程编译 Agent
→ 练习/内容生成 Agent
→ 用户完成学习
→ 评测 Agent
→ 能力更新 Agent
→ 复习 Agent
→ 重新影响下一节课
       


1. 用户画像
> 负责回答 这个用户是谁？他想去哪？，
输入： 职业、现状（水平，年龄，性别）、目标、学习偏好
输出： 用户画像、目的、当前能力缺口

2. 人生推演 
**如果用户不输入目标，或者明确推演自己的未来**，那么就应该走这一条路，要创建一个人生推演的故事概括

输出：未来人生剧本
是的，现在应该开始做“工程架构思路”了。

但我建议不要一开始就把 agent 做得太多。正确顺序是：

> 先设计闭环，再拆 agent。  
> 不是先堆 agent 名字。

## 推荐 Agent 数量
我建议分成两层：

**MVP 阶段：6 个核心 Agent + 1 个编排器**

这已经可以跑通完整产品闭环。

**完整阶段：9 到 11 个 Agent**

等产品验证后，再把内容治理、知识图谱治理、AI 安全、CMS 等拆出去。

## MVP 闭环
最小闭环应该是：

```text
用户目标
→ 用户画像 Agent
→ 路线规划 Agent
→ 故事场景 Agent
→ 知识点映射 Agent
→ 课程编译 Agent
→ 练习/内容生成 Agent
→ 用户完成学习
→ 评测 Agent
→ 能力更新 Agent
→ 复习 Agent
→ 重新影响下一节课
```

这才叫闭环。

用户不是学完就结束，而是每一次学习结果都会反过来改变下一次课程。

## MVP Agent 设计
### 1. Orchestrator 编排器
它不是业务 agent，而是总调度。

负责：

- 决定调用哪个 agent
- 管理流程状态
- 拼接上下文
- 处理失败重试
- 保存每一步输入输出

它像系统大脑，但不直接做内容判断。

### 2. User Profile Agent 用户画像 Agent
负责回答：

> 这个用户是谁？他想去哪？

输入：

- 职业
- 英语水平
- 目标
- 学习偏好
- 最害怕的场景

输出：

- 用户画像
- 主线目标
- 当前能力缺口

### 3. Route Planner Agent 路线规划 Agent
负责回答：

> 用户应该先走哪条成长路线？

例如：

- 海外面试线
- 远程工作线
- 自由职业线
- 出国生活线

MVP 先只做一条：  
`前端工程师 → 海外面试 → 项目表达 → 远程协作`

### 4. Story Scenario Agent 故事场景 Agent
负责回答：

> 这条路线应该变成什么故事章节？

例如：

- 你是谁
- 你做过什么
- 你为什么值得被支付美元
- 你如何通过技术面试
- 你如何参与远程协作

它的核心价值是把学习变成连续剧情，而不是课程列表。

### 5. Knowledge Mapping Agent 知识点映射 Agent
负责回答：

> 这个场景需要哪些英语知识点？

它把故事场景映射到：

- CEFR 等级
- EGP 语法点
- 词汇
- 句型
- 语言功能

用户看到的是“模拟海外面试”。  
系统内部知道这节课覆盖了哪些知识点。

### 6. Course Compiler Agent 课程编译 Agent
负责回答：

> 这一节课应该怎么组织？

它不负责写漂亮文案，主要负责结构。

输出一节课的骨架：

```text
输入 → 理解 → 语言 → 输出
```

例如：

- 输入：海外面试邀请
- 理解：判断对话重点
- 语言：学习自我介绍句型
- 输出：录制 30 秒回答

### 7. Content / Exercise Agent 内容练习 Agent
负责把课程骨架变成真实内容。

生成：

- 场景文本
- 对话
- 题目
- 填空
- 排序
- 写作任务
- 口语任务

它必须服从 Course Compiler 给出的知识点范围，不能随便超纲。

## 后续完整 Agent
等 MVP 跑通后，可以继续拆：

- Assessment Agent：评测用户答案
- Competency Agent：更新理解、记忆、调用、迁移四维能力
- Review Agent：根据错误生成复习
- Governance Agent：检查内容是否超纲、重复、难度跳跃
- CMS Agent：辅助运营人员生产和审核内容

## 最关键的工程原则
每个 agent 都应该当作独立项目设计。

每个 agent 至少要有：

- 独立输入 schema
- 独立输出 schema
- 独立 prompt 或规则
- 独立测试样例
- 独立版本号
- 独立日志
- 独立失败处理
- 可被 Orchestrator 调用的 API

不要让 agent 之间直接互相乱调。  
统一由 Orchestrator 调度。

## 我的建议
现在先不要做 11 个 agent。

第一阶段就设计这 7 个：

1. `Orchestrator`
2. `User Profile Agent`
3. `Route Planner Agent`
4. `Story Scenario Agent`
5. `Knowledge Mapping Agent`
6. `Course Compiler Agent`
7. `Content / Exercise Agent`

这 7 个能先打通：

> 用户画像 → 成长路线 → 故事章节 → 知识点 → 课程 → 练习

然后第二阶段再补：

> 评测 → 能力更新 → 复习 → 下一课自适应

这样工程不会一开始爆炸，但方向是对的。