import _pickle as pickle
import numpy as np
import pandas as pd
import os
from src.data_type import config as data_type

dataPath = "data/"
projectPath = dataPath + "rlb-dp/"

ipinyouPath = dataPath + "ipinyou-data/"

ipinyou_camps = [data_type['campaign_id'].split('/')[0]]

logPath = 'result/' + ipinyou_camps[0] + '/' + data_type['type']

if not os.path.exists(logPath):
	os.mkdir(logPath)
elif not os.path.exists(ipinyouPath + ipinyou_camps[0] + '/bid-model/'):
	os.mkdir(ipinyouPath + ipinyou_camps[0] + '/bid-model/')

ipinyou_max_market_price = 300

info_keys = ["imp_test", "cost_test", "clk_test", "imp_train", "cost_train", "clk_train", "field", "dim", "price_counter_train"]

def price_counter_train(train_data):
	price_counter_train = []
	for i in range(0, 301):
		sum_price = np.sum(train_data.iloc[:, 1].isin([i]))
		price_counter_train.append(sum_price)
	return price_counter_train

# info_keys:imp_test   cost_test   clk_test    clk_train   imp_train   field   cost_train  dim  price_counter_train
def get_camp_info(camp, src="ipinyou"):
	if src == "ipinyou":
		info = pickle.load(open(ipinyouPath + camp + "/info.txt", "rb"))

		train_data = pd.read_csv(ipinyouPath + camp + "/train.theta." + data_type['type'] + ".txt", header=None)
		test_data = pd.read_csv(ipinyouPath + camp + "/test.theta." + data_type['type'] + ".txt", header=None)
		train_data.iloc[:, :] = train_data.iloc[:, :].astype(float)
		test_data.iloc[:, :] = test_data.iloc[:, :].astype(float)

		# info['cost_train'], info['cost_test'] = np.sum(train_data.iloc[:, 1]), np.sum(test_data.iloc[:, 1])
		info['cost_train'], info['cost_test'] = 32000000, 32000000
		info['imp_train'], info['imp_test'] = len(train_data), len(test_data)  # 155443, 145396
		info['clk_train'], info['clk_test'] = int(np.sum(train_data.iloc[:, 0])), int(np.sum(test_data.iloc[:, 0]))
		info['price_counter_train'] = price_counter_train(train_data)

	return info

