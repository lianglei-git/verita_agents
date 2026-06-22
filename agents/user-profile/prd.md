## Digital Twin（数字孪生）系统
> 重点: 持续回答! 持续回答! 持续回答!
> 用户现在是谁、正在变成谁、未来可能成为谁。

--- 
- 版本：V1.0
- 归属：World Model Layer
- 系统编号：W2
- 代号：Digital Twin Engine
---


### 系统职责
这是一个回答用户信息的系统。



1. 身份建模（Identity Modeling）
问题收集
```json
{
    "name":"", // 姓名
    "age_range":"", // 年龄范围
    "country":"", // 国家
    "city":"",   // 城市
    "native_language":"", // 母语
    "occupation":"", // 职业
    "industry":"", // 
    "education_level":"", // 文化水平
    "timezone":"" // 时区 - 可以根据国家来确定
}
```


2. 能力建模（Capability Modeling）

问题收集
```json
{
"cefr":"A2", // cefr水平，通过听说读写分数来衡量。
"listening":62,
"speaking":41,
"reading":74,
"writing":55,
"grammar":69,
"vocabulary":58
}
```

3. 学习建模（Learning Modeling）

4. 成长建模（Growth Modeling）


系统阶段：

#### p0：基础信息
- 最基础的信息采集：职业、国家、母语、当前要学习语言水平等级、听说读写水平（通俗的按照0-100分打分，不及格、及格、良好、优秀）
-【来源】注册、问卷、用户修改、评测结果



#### p1：学习行为采集
- 每日学习时间、最长学习时间、完成率、遗漏率、练习喜好、忍耐分数。
- 得到学习节奏、内容偏好、认知能力。



#### p2：能力收敛：记忆能力、理解能力、成长能力
- 来源： 复习结果、课程结果
