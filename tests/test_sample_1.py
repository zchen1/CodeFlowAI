import serial
import serial.tools.list_ports

def serial_communication(port, baudrate=9600, timeout=1):
    """
    串口通信基础函数
    :param port: 串口号（如COM3、/dev/ttyUSB0）
    :param baudrate: 波特率（默认9600，需与设备匹配）
    :param timeout: 读取超时时间（单位：秒）
    """
    ser = None
    try:
        # 1. 打开串口
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,  # 数据位：8位
            parity=serial.PARITY_NONE,  # 校验位：无
            stopbits=serial.STOPBITS_ONE,  # 停止位：1位
            timeout=timeout
        )
        
        if ser.is_open:
            print(f"成功打开串口：{port}")
            
            # 2. 发送数据（需转为字节流，示例发送"Hello Serial"）
            send_data = "Hello Serial".encode('utf-8')
            ser.write(send_data)
            print(f"已发送：{send_data.decode('utf-8')}")
            
            # 3. 接收数据（读取最多1024字节）
            recv_data = ser.read(1024)
            if recv_data:
                print(f"收到数据：{recv_data.decode('utf-8')}")
            else:
                print("未收到数据（可能超时）")
        
    except serial.SerialException as e:
        print(f"串口错误：{e}")  # 常见错误：串口号错误、设备被占用
    finally:
        # 4. 关闭串口（确保资源释放）
        if ser and ser.is_open:
            ser.close()
            print(f"已关闭串口：{port}")

# ------------------- 调用示例 -------------------
if __name__ == "__main__":
    # 步骤1：先获取电脑已连接的串口号（解决不知道端口的问题）
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("未检测到任何串口设备，请检查硬件连接！")
    else:
        print("已检测到的串口号：")
        for i, port in enumerate(ports):
            print(f"{i+1}. {port.device} - {port.description}")
        
        # 步骤2：手动输入要使用的串口号（如输入 COM3 或 /dev/ttyUSB0）
        target_port = input("请输入要操作的串口号：")
        # 步骤3：执行串口通信（波特率需与你的设备（如单片机）配置一致）
        serial_communication(port=target_port, baudrate=9600)