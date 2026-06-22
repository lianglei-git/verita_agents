很好，我们进入到真正的核心层了。

因为我认为在 Verita 里面，**用户画像（User Profile）不是注册信息，也不是推荐系统画像。**

它实际上应该升级为：

> **Digital Twin（数字孪生）系统**
>
> 用于持续回答：
>
> **用户现在是谁、正在变成谁、未来可能成为谁。**

这一层未来会影响：

```text
学习规划
课程生成
难度控制
场景生成
复习策略
成长记录
AI导师行为
```

所以这里需要按平台级能力设计。

---

# Verita PRD — 用户画像系统（Digital Twin）

版本：

```text
V1.0
```

归属：

```text
World Model Layer
```

系统编号：

```text
W2
```

代号：

```text
Digital Twin Engine
```

---

# 一、系统使命

传统学习产品：

记录：

```text
等级
学习记录
积分
```

---

Verita：

持续构建：

```text
这个人是谁
↓
为什么学习
↓
如何学习
↓
正在成长成什么样
```

---

系统目标：

构建用户数字镜像。

输出：

```text
User Graph
```

---

# 二、系统职责

用户画像系统负责：

---

## 1 身份建模（Identity Modeling）

回答：

```text
用户是谁
```

---

## 2 能力建模（Capability Modeling）

回答：

```text
用户会什么
```

---

## 3 学习建模（Learning Modeling）

回答：

```text
用户如何学习
```

---

## 4 成长建模（Growth Modeling）

回答：

```text
用户正在成为谁
```

---

## 5 场景建模（Scenario Modeling）

回答：

```text
用户接下来可能遇见什么
```

---

最终输出：

```text
Digital Twin
```

---

# 三、整体结构

```text
Digital Twin
│
├── Identity Profile
├── Capability Profile
├── Learning Profile
├── Growth Profile
├── Scenario Profile
├── Behavior Profile
└── System Metadata
```

---

# 四、领域模型

---

## P1 Identity Profile

身份画像

目的：

建立用户基础现实世界模型。

---

字段：

```json
{
"id":"",
"name":"",
"age_range":"",
"country":"",
"city":"",
"native_language":"",
"occupation":"",
"industry":"",
"education_level":"",
"timezone":""
}
```

---

说明：

年龄不建议精确。

建议：

```text
18–24

25–34

35–44
```

---

职业：

建议标准化。

例如：

```text
Software Engineer
Designer
Student
Teacher
```

---

更新频率：

```text
低
```

---

来源：

```text
注册
问卷
用户修改
```

---

---

## P2 Capability Profile

能力画像

目的：

建立学习能力地图。

---

结构：

```json
{
"cefr":"A2",
"listening":62,
"speaking":41,
"reading":74,
"writing":55,
"grammar":69,
"vocabulary":58
}
```

---

升级版：

能力矩阵：

```json
{
"memory":{},
"understanding":{},
"retrieval":{},
"transfer":{}
}
```

---

示例：

```json
{
"memory":72,
"understanding":83,
"retrieval":46,
"transfer":35
}
```

---

来源：

```text
评测引擎

课程结果

复习结果
```

---

更新频率：

```text
实时
```

---

---

## P3 Learning Profile

学习画像

目的：

建立学习方式模型。

---

结构：

```json
{
"daily_minutes":30,
"peak_hour":"21:00",
"completion_rate":0.81,
"drop_rate":0.14,
"preferred_mode":"dialogue",
"patience_score":63
}
```

---

关键指标：

---

学习节奏：

```text
Slow

Normal

Fast
```

---

内容偏好：

```text
Story

Dialogue

Exercise

Immersion
```

---

认知负荷：

```text
Low

Medium

High
```

---

来源：

```text
行为埋点
```

---

更新：

```text
每日
```

---

---

## P4 Growth Profile

成长画像

目的：

记录变化。

---

结构：

```json
{
"goal":"海外工作",
"current_stage":"Interview",
"completed_milestones":[]
}
```

---

成长节点：

```json
[
"完成首次英文自我介绍",
"完成模拟面试",
"首次连续学习30天"
]
```

---

来源：

```text
事件流
```

---

更新：

```text
事件驱动
```

---

---

## P5 Scenario Profile

场景画像

目的：

描述未来学习环境。

---

结构：

```json
{
"primary_track":"Global Career",
"current_scenario":"Technical Interview",
"next_scenarios":[]
}
```

---

示例：

```json
{
"next":[
"Offer Negotiation",
"Team Meeting",
"First Day"
]
}
```

---

来源：

```text
场景引擎
```

---

更新：

```text
按阶段
```

---

---

## P6 Behavior Profile

行为画像

目的：

预测学习行为。

---

结构：

```json
{
"avg_session":18,
"hint_usage":0.21,
"retry_rate":0.44,
"skip_rate":0.12,
"engagement":73
}
```

---

推导：

```text
坚持能力

探索倾向

逃避倾向
```

---

来源：

```text
事件流
```

---

更新：

```text
实时
```

---

---

## P7 Metadata

系统元数据

结构：

```json
{
"profile_version":"1.0",
"created_at":"",
"updated_at":"",
"confidence":0.82
}
```

---

confidence：

表示：

```text
系统对画像可信度
```

---

# 五、输入输出定义

---

输入：

```json
{
"events":[],
"assessment":{},
"lesson_history":[],
"user_input":{}
}
```

---

输出：

```json
{
"digital_twin":{}
}
```

---

消费者：

```text
Learning Planner

Curriculum Compiler

Review Compiler

Scenario Engine

AI Mentor
```

---

# 六、生命周期

---

创建：

```text
首次注册
```

↓

初始画像

↓

学习行为采集

↓

画像迭代

↓

能力收敛

↓

长期稳定

---

# 七、画像更新策略

不要实时全量更新。

建议：

---

身份：

```text
手动
```

---

能力：

```text
实时
```

---

学习习惯：

```text
每日
```

---

成长：

```text
事件驱动
```

---

场景：

```text
阶段驱动
```

---

行为：

```text
小时级
```

---

# 八、AI参与范围

AI允许：

```text
推断兴趣

生成成长建议

生成学习路径
```

---

AI禁止：

```text
修改身份

推断敏感属性

覆盖事实数据
```

---

只能：

```text
建议
```

---

# 九、MVP范围

第一版只做：

```text
Identity

Capability

Learning

Growth
```

不做：

```text
Behavior

Scenario
```

---

# 十、成功指标

画像系统成功标准：

```text
课程完成率 ↑

复习命中率 ↑

学习连续性 ↑

用户满意度 ↑
```

---

首页建议放这一句话：

> **Digital Twin 不是用户档案。**
>
> **它是系统对一个人成长状态的持续理解。**
>
> 用户画像不是为了判断用户是谁，而是为了帮助系统理解：下一步应该怎样帮助他成长。
