# LS AI 图片生成 Prompt 手册 · v1.0

> **定位**：本手册是 LS 全部 AI 生成图片的 Prompt 生产线，覆盖四类需求——封面生成、目标插画、功能插画、单词图片。
> **上游约束**：一切风格决策源自《LS 设计价值观 v1.0》（第 3 章色彩、第 7 章图标与插画）。色值、气质以该文件为准，本手册只做「翻译」——把 token 翻译成图像模型听得懂的语言。
> **使用方法**：每张图的 Prompt = `① 主体变量` + `② 场景变量` + `③ 风格锚（固定，照抄）` + `④ 输出参数`。四类图片各有一个固定风格锚，**全项目任何人、任何时候生成同类图，风格锚一字不改**——这是几千张图看起来出自同一套视觉体系的唯一办法。

---

## 0. 总纲：五条生成纪律

1. **一个彩色家族**。所有插画类图片只允许紫色家族 + 中性色（纸白/墨黑）。封面允许出现主题色，但必须经风格锚压饱和。任何一张图出现第二个高饱和彩色家族，报废。
2. **图中永不出现文字、字母、数字、水印、Logo**。图像模型渲染文字必然出错，文字信息由 UI 层叠加，不由图片承担。所有 Prompt 的负向约束第一条就是它。
3. **风格锚 > 灵感**。先固定风格锚跑 20 张不同主题的图验证一致性，锚定稿经评审通过后锁死进本手册；之后只允许改主体变量，不允许「这次换个风格试试」。
4. **低细节、几何化、扁平**。学习产品的图像是功能件不是艺术品：0.5 秒内能读懂主体即为合格，细节越多越容易穿帮。
5. **先小图验证，后大图投产**。所有新 Prompt 先 1K 出 4 张选 1，确认后再升 2K/4K 交付；批量任务（如 500 个单词图）先跑 20 个样例走查，再全量。

---

## 1. Prompt 通用解剖

### 1.1 四段式结构

```
[① 主体]  谁/什么，一个画面只有一个主角
[② 场景]  在哪、做什么，一句话以内，拒绝复合剧情
[③ 风格锚]  照抄本手册对应类别的固定段落（含画风、色板、光线、质感、负向约束）
[④ 参数]  比例、分辨率、背景（透明/不透明）
```

### 1.2 语言策略

- **生成用英文 Prompt**（主流模型对英文的构图与风格控制显著更稳），手册中每条 Prompt 附中文注释。
- 主体与场景变量维护一张中英对照表（见第 6 章模板），保证批量生产时变量可程序化拼接。

### 1.3 通用负向约束（所有类别共用，追加在风格锚尾部）

```
no text, no letters, no numbers, no watermark, no logo, no signature,
no realistic human face close-up, no photo collage, no neon glow,
no rainbow gradients, no clutter, no extra unrelated objects
（无文字/字母/数字/水印/Logo/签名；无人脸特写；无拼贴；
无霓虹发光；无彩虹渐变；无杂物堆砌；无与主体无关的元素）
```

### 1.4 输出规格速查

| 用途槽位 | 比例 | 分辨率 | 背景 | 格式 |
|---|---|---|---|---|
| Collection 封面 | 16:9 | 2K | 不透明 | WebP（归档 PNG） |
| Goal 目标插画（L1/L2 大卡右侧） | 16:9 或 3:2 | 2K | 不透明 | WebP |
| Onboarding / 空状态插画 | 1:1 或 3:2 | 1K | 透明 PNG | PNG |
| 成就徽章底图 | 1:1 | 1K | 透明 PNG | PNG |
| 单词图片 | 1:1 | 1K | 透明 PNG（首选） | PNG |
| 句子配图 | 3:2 | 1K | 不透明 | WebP |

---

## 2. 类别一：封面生成（Collection Cover）

### 2.1 定位

Explore 与 My Collections 卡片上的 16:9 封面。它是「课程的门面」，允许比插画更有内容感，但**必须克制**——封面的职责是传达主题，不是炫技。在卡片栅格中并排出现时，明度与饱和度必须整齐划一，否则会像菜市场。

### 2.2 风格锚（固定照抄）

```
Flat vector illustration, modern editorial style, soft matte texture,
dominant deep violet and lavender palette (#7A68EE, #BDB0F7, #EBE7FD)
with warm off-white background (#F8F8FC), one small accent of muted gold,
calm and composed mood, generous negative space, clean geometric shapes,
subtle grain, no outlines thicker than 2px, flat lighting, no shadows longer than the subject itself
（扁平矢量插画、现代编辑部风格、柔和哑光质感；
深紫与薰衣草紫为主、暖米白底、一点哑光金点缀；
沉静气质、大量留白、几何形体、细颗粒、无粗描边、平光）
```

### 2.3 变量槽与模板

```
[① 主题场景，一句话] , [② 构图指令] , + 风格锚 + 通用负向约束 + 16:9, 2K
```

构图指令三选一（批量生产时轮换，保证 Explore 页并排不雷同）：
- `centered composition, single focal object`（居中单体）
- `rule of thirds, subject on the right, space for title on the left`（右主体左留白——标题叠加用）
- `horizontal panorama with layered depth`（横向前中后三层景深）

### 2.4 成品 Prompt 示例

**示例 1｜开发者英语课程**
```
A minimalist workspace scene: an open laptop, a coffee cup, and a small potted plant
on a desk, a window with soft morning light behind, centered composition, single focal group,
Flat vector illustration, modern editorial style, soft matte texture, dominant deep violet
and lavender palette (#7A68EE, #BDB0F7, #EBE7FD) with warm off-white background (#F8F8FC),
one small accent of muted gold, calm and composed mood, generous negative space,
clean geometric shapes, subtle grain, flat lighting,
no text, no letters, no watermark, no neon glow, no clutter
--ar 16:9 --quality 2K
```

**示例 2｜酒店预订主题（旅游英语）**
```
A hotel reception bell and a key card on a counter, a suitcase standing nearby,
rule of thirds, subject on the right, wide quiet space on the left,
Flat vector illustration, modern editorial style, soft matte texture, dominant deep violet
and lavender palette (#7A68EE, #BDB0F7, #EBE7FD) with warm off-white background (#F8F8FC),
one small accent of muted gold, calm and composed mood, generous negative space,
clean geometric shapes, subtle grain, flat lighting,
no text, no letters, no watermark, no neon glow, no clutter
--ar 16:9 --quality 2K
```

**示例 3｜面试英语**
```
Two simple chairs facing each other across a small round table, a window light falling
between them, horizontal panorama with layered depth, quiet and expectant atmosphere,
+ 风格锚 + 负向约束 --ar 16:9 --quality 2K
```

### 2.5 封面专属质检

- [ ] 缩到 360px 宽（卡片实际显示尺寸）主体仍一眼可辨
- [ ] 与另外 8 张封面并排时无明度/饱和度跳变
- [ ] 左侧留白款（构图 b）叠加 32px 白字标题后对比度 ≥ 4.5:1
- [ ] 无文字、无人脸特写、无第二彩色家族

---

## 3. 类别二：目标插画（Goal Illustration）

### 3.1 定位

L1 Home 的 Goal 卡与 L2 Learning Path 页头的**叙事性焦点插画**。它是全产品情感浓度最高的一张图，而它的**内容不是我们的装饰，是用户数据的函数**：想成为全球前端工程师的人、想考律师的学生、为旅行学语言的人，看到的「远方」必须不同。这张图回答的是——「你的现状在哪里，你的目标长什么样」。每屏仍只允许这一处插画焦点（设计价值观 §7.2），个性化不改变这条纪律。

### 3.2 三层架构：什么锁死、什么生成

| 层级 | 内容 | 策略 |
|---|---|---|
| 风格层 | 色板（单色紫阶）、扁平分层、光线、质感、负向约束 | **锁死**，照抄风格锚（§3.3） |
| 叙事语法层 | 构图骨架：近景带 = 现状（下方/左下），远景带 = 目标（上方/右上），一条线索连接两者，上半部留白 | **锁死**——一万张图内容不同，骨架相同 |
| 内容层 | 近景与远景具体画什么 | **双轨生成**（§3.4 母题库 / §3.5 全生成） |

**叙事语法细则**（任何一张目标插画都必须满足）：

1. 画面分两个明度带：近景带用紫阶中深部（#7A68EE–#312878），远景带用浅部（#BDB0F7–#F4F2FE）——目标永远更亮，光在远方；
2. 近景 2–4 个物件讲「现状」，远景 1 个主体讲「目标」，连接线索 1 条（小径、桥、河流、公路、航线皆可）；
3. 元素总数 ≤ 6；无人、无文字、无日月等具体天体（避免时间暗示）；
4. 上半部至少 40% 留白，供 UI 叠加标题与进度。

### 3.3 风格锚（锁死照抄）

```
Minimal geometric landscape illustration, layered flat shapes with soft depth,
monochromatic violet scale from deep indigo (#312878) to pale lavender (#F4F2FE),
distant layers lighter and lower contrast, crisp clean edges, no texture noise,
airy negative space occupying upper half, serene and determined mood,
flat design, no outlines
（极简几何风景插画；扁平分层、柔和景深；单色紫阶由深靛到淡薰衣草；
远层更浅更灰；边缘干净；无噪点肌理；上半幅大量留白；宁静而笃定）
```

### 3.4 轨道 A：隐喻母题库（默认轨 & 兜底轨）

**适用**：新用户未填写完整目标 / 轨道 B 质检失败回退 / 运营位批量配图。
**机制**：LLM 或规则把用户目标关键词映射到预置母题；每个母题一条评审锁定的 Prompt，内容固定不变。

| 母题 | 语义 | 映射关键词示例 |
|---|---|---|
| 山径（通用默认） | 任何向上的旅程 | 无法分类时的最终兜底 |
| 跨海天际线 | 国际化职业、海外工作 | global、海外、international、外企 |
| 书阶 | 学业、考试、升学 | 考研、考试、academic、留学申请 |
| 桥 | 转行、跨界 | 转行、转岗、career change |
| 港口与灯塔 | 旅行、远行 | travel、旅居、移民 |
| 门与光廊 | 新机会、新身份 | interview、offer、入职 |
| 跑道 | 技能精进、职业深化 | 晋升、expert、精通 |
| 罗盘地平线 | 个人成长、探索 | personal growth、兴趣、自我提升 |

母题 Prompt 示例（跨海天际线）：

```
A small desk with a monitor and a coffee cup on quiet ground in the lower left,
a distant city skyline across calm water in the upper right,
a single narrow bridge path connecting the desk to the city,
+ 目标插画风格锚 + 通用负向约束 --ar 16:9 --quality 2K
```

母题全表（首批 8 条锁定 Prompt）随插画资产库维护，扩充走评审。

### 3.5 轨道 B：全生成（目标描述完整的用户）

**触发条件**（同时满足）：目标文本 ≥ 10 个字符；身份/现状字段已填；Onboarding 完整结束。

**生产管线**：

```
用户 Profile（身份 / 现状 / 目标原文 / 学习语言）
  ↓ ① LLM 视觉翻译（meta-prompt，锁死照抄）
场景短语 JSON：{ current_scene, goal_scene, connector }
  ↓ ② 按叙事语法组装 + 风格锚 + 负向约束
生成 4 候选
  ↓ ③ 机器质检（§3.6）
入库使用；失败 → 退回轨道 A
```

**① LLM 视觉翻译 meta-prompt**（轨道 B 的核心资产，锁死照抄）：

```
You are an art director for a language-learning product. Convert a learner's
profile into a minimal geometric illustration scene description.

Input: { "identity": "...", "current": "...", "goal": "...", "language": "..." }

Output strict JSON only:
{
  "current_scene": "2-4 concrete physical objects describing the learner's PRESENT situation, lower-left foreground",
  "goal_scene": "1 concrete physical subject describing the learner's GOAL, upper-right distance",
  "connector": "one connecting element: a path, river, road, bridge, or flight trail"
}

Rules:
- Only concrete, drawable, physical objects. No abstract concepts (no "success", no "dream").
- No people, no faces, no text, no letters, no logos, no flags with symbols.
- No sun, moon, stars, or clock — nothing that indicates a specific time.
- Each element describable in under 8 English words.
- Objects must be culturally neutral unless the goal explicitly names a culture.
- If the goal is too vague, output { "fallback": true }.
```

**② 组装模板**：

```
{ current_scene }, in the lower left foreground, { goal_scene }, in the upper
right distance, { connector } connecting the foreground to the distance,
+ 目标插画风格锚 + 通用负向约束 --ar 16:9 --quality 2K
```

**③ 三个用户的完整示例**（同语法、同锚、不同内容）：

前端工程师 B1→B2：
```
A desk with a monitor, a keyboard and a small potted plant, in the lower left
foreground, a city skyline across calm water, in the upper right distance,
a narrow bridge connecting the foreground to the distance, + 风格锚 + 负向约束 --ar 16:9 --quality 2K
```

法学学生（目标考律师资格）：
```
A stack of books and a desk lamp, in the lower left foreground, a classical
courthouse with columns, in the upper right distance, a winding path connecting
the foreground to the distance, + 风格锚 + 负向约束 --ar 16:9 --quality 2K
```

旅行学习者：
```
A passport and a coffee cup on a small table, in the lower left foreground,
a lit mountain lodge in a valley, in the upper right distance, a winding road
connecting the foreground to the distance, + 风格锚 + 负向约束 --ar 16:9 --quality 2K
```

### 3.6 质量门与兜底（轨道 B 专属）

| 质检项 | 方法 | 不通过处理 |
|---|---|---|
| 文字检测 | OCR 扫描，检出字符即失败 | 重生成 1 次，仍失败 → 轨道 A |
| 色板合规 | 直方图校验：紫阶 + 中性色像素占比 ≥ 85% | 重生成 1 次，仍失败 → 轨道 A |
| 人脸检测 | 人脸模型扫描 | 直接退回轨道 A |
| 元素过载 | 人工抽检（每批 10%） | 收紧 meta-prompt 元素上限 |
| 语义贴合 | 上线初期人工走查 50 张 | 迭代 meta-prompt 并升版本号 |

**缓存规则**：以 `hash(目标文本 + 身份)` 为 key 复用已生成的图——目标没变不重新生成（省钱且稳定）；用户修改目标（D-09）后触发重新生成，旧图保留 30 天。

### 3.7 目标插画纪律

1. 内容层只允许经两条轨道产出；任何人不得为单个用户或运营活动手工定制一次性插画。
2. 等级与进度变化**不换图**——进度由 UI 进度条承担，插画只表达「去哪」，不表达「走到哪」。
3. 母题库扩充 = 新增映射关键词 + 新增锁定 Prompt，走评审；母题总数 ≤ 12。
4. 轨道 B 的 meta-prompt 与风格锚同为代码库常量，修改须升版本号并留记录（对齐 PRD 13.7 Prompt 版本管理）。
5. 永不出现人物、动物、太阳、文字——这些元素会把「你的旅程」变成「别人的故事」。

---

## 4. 类别三：功能插画（空状态 / 引导 / 成就）

### 4.1 定位与分区

| 子类 | 用途 | 气质 |
|---|---|---|
| 空状态插画 | 无收藏、无复习包、无搜索结果 | 安静、一点点幽默，但不卖萌 |
| 引导插画 | Onboarding 各步骤题图 | 期待感、向前感 |
| 成就徽章 | 连胜、完成 Phase、词汇量里程碑 | 仪式感、几何徽章，可含哑光金 |
| 错误/降级插画 | AI 失败、加载失败 | 平静中性，绝不画「事故现场」 |

### 4.2 风格锚（固定照抄）

```
Simple geometric spot illustration, one single object or one tiny scene,
flat violet and lavender palette (#7A68EE, #BDB0F7, #EBE7FD) on transparent background,
thick-and-thin balance of shapes, 1.5px line details, soft rounded corners everywhere,
friendly but restrained, no facial expressions beyond two dots and one curve at most
（极简几何小插画；单个物体或一个微型场景；紫阶扁平色、透明底；
1.5px 线稿细节；全部圆角；友好但克制；表情最多两点一线）
```

成就徽章在风格锚尾部追加：
```
, circular medal composition, muted gold accent (#C9A227) on violet base,
subtle radial depth, centered
（圆形徽章构图；紫底哑光金点缀；轻微径向层次；居中）
```

### 4.3 成品 Prompt 示例

**空状态：无收藏**
```
An open empty book with a small violet bookmark ribbon, floating 2-3 tiny stars around,
+ 功能插画风格锚 + 通用负向约束 --ar 1:1 --transparent --quality 1K
```

**空状态：无搜索结果**
```
A magnifying glass hovering over three faint dashed circles, one violet dot inside the lens,
+ 风格锚 + 负向约束 --ar 1:1 --transparent
```

**引导：Onboarding 第 1 步（你为什么学习）**
```
A small geometric figure standing at a fork of two simple paths on a round patch of ground,
looking forward, + 风格锚 + 负向约束 --ar 1:1 --transparent
（注意：人物只允许背影/侧面剪影，无五官）
```

**引导：设定目标**
```
A small violet flag planted on a round hilltop, a dotted path line leading to it,
+ 风格锚 + 负向约束 --ar 1:1 --transparent
```

**成就徽章：7 日连胜**
```
A geometric flame icon inside a circular medal, + 徽章锚 + 负向约束 --ar 1:1 --transparent
```

**成就徽章：词汇大师（500 词）**
```
Three stacked geometric book spines inside a circular medal, + 徽章锚 + 负向约束 --ar 1:1 --transparent
```

**错误态：AI 任务失败**
```
A small geometric cloud with a single rain drop paused mid-air, a tiny violet arrow
circling back (retry metaphor), + 风格锚 + 负向约束 --ar 1:1 --transparent
（画「暂停与重试」，不画断裂、爆炸、红色叉号）
```

### 4.4 功能插画纪律

- 尺寸小（显示 120–200px），因此**一个元素主角 + 至多 3 个辅助元素**，多一个就糊。
- 透明底必须真透明（无白边、无投影残留）；落地 UI 后由 token 决定是否加浅底色块。
- 人物出现规则：仅引导插画允许，且永远是无五官剪影——五官是廉价的亲和，剪影才是普适的共情。

---

## 5. 类别四：单词图片（Vocabulary Image）

### 5.1 定位与特殊性

单词图片是**教学材料**，不是装饰——它的功能是建立「词 → 意象」的直接记忆联结。因此它的设计目标与其他三类相反：**不求美，求准**。一个词的图必须让学习者在不看释义的情况下 0.5 秒内说出这个词。

产量预估：单个 Collection 500–2000 词，全平台可能上万张。**这是唯一必须全程序化批量生产的类别**，Prompt 模板化程度最高。

### 5.2 风格锚（固定照抄）

```
A single [word] , flat vector icon illustration, centered composition,
one object only filling 70% of the frame, soft violet-tinted neutral palette
with the object's natural colors slightly desaturated, clean simple shapes,
rounded corners, no outline heavier than 2px, plain background removed,
educational flashcard style, instantly recognizable at small size
（单一主体；扁平矢量图标；居中、占画面 70%；物体固有色轻微降饱和；
形体简洁、圆角；无粗描边；透明底；教学抽认卡风格；小尺寸下可一眼识别）
```

> 为什么是「固有色轻微降饱和」而不是全紫：单词图需要利用颜色做记忆线索（香蕉是黄的、救护车有红十字），全紫会损害教学效果。这是全手册唯一允许跳出紫色家族的地方——但饱和度必须压到与紫色家族同档，混排时不刺眼。

### 5.3 词性分桶模板（变量槽按词性切换）

| 词性 | 模板 | 示例（run） |
|---|---|---|
| 具体名词 | 单体物品居中 | `a single coffee mug` |
| 动词 | 物品 + 运动线索（速度线/姿态），不画人 | `a running shoe with three motion lines` |
| 形容词 | 对比或象征物 | `tall: one tall glass beside one short glass` |
| 抽象名词 | 约定俗成的隐喻物 | `deadline: a calendar page with a circled corner` |
| 短语/词组 | 微型场景（≤2 元素） | `check in: a suitcase in front of a reception desk` |

人形规则：动词若必须出现人，用无五官剪影；形容词对比组内元素必须同款不同态（两个一样的杯子，一高一矮）。

### 5.4 批量生产 Prompt 模板（可直接程序拼接）

```
A single {EN_WORD_OR_SCENE} , flat vector icon illustration, centered composition,
one object only filling 70% of the frame, soft violet-tinted neutral palette
with natural colors slightly desaturated, clean simple shapes, rounded corners,
plain background removed, educational flashcard style, instantly recognizable
at small size, no text, no letters, no watermark, no realistic details,
no background scenery, no extra objects
--ar 1:1 --transparent --quality 1K
```

`{EN_WORD_OR_SCENE}` 填词性分桶产出的英文短语（由 LLM 预先把单词转成「视觉描述短语」再入库，例如 `ambulance → a single ambulance with a cross symbol, side view`）。

### 5.5 单词图质检（每张必过）

- [ ] **裸测**：给不看单词的人看图，0.5 秒内说出目标词即合格
- [ ] 缩到 96px 仍可识别（词卡实际显示尺寸）
- [ ] 单主体；无背景场景；无文字（包括物体上的商标、标签字）
- [ ] 与同词表随机 20 张并排：风格、明度、占比一致
- [ ] 多义词检查：图义 = 该 Collection 教授的义项（`bank` 在商务课程画银行大楼，在自然课程画河岸——**义项来自词表数据，不由模型自由发挥**）

### 5.6 失败模式与对策

| 失败 | 原因 | 对策 |
|---|---|---|
| 图里出现字母 | 物体自带文字（书、报纸、招牌） | 负向加 `no printed text on object`；或换无字变体（`a closed book, plain cover`） |
| 一词多义错配 | 直接填单词 | 必须先经「义项 → 视觉短语」转换层，禁止裸单词直填 |
| 同义词图雷同 | big / large / huge 都画大象 | 形容词走对比模板，且同义词共用底图后由 UI 角标区分 |
| 文化负载词失真 | 饺子生成成意大利饺 | 视觉短语中显式指定文化语境（`Chinese jiaozi dumplings on a round plate`） |
| 透明底残留白边 | 模型缺陷 | 后处理：边缘 2px 去边 + alpha 阈值清理，入库前机器校验 |

---

## 6. 生产线：变量表与工程化

### 6.1 变量维护表（示例，存为 CSV 供批量脚本读取）

| id | 类别 | 主体变量（EN） | 构图 | 义项/语境 | 输出槽位 |
|---|---|---|---|---|---|
| cov-001 | 封面 | a minimalist workspace… | centered | 开发者英语 | 16:9 2K |
| goal-001 | 目标插画·轨道A | 母题：跨海天际线 | — | 海外工作目标映射 | 16:9 2K |
| goal-002 | 目标插画·轨道B | LLM 组装的场景短语 | — | hash(目标+身份) | 16:9 2K |
| ill-001 | 空状态 | an open empty book… | — | 无收藏 | 1:1 透明 |
| voc-0001 | 单词 | a single ambulance, side view | — | 救护车（n.） | 1:1 透明 |

### 6.2 命名与入库

```
{类别}-{序号}-{slug}-v{生成批次}.png     例：voc-0001-ambulance-v1.png
```

- 每次生成都留 4 候选，选中图入库、落选图保留 30 天（重训风格锚时的对照样本）。
- 元数据落库：prompt 全文、风格锚版本号、模型版本、seed（如平台支持）、人工质检结果。与 PRD 13.6「AI 真相留存」对齐——**图和生成它的 prompt 一起存**，可复现、可追责。

### 6.3 一致性保障手段（按优先级）

1. **风格锚锁死**：本手册中的锚段落进代码库作常量，任何修改走评审并升版本号（`style-anchor-v1.1`）。
2. **同 seed 微调**：平台支持时，同系列图固定 seed 段。
3. **参考图约束**：支持垫图的平台，用首张评审通过的图作为后续生成的 reference image。
4. **批量走查**：每批 20 张并排截图评审，重点看明度、占比、色温是否跳变。

### 6.4 与其他系统的边界

- 单词图、封面在 Unit Studio / Collection 编辑器中通过「AI Generate」按钮触发（需求文档 10.7），生成任务进 AI Processing Center，遵守配额（D2）。
- 图片生成失败的 UI 表现按设计价值观 §8「AI 出错/降级」：浅黄提示 + 重试 + 手动上传入口。

---

## 7. 反模式清单（图片专属）

1. 图中出现任何文字、字母、数字、水印。
2. 插画类出现第二个高饱和彩色家族（紫+大面积亮绿/橙红同图即报废）。
3. 照片级写实风格混入插画体系（单词图可保留固有色，但仍为扁平矢量，不用照片）。
4. 人脸特写、有五官的卡通表情、吉祥物角色。
5. 霓虹发光、彩虹渐变、星空粒子——烟花元素全面禁止（设计价值观 §1.4）。
6. 复杂场景叙事（多人物多动作的剧情画面）——0.5 秒读不完的图都是失败品。
7. 单词图裸填单词（跳过义项转换层）。
8. 同一槽位频繁换风格（风格锚的修改频率应低于季度级）。
9. 用 AI 图承载信息（如把例句嵌进图里）——信息永远由 UI 文本层承担。
10. 无元数据入库的图直接上线（不可复现的图不可维护）。

---

## 8. 速查卡：四条风格锚（复制区）

**封面锚**：`Flat vector illustration, modern editorial style, soft matte texture, dominant deep violet and lavender palette (#7A68EE, #BDB0F7, #EBE7FD) with warm off-white background (#F8F8FC), one small accent of muted gold, calm and composed mood, generous negative space, clean geometric shapes, subtle grain, flat lighting`

**目标插画锚**：`Minimal geometric landscape illustration, layered flat shapes with soft depth, monochromatic violet scale from deep indigo (#312878) to pale lavender (#F4F2FE), distant layers lighter and lower contrast, crisp clean edges, no texture noise, airy negative space occupying upper half, serene and determined mood, flat design, no outlines`

**功能插画锚**：`Simple geometric spot illustration, one single object or one tiny scene, flat violet and lavender palette (#7A68EE, #BDB0F7, #EBE7FD) on transparent background, 1.5px line details, soft rounded corners everywhere, friendly but restrained, no facial expressions beyond two dots and one curve at most`

**单词图锚**：`flat vector icon illustration, centered composition, one object only filling 70% of the frame, soft violet-tinted neutral palette with natural colors slightly desaturated, clean simple shapes, rounded corners, plain background removed, educational flashcard style, instantly recognizable at small size`

**通用负向约束**：`no text, no letters, no numbers, no watermark, no logo, no signature, no realistic human face close-up, no neon glow, no rainbow gradients, no clutter, no extra unrelated objects`
