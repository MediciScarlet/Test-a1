import PCF8591 as ADC
import RPi.GPIO as GPIO
import time
import os
import pymysql


makerobo_DO = 17       # 光敏传感器管脚
GPIO.setmode(GPIO.BCM) # 管脚映射，采用BCM编码
makerobo_ds18b20 = ''  # ds18b20 设备
DHTPIN = 17

GPIO.setmode(GPIO.BCM)

MAX_UNCHANGE_COUNT = 100

STATE_INIT_PULL_DOWN = 1
STATE_INIT_PULL_UP = 2
STATE_DATA_FIRST_PULL_DOWN = 3
STATE_DATA_PULL_UP = 4
STATE_DATA_PULL_DOWN = 5



# 初始化工作
def makerobo_setup():
	ADC.setup(0x48)      # 设置PCF8591模块地址
	GPIO.setup(makerobo_DO, GPIO.IN) # 光敏传感器，设置为输入模式
	global makerobo_ds18b20  # 全局变量
	# 获取 ds18b20 地址
	for i in os.listdir('/sys/bus/w1/devices'):
		if i != 'w1_bus_master1':
			makerobo_ds18b20 = i       # ds18b20存放在ds18b20地址

# 读取ds18b20地址数据
def makerobo_read():
	makerobo_location = '/sys/bus/w1/devices/' + makerobo_ds18b20 + '/w1_slave' # 保存ds18b20地址信息
	makerobo_tfile = open(makerobo_location)  # 打开ds18b20
	makerobo_text = makerobo_tfile.read()     # 读取到温度值
	makerobo_tfile.close()                    # 关闭读取
	secondline = makerobo_text.split("\n")[1] # 格式化处理
	temperaturedata = secondline.split(" ")[9]# 获取温度数据
	temperature = float(temperaturedata[2:])  # 去掉前两位
	temperature = temperature / 1000          # 去掉小数点
	return temperature                        # 返回温度值



def read_dht11_dat():
	GPIO.setup(DHTPIN, GPIO.OUT)
	GPIO.output(DHTPIN, GPIO.HIGH)
	time.sleep(0.05)
	GPIO.output(DHTPIN, GPIO.LOW)
	time.sleep(0.02)
	GPIO.setup(DHTPIN, GPIO.IN, GPIO.PUD_UP)

	unchanged_count = 0
	last = -1
	data = []
	while True:
		current = GPIO.input(DHTPIN)
		data.append(current)
		if last != current:
			unchanged_count = 0
			last = current
		else:
			unchanged_count += 1
			if unchanged_count > MAX_UNCHANGE_COUNT:
				break

	state = STATE_INIT_PULL_DOWN

	lengths = []
	current_length = 0

	for current in data:
		current_length += 1

		if state == STATE_INIT_PULL_DOWN:
			if current == GPIO.LOW:
				state = STATE_INIT_PULL_UP
			else:
				continue
		if state == STATE_INIT_PULL_UP:
			if current == GPIO.HIGH:
				state = STATE_DATA_FIRST_PULL_DOWN
			else:
				continue
		if state == STATE_DATA_FIRST_PULL_DOWN:
			if current == GPIO.LOW:
				state = STATE_DATA_PULL_UP
			else:
				continue
		if state == STATE_DATA_PULL_UP:
			if current == GPIO.HIGH:
				current_length = 0
				state = STATE_DATA_PULL_DOWN
			else:
				continue
		if state == STATE_DATA_PULL_DOWN:
			if current == GPIO.LOW:
				lengths.append(current_length)
				state = STATE_DATA_PULL_UP
			else:
				continue
	if len(lengths) != 40:
		print ("Data not good, skip")
		return False

	shortest_pull_up = min(lengths)
	longest_pull_up = max(lengths)
	halfway = (longest_pull_up + shortest_pull_up) / 2
	bits = []
	the_bytes = []
	byte = 0

	for length in lengths:
		bit = 0
		if length > halfway:
			bit = 1
		bits.append(bit)
#	print ("bits: %s, length: %d" % (bits, len(bits)))
	for i in range(0, len(bits)):
		byte = byte << 1
		if (bits[i]):
			byte = byte | 1
		else:
			byte = byte | 0
		if ((i + 1) % 8 == 0):
			the_bytes.append(byte)
			byte = 0
#	print (the_bytes)
	checksum = (the_bytes[0] + the_bytes[1] + the_bytes[2] + the_bytes[3]) & 0xFF
	if the_bytes[4] != checksum:
		print ("Data not good, skip")
		return False

	return  the_bytes[0]

# 循环函数
def makerobo_loop():
	makerobo_status = 1 # 状态值
	# 无限循环
	while True:
		if makerobo_read() != None:  # 调用读取温度值，如果读到到温度值不为空
			print ("Current temperature : %0.3f C" % makerobo_read()) # 打印温度值
			result = read_dht11_dat()
			humidity = result
			print ("humidity: %s %%" % (humidity))
		a=ADC.read(0)
		print ('Photoresistor Value: ')
		print(a)

		sql = "insert into weather(time,temperature,humidity,sun) value('%s','%s',%s,'%s')" % (time.strftime('%Y-%m-%d',time.localtime(time.time())),makerobo_read(),humidity,a)
		print(sql)
		cur.execute(sql)
		conn.commit()
		time.sleep(0.2)

# 释放资源
def destroy():
	GPIO.cleanup()


# 程序入口
if __name__ == '__main__':
	conn=pymysql.connect(host='120.25.201.246',port=3306,user ='root',passwd = 'password',db ='project')
	cur=conn.cursor()
	print(cur)

#	cur.execute('drop table if exists weather')

	sql="""CREATE TABLE IF NOT EXISTS `weather` (

	`id` int(11) NOT NULL AUTO_INCREMENT,

	`time` varchar(40) NOT NULL,

	`temperature` varchar(10) NOT NULL,

	`humidity` varchar(10) NOT NULL,

	`sun`varchar(10) NOT NULL,

	PRIMARY KEY (`id`)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8 AUTO_INCREMENT=0""" # 表头内容

	cur.execute(sql)

	print('succeed')
	try:
		makerobo_setup() # 地址设置
		makerobo_loop()  # 调用无限循环
	except KeyboardInterrupt:
		destroy()             # 释放资源	