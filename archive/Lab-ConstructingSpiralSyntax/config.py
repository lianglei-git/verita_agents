"""
EGP Grammar Ordering System — Configuration
"""
import os
from dataclasses import dataclass, field
from pathlib import Path


# BASE_DIR = Path(__file__).parent
# DATA_DIR = BASE_DIR.parent.parent / "资源数据" / "dirty"
# OUTPUT_BASE_DIR = BASE_DIR / "output"

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "example"
OUTPUT_BASE_DIR = BASE_DIR / "output"

# CEFR levels supported for English EGP
CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


@dataclass
class LLMConfig:
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-reasoner"))
    temperature: float = 0.2
    max_retries: int = 3
    retry_delay: float = 2.0
    timeout: float = 1800.0
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "64000")))
    context_window: int = field(default_factory=lambda: int(os.getenv("LLM_CONTEXT_WINDOW", "128000")))
    response_preview_chars: int = field(default_factory=lambda: int(os.getenv("LLM_RESPONSE_PREVIEW_CHARS", "8000")))
    invalid_fix_input_chars: int = field(default_factory=lambda: int(os.getenv("LLM_INVALID_FIX_INPUT_CHARS", "100000")))


@dataclass
class Phase1Config:
    level: str = "A1"
    max_retries: int = 2
    output_filename_prefix: str = "score_ranking"
    
    def _read_phase0_output_prompt(self) -> str | None:
        """读取Phase 0生成的JSON prompt文件
        
        返回:
            str | None: 成功读取返回prompt内容，否则返回None
        """
        prompt_json_path = Path(__file__).parent / "output" / self.level / "prompt.json"
        if prompt_json_path.exists():
            import json
            with open(prompt_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "LearningSyllabus" in data and "finalResult" in data["LearningSyllabus"]:
                    return data["LearningSyllabus"]["finalResult"]
        return None


    @property
    def fixed_prompt(self) -> str:
#         return f"""
# 你是一位精通CEFR标准和二语习得理论的资深课程设计师。你的任务是根据提供的语法点数据，为输入的数据以及严格遵守用户的意见进行数据排序。

# 数据源
# 你将获得一个包含{self.level}级别所有语法点的数据。请严格基于数据中的知识点，**不得自行添加或删除**。如果数据中有重复或可以合并的点，请合理整合。

# 核心任务
# 用户会给你排序要求和建议，严格遵守用户的需求进行打分排序即可。

# """
        return (
            "你精通英语CEFR的设计原则以及精通语言教学，母语为中文，现在需要按照二语习得的原则为每个语法评分，"
            "最后我会根据整体数据的打分结果排序，而排序后的顺序为螺旋语法学习顺序，等价于从0到100分逐步学习该语言的学习路径。"
            "并给出打分理由。"
            "重要：打分时请使同一语法范畴（如情态、被动、时态、名词短语、从句等）的条目落在相近分数区间，以便按分数排序后形成模块连贯、减少范畴穿插的学习路径。"
        )
    
    LLM_Prompt_Score_Config = {
        "A1": """
第一阶段：基础句子构成
主语代词、be动词的肯定/否定/疑问、普通名词、专有名词、名词复数-s、冠词a/an/the、物主限定词、指示代词this（指代及未来时间）、there is/are、限定词+名词、数量限定词（a, every, some, lots of）。
第二阶段：现在时与情态动词
一般现在时（肯定/否定/习惯）、really强调、like + to不定式/动名词、宾语代词（me, you, him等）、介词后宾语代词、情态动词can（肯定/否定/疑问/能力/请求/可能性）、will（肯定/计划）、would like（邀请/愿望）。
第三阶段：进行时与过去时
现在进行时（肯定/进行中事件）、一般过去时（肯定/日常事件）、规则与不规则动词过去式。
第四阶段：介词、形容词、副词
简单介词（to, in, for等）、介词短语、时间介词+the、零冠词固定表达、形容词作定语/表语、very修饰形容词、形容词并列、best最高级、冠词+形容词+名词、名词+名词修饰、地点副词（here/there）、频率副词（always/sometimes）、程度副词（really/very much）、副词修饰动词、副词位置（句首/句中/句末）、very修饰副词。
第五阶段：连词与复合句
并列连词and/but/or连接词、短语、句子、列举、转折、原因状语because、并列句主语省略。
第六阶段：名词短语扩展及其他
名词作主语/宾语/补语/介词宾语/时间状语、复合名词、介词动词（动词+介词+宾语）、不定代词（everything, something, anything）作主语/宾语
螺旋铁律：每个语法点内部遵循"肯定→否定→疑问→扩展"小螺旋；模块之间遵循"单词→短语→简单句→并列句"大螺旋；时间轴遵循"现在→进行→过去→未来"认知顺序
""".strip(),
        "A2": """
 第一阶段：身份与存在（0-10分）
解决英语句子静态骨架，纠正中文"是"的滥用。0-5分：名词与代词精修——可数/不可数界限、所有格代词mine/yours、反身代词基础。6-10分：限定词初步规范——定冠词the与零冠词区分、指示代词these/those空间感。
第二阶段：日常惯例（11-20分）
建立时态意识，尤其是中文没有的三单变化。11-15分：一般现在时严谨化——三单形式自动化、否定与疑问句do/does补位。16-20分：频度与程度定位——always/sometimes/never句中位置（be后动前）。
第三阶段：空间与动作（21-30分）
建立英语介词思维，中文母语者长期痛点。21-25分：静态与动态介词——in/at/on扩展到across/into/through。26-30分：现在进行时当下感——动作临时性、正在发生场景描述。
第四阶段：描述与等级（31-40分）
建立英语比较逻辑，从平面描述转向立体对比。31-35分：形容词进阶用法——后缀变化、多形容词排列顺序。36-40分：比较级基础构建——er与more选择、than连接逻辑。
第五阶段：回望过去（41-50分）
扭转中文通过"了"表达、英文通过词尾表达的习惯。41-45分：一般过去时叙事——规则动词ed与最高频不规则动词。46-50分：过去时间节点——ago/last week/in 2024精准挂钩。
第六阶段：量化与可能（51-60分）
精确表达多少和把握。51-55分：量词精细区分——(a)little/(a)few情感色彩、too much/too many压力感。56-60分：初步情态语感——can/could请求语境转换、may初步接触。
第七阶段：动态延伸（61-70分）
从做过到正在做的画面切换。61-65分：过去进行时背景化——故事背景铺垫、两件事并行。66-70分：形容词最高级——最值绝对表达、the强制性。
第八阶段：意图与计划（71-80分）
分清主观打算与客观将要。71-75分：未来表达多样性——be going to打算vs will预测vs现在进行时表计划。76-80分：简单从句初探——because/if/when引导状语从句，打破简单句。
第九阶段：经验与结果（81-90分）
通往B1大门，解决截止到现在的状态。81-85分：现在完成时体验感——ever/never问经历、just/already谈完成。86-90分：动词形态束缚——哪些动词后接to do、哪些接ing。
第十阶段：逻辑高度（91-100分）
信息嵌套与视角转换。91-95分：定语从句雏形——who/which/that对人或物无缝修饰。96-100分：被动语态与引语——基本被动结构物作主语、简单说辞转述say/tell。
""".strip(),
        "B1": """
请严格按照下面逻辑进行排序，不允许你参考其他任何意见：
0-5分：基础时态巩固与扩展学习方针：复习并扩展一般现在时（心理动词、言语行为动词）、一般过去时（叙述顺序、习惯）、现在完成时（未完成、副词搭配、since/already），引入现在进行时和一般现在时表将来，为后续时态和情态动词打基础。一般现在时疑问句：Yes/No与Wh-问句的构成与应用一般现在时：心理过程动词的用法一般现在时与言语行为动词：suggest、apologise、recommend一般现在时与报告动词搭配：say、show等一般过去时肯定式：动词过去式的构成与使用一般过去时否定形式：didn't + 动词原形一般过去时：描述过去的习惯性状态或行为一般过去时：按时间顺序叙述过去事件现在完成时肯定式：基本结构与用法现在完成时否定形式：hasn't/haven't + 过去分词现在完成时与副词搭配：中位副词的正确使用现在完成时：表示最近发生的、与现在相关的事件现在完成时：表示未完成或无限期的状态或时间段现在完成时与'since'连用：表示持续时间的用法现在完成时与already连用：强调已完成动作现在进行时表示将来安排：be + V-ing现在进行时表将来：询问未来计划一般现在时表将来：与'as soon as'连用
6-10分：情态动词基础与功能学习方针：系统学习核心情态动词can, could, must, should, ought to的基本用法（能力、可能性、义务、建议、推测），掌握与副词搭配及疑问否定形式，为完成式和半情态动词铺垫。情态动词can：表达普遍真理和倾向性情态动词can与副词搭配：中位副词用法情态动词can的否定疑问句：主句否定疑问与附加疑问表达惊讶的固定短语：can you believe情态动词could：表示过去能力的肯定用法情态动词could：表示可能性情态动词could：用于提出建议情态动词could：礼貌请求许可的用法情态动词must：表示义务与必要性情态动词must：表示推测与结论的用法情态动词must：表达强烈建议的用法情态动词must的邀请用法情态动词must与副词搭配：must also/always等用法省略主语的must用法：口语和书信中的简洁表达情态动词must的省略用法：省略后续动词情态动词should：表达理想或期望的情况情态动词should：表示可能性推测情态动词should的反意疑问句：用于提出建议和征求意见情态动词ought的肯定形式：ought to情态动词ought to：用'you ought to'给出建议
11-15分：短语动词与动词模式学习方针：引入短语动词（及物/不及物、可分）和动词后接不定式、-ing、宾语+不定式、使役动词，丰富动词短语，为被动语态和从句准备。三词短语动词：动词+小品词+介词+宾语介词动词：动词+介词+宾语结构三词短语动词：动词+小品词+宾语结构短语动词+宾语代词+小品词：三词结构用法不带宾语的短语动词：hang out, run out, give up动词后接不定式：VERB + 'TO-' INFINITIVE 结构动词后接-ing形式：常见搭配与用法使役动词make和let的用法：make/let + 动词原形（不带to）动词+宾语+to不定式：请求与命令表达动词help的宾语后接不定式：带to与不带to的用法礼貌表达偏好：would prefer + to不定式
16-20分：情态动词完成式与半情态动词学习方针：学习情态动词完成式（might have, should have, would have）表达过去推测、遗憾、虚拟，以及半情态动词（used to, ought to）和be able to, be allowed to等，完成情态系统。情态动词might的过去可能性表达：might have + 过去分词情态动词might的过去肯定式：might have + 过去分词情态动词should的过去肯定式：should have + 过去分词情态动词should的过去否定式：shouldn't have + 过去分词情态动词should的过去式用法：表达遗憾与后悔叙事强调结构：you should have + 过去分词礼貌接受礼物用语：you shouldn't have (+ -ed)虚拟条件句过去否定式：would not have + 过去分词情态动词would的过去肯定式：would have + 过去分词情态动词+be able to结构：表达可能性与能力情态表达：be allowed to 表示许可BE动词短语：be allowed to, be supposed to, be able to表达过去预期的短语：be supposed to的过去式用法过去时态表达：was/were able to半情态助动词：used to与ought to的用法过去习惯表达：used to（表示过去经常做某事，现在不再如此）情态动词：used to 的肯定形式情态动词used to的否定形式：didn't use to和didn't used to
21-25分：过去完成时与过去完成进行时学习方针：学习过去完成时（“过去的过去”）和过去完成进行时（持续到过去），为第三条件句和间接引语提供时态基础。过去完成时肯定式：had + 过去分词过去完成时否定形式：had not + 过去分词过去完成时与副词搭配：never/ever/just/always/already过去完成时：表示过去某时间之前已完成的动作过去完成时在if条件句中的用法：表达对过去的假设与遗憾过去完成进行时肯定形式：had been doing过去完成进行时：描述过去背景事件过去完成进行时：描述过去某点前持续进行的动作
26-30分：被动语态基础学习方针：学习各时态被动语态形式（一般现在、一般过去、现在进行、不定式）及特殊用法（双宾语、get被动），为复杂句式打底。一般现在时被动语态：肯定句形式一般现在时被动语态否定式：is/are not + 过去分词过去时被动语态：肯定句形式被动语态在定语从句中的使用：带'by'的被动结构现在进行时被动语态肯定式：is/are being + 过去分词现在进行时被动语态表示将来：is being held, are being visited被动不定式：与going to、have to、need to、want to等搭配使用被动语态：用by强调动作执行者被动语态：双宾语动词的过去简单被动式（间接宾语作主语）被动语态：'get' + 过去分词结构
31-35分：将来时态深化学习方针：深化将来时，学习将来进行时，区分will和be going to，掌握过去将来时（was/were going to, would），为间接引语中的时态变化做准 备。将来进行时肯定式：will/shall be doing将来进行时否定形式：won't be doing一般将来时预测用法：will和'll的预测表达将来时简单式：用will表达固定计划将来时简单式：用shall表达立即计划（I/we主语）将来时否定形式：be going to 的否定句将来时态：be going to的否定形式表达意图和计划将来时be going to与副词搭配：副词在be后的位置将来时预测表达：be going to 表示预测过去将来时：be going to的过去形式过去计划表达：was/were going to过去视角谈未来：使用 'would' 表达过去对未来的预测间接引语中的过去将来时：was/were going to
36-40分：间接引语学习方针：系统学习间接引语（陈述、疑问、命令的转述），掌握时态、代词变化及直接引语位置，结合情态动词过去式（might, would）。间接引语：用say/tell+that从句转述陈述句（含代词和时态变化）间接引语：报告一般疑问句（ask + if/whether + 从句）间接引语：如何转述特殊疑问句（wh-疑问句）间接引语：用ask/tell+宾语+to不定式转述请求和命令间接引语：未来事件的转述与时态变化直接引语转述：主句在前，引语在后间接引语：直接引语后接报告动词的结构间接引语：用wonder表达疑问想法间接引语中的情态动词：might作为may的过去式间接引语中的would：作为will的过去式用法
41-45分：条件句（第一、第二）学习方针：学习第一条件句（真实可能）和第二条件句（虚拟假设），掌握unless, if so, if not等变体，为第三条件句铺垫。条件句：if + 一般现在时 + 情态动词，表达未来可能情况第一类条件句：if + 一般现在时 + will 表示可能发生的未来情况条件句：用现在进行时或'going to'表达可能计划，主句用情态动词或祈使句给出建议第二条件句：if + 过去式 + would，谈论想象情境条件从句：if + 一般过去时 + could 表达想象建议条件句中的过去简单时：if引导的假设情境条件句：'If I were you' + 'would' 表达建议或意见条件句中的例外表达：unless + 一般现在时条件从句：省略if的'If not'替代用法条件从句：省略if的'If so'用法（用于确认性提问）
46-50分：第三条件句与混合条件学习方针：学习第三条件句（if+过去完成+would have）表达过去遗憾，结合情态动词完成式，完善条件句体系。第三条件句：if + 过去完成时 + would have + 过去分词过去完成时在if条件句中的用法（复习巩固）情态动词完成式在条件句中的应用（如would have, could have等）
51-55分：比较结构基础学习方针：学习各种比较结构（同级比较、比较级+than、too...to、so...that），以及比较级的修饰词（much, a bit, even）和重复比较级，为最高级准备。比较结构：'AS … AS' 同级比较句型比较级后接'than'引导的限定性从句比较级后接than + -ing非谓语从句比较结构：'rather than' + 短语的用法比较结构：'the same' (+名词) + 'as' + 代词或名词比较结构：'too + 形容词 + to-不定式' 表示『太……而不能』结果状语从句：so + 形容词 + that 从句比较级形容词的强调用法：用‘(so) much’修饰比较级修饰语：用'a (little) bit'表示'稍微/一点儿'比较级形容词的强调用法：用 'even' 加强比较程度比较级形容词重复结构：用'and'连接表示逐渐变化比较级形容词并列：用'and'连接多个比较级形容词
56-60分：最高级与完成时学习方针：学习最高级与完成时连用（the best I have ever seen），以及最高级的扩展用法（+介词短语、不定式、one of the），丰富描述性语言。现在完成时与最高级形容词搭配：描述独特经历最高级名词短语：用现在完成时或过去完成时从句补充说明独特性比较级最高级结构：'the best (that)' + 现在完成时从句最高级搭配：'the best' + 名词 + 现在完成时最高级形容词+介词短语构成的复杂名词短语最高级结构：'the best' + 名词 + 'to-'不定式形容词最高级搭配：'one of the' + 最高级形容词 + 复数名词最高级形容词前加限定词构成名词短语
61-65分：关系从句（限定性）学习方针：学习限定性关系从句，掌握关系代词（who/that/whose）和关系副词（where/when/why）的用法，为复杂句构建提供工具。限定性关系从句：the + 名词 + who/that 强调结构关系从句：用'where'定义地点名词限定性关系从句：用'when'定义时间名词定语从句：用'why'修饰'reason'解释原因限定性关系从句：用who/that作宾语关系从句：使用'whose name'表达所属关系
66-72分：非限定性关系从句与关系副词学习方针：学习非限定性关系从句（逗号分隔），巩固关系副词，使句子表达更灵活。非限定性定语从句：用who作宾语被动语态在定语从句中的使用（复习巩固）关系从句中whose的进一步应用
73-80分：名词短语扩展学习方针：系统扩展名词短语，包括前置修饰（多个形容词、副词+形容词）、后置修饰（介词短语）、同位语、所有格特殊结构、不定代词+形容词，以及集体名词和不可数名词的用法。复杂名词短语：副词+形容词+名词结构名词短语扩展：名词+介词短语复杂名词短语：多个形容词修饰名词强调性名词短语：such (a) + 形容词 + 名词名词短语同位语：用逗号连接两个指代同一事物的名词短语复杂名词短语：名词短语 + 'of' + 所有格's + 名词短语不定代词短语：不定代词+形容词/从句名词短语：'a friend of'/'friends of' + 物主限定词 + 名词名词短语：名词 + 'of' + 物主代词所有格's省略名词：谈论熟悉的地点形容词短语：quite a + 形容词形容词短语前置修饰名词：形容词短语+名词结构普通名词的扩展使用：掌握常见名词的灵活运用集体名词的单复数动词搭配：根据语境选择is/are不可数名词的扩展使用：掌握常见抽象与物质名词不可数名词与数量限定词搭配：much, a bit of, enough, plenty of等
81-86分：代词深化学习方针：系统学习各类代词的复杂用法，包括反身代词、相互代词、指示代词回指、物主代词特殊结构、数量代词、替代词one/ones、不定代词及其修饰，以及形式主语it。单数反身代词：主语与宾语相同时的用法反身代词与by搭配：表示独自完成介词后的单数反身代词：myself, yourself, himself, herself反身代词强调用法：myself, yourself, himself, herself相互代词：each other的用法指示代词'this'：回指前文句子或从句指示代词'those'的复数用法：指代前文提到的复数名词指示代词'those'：指代已提及事物的用法指示代词'These'的复数用法：指代多个事物指示代词these：指代已提及的相关事物指示代词替代用法：this one/that one 替代可数单数名词指示代词替换：this one与that one的用法指示代词与量化限定词+of的搭配用法物主代词：表示所有关系的代词用法物主代词'yours'作主语：单数指代用法比较从句中的物主代词：mine和yours在as...as结构中的用法名词+of yours：所有格代词yours的特殊用法数量代词：both、a few、another作主语和宾语数量代词与'of'加宾语代词连用：some of them, any of us等间接疑问句中的替代词：which one代词替换：用'ones'替代已提及的复数名词代词替换：使用前置修饰语+ones进行泛指代词替代：使用限定词+前置修饰语+ones代词替代：用'the ones'后接补语指代特定事物不定代词作主语：something、nobody等与单数动词的搭配不定代词作宾语或补语：-thing、-one、-body等不定代词前置修饰语：强化表达代词'one'的泛指用法：正式语境中泛指人形式主语it：用于引出话题的虚拟主语
88-93分：连词与从句连接学习方针：学习各类连词（并列连词both...and, either...or, plus；从属连词although, as, since, so that, before/after+ing），掌握连接从句表达逻辑关系（对比、原因、目的、时间），使语篇连贯。并列连词：either … or（二选一结构）并列连词plus：连接句子表示积极补充并列连词plus：用于连接名词，常与数字相关并列连词复杂添加：and, but, or, so, then的多从句连接并列连词：both … and 连接名词短语简单从属连词：as, after, before, since, until, although, whether, so (that), though从属连词引导的对比状语从句：even though, although, while if原因状语从句：用as/since引导的从属从句目的与结果状语从句：so that, in order that时间状语从句简化：before/after + -ing形式并列从句连接：用连词组合相同类型的从句并列主句连接：叙事中的多主句组合
94-100分：副词与语篇标记学习方针：全面学习副词的各类功能（时间、地点、方式、程度、焦点、态度）和位置，掌握语篇标记词和强调结构（do强调、it强调、副词前置），提升表达准确性和语篇连贯性。时间副词与副词短语：事件时间表达方式副词及副词短语：描述动作如何发生地点副词及副词短语：near, far away, upstairs, downstairs等程度副词重复强调：really really 的用法程度副词短语：a little, a bit 与动词搭配表示程度方式副词修饰动词：描述动作如何发生副词修饰从句和句子：表达立场与态度程度副词修饰副词：副词短语的构成与用法副词短语构成：副词修饰副词连接副词：therefore、furthermore、otherwise的用法聚焦副词：particularly和especially的用法与位置副词作为语篇标记：组织文本的逻辑连接词表态副词：表达态度和观点的副词用法副词表达确定性程度：probably, certainly, definitely等副词前置：用于强调的句首位置强调句型：It + be + 形容词 + that从句陈述句中助动词'do'的强调用法强调性祈使句：do + 动词原形祈使句：用于发出邀请或提议祈使句聚焦结构：let me + 动词原形以'wh-'疑问词作主语的疑问句疑问句中的副词中位用法：主语与主要动词之间的副词位置疑问从句：使用WHICH和WHOSE的特殊疑问句感叹句结构：How + 形容词感叹句结构：How + 形容词 + 从句/短语写作语篇标记词：添加信息类（moreover, in addition, besides, what is more, furthermore）写作中的序列副词：firstly, secondly, finally等写作中的话语标记：对比类短语（如on the one hand...on the other hand）话语标记语：you see和the thing is（用于引出新信息）副词强调用法：certainly, obviously, definitely等情态动词+情态副词：弱化或强调断言礼貌请求句型：Could + 主语 + possibly + 动词原形
""".strip(),
        "B2": """
请严格按照下面逻辑进行排序，不允许你参考其他任何意见：
阶段1: 动词短语与基础动词结构 (0-10分)  
路径清单：  
- 三词短语动词：动词+小品词+介词结构（如look up to）  
- 动词与介词短语的副词插入结构：VERB + ADVERB + PREPOSITION  
- 介词动词与悬垂介词：动词+介词分离结构  
- 无宾语短语动词：die out, show up, end up等  
- 三词短语动词：动词+名词+小品词结构  
- 三词短语动词：动词+小品词+宾语结构  
- 半情态助动词：dare与need的用法  
- 动词后接新主语加-ing形式：mind/stand/imagine等动词的特殊用法  
- 动词后接to不定式或-ing形式的用法区别  
- 动词后接-ing形式：常见搭配与用法  
- 感官动词 + 宾语 + '-ing'形式：强调进行中的活动  
- there与情态动词搭配：there + 情态动词 + be + 补语  
- 系动词+补语结构：描述状态与特征  
学习方针：掌握各种动词短语的构成和词序，区分及物与不及物用法，理解感官动词和系动词的搭配，为后续复杂时态和情态打下基础。  

阶段2: 现在时态与过去时态的深化 (10-20分)  
路径清单：  
- 现在进行时搭配不定频率副词：表达持续或频繁行为  
- 倒装结构：not only … but also 的现在简单式用法  
- 一般现在时：用于故事和历史事件总结  
- 一般现在时与言语行为动词：表达观点、建议与回应  
- 过去进行时与副词搭配：中位副词用法详解  
- 过去进行时：用于礼貌请求或建议  
- 过去时一般疑问句：yes/no、wh-、附加与否定问句  
- 一般过去时否定形式：didn't + 动词原形  
- 过去简单时与从属连词的搭配使用  
- 一般过去时：与时间状语搭配使用  
- 过去式礼貌表达：用I wondered和I wanted进行礼貌请求与感谢  
- 过去式在'if'后的礼貌用法：书信邮件中的委婉表达  
学习方针：通过时间状语和语境，准确使用不同过去时态，掌握礼貌表达，注意现在时在叙述中的特殊用法。  

阶段3: 完成时态的基本形式与用法 (20-30分)  
路径清单：  
- 现在完成进行时与副词搭配：中位副词的使用  
- 现在完成进行时否定形式：have/has not been doing  
- 现在完成进行时：强调近期已完成活动的影响  
- 现在完成时疑问句：如何正确提问  
- 现在完成时否定式与still连用：强调预期未发生之事  
- 过去完成进行时否定形式：had not been doing  
- 过去完成进行时：时间连词后的背景信息描述  
- 过去完成进行时在关系从句中提供背景信息  
- 过去完成进行时：强调过去某时之前持续动作的结果或影响  
- 过去完成进行时与副词搭配：副词在句中位置的使用  
- 过去完成时在because后解释原因  
- 过去完成时在'if only'和'wish'后的用法：表达遗憾与想象  
- 过去完成时与副词搭配：finally, recently, simply等副词的中位用法  
- 过去完成时疑问句：had + 主语 + 过去分词  
- 过去完成时主语省略：在从句中省略已明确的主语  
- 过去完成时：描述情况变化的用法  
学习方针：理解完成时态的“过去与现在联系”和“过去某时之前完成”的概念，掌握时间状语和副词的搭配，学会用完成时表达遗憾和结果。  

阶段4: 将来时态与未来表达 (30-40分)  
路径清单：  
- 将来进行时礼貌问句：will be doing 的委婉用法  
- 将来进行时疑问句：will be doing的疑问形式  
- 将来时表达：be about to 结构  
- 未来表达：用be due to和be to谈论预定或预期事件  
- 将来时表达：be to 结构  
- 未来表达：用be to表示义务和指令  
- 将来时表达：用be about to表示即将发生的动作  
- 未来表达：be due to 结构  
- 将来完成进行时否定形式：will not have been doing  
- 将来完成进行时肯定式：will have been doing  
- 过去将来时态：be on the point of + -ing 结构  
- 过去将来时：be about to 的过去式用法  
- 将来完成进行时：从未来某点回顾过去并强调持续时间  
- 将来完成时肯定式：will have + 过去分词  
- 将来完成时否定形式：will not have + 过去分词  
- 将来完成时：will have + 过去分词  
- 现在进行时表将来安排：be + V-ing 表示已确定的未来计划  
- 现在进行时表将来：询问未来计划  
学习方针：区分不同将来表达法的语用功能，掌握将来完成时和将来完成进行时的构成，学会用现在进行时谈论未来安排。  

阶段5: 情态动词的深度用法 (40-50分)  
路径清单：  
- 情态动词can与副词搭配：中位副词用法  
- 情态动词can：表达普遍真理和一般倾向  
- 情态动词can的否定形式：用于猜测、预测和推断  
- 情态动词can的否定形式：表达责备与劝诫  
- 情态动词dare的否定形式：dare not/daren't + 不带to的不定式  
- 情态动词dare的肯定形式：dare + 不带to的不定式  
- 半情态动词dare：表达勇气与胆量  
- BE+不定式表达：可能性与义务的固定搭配  
- 表达理想状态的短语：be meant to  
- 表达预定与预期的结构：be due to 与 be to  
- 表达可能性的结构：be likely to  
- 比较可能性表达：be more/less likely  
- 情态表达：be supposed to 表示传闻或推测  
- 表达必然性的短语：be bound to  
- BE + 形容词 + THAT 从句：表达确定性或可能性  
- 情态表达：be supposed to 的用法（义务与期望）  
- 祈使句表达义务：be sure to  
- 表达确定性的短语：be sure to / be certain to  
- 被动义务表达：be forced to 的用法  
- 表达外部义务的短语：be obliged to  
- 情态动词have (got) to：表达强烈建议的用法  
- 情态动词may与副词搭配：even、only、already等副词的中位用法  
- 情态动词may的礼貌请求用法：May I...  
- 情态动词may的过去肯定式：may have + 过去分词  
- 情态动词may的礼貌请求用法：may I  
- 情态动词may的聚焦用法：as you may know/have + -ed  
- 情态动词may的转折用法：may … but表达意外观点  
- 情态动词must的疑问句形式：如何正确提问  
- 情态动词must的过去肯定式：must have + 过去分词  
- 强调性固定表达：I must say  
- 情态动词must与副词搭配：must + 副词结构  
- 情态动词must：询问义务与必要性  
- 情态动词must的完成式：表示对过去的推测与结论  
- 让步表达：固定短语 'I must admit' 和 'you must admit'  
- 情态动词must的否定形式：表示禁止或不允许  
- 情态动词ought to的省略用法：省略后续动词  
- 情态动词needn't：表达无义务或没必要  
- 情态动词need的否定形式：needn't与need not  
- 情态动词ought to：表达理想状态与应然之事  
- 情态动词should的省略用法：省略后续动词  
- 情态动词should的进行时态：should be + -ing  
- 情态动词should：表示当前一般义务的进行时态用法  
- 情态动词should的进行时态：表达预期与推测  
- used to的省略用法：省略后续动词的惯用表达  
- 情态动词will的请求用法：Will you please...  
- 情态动词would：描述过去的习惯性动作  
- 情态动词could的过去推测用法：could have + 过去分词  
- 情态动词could + have + 过去分词：表达过去可能性  
- 情态动词could：表达遗憾的could have + -ed结构  
- 情态动词could的过去推测用法：could have + 过去分词  
- 间接引语中could作为can的过去式用法  
学习方针：系统学习各类情态动词的多种用法，包括推测、义务、请求、建议、遗憾等，重点掌握情态动词+完成式表示过去意义，以及情态动词在间接引语中的变化。  

阶段6: 被动语态全览 (50-60分)  
路径清单：  
- 被动不定式：肯定与否定形式  
- 过去完成时被动语态肯定式：had been + 过去分词  
- 情态动词+现在完成时被动语态：could have been done  
- 过去进行时被动语态肯定式  
- 一般过去时被动语态否定式：was/were not + 过去分词  
- 过去完成时被动语态否定形式：had not been + 过去分词  
- 现在进行时被动语态：肯定句形式  
- 现在进行时被动语态否定式：are/is not being + 过去分词  
- 现在完成时被动语态肯定式：用于报告和转述  
- 情态动词被动语态：用于总结与评价  
- 被动语态：双宾语动词的被动形式（直接宾语作主语）  
- 被动语态与will连用：表达未来事件  
- 情态动词被动语态：should be done, could be improved  
- 双宾语动词的被动语态：间接宾语作主语  
- 现在完成时被动语态否定形式：has/have not been + 过去分词  
- 主动/被动表达：have + 宾语 + -ed 结构  
- 被动语态：'get' + 反身代词 + '-ed' 结构  
- 使役结构：get + 宾语 + to-不定式  
学习方针：掌握各种时态和情态动词的被动形式，区分直接宾语和间接宾语作主语的不同，理解have/get + 宾语 + 过去分词的使役用法。  

阶段7: 间接引语与转述技巧 (60-70分)  
路径清单：  
- 间接引语中修饰转述动词的副词用法  
- 间接引语：报告动词位于引语中间位置  
- 间接引语：主语与动词倒装（专有名词/名词短语作主语）  
- 间接引语：用过去进行时报告心理活动（含wh-从句）  
- 转述书面信息：使用现在时态动词的间接引语  
- 间接引语：用ask/tell+宾语+not+to不定式转述否定请求和命令  
- 间接引语：过去时态的时间回溯与时态转换  
- 祈使句附加疑问句：用疑问尾句软化命令语气  
- wh-疑问句的否定形式：用助动词do构成  
学习方针：掌握直接引语转间接引语时的时态后退、人称变化、时间状语调整，学会转述不同句型（陈述、疑问、祈使），注意转述动词的位置和倒装。  

阶段8: 代词的精细化用法 (70-80分)  
路径清单：  
- 物主代词'ours'作宾语和补语：单复数指代与位置用法  
- 比较从句中的物主代词：hers和ours的用法  
- 名词后接“of ours”的所有格代词用法  
- 物主代词'ours'作主语：单复数指代用法  
- 物主代词hers作宾语和补语：单数指代用法详解  
- 物主代词'theirs'作宾语和补语用法  
- 反身代词与'by'连用：表示'独自、无需帮助'  
- 反身代词yourselves的礼貌用法  
- 反身代词强调用法：itself的强调功能  
- 介词后使用复数反身代词：当介词宾语与动词主语相同时  
- 复数反身代词：主语与宾语相同时的用法  
- 复数反身代词用于强调：ourselves, yourselves, themselves  
- 反身代词搭配：by itself 表示“独自/自动”  
- 反身代词固定表达：'in itself'作为强调用法  
- 代词it作宾语：用it引入后续内容的结构  
- 非正式语境中省略主语代词  
- 通用人称代词：主语位置上的'one'  
- 形式主语it搭配感官动词：appears、feels、looks、seems  
- 指示代词'those'的替代用法：后接关系从句或分词结构  
- 指示代词复数替代：these ones/those ones的用法  
- 数量代词作主语和宾语：each, several, neither, enough  
- 代词与'of'结构：neither/either/none + of + 宾语代词  
- 不定代词与关系从句：用something/anything/everything等构建强调性名词短语  
- 不定代词作主语：everything、nothing、everybody等与单数动词的搭配  
- 不定代词在模糊表达中的用法：-thing、-one、-body等  
- 代词泛指用法：用'we'和'us'指代一般人  
- 不定代词回指：they/them的性别中立用法  
- 性别中性单数名词回指：he/she、he、she、they的通用用法  
- 相互代词：one another（正式场合用法）  
学习方针：掌握各类代词在句子中的位置和功能，注意所有格、反身、不定代词的用法细节，学会用代词避免重复，理解性别中性的表达方式。  

阶段9: 名词短语、限定词与形容词 (80-90分)  
路径清单：  
- 复数名词所有格：复数名词 + ' + 名词  
- 名词短语：名词 + 'of' + 物主限定词 + 名词 + '’s' 结构  
- 名词短语后置修饰：形容词短语作后置定语  
- 复杂名词短语：用'but'连接多个形容词  
- 动词-ing形式作主语：动名词主语用法  
- 不可数名词泛指抽象概念：无冠词用法  
- 否定词'not'的非缩写形式：强调与正式用法  
- 否定表达：'neither of'与'none of' + 代词/名词短语  
- 否定连接结构：neither … nor  
- 否定副词'never'前置倒装结构：强调表达  
- 形式主语结构：It + 系动词 + 形容词 + (that)从句  
- 间接断言句型：It + 系动词 + 形容词 + (that)从句  
- 强调句型：It + 系动词 + 形容词 + (that)从句  
- 形容词+to不定式结构：表达可能性与确定性  
- 所有格结构：of + 名词短语 + 's  
- 复数名词所有格：复数名词加's'表示所属关系  
- 物主代词their的泛指用法：用于单数主语的泛指人群  
- 物主限定词：its的用法  
- 数量限定词：little/few的修饰用法  
- 并列连词：both … and 用于连接短语和从句  
- 并列连词：neither … nor 的用法  
- 复杂从属连词：as long as, as soon as, in order that, despite the fact that, due to the fact that, as if, as though  
- 简单从属连词：once, whereas, unless, except (that), provided (that)  
- 比较结构：'the same' (+名词) + 'as' + 从句  
- 形容词+enough+to不定式：表示“足够...去做...”的结构  
- 最高级形容词+that从句：描述独特事物的表达方式  
- 比较级形容词+than+非谓语从句：高级比较结构  
- 比较结构：'rather than' + 非谓语从句  
- 比较从句：'as if' 或 'as though' + 限定从句  
- 并列否定结构：neither ... nor 的强调用法  
- 并列从句结构：not only … but (also) 强调用法  
- 建议性否定祈使句：Let's not + 动词原形  
- 强调性否定祈使句：'Do not' 的正式与强调用法  
- 否定疑问句+副词中位结构：如“Why don't you ever listen?”  
- 否定疑问句表达惊喜或热情：Wouldn't it be wonderful!  
- 关系从句：介词结尾的限定性与非限定性从句  
- 非限定性定语从句：使用'whose'补充信息  
- 限定性关系从句：使用'whose'表示所属关系  
- 关系从句：用于评价或说明整个句子  
- 非谓语从句：'after having/being + -ed' 表示过去时间  
- 条件状语从句：使用unless、provided等连词引导  
- 非限定性-ing从句：主句前表补充信息  
- 条件状语从句：使用as long as/provided等连词+现在时表将来条件  
- 方式副词：修饰动作发生的方式  
- 时间副词与副词短语：事件时间表达  
- 程度副词修饰限定词：almost、very等  
- 程度副词修饰名词短语：quite a, rather a, almost a  
- 副词位置：never前置倒装句  
- 副词短语的比较级结构：如何用比较级修饰副词  
- 复合形容词：up-to-date、state-of-the-art等组合用法  
- 形容词短语修饰名词：用短语丰富名词描述  
- 比较级修饰词：用'slightly'表示轻微程度  
- 比较级形容词的强化修饰：使用'a lot'  
- 形容词比较级强化修饰：用'much'修饰名词前的比较级形容词  
- 形容词后接enough加to不定式：表达足够程度做某事  
- 形容词短语：rather a + 形容词  
- 限定性时间形容词：present、future、former的定语用法  
- 程度形容词前置：real、absolute、complete在名词前的强调用法  
- 形容词最高级强化表达：使用'by far'  
- 最高级形容词省略名词：使用'(one of) the'结构  
- 最高级形容词 + 名词 + 'to-'不定式：表达最佳方式的句型  
学习方针：综合运用名词短语的修饰、限定词、形容词比较级和最高级，掌握各种从句（定语、状语、名词性）的构成和功能，学习倒装、强调等高级句式，提升表达的准确性和丰富性。  

阶段10: 高级句式与语篇衔接 (90-100分)  
路径清单：  
- 焦点强调句型：The thing/fact/point/problem/reason is (that)  
- 焦点结构：'The reason (that)'和'The place (which)'引导的从句作主语  
- 书面语篇标记：用于比较的短语  
- 书面语篇标记：总结性正式表达  
- 书面语篇标记语：开头、结尾与结论引导词（正式语境）  
- 比较级结构：the more … the more …  
学习方针：学习使用语篇标记组织文章，掌握焦点结构突出重点，运用复杂比较级表达相互关系，提升写作和口语的逻辑性和连贯性。

""".strip(),
        "C1": """
C1 语法螺旋式学习路径（整合版）
阶段 1：夯实高阶语感——复杂动词短语与基础语用（0-10分）
骨架名称：让表达更地道、更委婉

学习方针： 从C1级别最实用的动词短语和疑问句式切入。学习如何通过结构的变化（如介词悬空、代词位置）使表达更自然，如何通过疑问句的变体（如省略、极端对比）来实现委婉、强调等语用目的，为高阶表达打下坚实的语感基础。

路径清单：

三词短语动词：动词+小品词+介词
三词短语动词：动词+代词宾语+小品词
感官动词 + 宾语 + 不带to的不定式
省略情态动词的替代疑问句（委婉表达）
强对比选择疑问句（增强语效）
存在句反意疑问句（there be + tag）
wh-疑问句作为焦点强调手段
物主代词'ours'作主语
形式主语'it'与被动语态的搭配
正式所有格：that of / those of
阶段 2：精准确认与否定——代词与否定词的高级用法（10-20分）
骨架名称：让指代更清晰，让否定更精确

学习方针： 在代词和否定这两个基础语法点上进行深化。学习如何使用复杂的代词结构（如相互代词、后置修饰）来精确指代，以及如何使用部分否定、强调性否定词来微妙地表达立场，提升语言的精确度和逻辑性。

路径清单：

否定代词 'none' 的综合用法（替代主语/宾语）
数量代词指代人：few / many / most / others
关系代词修饰：some of / many of + which/whom
数量代词的强化：very / too / so + few/many
不定代词anything的省略从句用法
不定代词anything的后置修饰（作主语）
相互代词：'each ... the other(s)' 作介词补语
否定强调词：whatsoever
部分否定：not all / not every / not everyone
阶段 3：驾驭时间——过去时态的深度叙事与语用（20-30分）
骨架名称：让叙事有层次，让表达有温度

学习方针： 聚焦过去时态。学习如何通过倒装、强调结构（did）来增强叙事的戏剧性，如何使用过去时（I thought）来实现礼貌，以及如何通过情态动词+have done来表达对过去的推测与批评。这是在时间线上叠加情感和逻辑的关键一步。

路径清单：

过去完成时倒装（表达遗憾）
过去时倒装：Not only … but also
过去时强调：用'did'加强语气
过去时复杂疑问句（yes/no, wh-, 反意）
过去时复杂事件排序（after, before等）
礼貌表达：I thought...（委婉）
现在完成时否定式（正式语境）
情态动词的过去推测：can't/couldn't have done
情态动词的过去推测：may/might not have done
阶段 4：掌控情态——情态动词的推测、批评与修辞（30-40分）
骨架名称：让语气更精准，让观点更多维

学习方针： 系统整合情态动词的多种高阶功能，超越“可能性”的基础认知。学习如何用情态动词进行强调（as you can see）、表达强烈情感（how dare）、进行礼貌批评（might I suggest）以及巧妙辩解（might...but）。这是让语言“活”起来的关键。

路径清单：

情态动词can与副词搭配（can fully understand）
情态动词can的强调表达（as you can see, I can tell you）
情态动词can的被动报告从句（It can be argued that）
固定表达：I dare say
情态动词dare的疑问句
情态动词短语：how dare ...!
情态动词might的疑问句（委婉建议）
情态动词might的礼貌批评（Might I suggest...）
情态动词的辩解结构：might...but
阶段 5：客观与使役——被动语态与非谓语结构的进阶（40-50分）
骨架名称：让写作更正式，让表达更简洁

学习方针： 学习如何用被动语态和非谓语动词来构建信息密度高、结构紧凑的句子。被动语态从“形式”转向“功能”（如总结评价），使役结构从have/get转向更复杂的表达，为学术和商务写作做准备。

路径清单：

被动非谓语-ing形式作背景信息（Being born...）
现在进行时被动语态否定式（is not being done）
被动语态：形式主语it作总结评价（It can be concluded that）
非正式使役：get + 宾语 + -ed（get it repaired）
使役结构：get + 宾语 + -ing（get things moving）
非谓语-ed从句前置（Compared to..., Given...）
非谓语从句：'not' + '-ing'（Not knowing...）
条件句中的非谓语：if + -ed（if needed）
省略if的条件从句：if + -ed（if requested）
阶段 6：概念化与抽象化——名词短语的复杂化（50-60分）
骨架名称：让思想更深刻，让语言更凝练

学习方针： 学习如何用名词化的方式来表达复杂概念。这包括使用所有格省略、名词化短语（如with reference to）、动名词作主语、以及抽象不可数名词。这是C1级别从“说事”到“论理”的关键跨越。

路径清单：

名词短语：省略名词的所有格's（than our competitors'）
名词化结构（with reference to, an increase in）
'wh-' 分裂句作名词短语（What we need is...）
动词-ing形式作抽象名词（Learning, Advertising）
抽象概念不可数名词（safety, tolerance, humanity）
复合形容词（open-minded, above-mentioned）
过去分词作后置形容词（the films shown）
最高级强化：最高级 + possible + 名词
最高级强化：最高级 + 名词 + possible/ever
阶段 7：组织信息——焦点结构与语篇连贯（60-70分）
骨架名称：让重点更突出，让行文更流畅
学习方针： 从“句子”层面上升
表允许/指令
祈使句+and条件句（See one and you'll...）
阶段 8：构建逻辑——复杂条件句与虚拟倒装（70-80分）
骨架名称：让假设更严谨，让论证更有力
学习方针： 深入学习条件句的各种复杂形式，尤其是倒装和虚拟语气。这是进行严谨论证、表达遗憾、提出正式建议的高级工具，能极大提升语言的正式程度和逻辑力量。
路径清单：
过去虚拟条件句（if + had done, ... would have done）
正式礼貌条件句：'if you should'
条件从句倒装：'Should' 引导的虚拟条件句
正式倒装条件从句：Should/Had/Were + 主语...
情态动词ought to表理想状态（There ought to be）
情态动词ought to的强调（really ought to）
情态动词ought to表可能性
情态动词ought to的过去式（ought to have done）
阶段 9：规划未来——将来时态的高级表达（80-90分）
骨架名称：让预测更丰富，让计划更周全
学习方针： 集中学习将来时的各种复杂形式及其语用功能。从be going to与副词的搭配，到将来完成时的推测与礼貌用法，再到shall在正式文本中的独特作用，全方位提升谈论未来的能力。
路径清单：
将来进行时与情态动词（might/may be doing）
将来完成时与副词（will have probably done）
将来完成时表对现在的推测（As you will have heard）
将来完成时作礼貌策略（I hope I will have...）
将来时否定形式：shall not（正式）
be going to与确定性副词（is undoubtedly going to）
一般现在时表将来：与'by the time'连用
现在时表将来：建议/义务动词后的从句（suggest that...）
情态动词will表典型/习惯行为（will usually...）
阶段 10：精准修饰与修辞——副词与限定词的极致运用（90-100分）
骨架名称：让修饰更精准，让语言更生动
学习方针： 最后阶段，聚焦于语言的精雕细琢。学习如何使用副词表达微妙的立场和程度差异，如何使用夸张的限定词（tons of）来增强表达效果。这是从“准确表达”到“精彩表达”的最后一跃。
路径清单：
副词表达确定性程度（probably, undoubtedly）
立场副词表达态度（Frankly, Apparently, Luckily）
副词修饰形容词表程度（completely different）
程度副词修饰比较级（slightly more, much better）
程度副词修饰其他副词（incredibly fast）
副词短语：副词+enough表强调（Surprisingly enough）
副词修饰副词（extremely rapidly）
副词后置修饰+介词短语（Luckily for me...）
副词短语短回应：Not necessarily
夸张表达中的数量限定词（millions of, loads of）
""".strip(),
        "C2": """
设计思路是：

基础优先：从最核心、最常用的句子结构和动词短语开始。

代词与焦点：代词是连接句子的关键，之后自然引入如何突出重点信息。

时态深化：从最熟悉的时态入手，逐步扩展到其更高级、更微妙的用法。

情态与语态深化：在掌握基本时态后，深入探讨情态动词和语态的高级表达。

从句与连接：学习如何构建更复杂的句子，连接思想。

描述与修饰：最后聚焦于如何用形容词和副词使语言更精确、生动。

循环巩固：在每个阶段中，会不同程度地融入之前学过的语法点，实现循环巩固。

请严格按照下面逻辑进行排序，不允许你参考其他任何意见：

阶段 1：基础句型与动词短语 (进度 0-10分)
骨架名称: 构建复杂句子的基石

路径清单:

三词短语动词：动词+直接宾语+小品词+介词+介词宾语
情态动词短语：would hate + to不定式（强调用法）
使役结构：have + 宾语 + 动词原形（不带to）
祈使句：'let' + 第三人称代词 + 动词原形（转移责任用法）
强调型祈使句：'Don't you ...' 结构
学习方针：本阶段聚焦于构建C2级别的核心句子骨架。从最实用的三词短语动词入手，学习如何将多个成分自然地组合在一起。接着，掌握表达强烈情感和使役关系的固定结构，并通过祈使句的高级形式（转移责任和强调）来丰富你的命令和建议表达方式，为后续学习打下坚实的句型基础。

阶段 2：代词的深度与广度 (进度 10-20分)
骨架名称: 指代的精确性与灵活性

路径清单:

物主代词'his'的全面用法：单复数指代与多位置应用
物主代词'theirs'作主语：单复数指代与用法详解
物主代词'hers'作主语：单数指代与主语位置用法
名词+of+物主代词：hers/theirs/his的用法
表达态度结构：that ... of + 物主代词
相互代词结构：each ... the other(s) 作宾语
数量代词作主语：'a lot'与'much'的用法
学习方针：代词是避免重复、连接上下文的关键。本阶段将带你超越基础的所有格，全面掌握his、theirs、hers在句中任何位置（主语、宾语、补语）的用法。随后，学习名词+of+物主代词和that ... of + 物主代词这两个高级结构，前者用于客观描述，后者则能精妙地表达幽默或讽刺等主观态度。最后，引入相互代词和数量代词作主语，让你在指代人和事物时更加游刃有余。

阶段 3：聚焦与强调 (进度 20-30分)
骨架名称: 让重点信息脱颖而出

路径清单:

强调主语的it分裂句结构
强调结构：'The one(s) that' + 从句作主语
WH-分裂句：How/Why/Where引导的强调结构
强调句型：The + 修饰语 + 名词 + is (that) 结构
前置多重固定表达：增强句子焦点
指示词'this'在叙事中的运用：营造即时感
指示代词that/those的情感距离用法：表达不赞同或疏远
学习方针：C2水平要求你能精准地控制信息的焦点。本阶段将系统性地学习各种强调句型，从最经典的it分裂句，到可以强调任何成分的wh-分裂句，再到用于总结观点的The thing is...结构。你还会学习如何通过前置多个短语和巧妙使用this/that来引导读者的注意力或表达你的个人立场，让你的叙述重点突出、富有层次感。

阶段 4：过去时态的高级用法 (进度 30-40分)
骨架名称: 时间的精准回溯与情感表达

路径清单:

过去进行时搭配always/constantly表达不受欢迎或失控的重复事件
过去完成进行时疑问句：had been doing
过去完成时固定表达：'had it not been for'与'if it hadn't been for'
过去完成时在'if only'后的否定形式：表达遗憾
过去完成时倒装结构：hardly … when
现在完成时简单式：新闻引入用法
叙事背景构建：'as' + 代词 + 'used to' 结构
过去时态中的未来安排：be due to 的过去式用法
学习方针：在熟悉基础时态后，本阶段带你探索过去时态的“情感维度”。你将学会用过去进行时 + always来表达不满，用if only + 过去完成时来抒发遗憾，用hardly...when的倒装结构来生动描述接连发生的事件。同时，学习如何用现在完成时引入新话题，以及用as...used to和was due to来构建叙事的背景和“过去的未来”，让你的时间叙述精准而富有情感。

阶段 5：否定艺术的进阶 (进度 40-45分)
骨架名称: 否定中的强调与修辞

路径清单:

否定疑问句：使用未缩写的'not'进行强调
复杂名词短语：'little or no' + 名词结构
强调否定结构：'not a' + 名词 + 被动语态
否定祈使句警告用法：Don't you...
否定结构：Neither/Nor + do/be + 倒装主语
否定强调短语：'in the least'的用法
强调否定结构：'Not a' + 名词 + 被动动词/倒装结构
学习方针：否定不仅仅是加个not。本阶段将教会你如何用否定来达到强调、警告和修辞的效果。学习用未缩写的not在正式辩论中加强语气，用little or no和not a构成强烈否定，以及用Neither/Nor引导倒装句来追加否定信息。掌握in the least等短语，让你的否定表达更加细腻、有力。

阶段 6：情态动词的微妙世界 (进度 45-60分)
骨架名称: 语气、推测与态度的精确表达

路径清单:

修辞性疑问句：how can 用于反思与质疑
情态动词dare的否定形式：didn't dare + 不带to的不定式
情态动词have to的推论与结论用法
情态动词have to的过去形式：have to have + 过去分词
情态动词短语：may as well / might as well（不妨/干脆）
学术写作中的缓和表达：it may be + 过去分词 + that 从句
让步从句中的may：与however/whatever/whoever等连用
情态动词must的过去否定形式：must not have been
情态动词must的倒装用法：与否定短语连用强调
情态动词need的疑问句形式：Need you...?
情态动词ought的否定缩略形式：oughtn't + 动词原形
情态动词ought的否定形式：ought not to
情态动词would与副词搭配：高级表达方式
副词表达确定性：简短回应用法
推测过去不可能发生的事：couldn't have + 过去分词
学习方针：情态动词是C2级别的核心难点。本阶段我们将把情态动词拆解成一个一个的“微技能”来学习。从表达反思的how can，到表达无奈选择的may/might as well，再到学术写作中表达谨慎的it may be argued that。你还会学习must的否定推测must not have been、need的修辞问句、ought的否定形式，以及would与丰富副词的搭配。最终，你将能精确地表达可能性、必要性、意愿、推测等任何微妙的语气。

阶段 7：被动语态与非谓语动词 (进度 60-65分)
骨架名称: 客观叙述与信息重组

路径清单:

被动非限定完成式-ing从句：用于解释背景信息
被动语态非谓语完成式作介词补语：having been + 过去分词
现在完成进行时被动语态：形式与用法详解
学习方针：被动语态在正式写作和客观叙述中至关重要。本阶段将带你超越简单的be + done，深入到非谓语动词的被动完成式，如having been educated。你将学会如何用这些结构作为背景信息或介词补语，使句子信息密度更高、逻辑更严谨。同时，挑战一个极高级的时态——现在完成进行时的被动语态，看看它在实际中是如何运用的。

阶段 8：未来时间框架 (进度 65-70分)
骨架名称: 预测、意图与假设

路径清单:

将来完成进行时：基于假设推测现在情况
将来完成时疑问句：Will he have changed?
用shall表达长期意图：高级用法详解
正式语境下的预测用法：shall 表示预测
将来时be going to结构：与副词连用的灵活表达
倒装结构：'only when'引导的现在简单式表将来
学习方针：本阶段聚焦于未来的高级表达。学习如何用将来完成进行时从现在的角度推测过去一直在进行的动作。掌握shall在正式语境中表达庄重的个人承诺和预测。探索be going to与副词灵活搭配的多种可能性。最后，学习用only when引导的时间状语从句搭配倒装主句，来表达未来事件发生的唯一条件。

阶段 9：复杂条件句与虚拟语气 (进度 70-80分)
骨架名称: 假设、条件与逻辑推演

路径清单:

倒装过去完成时：表达对过去情况的虚拟假设
倒装式'Should'条件句：表达未来可能性与礼貌请求
正式条件句：Were it not for + 名词短语
正式条件句：倒装were + to不定式
条件状语从句：使用so long as/on condition that/in the event that等从属连词
正式条件句：If it weren't/were not for + 名词短语
正式条件句：If it were + to不定式
正式语境条件从句：whether or not 的用法
学习方针：C2级别的逻辑思维需要同样复杂的条件句来表达。本阶段将系统学习所有高级条件句形式，重点是它们的倒装结构（Had I known..., Should you need..., Were it not for...）和正式连接词（so long as, on condition that）。你将学会如何用这些结构优雅、正式地讨论假设、条件和可能的结果，使你的论证滴水不漏。

阶段 10：从句的融合与简化 (进度 80-90分)
骨架名称: 思想的精妙连接与简化

路径清单:

从属连词：'in that'的深入解释用法
并列连词：'And yet' 的让步对比用法
并列连词倒装结构：Neither/Nor + 助动词/be动词 + 主语
否定句与倒装句的nor连接：强调结构
感叹句结构：'How' + 从句 / 'How' + 副词 + 从句
选择疑问句：多从句省略结构
比较从句：'as if' + 非限定从句
从属连词后接非谓语从句：although/though + 非谓语结构
学习方针：本阶段教你如何让句子之间的逻辑关系更紧密、表达更精炼。学习用in that提供深度解释，用And yet制造意外转折，用nor引导倒装句追加否定信息。你还会掌握如何将从句简化为非谓语形式（如as if to..., although married...），使句子结构更紧凑。同时，感叹句和省略问句能让你的语言在书面和口头都更具表现力。

阶段 11：修饰的艺术：形容词与副词 (进度 90-100分)
骨架名称: 语言的色彩与精准度

路径清单:

副词中位用法：表达距离感的写作技巧
副词hardly前置倒装结构：强调“刚……就……”
副词短语的修饰结构：前置修饰语与后置补足语
形容词列表在省略从句中的聚焦用法：名词前后的省略结构
复杂形容词串组合：用'and'连接最后两个形容词
比较级与否定词搭配：'no'/'not any' + 比较级形容词
比较级修饰语：not that much 的用法
形容词比较结构：as...as与so...that的用法
程度形容词前置：在名词前使用形容词表达强度
最高级否定表达：the slightest/the faintest 的用法
学习方针：最后的阶段，我们将聚焦于如何让你的语言更精确、生动、有风格。学会用副词（如supposedly）巧妙地与所述内容保持距离。掌握hardly的倒装句来增强叙事的戏剧性。学习如何堆叠复杂形容词串来描绘细腻的人物或事物，并精确控制比较的程度（no higher than, not that much older）。最终，用the slightest idea等最高级否定表达来达到强烈的修辞效果，让你的英语表达臻于完美
""".strip(),
    }

    @property
    def score_prompt(self) -> str:
        content = self._read_phase0_output_prompt()
        if content is None:
            print(f"[ERROR] 无法读取Phase 0生成的prompt文件，请执行Phase 0后重试。")
            exit()
        return content.strip()


@dataclass
class Phase2Config:
    vote_threshold: float = 0.5
    rank_window: int = 15
    auto_edge_threshold: int = 35
    # Cross-supercat auto edges require rank_diff > auto_edge_threshold * this multiplier.
    # Same-supercat edges still use auto_edge_threshold.
    # Set to 1.0 to treat all categories the same as before.
    cross_cat_auto_multiplier: float = 2.5


@dataclass
class Phase3Config:
    level: str = "A1"              # CEFR 级别（由 get_config 注入）
    llm_validate: bool = True      # 是否运行 LLM 复杂度评分校验
    score_batch_size: int = 25     # 每批送 LLM 的条目数
    inversion_threshold: float = 2.0  # 判定"逆序嫌疑"的分数差阈值
    # Step 3 — Cluster compaction
    # Same-layer items more than this many positions apart trigger a compaction attempt.
    # Lower = tighter clusters; 0 = disabled.
    cluster_gap_threshold: int = 15
    # Maximum positions an item may be moved FORWARD (earlier) by compaction.
    # Prevents meta-concept items (e.g. "MODAL AUXILIARY VERBS") from being dragged
    # to the very beginning just because another item in the same broad category is there.
    cluster_max_forward_move: int = 30


@dataclass
class AppConfig:
    level: str = "A1"
    lang: str = "en"
    llm: LLMConfig = field(default_factory=LLMConfig)
    phase1: Phase1Config = field(default_factory=Phase1Config)
    egp_csv_path: Path = field(default_factory=lambda: DATA_DIR / "egp_A1.csv")
    output_dir: Path = field(default_factory=lambda: OUTPUT_BASE_DIR / "A1")


def _csv_path(level: str, lang: str) -> Path:
    """
    CSV naming convention:
      English  : egp_{level}.csv        (e.g. egp_A1.csv)
      Others   : egp_{lang}_{level}.csv (e.g. egp_fr_A1.csv)
    """
    if lang == "en":
        return DATA_DIR / f"egp_{level}.csv"
    return DATA_DIR / f"egp_{lang}_{level}.csv"


def get_config(level: str = "A1", lang: str = "en") -> AppConfig:
    """
    Build AppConfig for the given CEFR level and language.

    Args:
        level: CEFR level — A1 / A2 / B1 / B2 / C1 / C2
        lang:  Language code — en / fr / ru / de / es / …
    """
    output_dir = OUTPUT_BASE_DIR / level
    output_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        level=level,
        lang=lang,
        phase1=Phase1Config(level=level),
        egp_csv_path=_csv_path(level, lang),
        output_dir=output_dir,
    )
