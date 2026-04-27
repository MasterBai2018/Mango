#ifndef  PACHIRA_SPEECH_ENGINE_SERVER_API_H_
#define  PACHIRA_SPEECH_ENGINE_SERVER_API_H_

#ifdef __cplusplus
extern "C" {
#endif

void ota_daemon_callback(const char* json_string, void *arg);
int start_SpeechEngine_service(const char *filename, const char *lang);
int set_speech_logpath(const char *log_path);
void set_speech_alone(int alone);
int stop_SpeechEngine_service();

#ifdef __cplusplus
};
#endif

#endif
