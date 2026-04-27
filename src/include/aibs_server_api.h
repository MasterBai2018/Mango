#ifndef __PACHIRA_AIBS_SERVER_API_H_
#define __PACHIRA_AIBS_SERVER_API_H_

#ifdef __cplusplus
extern "C" {
#endif

/*
* @breif:启动服务
* @param: config_path 配置文件路径
* @return: 成功返回0，失败返回-1
*/
int start_AIBSServer_service(const char *filename, const char *lang, const char *car_type);

int set_aibs_logpath(const char *log_path);

int stop_AIBSServer_service();

#ifdef __cplusplus
};
#endif

#endif
