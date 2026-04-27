" Vim syntax file
" Language: Mango NANO .mgo DSL
" Maintainer: Mango Project
" Source of truth:
"   src/testsuite/NANO/doc/NANO_DSL_HIGHLIGHT_KEYWORDS.md

if exists("b:current_syntax")
  finish
endif

syntax case match
syntax sync minlines=200

" ---------------------------------------------------------------------------
" 基础结构
" ---------------------------------------------------------------------------

syntax match nanoComment /^\s*#.*$/
syntax match nanoComment /^\s*\/\/.*$/
syntax match nanoComment /\%(^\|\s\)\zs#.*$/

syntax match nanoBlockMarker /^\s*>>>\ze\(\s*\S\+\)\?/
syntax match nanoBlockMarker /^\s*<<<\s*$/
syntax match nanoFixtureKeyword /\%(^\s*>>>\s\+\)\@<=\(SETUP\|TEARDOWN\|SUITE_TEARDOWN\|CASE_SETUP\|CASE_TEARDOWN\)\>/
syntax match nanoParameterKeyword /\%(^\s*>>>\s\+\)\@<=PARAMETER\>/
syntax match nanoRepeatCount /^\s*>>>\s*\zs\d\+\ze\s*$/
syntax match nanoParameterValue /\%(^\s*>>>\s\+PARAMETER\s\+\)\@<=\S\+\ze\s*$/

" 客户端标签
syntax match nanoExpClient /\[EXP\]/ nextgroup=nanoAssertType skipwhite
syntax match nanoClient /\[\%(TSA\|SET\|VOI\|OMS\|TTS\|HWK\|PST\|TIA\|CPL\|ENR\|PIS\|TSS\|TSR\|SYS\|NIS\|NSE\)\]/ nextgroup=nanoCommand skipwhite

" ---------------------------------------------------------------------------
" 静态词表：命令与断言
" ---------------------------------------------------------------------------

syntax keyword nanoCommand contained
      \ CREATE START STOP FREE DATA TEXT_DATA EVENT CANCEL FREEWAKEUP PARALLELSR
      \ SETVRCONFIG TEXT STRATEGY PAUSE RESUME GET_VERSION CAR_TYPE LOG_PATH
      \ MIC_STATUS VR_STATUS LINK_TYPE VREVENT START_RECORD STOP_RECORD
      \ OPEN_VOICE_INPUT CLOSE_VOICE_INPUT START_SPEAKER_ENROLL
      \ END_SPEAKER_ENROLL RECOGNIZE_SPEAKER VOICEPRINT_LOGIN
      \ VERIFY_VOICEPRINT CANCEL_VERIFY_VOICEPRINT DELETE_SPEAKER
      \ GET_SPEAKER_INFO GET_SPEAKERS GET_ENROLL_TEXT SENSITIVE_WORD_CHECK
      \ REGISTER_VOICEPRINT_LIST CLEAR_VR_CONFIG GET_CONFIG_ITEM
      \ GET_FOTA_STATUS WRITE_LOG CONFIG_VOICELOG SET_VOICELOG_PATH
      \ SET_PARAM SET_TTS_STATE SET_LANGUAGE_MODE SET_WORKMODE
      \ UPDATE_PERSONALIZED SET_PAGE_INTENT GET_WAKEUP_WORD GET_VR_CONFIG
      \ INPUTEVENT CALLBACK SET_WAKEUP_WORD SET_WAKEUP_ENABLE INIT_DECODE
      \ SET_DATA_TYPE SET_WORK_MODE SET_FREETALK_STATE ADD_WAKEUP_WORD
      \ GET_WAKEUP_TERM SET_VOICE_WAKEUP_OPTION SET_SRE_REQUEST
      \ SET_SRE_ENABLE_OPTION SET_LANGUAGE_INFO SET_VR_SILENCE_TIMEOUT
      \ SET_LINK_TYPE SET_MIC_STATUS SET_CAR_TYPE HMI DATA_QUEUE CASELIST
      \ SET_DOWNLINK AMP_TYPE ECNR_TYPE SET_PNR_MIC_MUTE_OPTION
      \ SET_PNR_ENABLE_OPTION SET_PNR_AUDIO_QUALITY GET_PNR_VERSION
      \ GET_PNR_HFT_PARAM GET_PNR_MVR_PARAM GET_PNR_GEN_PARAM
      \ ANALYZE_AUDIO_DATA AIBSServer AIBS_SET_CARTYPE AIBS_SET_WORK_MODE
      \ AIBS_CREATE AIBS_START AIBS_STOP VEDIO WAIT UPDATE START_SERVICE
      \ SET_CARTYPE PULL KILL SLEEP CMD PRINT ENV UPLOAD ALLURE
      \ FOTA_RANDOM_ZIP BREF CLEAR_ASSERT ASR_ACCURACY ASR_LANGUAGE DELAY
      \ WAKEUP_ACCURACY VAD_ACCURACY VAD_PRECISION TIME_BOUNDARY_ACCURACY
      \ LLM PSTT_ACCURACY

syntax keyword nanoAssertType contained
      \ CREATE_RET START_RET STOP_RET FREE_RET DATA_RET EVENT_RET CANCEL_RET
      \ FREEWAKEUP_RET SETVRCONFIG_RET PAUSE_RET RESUME_RET GET_VERSION_RET
      \ CAR_TYPE_RET LOG_PATH_RET MIC_STATUS_RET VR_STATUS_RET LINK_TYPE_RET
      \ VREVENT_RET START_RECORD_RET STOP_RECORD_RET OPEN_VOICE_INPUT_RET
      \ CLOSE_VOICE_INPUT_RET CLEAR_VR_CONFIG_RET GET_FOTA_STATUS_RET
      \ SET_PARAM_RET UPDATE_PERSONALIZED_RET SET_TTS_STATE_RET
      \ SET_PAGE_INTENT_RET SET_LANGUAGE_MODE_RET SET_WAKEUP_WORD_RET
      \ SET_WAKEUP_ENABLE_RET GET_WAKEUP_WORD_RET SET_WORKMODE_RET
      \ GET_VR_CONFIG_RET START_SPEAKER_ENROLL_RET END_SPEAKER_ENROLL_RET
      \ RECOGNIZE_SPEAKER_RET VOICEPRINT_LOGIN_RET VERIFY_VOICEPRINT_RET
      \ CANCEL_VERIFY_VOICEPRINT_RET DELETE_SPEAKER_RET GET_SPEAKER_INFO_RET
      \ GET_SPEAKERS_RET GET_ENROLL_TEXT_RET SENSITIVE_WORD_CHECK_RET
      \ GET_CONFIG_ITEM_RET WRITE_LOG_RET CONFIG_VOICELOG_RET
      \ SET_VOICELOG_PATH_RET VR_OPTION_RET SHOW_STYLE_RET WAKEUP_ALIAS_RET
      \ DIALOGUE_STYLE_RET DIALOGUE_LANGUAGE_RET SOUND_AREA_OPTION_RET
      \ WAKEUP_KEYWORD_OPTION_RET VOICE_WAKEUP_OPTION_RET WAKEUP_ENABLE_RET
      \ SET_TTS_VOICE_TYPE_RET MULTI_DIALOGUE_RET EXPERIENCE_IMPROVENMENT_RET
      \ PERSONAL_SENSITIVE_AUTHORIZATION_RET VOICE_SENSITIVE_AUTHORIZATION_RET
      \ ACTIVE_INTERACTION_RET SRE_SENSITIVE_EMPOWER_OPTION_RET
      \ SRE_FUNC_ENABLE_OPTION_RET SERVER_CACHE_LANGUAGE_RET GPT_ENABLE_OPTION_RET
      \ SRE_MEMORY_RET VEHICLE_MEMORY_RET AIBS_PARAM_SESSION_LINK_TYPE_RET
      \ AIBS_PARAM_SEAT_SIGNAL_RET AIBS_PARAM_FULL_VEHICLE_SPEECH_RET
      \ AIBS_PARAM_REAL_TIME_RESULT_RET AIBS_PARAM_PUNC_RESULT_RET
      \ AIBS_PARAM_DIGIT_CONVERT_RESULT_RET AIBS_PARAM_SILENCE_DURATION_RET
      \ AIBS_PARAM_SILENCE_TIMEOUT_RET AIBS_PARAM_SPEECH_TIMEOUT_RET
      \ AIBS_PARAM_SCENAROI_NAME_RET AIBS_PARAM_WAKEUP_SCENE_RET
      \ AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION_RET
      \ AIBS_PARAM_SOUND_EVENT_OPTION_RET
      \ AIBS_PARAM_DISABLE_BUTTON_WAKEUP_RET AIBS_PARAM_EMOTION_OPTION_RET
      \ AIBS_PARAM_SR_PTT_OPTION_RET AIBS_PARAM_SR_VOICE_WAKEUP_RET
      \ AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE_RET
      \ AIBS_PARAM_SR_AUDIO_SPECTRAL_RET
      \ AIBS_PARAM_SR_RECORD_DEVICE_STATE_RET CARPLAY_CREATE_RET
      \ CARPLAY_FREE_RET NLPResult ASRInputResult ASRInputResultTemp
      \ HICARWakeup ASRResultTemp ASRResult cloudASRResult localASRResult
      \ startEnroll verifyVoiceprint SpeechWakeup LCSInit
      \ SpeechASRResultTemp SpeechASRResult SpeechEngineWakeup TSSAIBSWakeup
      \ TiTanASRResultTemp TiTanASRResult PSTTASRResultTemp PSTTASRResult
      \ VRConfig CarPlayWakeup CarPlayVadStart CarPlayVadEnd CarPlayStatus
      \ PISASRResult ResponseTTS PISAVedioText PISToolCall TSS ECNR
      \ FILEEXIT FILESIZE FILEMD5 FILEDIF LOG SUM

syntax match nanoAssertType /\<VoiceInput-SilenceTimeout\>/ contained

" ---------------------------------------------------------------------------
" 变量、参数、字面量
" ---------------------------------------------------------------------------

syntax match nanoParamVar /\${[A-Za-z_][A-Za-z0-9_]*}/
syntax match nanoEnvVar /{\%(WORKPATH\|ROOTPATH\|WORKSPACE\|BASEPATH\|LIBPATH\|CASEPATH\|LOGPATH\|SOCKETPATH\|CONFIGPATH\|CARPLAYCONFIG\|LCSCONFIG\|CASELIST\|PARAMETERIZEDATA\|SUITEID\|SUITENAME\|CASEID\|UUID\|TIMESTAMP\|NOW\)}/
syntax match nanoEvalVar /{EVAL:[^}]*}/

syntax region nanoTimeoutRegion start=/<timeout=/ end=/>/ contains=nanoTimeoutKeyword,nanoNumber,nanoOperator
syntax match nanoTimeoutKeyword /timeout/ contained

syntax match nanoChannel /\[[0-9]\+\]/

syntax match nanoNumber /\<-\=\d\+\(\.\d\+\)\?\%(ms\|s\|%\)\?>/
syntax keyword nanoBoolean true false True False
syntax keyword nanoNull None null NULL

syntax region nanoString start=/"/ skip=/\\"/ end=/"/ contains=nanoParamVar,nanoEnvVar,nanoEvalVar
syntax region nanoString start=/'/ skip=/\\'/ end=/'/ contains=nanoParamVar,nanoEnvVar,nanoEvalVar

" ---------------------------------------------------------------------------
" 参数与断言细节
" ---------------------------------------------------------------------------

syntax match nanoArgKey /\<[A-Za-z_][A-Za-z0-9_]*\ze=/
syntax match nanoFieldKey /\%(\[[0-9]\+\]\)\?\zs[A-Za-z_][A-Za-z0-9_.\[\]-]*\ze:/

syntax match nanoOperator />=\|<=\|==\|!=\|>\|<\|=\|:\|;/
syntax match nanoOperator /\V!~/
syntax match nanoOperator /\V~/
syntax match nanoOperator /@in\|@notin\|@i/

syntax keyword nanoSpecialKeyword SEARCH MATCH DIFF KV JSON EXTRACT EXISTS ABSENT COUNT
syntax keyword nanoModeKeyword cmn eng yue JSON LINE REPLACE DELETE TEXT CSV default

" VR 配置项（SETVRCONFIG / GET_VR_CONFIG 的第一个参数）
syntax match nanoVrConfigName /\%(\[\%(TSA\|SET\|TTS\|VOI\|OMS\|NIS\|NSE\)\]SETVRCONFIG\s\+\)\@<=\%(DEVICE_INFO\|VR_OPTION\|SHOW_STYLE\|WAKEUP_ALIAS\|DIALOGUE_STYLE\|DIALOGUE_LANGUAGE\|SOUND_AREA_OPTION\|WAKEUP_KEYWORD_OPTION\|VOICE_WAKEUP_OPTION\|WAKEUP_ENABLE\|GET_WAKEUP_WORD\|SET_TTS_VOICE_TYPE\|MULTI_DIALOGUE\|EXPERIENCE_IMPROVENMENT\|PERSONAL_SENSITIVE_AUTHORIZATION\|VOICE_SENSITIVE_AUTHORIZATION\|ACTIVE_INTERACTION\|SRE_SENSITIVE_EMPOWER_OPTION\|SRE_FUNC_ENABLE_OPTION\|SERVER_CACHE_LANGUAGE\|GPT_ENABLE_OPTION\|SRE_MEMORY\|VEHICLE_MEMORY\)\>/
syntax match nanoVrConfigName /\%(\[\%(TSA\|SET\|TTS\|VOI\|OMS\|NIS\|NSE\)\]GET_VR_CONFIG\s\+\)\@<=\%(DEVICE_INFO\|VR_OPTION\|SHOW_STYLE\|WAKEUP_ALIAS\|DIALOGUE_STYLE\|DIALOGUE_LANGUAGE\|SOUND_AREA_OPTION\|WAKEUP_KEYWORD_OPTION\|VOICE_WAKEUP_OPTION\|WAKEUP_ENABLE\|GET_WAKEUP_WORD\|SET_TTS_VOICE_TYPE\|MULTI_DIALOGUE\|EXPERIENCE_IMPROVENMENT\|PERSONAL_SENSITIVE_AUTHORIZATION\|VOICE_SENSITIVE_AUTHORIZATION\|ACTIVE_INTERACTION\|SRE_SENSITIVE_EMPOWER_OPTION\|SRE_FUNC_ENABLE_OPTION\|SERVER_CACHE_LANGUAGE\|GPT_ENABLE_OPTION\|SRE_MEMORY\|VEHICLE_MEMORY\)\>/

" ---------------------------------------------------------------------------
" 视觉风格
" ---------------------------------------------------------------------------

highlight default nanoComment          ctermfg=DarkGray guifg=#A0A0A0

highlight default nanoBlockMarker      ctermfg=180 guifg=#D7BA7D gui=bold cterm=bold
highlight default nanoFixtureKeyword   ctermfg=176 guifg=#C586C0 gui=bold cterm=bold
highlight default nanoParameterKeyword ctermfg=73 guifg=#4EC9B0 gui=bold cterm=bold
highlight default nanoParameterValue   ctermfg=114 guifg=#98C379
highlight default nanoRepeatCount      ctermfg=111 guifg=#61AFEF gui=bold cterm=bold

highlight default nanoClient           ctermfg=75 guifg=#569CD6 gui=bold cterm=bold
highlight default nanoExpClient        ctermfg=203 guifg=#E06C75 gui=bold cterm=bold
highlight default nanoCommand          ctermfg=114 guifg=#98C379 gui=bold cterm=bold
highlight default nanoAssertType       ctermfg=204 guifg=#E06C75 gui=bold cterm=bold

highlight default nanoEnvVar           ctermfg=114 guifg=#98C379
highlight default nanoParamVar         ctermfg=79 guifg=#7FD1B9
highlight default nanoEvalVar          ctermfg=80 guifg=#56B6C2 gui=italic cterm=italic
highlight default nanoTimeoutRegion    ctermfg=221 guifg=#E5C07B gui=bold cterm=bold
highlight default nanoTimeoutKeyword   ctermfg=221 guifg=#E5C07B gui=bold cterm=bold
highlight default nanoChannel          ctermfg=215 guifg=#D19A66 gui=bold cterm=bold

highlight default nanoNumber           ctermfg=151 guifg=#B5CEA8
highlight default nanoBoolean          ctermfg=151 guifg=#B5CEA8 gui=bold cterm=bold
highlight default nanoNull             ctermfg=181 guifg=#D19A66 gui=italic cterm=italic
highlight default nanoString           ctermfg=173 guifg=#CE9178
highlight default nanoFieldKey         ctermfg=117 guifg=#9CDCFE
highlight default nanoArgKey           ctermfg=222 guifg=#DCDCAA
highlight default nanoOperator         ctermfg=176 guifg=#C678DD
highlight default nanoSpecialKeyword   ctermfg=176 guifg=#C586C0 gui=bold cterm=bold
highlight default nanoModeKeyword      ctermfg=150 guifg=#A3BE8C
highlight default nanoVrConfigName     ctermfg=212 guifg=#FF79C6 gui=bold cterm=bold

let b:current_syntax = "nano_mgo"
