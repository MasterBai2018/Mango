import hashlib
import os
from src.utils.common import capture_library_output, parse_params
from ctypes import *
from loguru import logger
from pytest import Config
import time
from src.testsuite.NANO.dsl_engine import DSLCommand, Status
from src.utils.audio_rms_calculate import analyze_audio_rms


# 定义PNR配置结构体
class PNRConfigST(Structure):
    _fields_ = [
        ("type", c_char * 32),      # 设备标识
        ("mic_num", c_int),          # MIC数量
        ("mic_distance", c_int),     # MIC距离
        ("channel_num", c_int),      # 通道数量（含mic和reference）
    ]

class AIBSPNRDataST(Structure):
    _fields_ = [("input", POINTER(c_char)),
                ("output", POINTER(c_char))]

# CarInfoFor24MM（libNR_dynamic.so 内 C++ 修饰名，需与 so 符号一致）
_CARINFO_GET_INSTANCE = '_ZN8car_info14CarInfoFor24MM11getInstanceEv'
_CARINFO_SET_DEFAULT_AMP = '_ZN8car_info14CarInfoFor24MM17setDefaultAmpTypeEPKc'
_CARINFO_SET_DEFAULT_ECNR = '_ZN8car_info14CarInfoFor24MM18setDefaultEcnrTypeEPKc'


class ECNRClient():
    """ECNR客户端封装"""
    def __init__(self, client_name: str, lib_path: str, config: Config):
        self.client_name = client_name
        self.lib_path = os.path.join(lib_path, "libNR_dynamic.so")
        if not os.path.exists(self.lib_path):
            raise FileNotFoundError(f"libNR_dynamic.so不存在: {self.lib_path}")
        self.m_library = None
        self.downlink = 0
        self.m_engine = None  # 保存PNR引擎指针
        self.workMode = 0
        self.sampleRate = 16000
        self.config = config
        self.log_file_path = self._get_log_file_path()
        self.output_file_path = ""
        self.m_outputChannelNum = None
        self.mic_num = 4
        self.ref_num = 7
        self.pnr_config = None
        self.last_pnr_vec_name = None
        self._carinfo_get_instance = None
        self._carinfo_set_default_amp = None
        self._carinfo_set_default_ecnr = None
        # 初始化动态库
        self._load_library()

    def _load_library(self):
        """加载动态库并设置函数签名"""
        try:
            self.m_library = cdll.LoadLibrary(self.lib_path)
            
            # 设置 create_pnr_engine 函数签名
            self.m_library.create_pnr_engine.argtypes = [POINTER(PNRConfigST)]
            self.m_library.create_pnr_engine.restype = c_void_p
            
            # 设置 create_linein_pnr_engine 函数签名
            self.m_library.create_linein_pnr_engine.argtypes = [POINTER(PNRConfigST)]
            self.m_library.create_linein_pnr_engine.restype = c_void_p
            
            # 设置 start_pnr_engine 函数签名
            self.m_library.start_pnr_engine.argtypes = [c_void_p, c_int, c_int, c_int, c_int, c_int]
            self.m_library.start_pnr_engine.restype = c_int
            
            # 设置 start_linein_pnr_engine 函数签名
            self.m_library.start_linein_pnr_engine.argtypes = [c_void_p, c_int, c_int, c_int, c_int, c_int]
            self.m_library.start_linein_pnr_engine.restype = c_int
            
            # 设置 set_pnr_work_mode 函数签名
            self.m_library.set_pnr_work_mode.argtypes = [c_void_p, c_int, c_int]
            self.m_library.set_pnr_work_mode.restype = c_int
            
            # 设置 set_linein_pnr_work_mode 函数签名
            self.m_library.set_linein_pnr_work_mode.argtypes = [c_void_p, c_int, c_int, c_int]
            self.m_library.set_linein_pnr_work_mode.restype = c_int
            
            # 设置 free_pnr_engine 函数签名
            self.m_library.free_pnr_engine.argtypes = [c_void_p]
            self.m_library.free_pnr_engine.restype = c_int
            
            # 设置 free_linein_pnr_engine 函数签名
            self.m_library.free_linein_pnr_engine.argtypes = [c_void_p]
            self.m_library.free_linein_pnr_engine.restype = c_int

            self.m_library.process_pnr_data.argtypes = [c_void_p, POINTER(AIBSPNRDataST), c_int, c_long]
            self.m_library.process_pnr_data.restype = c_int

            self.m_library.process_linein_data.argtypes = [c_void_p, POINTER(AIBSPNRDataST), c_int, c_long]
            self.m_library.process_linein_data.restype = c_int

            self.m_library.get_pnr_vec_name.argtypes = [c_void_p]
            self.m_library.get_pnr_vec_name.restype = c_char_p

            self._bind_carinfo_symbols()
            
        except Exception as e:
            logger.error(f"[{self.client_name}] 加载库失败: {e}")
            raise

    def _bind_carinfo_symbols(self):
        try:
            self._carinfo_get_instance = getattr(self.m_library, _CARINFO_GET_INSTANCE)
            self._carinfo_get_instance.argtypes = []
            self._carinfo_get_instance.restype = c_void_p

            self._carinfo_set_default_amp = getattr(self.m_library, _CARINFO_SET_DEFAULT_AMP)
            self._carinfo_set_default_amp.argtypes = [c_void_p, c_char_p]
            self._carinfo_set_default_amp.restype = None

            self._carinfo_set_default_ecnr = getattr(self.m_library, _CARINFO_SET_DEFAULT_ECNR)
            self._carinfo_set_default_ecnr.argtypes = [c_void_p, c_char_p]
            self._carinfo_set_default_ecnr.restype = None
        except AttributeError as e:
            logger.warning(f"[{self.client_name}] CarInfo 符号未找到，AMP_TYPE/ECNR_TYPE 将不可用: {e}")
            self._carinfo_get_instance = None
            self._carinfo_set_default_amp = None
            self._carinfo_set_default_ecnr = None

    def _ensure_carinfo_singleton(self):
        if not self._carinfo_get_instance:
            raise RuntimeError('CarInfo::getInstance 未绑定，请确认 libNR_dynamic.so 已导出该符号')
        this = self._carinfo_get_instance()
        if not this:
            raise RuntimeError('CarInfo::getInstance 返回 NULL')
        return this

    def _decode_c_str(self, p) -> str:
        if p is None:
            return ''
        raw = p.value if hasattr(p, 'value') else p
        if raw is None:
            return ''
        if isinstance(raw, bytes):
            return raw.decode('utf-8', errors='replace')
        return str(raw)

    def _read_pnr_vec_name(self) -> str:
        if not self.m_engine:
            return ''
        p = self.m_library.get_pnr_vec_name(self.m_engine)
        return self._decode_c_str(p)
    
    def _get_log_file_path(self):
        """获取日志文件路径"""
        if self.config and hasattr(self.config, 'log_path'):
            return os.path.join(self.config.log_path, "ecnr_library.log")
        elif self.config and hasattr(self.config, 'base_dir'):
            return os.path.join(self.config.base_dir, "ecnr_library.log")
        return None
    
    def set_downlink(self, command: DSLCommand) -> int:
        """
        SET_DOWNLINK接口 - 设置下行链接模式
        DSL格式: [ENR]SET_DOWNLINK downLink
        
        Args:
            command: DSL指令对象，params=[downLink]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            if len(command.params) < 1:
                logger.error(f"[{self.client_name}] SET_DOWNLINK参数不足，需要1个参数，实际: {len(command.params)}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_DOWNLINK参数不足'
                return -1
            
            downLink = int(command.params[0]) if str(command.params[0]).isdigit() else 0
            if downLink not in [0, 1]:
                logger.error(f"[{self.client_name}] SET_DOWNLINK参数错误，downLink只能为0或1，实际: {downLink}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_DOWNLINK参数错误，downLink只能为0或1'
                return -1
            self.downlink = downLink
            
            command.status = Status.PASSED
            command.message = f'[{self.client_name}] SET_DOWNLINK执行成功: {downLink}'
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_DOWNLINK执行异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_DOWNLINK执行异常: {str(e)}'
            return -1

    def amp_type(self, command: DSLCommand) -> int:
        """
        CarInfo 默认功放类型（CREATE 前调用）
        DSL: [ENR]AMP_TYPE 0  -> setDefaultAmpType("0")
        """
        try:
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] AMP_TYPE 需要 1 个参数'
                return -1
            v = str(command.params[0]).strip().replace('"', '').replace("'", '')
            if v not in ('0', '1', '2', '3', '4', '5', '6', '7', '8'):
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] AMP_TYPE 参数须为 0-8，实际: {v}'
                return -1
            if not self._carinfo_set_default_amp:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] AMP_TYPE: CarInfo 符号不可用'
                return -1
            with capture_library_output(self.log_file_path):
                this = self._ensure_carinfo_singleton()
                self._carinfo_set_default_amp(this, v.encode('utf-8'))
            command.status = Status.PASSED
            command.message = f'[{self.client_name}] AMP_TYPE={v} 成功'
            return 0
        except Exception as e:
            logger.error(f"[{self.client_name}] AMP_TYPE 异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] AMP_TYPE 异常: {e}'
            return -1

    def ecnr_type(self, command: DSLCommand) -> int:
        """
        CarInfo 默认 ECNR 类型（CREATE 前调用）
        DSL: [ENR]ECNR_TYPE 450D -> setDefaultEcnrType("450D")
        """
        try:
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] ECNR_TYPE 需要 1 个参数'
                return -1
            v = str(command.params[0]).strip().replace('"', '').replace("'", '')
            if not self._carinfo_set_default_ecnr:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] ECNR_TYPE: CarInfo 符号不可用'
                return -1
            with capture_library_output(self.log_file_path):
                this = self._ensure_carinfo_singleton()
                self._carinfo_set_default_ecnr(this, v.encode('utf-8'))
            command.status = Status.PASSED
            command.message = f'[{self.client_name}] ECNR_TYPE={v} 成功'
            return 0
        except Exception as e:
            logger.error(f"[{self.client_name}] ECNR_TYPE 异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] ECNR_TYPE 异常: {e}'
            return -1
    
    def create(self, command: DSLCommand) -> int:
        """
        CREATE接口 - 创建ECNR引擎
        DSL格式: [ENR]CREATE [device:lexus_2S;micNum:4;refNum:7;micDistance:560]
        
        Args:
            command: DSL指令对象，params可选，如果提供则格式为: key:value;key:value;...
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 检查库是否已加载
            if self.m_library is None:
                logger.error(f"[{self.client_name}] 动态库未加载")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 动态库未加载'
                return -1
            
            params_dict = parse_params(command.params)
            
            device = str(params_dict.get('device', 'lexus_2S'))
            micNum = int(params_dict.get('micNum', '4'))
            refNum = int(params_dict.get('refNum', '7'))
            self.mic_num = micNum
            self.ref_num = refNum
            micDistance = int(float(params_dict.get('micDistance', '802')))

            # CREATE 前初始化 CarInfo 单例（与 show_vec 一致）
            if self._carinfo_get_instance:
                with capture_library_output(self.log_file_path):
                    try:
                        self._ensure_carinfo_singleton()
                    except Exception as e:
                        logger.warning(f"[{self.client_name}] CREATE 前 CarInfo 初始化失败（可忽略）: {e}")
            
            # 准备PNR配置结构体
            self.pnr_config = PNRConfigST()
            self.pnr_config.type = str(device).encode('utf-8')[:31]  # 设备类型，最多31字节
            self.pnr_config.mic_num = micNum
            self.pnr_config.mic_distance = micDistance
            self.pnr_config.channel_num = micNum + refNum

            # 使用上下文管理器重定向库输出
            with capture_library_output(self.log_file_path):
                if self.downlink == 1:
                    self.m_engine = self.m_library.create_linein_pnr_engine(byref(self.pnr_config))
                else:
                    self.m_engine = self.m_library.create_pnr_engine(byref(self.pnr_config))
            
            if self.m_engine is None:
                error_msg = f"Create pnr engine failed, returned NULL"
                logger.error(f"[{self.client_name}] {error_msg}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] CREATE执行异常: {error_msg}'
                return -1
            
            command.status = Status.PASSED
            command.message = f'[{self.client_name}] CREATE执行成功'
            return 0
            
        except IndexError as e:
            logger.error(f"[{self.client_name}] CREATE参数解析错误: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CREATE参数解析错误: {str(e)}'
            return -1
        except Exception as e:
            logger.error(f"[{self.client_name}] CREATE执行异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CREATE执行异常: {str(e)}'
            return -1

    
    def start(self, command: DSLCommand) -> int:
        try:
            params_dict = parse_params(command.params)
            channelMask = int(params_dict.get('channelMask', '15'))
            synthMethod = int(params_dict.get('synthMethod', '1'))
            self.m_outputChannelNum = self.output_channel(channelMask)
            # 使用上下文管理器重定向库输出
            with capture_library_output(self.log_file_path):
                if self.downlink == 1:
                    # LineIn模式
                    # 启动LineIn PNR引擎
                    s_ret = self.m_library.start_linein_pnr_engine(
                        self.m_engine,
                        self.sampleRate,
                        self.sampleRate,
                        16,  # audio_format
                        channelMask,
                        synthMethod
                    )
                    if s_ret != 0:
                        error_msg = f"Start linein pnr engine failed, code: {s_ret}"
                        logger.error(f"[{self.client_name}] {error_msg}")
                        raise Exception(error_msg)
                else:
                    s_ret = self.m_library.start_pnr_engine(
                        self.m_engine,
                        self.sampleRate,
                        self.sampleRate,
                        16,  # audio_format
                        channelMask,
                        synthMethod
                    )
                    if s_ret != 0:
                        error_msg = f"Start pnr engine failed, code: {s_ret}"
                        logger.error(f"[{self.client_name}] {error_msg}")
                        raise Exception(error_msg) 
            
            command.status = Status.PASSED
            command.message = f'[{self.client_name}] START执行成功'
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] START执行异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] START执行异常: {str(e)}'
            return -1
    
    def set_work_mode(self, command: DSLCommand) -> int:
        """
        SET_WORK_MODE接口 - 设置ECNR引擎工作模式
        DSL格式: [ECNR]SET_WORK_MODE workMode
        Args:
            command: DSL指令对象，params=[workMode]
        Returns:
            0: 成功, -1: 失败
        """
        try:
            params_dict = parse_params(command.params)
            workMode = int(params_dict.get('workMode', '0'))
            if workMode not in [0,1,2,3,4,5,6,7,8,9,10,11,21]:
                logger.error(f"[{self.client_name}] SET_WORK_MODE参数错误，workMode只能为0-11或21，实际: {workMode}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_WORK_MODE参数错误，workMode只能为0-11或21'
                return -1
            self.sampleRate = int(params_dict.get('sampleRate', '16000'))
            spectrum = int(params_dict.get('spectrum', '8000'))

            # 使用上下文管理器重定向库输出
            with capture_library_output(self.log_file_path):
                if self.downlink == 1:
                    result =  self.m_library.set_linein_pnr_work_mode(self.m_engine, c_int(workMode), c_int(self.sampleRate), c_int(spectrum))
                else:
                    result =  self.m_library.set_pnr_work_mode(self.m_engine, c_int(workMode), c_int(self.sampleRate))
            if result != 0:
                self.last_pnr_vec_name = None
                logger.error(f"[{self.client_name}] SET_WORK_MODE执行失败，code: {result}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_WORK_MODE执行失败，code: {result}'
                return -1
            self.last_pnr_vec_name = self._read_pnr_vec_name()
            command.vec_name = self.last_pnr_vec_name
            command.return_code = result
            command.status = Status.PASSED if result == 0 else Status.ERROR
            if self.last_pnr_vec_name:
                command.message = f'[{self.client_name}] SET_WORKMODE 成功, VEC={self.last_pnr_vec_name}'
            return result
        except Exception as e:
            self.last_pnr_vec_name = None
            logger.error(f"[{self.client_name}] SET_WORK_MODE执行异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_WORK_MODE执行异常: {str(e)}'
            return -1
    
    def data(self, command: DSLCommand) -> int:
        """
        DATA接口 - 发送音频数据
        DSL格式: [ECNR]DATA data
        上行：输入为与 CREATE 的 channel_num 一致的交织多声道（每帧字节=channel_num×单通道帧字节）。
        下行 linein：与 PreProcessAPI::processLineinData 一致，每次只送入单声道 m_dataLen=单通道帧字节
        （memcpy 到 mic_data[0]），输入应为单声道 PCM/WAV；库每次仅写回 m_dataLen 到 output（多路 mask 时
        仅首路有效数据以当前 NR 实现为准）。
        Args:
            command: DSL指令对象，params=[data]
        Returns:
            0: 成功, -1: 失败
        """
        try:
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] DATA指令缺少音频文件路径'
                return -1
            audio_path = command.params[0]
            output_path = self.config.base_dir
            output_path = os.path.join(output_path, "nr_audios")
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            if not os.path.exists(audio_path):
                logger.error(f"[{self.client_name}] 音频文件不存在: {audio_path}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 音频文件不存在: {audio_path}'
                return -1
                
            # 帧长：上行/下行分别用对应 API（底层通常同为 getFrameSize，语义与引擎类型一致）
            self.m_library.get_pnr_frame_size.argtypes = [c_void_p]
            self.m_library.get_pnr_frame_size.restype = c_int
            self.m_library.get_linein_pnr_frame_size.argtypes = [c_void_p]
            self.m_library.get_linein_pnr_frame_size.restype = c_int
            if self.downlink == 1:
                t_frame = self.m_library.get_linein_pnr_frame_size(self.m_engine)
            else:
                t_frame = self.m_library.get_pnr_frame_size(self.m_engine)
            channel_frame_length = self.sampleRate * 2 // 1000 * t_frame
            n_samples_out = channel_frame_length // 2
            output_length = channel_frame_length * self.m_outputChannelNum
            # 上行：整帧交织 = 参考通道数 × 单通道帧；下行 linein：NR 每包只吃单通道一帧（见 NR PreProcessAPI::processLineinData）
            multich_frame_size = int(self.pnr_config.channel_num) * channel_frame_length
            linein_chunk_bytes = channel_frame_length
            audio_length = os.path.getsize(audio_path)
            self.output_file_path = os.path.join(output_path, os.path.splitext(os.path.basename(audio_path))[0] + ".pcm")
            with open(audio_path, 'rb') as fp:
                # 获取文件头信息
                header = fp.read(100)
                if header[:4] == b"RIFF":
                    import re
                    # 如果是wav文件，则获取头信息中的音频长度
                    pos = re.search(b'data', header).end()
                    audio_length = int.from_bytes(header[pos:pos + 4], byteorder='little')
                    # 将文件指针移动到音频数据的起始位置
                    fp.seek(pos + 4, 0)
                else:
                    # PCM文件，从头开始读取
                    fp.seek(0, 0)
                with open(self.output_file_path, "wb") as output_file:
                    timestamp = 0
                    remaining_bytes = audio_length
                    _feed_idx = 0
                    chunk_expect = linein_chunk_bytes if self.downlink == 1 else multich_frame_size
                    logger.info(
                        f"[{self.client_name}] DATA: downlink={self.downlink} 每包期望读入={chunk_expect}B "
                        f"(上行整帧={multich_frame_size}B, 下行单声道帧={linein_chunk_bytes}B) "
                        f"t_frame={t_frame} channel_frame_length={channel_frame_length}"
                    )
                    while remaining_bytes > 0:
                        need = linein_chunk_bytes if self.downlink == 1 else multich_frame_size
                        if remaining_bytes >= need:
                            raw = fp.read(need)
                        else:
                            raw = fp.read(remaining_bytes)
                        if not raw:
                            break
                        consumed = len(raw)
                        # 方案A：无论上下行，尾包不足整帧时都补零，避免C库按整帧读取出现未定义行为
                        if self.downlink == 1 and consumed < linein_chunk_bytes:
                            raw = raw + b"\x00" * (linein_chunk_bytes - consumed)
                        elif self.downlink == 0 and consumed < multich_frame_size:
                            raw = raw + b"\x00" * (multich_frame_size - consumed)
                        buffer = raw
                        _feed_idx += 1
                        nr_data = AIBSPNRDataST()
                        nr_data.input = cast(create_string_buffer(buffer), POINTER(c_char))
                        nr_data.output = cast(create_string_buffer(b"\x00" * output_length), POINTER(c_char))

                        timestamp += 10
                        if self.downlink == 1:
                            ret = self.m_library.process_linein_data(self.m_engine, pointer(nr_data), t_frame, timestamp)
                        else:
                            ret = self.m_library.process_pnr_data(self.m_engine, pointer(nr_data), t_frame, timestamp)

                        if ret == 0:
                            offset = 0
                            channel_list = []
                            for i in range(self.m_outputChannelNum):
                                channel_list.append(nr_data.output[offset:offset+channel_frame_length])
                                offset += channel_frame_length
                            
                            offset_bytes = 0
                            for _ in range(n_samples_out):
                                for data in channel_list:
                                    output_file.write(data[offset_bytes:offset_bytes+2])
                                offset_bytes += 2
                        else:
                            # 处理失败
                            logger.error(f"[{self.client_name}] process nr data failed or the current task don't need the rest of data. ret={ret}")
                            command.status = Status.ERROR
                            command.message = f'[{self.client_name}] DATA处理失败: ret={ret}'
                            return -1

                        remaining_bytes -= consumed
                        if remaining_bytes <= 0:
                            break

                    logger.info(f"[{self.client_name}] DATA 结束: 共送库 {_feed_idx} 次, 音频payload={audio_length}B")

                digest = hashlib.md5()
                with open(self.output_file_path, 'rb') as out_fp:
                    for chunk in iter(lambda: out_fp.read(1024 * 1024), b''):
                        digest.update(chunk)
                command.md5 = digest.hexdigest()
                command.return_code = 0
                command.status = Status.PASSED
                command.message = f'[{self.client_name}] DATA执行成功, output_md5={command.md5}'
            return 0
        except Exception as e:
            logger.error(f"[{self.client_name}] DATA执行异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] DATA执行异常: {str(e)}'
            return -1
    
    def free(self, command: DSLCommand) -> int:
        """
        FREE接口 - 释放ECNR引擎资源
        
        Args:
            command: DSL指令对象
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            if self.m_engine is None:
                logger.warning(f"[{self.client_name}] 引擎未创建，无需释放")
                command.status = Status.PASSED
                command.message = f'[{self.client_name}] 引擎未创建'
                return 0
            # 使用上下文管理器重定向库输出
            with capture_library_output(self.log_file_path):
                if self.downlink == 1:
                    ret = self.m_library.free_linein_pnr_engine(self.m_engine)
                else:
                    ret = self.m_library.free_pnr_engine(self.m_engine)
            if ret != 0:
                error_msg = f"Free pnr engine failed, code: {ret}"
                logger.error(f"[{self.client_name}] {error_msg}")
                raise Exception(error_msg)            
            self.m_engine = None
            command.status = Status.PASSED
            command.message = f'[{self.client_name}] FREE执行成功'
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] FREE执行异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] FREE执行异常: {str(e)}'
            return -1

    def set_pnr_mic_mute_option(self, command: DSLCommand):
        params_dict = parse_params(command.params)
        option = int(params_dict.get('option', '0'))
        if option not in [0, 1]:
            logger.error(f"[{self.client_name}] SET_PNR_MIC_MUTE_OPTION参数错误，option只能为0或1，实际: {option}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_PNR_MIC_MUTE_OPTION参数错误，option只能为0或1'
            return -1
        result = self.m_library.set_pnr_mic_mute_option(self.m_engine, option)
        if result != 0:
            logger.error(f"[{self.client_name}] SET_PNR_MIC_MUTE_OPTION执行失败，code: {result}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_PNR_MIC_MUTE_OPTION执行失败，code: {result}'
            return -1
        command.status = Status.PASSED if result == 0 else Status.ERROR
        return result

    def set_pnr_enable_option(self, command: DSLCommand):
        params_dict = parse_params(command.params)
        option = int(params_dict.get('option', '0'))
        if option not in [0, 1]:
            logger.error(f"[{self.client_name}] SET_PNR_ENABLE_OPTION参数错误，option只能为0或1，实际: {option}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_PNR_ENABLE_OPTION参数错误，option只能为0或1'
            return -1
        result = self.m_library.set_pnr_enable_option(self.m_engine, option)
        if result != 0:
            logger.error(f"[{self.client_name}] SET_PNR_ENABLE_OPTION执行失败，code: {result}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_PNR_ENABLE_OPTION执行失败，code: {result}'
            return -1
        command.status = Status.PASSED if result == 0 else Status.ERROR
        return result

    def set_pnr_audio_quality(self, command: DSLCommand):
        params_dict = parse_params(command.params)
        quality = int(params_dict.get('quality', '0'))
        result = self.m_library.set_pnr_audio_quality(self.m_engine, quality)
        if result != 0:
            logger.error(f"[{self.client_name}] SET_PNR_AUDIO_QUALITY执行失败，code: {result}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_PNR_AUDIO_QUALITY执行失败，code: {result}'
            return -1
        command.status = Status.PASSED if result == 0 else Status.ERROR
        return result

    def get_pnr_version(self, command: DSLCommand):
        self.m_library.get_pnr_version.argtypes = [c_void_p]
        self.m_library.get_pnr_version.restype = c_char_p
        version = self.m_library.get_pnr_version(self.m_engine)
        version = version.decode('utf-8') if version else "未知版本"
        command.return_code = version
        command.status = Status.PASSED if version != None else Status.ERROR
        return 

    def get_pnr_HFT_param(self, command: DSLCommand):
        self.m_library.get_pnr_HFT_param.argtypes = [c_void_p]
        self.m_library.get_pnr_HFT_param.restype = c_char_p
        param = self.m_library.get_pnr_HFT_param(self.m_engine)
        command.return_code = param
        command.status = Status.PASSED if param != None else Status.ERROR
        return param

    def get_pnr_MVR_param(self, command: DSLCommand):
        self.m_library.get_pnr_MVR_param.argtypes = [c_void_p]
        self.m_library.get_pnr_MVR_param.restype = c_char_p
        param = self.m_library.get_pnr_MVR_param(self.m_engine)
        command.return_code = param
        command.status = Status.PASSED if param != None else Status.ERROR
        return param

    def get_pnr_Gen_param(self, command: DSLCommand):
        self.m_library.get_pnr_Gen_param.argtypes = [c_void_p]
        self.m_library.get_pnr_Gen_param.restype = c_char_p
        param = self.m_library.get_pnr_Gen_param(self.m_engine)
        command.return_code = param
        command.status = Status.PASSED if param != None else Status.ERROR
        return param

    def get_pnr_frame_size(self, command: DSLCommand):
        self.m_library.get_pnr_frame_size.argtypes = [c_void_p]
        self.m_library.get_pnr_frame_size.restype = c_int
        frame_size = self.m_library.get_pnr_frame_size(self.m_engine)
        command.return_code = frame_size
        command.status = Status.PASSED if frame_size != None else Status.ERROR
        return frame_size

    def get_linein_pnr_frame_size(self, command: DSLCommand):
        self.m_library.get_linein_pnr_frame_size.argtypes = [c_void_p]
        self.m_library.get_linein_pnr_frame_size.restype = c_int
        frame_size = self.m_library.get_linein_pnr_frame_size(self.m_engine)
        command.return_code = frame_size
        command.status = Status.PASSED if frame_size != None else Status.ERROR
        return frame_size
    
    def output_channel(self, number: int) -> int:
        binary_representation = bin(number)[2:]
        count_of_ones = binary_representation.count('1')
        return count_of_ones if count_of_ones != None else 0

    def analyze_audio_data(self, command):
        if not os.path.exists(self.output_file_path):
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] ANALYZE_AUDIO_DATA 失败：输出文件不存在: {self.output_file_path}'
            logger.error(command.message)
            return -1

        params_dict = parse_params(command.params)
        channel = int(params_dict.get('channel', '0'))
        if 'start' not in params_dict or 'end' not in params_dict:
            command.status = Status.ERROR
            command.message = (
                f'[{self.client_name}] ANALYZE_AUDIO_DATA 参数错误：'
                f'必须同时提供 start 和 end，当前参数: {command.params}'
            )
            logger.error(command.message)
            return -1
        try:
            start = float(params_dict['start'])
            end = float(params_dict['end'])
            voice_regions = [{"label": "1", "channel": channel, "start": start, "end": end}]
            results = analyze_audio_rms(
                self.output_file_path,
                self.sampleRate,
                16,
                self.mic_num,
                0,
                voice_regions,
            )
            result = None
            for _, metrics in results.items():
                result = {
                    "total_rms_dbfs": float(metrics['total_rms_dbfs']),
                    "max_rms_dbfs": float(metrics['max_rms_dbfs']),
                    "min_rms_dbfs": float(metrics['min_rms_dbfs']),
                    "avg_rms_dbfs": float(metrics['avg_rms_dbfs']),
                    "peak_amplitude": float(metrics['peak_amplitude'])
                }
                break
            if result is None:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] ANALYZE_AUDIO_DATA 失败：未提取到有效RMS结果'
                logger.error(command.message)
                return -1

            command.status = Status.PASSED
            command.message = f'[{self.client_name}] ANALYZE_AUDIO_DATA 执行成功'
            return result
        except Exception as e:
            logger.error(f"[{self.client_name}] ANALYZE_AUDIO_DATA 异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] ANALYZE_AUDIO_DATA 异常: {str(e)}'
            return -1