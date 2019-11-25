import pandas as pd
import numpy as np
import random
import os
from src.data_type import config as data_type

random.seed(1)

def generate_data(campaign_id):
    # 生成FAB使用的原始数据
    train_log = pd.read_csv(campaign_id + '/11_log.csv') # ipinyou 2013/06/11作为训练集
    test_log = pd.read_csv(campaign_id + '/12_log.csv') # ipinyou 2013/06/12作为测试集

    train_ctr = pd.read_csv(campaign_id + '/11_test_submission.csv') # ipinyou 2013/06/11训练集的预测点击率文件
    test_ctr = pd.read_csv(campaign_id + '/12_test_submission.csv') # ipinyou 2013/06/12测试集的预测点击率文件

    train_log_values = train_log.values
    train_data = {'ctr': train_ctr.values[:, 1] * 1000, 'clk': train_log_values[:, 0],
                  'market_price': train_log_values[:, 23], 'hour': train_log_values[:, 2], 'pctr': train_ctr.values[:, 1], 'minutes': train_log_values[:, 4]}
    test_log_values = test_log.values
    test_data = {'ctr': test_ctr.values[:, 1] * 1000, 'clk': test_log_values[:, 0],
                  'market_price': test_log_values[:, 23], 'hour': test_log_values[:, 2], 'pctr': test_ctr.values[:, 1], 'minutes': test_log_values[:, 4]}

    train_data_df = pd.DataFrame(data=train_data)
    train_data_df.to_csv(campaign_id + '/train_data.csv', index=None)
    test_data_df = pd.DataFrame(data=test_data)
    test_data_df.to_csv(campaign_id + '/test_data.csv', index=None)

    print(len(train_data_df), np.sum(train_data_df.iloc[:, 1]), np.sum(train_data_df.iloc[:, 2]))
    print(len(test_data_df), np.sum(test_data_df.iloc[:, 1]), np.sum(test_data_df.iloc[:, 2]))

    test_clks = np.sum(test_data_df.iloc[:, 1])
    test_auc_nums = len(test_data_df)

    return test_clks, test_auc_nums

# 对原始数据进行负采样，以对比FAB是否对环境具有动态适应性
def down_sample(campaign_id, test_clks, test_auc_nums):
    # 负采样后达到的点击率
    CLICK_RATE = 0.001  # 1:1000

    train_data = pd.read_csv(campaign_id + '/train_data.csv')
    train_data.to_csv(campaign_id + '/train_sample.csv', index=None) # 训练集保持不变

    click = test_clks
    total = test_auc_nums
    test_sample_rate = click / (CLICK_RATE * (total - click))
    # 原始数据中的点击和曝光总数
    print('clicks: {0} impressions: {1}\n'.format(click, total))
    print('test_sample_rate is:', test_sample_rate)

    # 获取训练样本
    test_sample_rate = test_sample_rate

    # 获取测试样本
    with open(campaign_id + '/test_sample.csv', 'w') as fo:
        fi = open(campaign_id + '/test_data.csv')
        p = 0  # 原始正样本
        n = 0  # 原始负样本
        nn = 0  # 剩余的负样本
        c = 0  # 总数
        for t, line in enumerate(fi, start=1):
            if t == 1:
                fo.write(line)
            else:
                c += 1
                label = line.split(',')[1]  # 是否点击标签
                if int(label) == 0:
                    n += 1
                    if random.randint(0, test_auc_nums) <= test_auc_nums * test_sample_rate:  # down sample, 选择对应数据量的负样本
                        fo.write(line)
                        nn += 1
                else:
                    p += 1
                    fo.write(line)

            if t % 10000 == 0:
                print(t)
        fi.close()
    print('测试数据负采样完成')

def all_sample(campaign_id):
    train_data = pd.read_csv(campaign_id + '/train_data.csv')
    train_data.to_csv(campaign_id + '/train_sample.csv', index=None)  # 训练集保持不变

    test_data = pd.read_csv(campaign_id + '/test_data.csv')

    if campaign_id == '1458':
        sample_rate = 1 - (356549 / len(test_data)) # 选择某几行删除
    else:
        sample_rate =  1- (355530 / len(test_data))

    sample_test_data = np.array([[]])
    for i in range(24):
        current_time_data = test_data[test_data.iloc[:, 3] == i]
        current_time_data = current_time_data.reset_index(drop=True) # 重新生成索引；如果用reindex方法后净会根据新索引进行重排，如果某个索引值当前不存在，就会引入缺失值NAN

        drop_sample_index = np.random.choice(len(current_time_data), size=int(len(current_time_data) * sample_rate), replace=False).tolist()
        temp_current_test_data = current_time_data.drop(drop_sample_index, axis=0)
        if i == 0:
            sample_test_data = temp_current_test_data
        else:
            sample_test_data = pd.concat([sample_test_data, temp_current_test_data])

    columns = ['ctr', 'clk', 'market_price', 'hour', 'pctr', 'minutes']
    sample_test_data_df = pd.DataFrame(data=sample_test_data, columns=columns)

    sample_test_data_df.to_csv(campaign_id + '/test_sample.csv', index=None)

# 生成DRLB所需的数据
def to_DRLB_data(campaign_id, type, train_data, test_data):
    DRLB_data_path = '../src/DRLB/data/'
    if not os.path.exists(DRLB_data_path):
        os.mkdir(DRLB_data_path)
    elif not os.path.exists(DRLB_data_path + campaign_id):
        os.mkdir(DRLB_data_path + campaign_id)

    # train_data
    train_data.iloc[:, [5]] = train_data.iloc[:, [5]].astype(str)  # 类型强制转换

    clk_arrays = train_data.iloc[:, 1].values
    pay_price_arrays = train_data.iloc[:, 2].values
    ctr_arrays = train_data.iloc[:, 4].values

    '''
        15,30,45,60
        115,130,145,160
        ....
        2315,2330,2345,2360
    '''
    time_faction = [15, 30, 45, 60]
    time_factions = []
    for i in range(24):
        temp_time_fraction = np.add(100 * i, time_faction)
        for i in range(4):
            time_factions.append(temp_time_fraction[i])

    origin_time_arrays = train_data.iloc[:, 5].values
    now_time_arrays = []
    for k, time_item in enumerate(origin_time_arrays):
        minute_item = int(origin_time_arrays[k][8: 12])
        now_time_arrays.append(minute_item)
    now_time_np_array = np.array(now_time_arrays)
    train_data.iloc[:, 5] = now_time_np_array
    origin_time_arrays = train_data.iloc[:, 5].values

    for i, fraction_item in enumerate(time_factions):
        up_time = fraction_item
        down_time = fraction_item - 15
        for k, time_item in enumerate(origin_time_arrays):
            if time_item <= up_time and time_item >= down_time:
                origin_time_arrays[k] = i + 1

    train_to_data = {'clk': clk_arrays, 'pCTR': ctr_arrays, 'pay_price': pay_price_arrays,
                     'time_fraction': origin_time_arrays}
    train_to_data_df = pd.DataFrame(data=train_to_data)
    train_to_data_df.to_csv('../src/DRLB/data/' + campaign_id + '/train_DRLB_' + type + '.csv', index=None)

    # test_data
    test_data.iloc[:, [5]] = test_data.iloc[:, [5]].astype(str)  # 类型强制转换

    clk_arrays = test_data.iloc[:, 1].values
    pay_price_arrays = test_data.iloc[:, 2].values
    ctr_arrays = test_data.iloc[:, 4].values

    '''
        15,30,45,60
        115,130,145,160
        ....
        2315,2330,2345,2360
    '''
    time_faction = [15, 30, 45, 60]
    time_factions = []
    for i in range(24):
        temp_time_fraction = np.add(100 * i, time_faction)
        for i in range(4):
            time_factions.append(temp_time_fraction[i])

    origin_time_arrays = test_data.iloc[:, 5].values
    now_time_arrays = []
    for k, time_item in enumerate(origin_time_arrays):
        minute_item = int(origin_time_arrays[k][8: 12])
        now_time_arrays.append(minute_item)
    now_time_np_array = np.array(now_time_arrays)
    test_data.iloc[:, 5] = now_time_np_array
    origin_time_arrays = test_data.iloc[:, 5].values

    for i, fraction_item in enumerate(time_factions):
        up_time = fraction_item
        down_time = fraction_item - 15
        for k, time_item in enumerate(origin_time_arrays):
            if time_item <= up_time and time_item >= down_time:
                origin_time_arrays[k] = i + 1

    test_to_data = {'clk': clk_arrays, 'pCTR': ctr_arrays, 'pay_price': pay_price_arrays,
                    'time_fraction': origin_time_arrays}
    test_to_data_df = pd.DataFrame(data=test_to_data)
    test_to_data_df.to_csv('../src/DRLB/data/' + campaign_id + '/test_DRLB_' + type + '.csv', index=None)


def to_RLB_data(campaign_id, type, train_data, test_data):
    RLB_data_path = '../src/RLB/data/'
    if not os.path.exists(RLB_data_path):
        os.mkdir(RLB_data_path)
    elif not os.path.exists(RLB_data_path + 'bid-model'):
        os.mkdir(RLB_data_path + 'bid-model')

    train_data = train_data.values
    test_data = test_data.values

    rlb_train_data = {'clk': train_data[:, 1].astype(int), 'market_price': train_data[:, 2].astype(int),
                      'pctr': train_data[:, 4].astype(float), 'hour': train_data[:, 3].astype(int)}
    rlb_test_data = {'clk': test_data[:, 1].astype(int), 'market_price': test_data[:, 2].astype(int),
                     'pctr': test_data[:, 4].astype(float), 'hour': test_data[:, 3].astype(int)}

    rlb_train_data_df = pd.DataFrame(data=rlb_train_data)
    rlb_train_data_df.to_csv('../src/RLB/data/ipinyou-data/' + campaign_id + '/train.theta.' + type + '.txt', index=None,
                             header=None)
    rlb_test_data_df = pd.DataFrame(data=rlb_test_data)
    rlb_test_data_df.to_csv('../src/RLB/data/ipinyou-data/' + campaign_id + '/test.theta.' + type + '.txt', index=None, header=None)


if __name__ == '__main__':
    campaign_id = '3386'
    type = data_type['type'] # down sample - sample; no sample - data

    sample_type = 2 # 1 - down sample; 2 - all sample
    print('######Generate Train and Test Datas######\n')
    test_clks, test_auc_nums = generate_data(campaign_id)

    if sample_type == 1:
        print('######Down Sample Datas######\n')
        down_sample(campaign_id, test_clks, test_auc_nums)
    else:
        print('######All Sample Datas######\n')
        all_sample(campaign_id)

    train_data = pd.read_csv(campaign_id + '/train_' + type + '.csv', header=None).drop([0])
    test_data = pd.read_csv(campaign_id + '/test_' + type + '.csv', header=None).drop([0])

    print('######To RLB Datas######\n')
    to_RLB_data(campaign_id, type, train_data, test_data)

    print('######To DRLB Datas######\n')
    to_DRLB_data(campaign_id, type, train_data, test_data)
