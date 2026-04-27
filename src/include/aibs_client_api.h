#ifndef __PACHIRA_AIBS_CLIENT_API_H_
#define __PACHIRA_AIBS_CLIENT_API_H_

#define AIBS_KEYWORD_TYPE_MAIN 0x01
#define AIBS_KEYWORD_TYPE_ALIAS 0x02
#define AIBS_KEYWORD_TYPE_SCENE 0x03

#define AIBS_RESULT_TYPE_STRLEN_MAX (128)

typedef enum {
    AIBS_SETTING_DEVICE_INFO = 0x00,
    AIBS_SETTING_VR_OPTION = 0x01,                         // TSA助手开关
    AIBS_SETTING_SHOW_STYLE = 0x02,                        // 设置显示风格
    AIBS_SETTING_WAKEUP_ALIAS = 0x03,                      // 设置唤醒词
    AIBS_SETTING_DIALOGUE_STYLE = 0x04,                    // 设置全时模式
    AIBS_SETTING_DIALOGUE_LANGUAGE = 0x05,                 // 设置语种
    AIBS_SETTING_SOUND_AREA_OPTION = 0x06,                 // 设置音区
    AIBS_SETTING_WAKEUP_KEYWORD_OPTION = 0x07,             // 设置场景唤醒词开关
    AIBS_SETTING_VOICE_WAKEUP_OPTION = 0x08,               // 设置语音唤醒开关
    AIBS_SETTING_WAKEUP_ENABLE = 0x09,                     // 设置唤醒词生效
    AIBS_SETTING_GET_WAKEUP_WORD = 0x10,                   // vrconfig获取唤醒词
    AIBS_SETTING_SET_TTS_VOICE_TYPE = 0x11,                // 设置TTS音色
    AIBS_SETTING_MULTI_DIALOGUE = 0x12,                    // 设置多人对话
    AIBS_SETTING_EXPERIENCE_IMPROVENMENT = 0x13,           // 用户体验改善计划
    AIBS_SETTING_PERSONAL_SENSITIVE_AUTHORIZATION = 0x14,  // 个性化交互敏感信息授权
    AIBS_SETTING_VOICE_SENSITIVE_AUTHORIZATION = 0x15,     // 声音敏感信息授权
    AIBS_SETTING_ACTIVE_INTERACTION = 0x17,                // 语音助手主动交互列表
    AIBS_SETTING_SRE_SENSITIVE_EMPOWER_OPTION = 0x18,      // 声纹隐私设置开关
    AIBS_SETTING_SRE_FUNC_ENABLE_OPTION = 0x19,            // 声纹功能使能设置开关
    AIBS_SETTING_SERVER_CACHE_LANGUAGE = 0x20,             // 修改缓存语种
    AIBS_SETTING_GPT_ENABLE_OPTION = 0x21,                 // enable gpt option
    AIBS_SETTING_SRE_MEMORY = 0x22,                        // 声纹记忆开关
    AIBS_SETTING_VEHICLE_MEMORY = 0x23                     // 车辆记忆开关
} AIBSVRConfigCode;

typedef enum {
    STATUS_AIBS_INIT_SUCCESS = 0x01,           //初始化成功
    STATUS_AIBS_INIT_FAILED = 0x02,            //初始化失败
    STATUS_AIBS_SESSION_START_SUCCESS = 0x03,  //开始会话成功
    STATUS_AIBS_SESSION_START_FAILED = 0x04,   //开始会话失败
    STATUS_AIBS_EVENT = 0x10,                  //事件信息
    STATUS_AIBS_AUDIO_ENERGY = 0x11,           //音频能量
    STATUS_AIBS_SESSION_FINISHED = 0x20,       //会话结束 事件，SessionEnd, 需要解析返回Status
    STATUS_AIBS_SRE_EVENT = 0x30,              //声纹回调事件
    STATUS_AIBS_VR_CLOSED = 0x31,              //助手关闭状态回调
} AIBSStatusCode;

typedef enum {
    AIBS_SUCCESS_CODE = 0x00,//成功
    AIBS_HANDLE_NULL_CODE = 0x01,//句柄为孔
    AIBS_MEMORY_ERROR_CODE = 0x02,//内存错误
    AIBS_SEND_DATA_ERROR_CODE = 0x03,//发送数据失败
    AIBS_CONNECT_SERVER_ERROR_CODE = 0x04,//连接服务器失败
    AIBS_LOAD_CONFIG_ERROR_CODE = 0x05,//加载配置文件失败
} AIBSClientErrorCode;

typedef enum {
    AIBS_PARAM_SESSION_LINK_TYPE = 0x01,
    AIBS_PARAM_SEAT_SIGNAL = 0x02,
    AIBS_PARAM_FULL_VEHICLE_SPEECH = 0x03,
    AIBS_PARAM_REAL_TIME_RESULT = 0x04,      //都发
    AIBS_PARAM_PUNC_RESULT = 0x05,           //都发
    AIBS_PARAM_DIGIT_CONVERT_RESULT = 0x06,  //都发
    AIBS_PARAM_SILENCE_DURATION = 0x07,      //都发
    AIBS_PARAM_SILENCE_TIMEOUT = 0x08,       //都发
    AIBS_PARAM_SPEECH_TIMEOUT = 0x09,        //都发
    AIBS_PARAM_SCENAROI_NAME = 0x0A,         //都发
    AIBS_PARAM_WAKEUP_SCENE = 0x0B,
    AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION = 0x0C,
    AIBS_PARAM_SOUND_EVENT_OPTION = 0x0D,
    AIBS_PARAM_EMOTION_OPTION = 0x0F,
    AIBS_PARAM_DISABLE_BUTTON_WAKEUP = 0x0E,
    AIBS_PARAM_SR_PTT_OPTION = 0x10,
    AIBS_PARAM_SR_VOICE_WAKEUP = 0x12,
    AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE = 0x14,
    AIBS_PARAM_SR_AUDIO_SPECTRAL = 0x15,      //声音能量获取开关
    AIBS_PARAM_SR_RECORD_DEVICE_STATE = 0x16       //录音设备不可用获取开关
} AIBSParam;

typedef enum {
    aibs_mode_WAKEUP = 0x00,      // when only switching to wakeup
    aibs_mode_ASR = 0x01,         // when only switching to asr
    aibs_mode_WAKEUP_ASR = 0x02,  // when switching to wakeup, asr
    aibs_mode_SMART_LINK = 0x03,  // when using third party wakeup assist
} AIBS_WORK_MODE;

typedef enum{
    VOICE_INPUT_ONLY        = 0x00,//only the index channel is on asr mode
    VOICE_INPUT_NORMAL      = 0x01,//the index channel is on asr mode， and the other is on vr mode
}VOICE_INPUT_MODE;

typedef enum {
    AIBS_LINK_TYPE_NONE = 0,
    AIBS_LINK_TYPE_CARPLAY,
    AIBS_LINK_TYPE_HICAR,
    AIBS_LINK_TYPE_CARLIFE,
} AIBS_LINK_TYPE;

typedef enum {
    aibs_classic_show_style = 0x01, //经典显示风格
    aibs_immerse_show_style = 0x02, //沉浸显示风格
}AIBS_SHOW_STYLE;

typedef enum {
    NONE_SAVE_TYPE = -1, //不存储
    ALWAYS_TYPE = 0,//always模式,该模式音频一直存储
    WAKEUP_ASR_TYPE = 1,//根据唤醒识别事件存储
} VOICE_LOG_TYPE;

typedef struct aibs_result_st {
    int flag;  //回调音频能量时，表示data的长度
    char* data;
    int mm_ctx;
    char type[AIBS_RESULT_TYPE_STRLEN_MAX];  //type信息
} * aibs_result_t;

#ifdef __cplusplus
extern "C" {
#endif

typedef int (*aibs_callback_t)(int status, aibs_result_t result, void* arg);

/**
 * @brief get aibs engine version
 * @return if success, will return version, or else return NULL;
 **/

const char *aibs_get_engine_version(void *engine);

/*
 * @breif:设置车机参数
 * @param: engine, 引擎句柄
 * @param: device_info，车机参数
 * @return: 成功返回0，失败返回-1
*/
int aibs_set_car_type(const char *device_info);

/**
 * @brief create speech engine, create IPC with LCS
 * @param file:       config file, or resource dir
 * @param callback:   event callback
 * @param arg:        this arg will return its value in the
 * @param config_path: config file path
 * @param appid: the appid to tag app's type
 *aibs_engine_callback_t
 * @return if success, will return resource pointer, or else return NULL;
 **/
void* aibs_create_engine(aibs_callback_t callback, void* arg, const char* config_path, const char *lang, const char *appid);

/**
 * @brief set logpath
 * @param logpath: log_path
 * @return if success,will return 0,or else return err code
 **/
int set_aibs_logpath(const char *log_path);



/**
 * @brief some additional information, help us to improvement personalized
 *performance. will use this parameter fo provide some personalization features
 * @param param: SpeechEngineParam
 * @param value: pararm value in crrosponding to AIBSEngineParam
 * @return if success,will return 0,or else return err code
 **/
int set_aibs_param(void* engine, AIBSParam param, void* value);

/**
 * @brief start aibs engine
 * @param decoder:    engine instance
 * @param arg:        any callback, will return arg at the same time
 * @return if success, return 0, or else return err code
 **/
int aibs_start_engine(void* engine, int channelNum, void* arg);

/**
 * @brief process audio data
 * @param engine:    instance
 * @param data:       audio data
 * @param data_size:  data_size
 * @return if success, return 0, or if failed or not need the rest audio, return
 *-1;
 **/
int aibs_process_data(void* engine, const char* data, int length,
                      unsigned long t);

/**
 * @brief stop or cancal decode process
 * @param decoder: engine instance
 * @return if success, return 0, or else failed
 **/
int aibs_stop_engine(void* engine);

/**
 * @brief cancel engine task, this will stop decoding immediately.
 *        after invoke this function with success,and not callback result any
 *more this function will return in synchronously
 * @param decoder: instance
 * @param flag:this parameter will affect the behavior of cancellation
 *             it is zero for now
 * @return if success,return 0 or else failed,return err-code
 **/
int aibs_cancel_engine(void* engine, int flag);

/*
 * @brief free engine resource
 * @param engine: engine instace
 * @return void
 */
int aibs_free_engine(void* engine);

/*
 * @brief: set personalized info.
 * @param engine:       instance
 * @param json_ulist:   userlist json string
 * @param weight:       weight in asr nerwork.
 * @restricted cond: no update model tasks
 * @return : if success ,return  0, or else failed
 */
int aibs_update_personalized_info(void* engine, const char* json_ulist,
                                  const char* char_set, float weight);

/*
 * @brief set play tts
 * @param decoder: engine instance
 * @param state:   true -->when tts opened
                   false-->when tts closed
 * @return if avaliable return 0, or else return err code
 */
int aibs_set_tts_state(void* engine, bool state);

/*
 * @brief set hmi info
 * @param engine: instance
 * @param hmi: page information, JSON-Style
 * @param app_name
 * @return : if success ,return  0, or else failed
 */
int aibs_set_page_intent(void* engine, const char* hmi, const char* app_name);

/*
 * @brief set language mode
 * @param engine: instance
 * @param mode: language mode, support: eng, cmn, yue
 * @return : if success ,return  0, or else failed
 */
int aibs_set_language_mode(void* engine, const char* mode);

// --- aibs集成  -- ?
// FreetalkTimeout -- 设置SpeechEngine的工作模式为：WAKEUP_ASR工作模式
//唤醒之后自动切换为true
//首句免唤醒 -- 增加设置参数 发送事件给LCS:
//       true: 设置工作模式, ASR

/*
 * @brief set wake-up term
 * @param decoder: engine instance
 * @param word: wake-up term
          threshold: wake-up threshold
 * @return if avaliable return 0, or else return err code
 */
int aibs_set_wakeup_word(void* engine, const char* word, float threshold);

/*
 * @brief set wake-up term option
 * @param decoder: engine instance
 * @param word: wake-up term
          option: wake-up option
 * @return if avaliable return 0, or else return -1
 */
int aibs_set_wakeup_word_enable(void* engine, const char* word, bool option);

/*
 * @brief get wakeup word
 * @param engine: instance
 * @return wakeup words if success, or return NULL
 */
const char* aibs_get_wakeup_word(void* engine);

/*
 * @brief: TSA向LCS传入TSA事件
 * @param: event: 事件内容
 * @return: 成功返回TSASDK_OK,否则返回其他错误码
 */
int aibs_set_event(void* engine, char* event);

/*
 * @breif:开启输入法模式
 * @param: engine, 引擎句柄
 * @param: param, 语音输入法参数设置
 * @return: 成功返回0，失败返回-1
 */
int aibs_open_voice_input(void* engine, const char* param);

/*
 * @breif:关闭输入法模式
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
 */
int aibs_close_voice_input(void* engine);

/*
 * @breif:设置工作模式（这个接口废弃，设置工作模式，是从aibs_set_vr_config中进行设置）
 * @param: engine, 引擎句柄
 * @param: mode, 工作模式，定义在AIBS_WORK_MODE
 * @return: 成功返回0，失败返回-1
 */
int aibs_set_workmode(void* engine, AIBS_WORK_MODE mode);

/*
 * @breif: 获取FOTA状态
 * @param: engine, 引擎句柄
 * @return: 返回FOTA_STATUS
 */
int get_fota_status(void *engine);

/*
 * @breif:注册声纹信息
 * @param: engine, 引擎句柄
 * @param: user_id 用户id
 * @param: text 文本内容
 * @param: id 当前的次数
 * @param: channel_id 通道id
 * @return: 成功返回0，失败返回-1
 */
int aibs_start_speaker_enroll(void* engine, const char *user_id, const char *text, int id, int channel_id);

/*
 * @breif:结束本次声纹注册
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
 */
int aibs_end_speaker_enroll(void* engine);

/*
 * @breif:识别给定边界内的发话人信息
 * @param: engine, 引擎句柄
 * @param: channel_id 通道id
 * @param: start_time 开始时间
 * @param: end_time 结束时间
 * @return: 成功返回用户信息，失败返回NULL
 */
const char* aibs_recognize_speaker(void* engine, int channel_id, long start_time, long end_time);

/*
 * @breif: 声纹验证，异步返回验证结果
 * @param: engine, 引擎句柄
 * @param: user_id 声纹id
 * @param: text 文本内容
 * @param: channel_id 结束时间
 * @return: 成功返回0，失败返回-1
 */
int aibs_verify_voiceprint(void* engine, const char *user_id, const char *text, int channel_id);

/*
 * @breif: 取消声纹验证
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
 */
int aibs_cancel_verify_voiceprint(void* engine);

/*
 * @breif:删除声纹信息
 * @param: engine, 引擎句柄
 * @param: user_id 用户id
 * @return: 成功返回0，失败返回-1
 */
int aibs_delete_speaker_info(void* engine, const char *user_id);

/*
 * @breif:获取说话人列表
 * @param: engine, 引擎句柄
 * @return: 成功返回用户信息，失败返回NULL
 */
const char* aibs_get_speaker_info(void* engine, const char *user_id);

/*
 * @breif:获取语音录入的文本内容
 * @param: engine, 引擎句柄
 * @return: 成功返回语音录入文本，失败返回NULL
 */
const char* aibs_get_enroll_text(void* engine);

/*
 * @breif: 判断文本中是否含有敏感词
 * @param: engine, 引擎句柄
 * @param: words, 待判断文本内容,最长512字节
 * @return: 成功返回0,输入内容包括敏感词返回-9，输入参数长度超限制返回-10。
 */
int aibs_sensitive_word_judgment(void* engine, const char* words);

/*
 * @breif: 获取已经注册的声纹userid
 * @param: engine, 引擎句柄
 * @return: 若获取成功，则返回JSON格式的字符串，否则返回空字符串
 */
const char* aibs_get_registered_speaker(void* engine);

/*
 * @breif:设置VR配置
 * @param: engine, 引擎句柄
 * @return: 成功返回设置结果，失败返回-1
 */
int aibs_set_vr_config(void* engine, AIBSVRConfigCode key, const void *value);

/*
 * @brief: VR设置向LCS设置event事件
 * @param: event: 事件内容
 * @return: 成功返回TSASDK_OK,否则返回其他错误码
 */
int aibs_set_vr_event(void* engine, char* event);

/*
 * @breif:设置VR配置
 * @param: engine, 引擎句柄
 * @return: 成功返回设置结果，失败返回NULL
 */
const char* aibs_get_vr_config(void* engine, AIBSVRConfigCode key);

/*
 * @breif:恢复出厂设置
 * @param: engine, 引擎句柄
 * @return: 成功返回设置结果，失败返回-1
 */
int aibs_clear_vr_config(void* engine);

/*
 * @breif:检查是否是助手
 * @param: filename配置文件路径
 * @param: key
 * @return: 返回value
 */
const char* aibs_get_config_item(const char *filename, const char *key);

/*
 * @brief: write log
 * @param: filename  / config filename
 * @param: text / log content
 */
void aibs_write_log(const char *filename, const char *tag, const char *text, int level);

/*
 * @breif:配置voicelog信息
 * @param: engine, 引擎句柄
 * @param: if_open true表示打开 false表示关闭
 * @param: mode 参考VOICE_LOG_TYPE 
 * @return: 成功返回0，失败返回-1
*/
int aibs_config_voicelog(void* engine, bool if_open, VOICE_LOG_TYPE mode);

/*
 * @breif:设置voicelog存储目录
 * @param: engine, 引擎句柄
 * @param: path 音频存储路径限制128个字节存储
 * @return: 成功返回0，失败返回-1
*/
int aibs_set_voicelog_path(void* engine, const char *path);

/*
 * @breif:设置 link type
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
*/
int aibs_set_link_type(void *engine, AIBS_LINK_TYPE type);

/* 
* @breif:开始录音
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
*/
int aibs_start_record(void *engine);

/*
 * @breif:停止录音
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
*/
int aibs_stop_record(void *engine);

/*
 * @breif:暂定引擎
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
*/
int aibs_pause_engine(void *engine);

/* 
* @breif:恢复引擎
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
*/
int aibs_resume_engine(void *engine);

/*
 *  * @breif:设置mic接续状态
 *   * @param: engine, 引擎句柄
 *    * @param: states, 当前接续的mic状态（1表示主驾、2表示副驾、4表示后排左、8表示后排右）
 *     * @return: 成功返回0，失败返回-1
 *     */
int aibs_set_mic_status(void *engine, int status);

/*
 * @breif:用于控制VR功能是否可用
 * @param: engine, 引擎句柄
 * @param: status, true，表示VR为enable；false，表示VR为disable
 * @return: 成功返回0，失败返回-1
*/
int aibs_set_vr_status(void *engine, bool status);

#ifdef __cplusplus
};
#endif

#endif
