#ifndef __PACHIRA_INPUT_ADAPTER_API_H_
#define __PACHIRA_INPUT_ADAPTER_API_H_

#define KEYWORD_TYPE_MAIN 0x01
#define KEYWORD_TYPE_ALIAS 0x02
#define KEYWORD_TYPE_SCENE 0x03
#define KEYWORD_TYPE_ONESHORT 0x04
#define KEYWORD_TYPE_ZEROSHORT 0x05

typedef enum{
    STATUS_SPEECH_SR_INIT_SUCCESS          = 0x01,//init sucess status, only if get the status, the audio can be processed
    STATUS_SPEECH_SR_INIT_FAILED           = 0x02,//when failed to init decoder, it occurs.
    STATUS_SPEECH_SR_START_SUCCESS         = 0x03,//reset & start the engine
    STATUS_SPEECH_SR_START_FAILED          = 0x04,//reset & start the engine failed
    STATUS_SPEECH_SR_PROCESS_DATA_FAILED   = 0x05,//process audio data failed, which was fed into decoder
    STATUS_SPEECH_SR_RESULT_SUCCESS        = 0x06,//when the asr result gained, it occurs.
    STATUS_SPEECH_SR_RESULT_FAILED         = 0x07,//it occurs, when getting result failed

    STATUS_SPEECH_NLU_RESULT_SUCCESS       = 0x08,//when the nlu result gained, it occurs.
    STATUS_SPEECH_SR_REALTIME_RESULT       = 0x09,//real-time result of offline decoder would be return
    STATUS_SPEECH_NLG_RESULT_FAILED        = 0x0A,//no result when the work mode is NLG, it occurs.
    STATUS_SPEECH_NR_OUTPUT_DATA           = 0x10,
    STATUS_SPEECH_VOICE_DB_LEVEL           = 0x11,//voice level, range 0 to 100

    STATUS_SPEECH_SET_PERSONALIZED_INFO_SUCCESS = 0x30,//upload user personalization info. successfully
    STATUS_SPEECH_SET_PERSONALIZED_INFO_FAILED  = 0x31,//upload user personalization info. unsuccessfully
    STATUS_SPEECH_SAVE_DATA_FAILED              = 0X32,//data save error
    STATUS_SPEECH_DB_LOCKED                = 0x33, // locked db file finish, mean no longer read it

    STATUS_SPEECH_SR_SPEECH_START          = 0x60,//the speech start in adudio
    STATUS_SPEECH_SR_SPEECH_END            = 0x61,//the speech end in adudio
    STATUS_SPEECH_SR_SILENCE_TIMEOUT       = 0x62,//input too much silence
    STATUS_SPEECH_SR_SPEECH_NOINPUT        = 0x63,//no speech in audio

    STATUS_SPEECH_WAKEUP_UNIVERSAL_SUCCESS = 0x70,//main-word wakeup success
    STATUS_SPEECH_WAKEUP_SCENARIO_SUCCESS  = 0x71,//scenario-word wakeup success
    STATUS_SPEECH_SESSION_BARGEIN          = 0x72,//session barge in
    STATUS_SPEECH_WAKEUP_SESSION_SIMPLE_ONE_SHOT   = 0x73,//session instant respond

    STATUS_SPEECH_WAKEUP_SMART_LINK_SUCCESS    = 0x80,//the third party assist wakeup success

    STATUS_SPEECH_RESULT_TIMEOUT               = 0x90,//get the asr or nlu result timeout
    STATUS_SPEECH_ERR_NETWORK_NOT_AVAILABLE    = 0x91,//online decode, but network unavailable
    STATUS_SPEECH_ERR_SERVICE_NOT_AVAILABLE    = 0x92,//online decode, network available, but VCG or PSTT service unavailable
    STATUS_SPEECH_CONNECT_NETWORK_SUCCESS      = 0x93, // connect network successfully
    STATUS_SPEECH_CONNECT_NETWORK_FAILED       = 0x94, // connect network failed
    STATUS_SPEECH_ERR_AUTHORIZATION_EXPIRED    = 0xA0,//authorization expires
    STATUS_SPEECH_ENGINE_RESET_SERVER_FINISHED = 0XA1,//reset engine finished when the server was killed

    STATUS_SPEECH_SESSION_SPEAKER_ENROLL_SUCCESS   = 0xB0,//session speaker enroll
    STATUS_SPEECH_SRE_EVENT                        = 0xC0,//speaker verification event
    STATUS_SPEECH_SESSION_FINISH           = 0xF0,//session finished, next session can be started.
    STATUS_SENSITIVE_WORD_JUDGMENT         = 0xF4,//sensitive word judgment.
}SpeechEngineStatusCode;

typedef enum {
    SPEECH_ENGINE_PARAM_LINK_TYPE = 0x01,
    SPEECH_ENGINE_PARAM_SEAT_SIGNAL = 0x02,
    SPEECH_ENGINE_FULL_VEHICLE_SPEECH = 0x03,
    SPEECH_ENGINE_PARAM_REAL_TIME_RESULT = 0x04, //都发
    SPEECH_ENGINE_PARAM_PUNC_RESULT = 0x05, //都发
    SPEECH_ENGINE_PARAM_DIGIT_CONVERT_RESULT = 0x06, //都发
    SPEECH_ENGINE_PARAM_SILENCE_DURATION = 0x07, //都发
    SPEECH_ENGINE_PARAM_SILENCE_TIMEOUT = 0x08, //都发
    SPEECH_ENGINE_PARAM_SPEECH_TIMEOUT = 0x09, //都发
    SPEECH_ENGINE_PARAM_SCENAROI_NAME = 0x0A,  //都发
    SPEECH_ENGINE_PARAM_WAKEUP_SCENE = 0x0B,
    SPEECH_ENGINE_PARAM_WAKEUP_DELAY_ONESHOT_DURATION = 0x0C,
    SPEECH_ENGINE_PARAM_SOUND_EVENT_OPTION = 0x0D,
    SPEECH_ENGINE_PARAM_EMOTION_OPTION = 0x0F,
    SPEECH_ENGINE_PARAM_SR_PTT_OPTION = 0x18,
    SPEECH_ENGINE_PARAM_SR_REALTIME_RESULT = 0x11,
    SPEECH_ENGINE_PARAM_SR_VOICE_WAKEUP = 0x12,
    SPEECH_ENGINE_PARAM_FULLTIME_OPTION = 0x13,
    SPEECH_ENGINE_PARAM_SR_WAKEUP_SCENE_ENABLE = 0x14,
    SPEECH_ENGINE_PARAM_SYSTEM_RESET = 0x15,
    SPEECH_ENGINE_PARAM_AUDIO_FILENAME = 0x40,
    SPEECH_ENGINE_PARAM_HMI_CONTEXT = 0x51
}SpeechEngineParam;

typedef enum{
    engine_mode_WAKEUP      = 0x00,//when only switching to wakeup
    engine_mode_ASR         = 0x01,//when only switching to asr
    engine_mode_WAKEUP_ASR    = 0x02,//when switching to wakeup, asr, nlp
}SPEECH_ENGINE_WORK_MODE;

typedef enum {
    SPEECH_NONE_SAVE_TYPE = -1, //不存储
    SPEECH_ALWAYS_TYPE = 0,//always模式
    SPEECH_WAKE_ASR_TYPE = 1,//根据唤醒识别事件存储
} SPEECH_VOICE_LOG_TYPE;

typedef enum{
    VR_SOURCE_NLU  = 0,
    VR_SOURCE_LCS = 1
}SPEECH_ENGINE_VR_SOURCE;

typedef struct speech_engine_result_st{
    unsigned long time;
    int flag;
    int back;
    char* data;
}*speech_engine_result_t;

typedef struct speech_data_st{
    char *mic_data[4];
    char *ref_data;
    char *output;
    int direction;
}*speech_data_t;

#ifdef __cplusplus
extern "C" {
#endif

typedef int (*speech_engine_callback_t)(int status, speech_engine_result_t result, void *arg);


/*
 * @brief set_default_language_info
 * param info 默认语种信息
 */
void speech_engine_set_default_language_info(const char *info);

/**
 * @brief attach_speech_engine
 * @param file:       config file, or resource dir
 * @param callback:   event callback
 * @param arg:        this arg will return its value in the aibs_engine_callback_t
 * @return if success, will return resource pointer, or else return NULL;
 **/
void* attach_speech_engine(const char *file, const char *device_info, speech_engine_callback_t callback, void* arg);


/**
 * @brief some additional information, help us to improvement personalized performance.
 *        will use this parameter fo provide some personalization features
 * @param param: init_speech_engine_decode
 * @param value: config_path
 * @return if success,will return 0,or else return err code
 **/
int init_speech_engine_decode(void *engine, const char *config_path);


/**
 * @brief some additional information, help us to improvement personalized performance.
 *        will use this parameter fo provide some personalization features
 * @param param: SpeechEngineParam
 * @param value: pararm value in crrosponding to AIBSEngineParam
 * @return if success,will return 0,or else return err code
 **/
int set_speech_engine_param(void* engine, SpeechEngineParam param, void* value);

/**
 * @brief set log path
 * @param decoder:    engine instance
 * @param log_path: log_path
 * @return if success, return 0, or else return err code
 **/
int set_speech_engine_log_path(void* engine, const char *log_path);

/**
 * @brief start speech engine
 * @param decoder:    engine instance
 * @param arg:        any callback, will return arg at the same time
 * @return if success, return 0, or else return err code
 **/
int start_speech_engine(void* engine, int channelNum, void *arg);

/**
 * @brief set data type 
 *        type == 1.  data after ECNR
 *        type == 2.  data need ECNR
 *        type == 0.  mono channel, don't need ECNR
 * @param engine:  decoder instance
 * @param type
 **/
void speech_engine_set_data_type(void *engine, int type);

/**
 * @brief process audio data
 * @param decoder:    instance
 * @param data:       audio data
 * @param data_size:  data_size
 * @return if success, return 0, or if failed or not need the rest audio, return -1;
 **/
int speech_engine_process_data(void* engine, const char* data, int length, unsigned long t);

/**
 * @brief stop or cancal decode process
 * @param decoder: engine instance
 * @return if success, return 0, or else failed
 **/
int stop_speech_engine(void* engine);

/*
 * @brief: set personalized info.
 * @param engine:       instance
 * @param json_ulist:   userlist json string
 * @param weight:       weight in asr nerwork.
 * @restricted cond: no update model tasks
 * @return : if success ,return  0, or else failed
 */
int update_personalized_info(void* engine, const char* json_ulist, const char* char_set, float weight);

/*
 *  * @brief set work mode
 *   * @param decoder: engine instance
 *    * @param state: ENGINE_WORK_MODE
 *     * @return if avaliable return 0, or else return err code
 *      */
int set_speech_engine_work_mode(void* engine, SPEECH_ENGINE_WORK_MODE mode);


/*
 * @brief set play tts
 * @param decoder: engine instance
 * @param state:   true -->when tts opened
                   false-->when tts closed
 * @return if avaliable return 0, or else return err code
 */
int set_tts_state(void* engine, bool state);

/*
 * @brief set freetalk start
 * @param decoder: engine instance
 * @param state:   true -->when freetalk opened
                   false-->when freetalk closed
 * @return if avaliable return 0, or else return err code
 */
int set_freetalk_state(void* engine, bool state, int channel_id, SPEECH_ENGINE_VR_SOURCE resource = VR_SOURCE_NLU);

/*
 * @brief set wake-up term
 * @param decoder: engine instance
 * @param word: wake-up term
          threshold: wake-up threshold
 * @return if avaliable return 0, or else return err code
 */
int add_wakeup_word(void* engine, const char *lang, const char *word, float threshold);

/*
 * @brief get wake-up term
 * @param decoder: engine instance
 * @param word: wake-up term
          threshold: wake-up threshold
 * @return if avaliable return 0, or else return err code
 */
char* get_wakeup_term(void* engine, const char *lang, int type);

/**
 * @brief cancel engine task, this will stop decoding immediately.
 *        after invoke this function with success,and not callback result any more
 *        this function will return in synchronously
 * @param decoder: instance
 * @param flag:this parameter will affect the behavior of cancellation
 *             it is zero for now
 * @return if success,return 0 or else failed,return err-code
 **/
int cancel_speech_engine(void* engine, int flag);

/*
 * @brief set wake-up term option
 * @param decoder: engine instance
 * @param word: wake-up term
          option: wake-up option
 * @return if avaliable return 0, or else return -1
 */
int set_wakeup_word_enable(void* engine, const char *word, bool option);

/*
 * @brief free engine resource
 * @param engine: engine instace
 * @return void
 */
int free_speech_engine(void* engine);

/*
 * @brief: add speaker verification reqeust, JSON-str
 * support: "type":"startEnroll"/"endEnroll"/"recognize"/"deleteSpeaker"/"checkSpeaker"
 *          "data":{
 *                  "channel":
 *                  "id":
 *                  "user_id":
 *                  "text":
 *                  "start_time":
 *                  "end_time":
 *           }
 */
int set_speech_engine_sre_request(void* engine, const char* buffer);

/*
 * @breif:调用指定音区的语音输入法
 * @param: engine, 引擎句柄
 * @param: param, 语音输入法相关参数
 * @return: 成功返回0，失败返回-1 
 */
int speech_engine_open_voice_input(void *engine, const char *param);

/*
 * @breif:关闭语音输入法
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1 
 */
int speech_engine_close_voice_input(void *engine);

/*
 * @breif:设置语音唤醒开关
 * @param: engine, 引擎句柄
 * @param: option 0:关闭 1:打开
 * @return: 成功返回0，失败返回-1
 */
int speech_engine_set_voice_wakeup_option(void *engine, int option);

/*
 * @brief: set language info
 * @param: language info
 *
 */
int speech_engine_set_language_info(void *engine, const char *info);

/*
 * @breif:配置voicelog信息
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
*/
int speech_config_voicelog(void* engine, bool if_open, SPEECH_VOICE_LOG_TYPE mode);

/*
 * @breif:设置voicelog存储目录
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
*/
int speech_set_voicelog_path(void* engine, const char *path);

/*
 * @breif:设置vr静音超时
 * @param: engine, 引擎句柄
 * @param: channelID, 通道号
 * @param: duration 超时时间
 * @return: 成功返回0，失败返回-1
 */
int set_vr_silence_timeout(void* engine, int channelID, int duration);

/*
 * @breif:设置carlife连接类型
 * @param: engine, 引擎句柄
 * @return: 成功返回0，失败返回-1
 */
int speech_set_link_type(void *engine, int type);

/*
 *  * @breif:设置MIC接续状态
 *   * @param: engine, 引擎句柄
 *    * @return: 成功返回0，失败返回-1
 *     */
int speech_set_mic_status(void *engine, int status);

/*
 * @breif:开始录音
 * @return: 成功返回0，失败返回-1
 */
int speech_start_record(void *engine);

/*
 * @breif:停止录音
 * @return: 成功返回0，失败返回-1
 */
int speech_stop_record(void *engine);

/*
 * @breif:敏感词检测
 * @param: engine, 引擎句柄
 * @param: words, 待判定的敏感词
 * @return: 成功返回0，失败返回-1
 */
int sensitive_word_judgment(void* engine, const char* words);

/*
 * @breif:设置车参信息
 * @param: engine, 引擎句柄
 * @param: car_type, 车参信息
 * @return: 成功返回0，失败返回-1
 */
int speech_set_car_type(void* engine, const char* car_type);

/*
 * @breif:声纹功能使能与否接口
 * @param: engine, 引擎句柄
 * @param: option, 0：关闭，1：开启
 * @return: 成功返回0，失败返回-1
 */
int set_sre_enable_option(void* engine, int option);

int set_server_cache_lang(void* engine, const char* lang);

int set_server_cache_update(void* engine, const char* lang, const char* alias, const char* enable);

int set_channel_mask(void* engine, int option);

int set_fota_resource(void* engine, const char* res_path);

int set_start_init(void* engine, int use_fota_res, const char* message);


/*
 * @breif:日志存储
 * @param: engine, 引擎句柄
 * @param: option, false：关闭，true：开启
 * @return: 成功返回0，失败返回-1
 */
int set_log_option(void *engine, bool option);

#ifdef __cplusplus
};
#endif

#endif
