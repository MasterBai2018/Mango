#ifndef _OTA_RESOURCE_TAG_SDK_H_
#define _OTA_RESOURCE_TAG_SDK_H_

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*ota_callback_t)(const char* result, void *arg);

/**
 * @brief 初始化OTAClientSDK，获取下一步动作
 * @param callback 回调函数
 * @param arg 回调函数参数
 * @param ota_config_path OTA配置文件路径(如: "./OTADaemon.conf")
 * @param name 服务名称 需要跟OTADaemon.conf中的name一致
 * @return 0: 调用成功, -1: 调用失败
 */
int ota_client_init(ota_callback_t callback, void *arg, const char *ota_config_path, const char* name);

/**
 * @brief 更新指定服务的状态标签 (tag)
 * @param status -1-2-3-4...:不同失败类型 0:成功 (ota_client_init回调动作是否执行成功)
 * @param data LCS下载文件后的文件压缩包路径，不涉及传空值
 *        e.g:/vdata/pachira/resource/lcs.zip
 * @param message 成功/错误原因
 * @return 0: 设置成功, -1: 设置失败
 */
int ota_client_set_state(int status, const char* data, const char* message);

#ifdef __cplusplus
};
#endif

#endif
