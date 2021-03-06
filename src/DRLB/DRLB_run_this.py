import numpy as np
import pandas as pd
import datetime
from src.DRLB.config import config
from src.data_type import config as data_type
from src.DRLB.env import AD_env

from src.DRLB.RL_brain import DRLB
from src.DRLB.reward_net import RewardNet

def bid_func(auc_pCTRS, lamda):
    return auc_pCTRS/ lamda

def statistics(B_t, origin_t_spent, origin_t_win_imps,
               origin_t_auctions, origin_t_clks, origin_reward_t, origin_profit_t,  auc_t_datas, bid_arrays, remain_auc_num, t):
    cpc = 30000
    if B_t[t] > 0:
        if B_t[t] - origin_t_spent <= 0 or remain_auc_num[t] - origin_t_auctions <= 0:
            temp_t_auctions = 0
            temp_t_spent = 0
            temp_t_win_imps = 0
            temp_reward_t = 0
            temp_t_clks = 0
            temp_profit_t = 0
            for i in range(len(auc_t_datas)):
                temp_t_auctions += 1
                if remain_auc_num[t] - temp_t_auctions >= 0:
                    if B_t[t] - temp_t_spent >= 0:
                        if auc_t_datas[i, 2] <= bid_arrays[i]:
                            temp_t_spent += auc_t_datas[i, 2]
                            temp_t_win_imps += 1
                            temp_t_clks += auc_t_datas[i, 0]
                            temp_profit_t += (auc_t_datas[i, 1] * cpc - auc_t_datas[i, 2])
                        temp_reward_t += auc_t_datas[i, 0] * auc_t_datas[i, 1]
                    else:
                        break
                else:
                    break
            t_auctions = temp_t_auctions
            t_spent = temp_t_spent if temp_t_spent > 0 else 0
            t_win_imps = temp_t_win_imps
            t_clks = temp_t_clks
            reward_t = temp_reward_t
            profit_t = temp_profit_t
        else:
            t_spent, t_win_imps, t_auctions, t_clks, reward_t, profit_t \
                = origin_t_spent, origin_t_win_imps, origin_t_auctions, origin_t_clks, origin_reward_t, origin_profit_t
    else:
        t_auctions = 0
        t_spent = 0
        t_win_imps = 0
        reward_t = 0
        t_clks = 0
        profit_t = 0

    return t_win_imps, t_spent, t_auctions, reward_t, t_clks, profit_t

def state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs, lamda, action, B_t, time_t, remain_auc_num):
    cpc = 30000
    auc_t_datas = auc_t_datas.values
    bid_arrays = bid_func(auc_t_data_pctrs, lamda)  # 出价
    bid_arrays = np.where(bid_arrays >= 300, 300, bid_arrays)
    win_auc_datas = auc_t_datas[auc_t_datas[:, 2] <= bid_arrays]  # 赢标的数据
    t_spent = np.sum(win_auc_datas[:, 2])  # 当前t时段花费
    t_auctions = len(auc_t_datas)  # 当前t时段参与拍卖次数
    t_win_imps = len(win_auc_datas)  # 当前t时段赢标曝光数
    t_clks = np.sum(win_auc_datas[:, 0])
    profit_t = np.sum(win_auc_datas[:, 1] * cpc - win_auc_datas[:, 2])  # RewardNet
    reward_t = np.sum(np.multiply(auc_t_datas[:, 0], auc_t_datas[:, 1])) # 按论文中的奖励设置，作为直接奖励
    origin_reward_t = reward_t

    done = 0

    # BCR_t = 0
    if time_t == 0:
        if remain_auc_num[0] > 0:
            t_win_imps, t_spent, t_auctions, reward_t, t_clks, profit_t \
                = statistics(B_t, t_spent, t_win_imps, t_auctions, t_clks, reward_t, profit_t, auc_t_datas, bid_arrays, remain_auc_num, 0)
        else:
            t_win_imps = 0
            t_spent = 0
            t_auctions = 0
            reward_t = 0
            t_clks = 0
            profit_t = 0

        B_t[0] = budget - t_spent
        if B_t[0] < 0:
            B_t[0] = 0
        remain_auc_num[0] = auc_num - t_auctions
        if remain_auc_num[0] < 0:
            remain_auc_num[0] = 0
        BCR_t_0 = (B_t[0] - budget) / budget
        BCR_t = BCR_t_0
    else:
        if remain_auc_num[time_t - 1] > 0:
            t_win_imps, t_spent, t_auctions, reward_t, t_clks, profit_t \
                = statistics(B_t, t_spent, t_win_imps, t_auctions, t_clks, reward_t, profit_t, auc_t_datas, bid_arrays, remain_auc_num, time_t - 1)
        else:
            t_auctions = 0
            t_spent = 0
            t_win_imps = 0
            reward_t = 0
            t_clks = 0
            profit_t = 0

        B_t[time_t] = B_t[time_t - 1] - t_spent
        if B_t[time_t] < 0:
            done = 1
            RL.reset_epsilon(0.05) # final epsilon value
            B_t[time_t] = 0
        remain_auc_num[time_t] = remain_auc_num[time_t - 1] - t_auctions
        if remain_auc_num[time_t] < 0:
            done = 1
            RL.reset_epsilon(0.05)
            remain_auc_num[time_t] = 0
        BCR_t_current = (B_t[time_t] - B_t[time_t - 1]) / B_t[time_t - 1] if B_t[time_t - 1] > 0 else 0
        BCR_t = BCR_t_current

    ROL_t = 96 - time_t - 1
    CPM_t = t_spent / t_win_imps if t_spent != 0 else 0
    WR_t = t_win_imps / t_auctions if t_auctions > 0 else 0
    state_t = [(time_t + 1), B_t[time_t] / budget, ROL_t, BCR_t, CPM_t, WR_t, origin_reward_t]

    state_action_t = np.hstack((state_t, action)).tolist()
    net_reward_t = RewardNet.return_model_reward(state_action_t)

    t_real_clks = np.sum(auc_t_datas[:, 0])

    t_real_imps = len(auc_t_datas)

    return state_t, lamda, B_t, net_reward_t[0][0], origin_reward_t, profit_t, t_clks, bid_arrays, remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done

def choose_init_lamda(campaign, original_ctr):
    results_train_best = open('../heuristic_algo/result/' + campaign + data_type['type'] + '/results_train.best.perf.txt', 'r')
    train_best_bid = {}
    for i, line in enumerate(results_train_best):
        if i == 0:
            continue
        line_array = line.strip().split('\t')
        train_best_bid.setdefault(int(line_array[0]), int(line_array[-1]))

    if config['budget_para'][0] == 0.5:
        init_lamda = original_ctr / train_best_bid[2]
    elif config['budget_para'][0] == 0.25:
        init_lamda = original_ctr / train_best_bid[4]
    elif config['budget_para'][0] == 0.125:
        init_lamda = original_ctr / train_best_bid[8]
    else:
        init_lamda = original_ctr / train_best_bid[16]

    return init_lamda

def run_env(budget_para):
    train_data = pd.read_csv('data/' + data_type['campaign_id'] + '/train_DRLB_' + data_type['type'] + '.csv', header=None).drop([0])
    train_data.iloc[:, [0, 2, 3]] = train_data.iloc[:, [0, 2, 3]].astype(int)
    train_data.iloc[:, [1]] = train_data.iloc[:, [1]].astype(float)

    # config['train_budget'] = np.sum(train_data.iloc[:, 2])
    config['train_budget'] = 32000000

    config['train_auc_num'] = len(train_data)
    original_ctr = np.sum(train_data.iloc[:, 0]) / len(train_data)

    auc_num = config['train_auc_num']
    budget = config['train_budget'] * budget_para

    result_data = []
    episode_lamda_records = []
    episode_action_records = []
    init_lamda = choose_init_lamda(data_type['campaign_id'], original_ctr)
    optimal_lamda = 0
    test_records_array = []
    test_actions_array = []

    test_all_records_array = []
    test_all_actions_array = []

    test_down_records_array = []
    test_down_actions_array = []

    for episode in range(config['train_episodes']):
        print('--------第{}轮训练--------\n'.format(episode + 1))
        B_t = [0 for i in range(96)]
        B_t[0] = budget

        remain_auc_num = [0 for i in range(96)]
        remain_auc_num[0] = auc_num
        temp_state_t_next, temp_lamda_t_next, temp_B_t_next, temp_reward_t_next, temp_remain_t_auctions = [], 0, [], 0, []

        RL.reset_epsilon(0.9) # init epsilon value

        episode_clks = 0
        episode_real_clks = 0
        episode_imps = 0
        episode_win_imps = 0
        episode_spent = 0
        episode_profit = 0

        action_records = [-1 for _ in range(96)]
        temp_lamda_record = [init_lamda]

        V = 0 # current episode's cumulative directive reward

        done = 0
        episode_loss = 0
        action_t_next = 0

        state_action_pairs = []
        for t in range(96):
            time_t = t
            ROL_t = 96-t-1
            # auc_data[0] 是否有点击；auc_data[1] pCTR；auc_data[2] 市场价格； auc_data[3] t划分[1-96]
            auc_t_datas = train_data[train_data.iloc[:, 3].isin([t + 1])] # t时段的数据
            auc_t_data_pctrs = auc_t_datas.iloc[:, 1].values # ctrs

            if RewardNet.memory_D_counter >= config['batch_size']:
                RewardNet.learn()

            if t == 0:
                init_action = 0
                state_t, lamda_t, B_t, reward_t, origin_reward_t, profit_t, t_clks, bid_arrays, t_remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done = state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs,
                                                                             init_lamda, init_action, B_t, time_t, remain_auc_num)  # 1时段
                action = RL.choose_best_action(state_t)
                auc_t_datas_next = train_data[train_data.iloc[:, 3].isin([t + 2])]  # t时段的数据
                auc_t_data_pctrs_next = auc_t_datas_next.iloc[:, 1].values  # ctrs

                lamda_t_next = lamda_t * (1 + action)
                action_t_next = action

                state_t_next, lamda_t_next, B_t_next, reward_t_next, origin_reward_t_next, profit_t_next, t_clks_next, bid_arrays_next, remain_auc_num_next, \
                t_win_imps_next, t_real_imps_next, t_real_clks_next, t_spent_next, done_next \
                    = state_(budget,auc_num, auc_t_datas_next,auc_t_data_pctrs_next,lamda_t_next, action, B_t,time_t + 1, t_remain_auc_num)

                temp_state_t_next, temp_lamda_t_next, temp_B_t_next, temp_reward_t_next, temp_remain_t_auctions\
                    = state_t_next, lamda_t_next, B_t_next, reward_t_next, remain_auc_num_next
            else:
                state_t, lamda_t, B_t, reward_t, origin_reward_t, profit_t, t_clks, bid_arrays, t_remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done = state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs,temp_lamda_t_next, action_t_next, temp_B_t_next, time_t, temp_remain_t_auctions)

                action = RL.choose_best_action(state_t)

                auc_t_datas_next = train_data[train_data.iloc[:, 3].isin([t + 2])]  # t时段的数据
                auc_t_data_pctrs_next = auc_t_datas_next.iloc[:, 1].values  # ctrs

                lamda_t_next = lamda_t * (1 + action)
                action_t_next = action

                if t == 95:
                    done = 1
                    RL.reset_epsilon(0.05)

                if t < 95:
                    state_t_next, lamda_t_next, B_t_next, reward_t_next, origin_reward_t_next, profit_t_next, t_clks_next, bid_arrays_next, remain_auc_num_next, \
                    t_win_imps_next, t_real_imps_next, t_real_clks_next, t_spent_next, done_next\
                        = state_(budget, auc_num,auc_t_datas_next,auc_t_data_pctrs_next,lamda_t_next, action, B_t,time_t + 1, t_remain_auc_num)

                    if t + 1 == 95:
                        optimal_lamda = lamda_t_next
                        temp_lamda_record.append(optimal_lamda)
                        episode_lamda_records.append(temp_lamda_record)

                temp_state_t_next, temp_lamda_t_next, temp_B_t_next, temp_reward_t_next, temp_profit_t_next, temp_remain_t_auctions\
                    = state_t_next, lamda_t_next, B_t_next, reward_t_next, profit_t_next, remain_auc_num_next
            # print(action)
            transition = np.hstack((state_t, action, reward_t, state_t_next, done))
            RL.store_transition(transition) # 存储在DRLB的经验池中

            state_action_pairs.append((state_t, action))

            action_records[t] = action

            RL.control_epsilon(t + 1)

            episode_spent += t_spent
            episode_imps += t_real_imps
            episode_win_imps += t_win_imps
            episode_clks += t_clks
            episode_real_clks += t_real_clks
            episode_profit += profit_t

            V += origin_reward_t

            if RL.memory_counter >= config['batch_size']: # 控制更新速度
                loss = RL.learn()
                episode_loss = loss

            if done == 1:
                break

        # 算法2
        for (s, a) in state_action_pairs:
            state_action = tuple(np.append(s, a))
            max_rtn = max(RewardNet.get_reward_from_S(state_action), V)
            RewardNet.store_S_pair(state_action, max_rtn)
            RewardNet.store_D_pair(s, a, max_rtn)

        print('第{}轮，真实曝光数{}, 赢标数{}, 共获得{}个点击, 真实点击数{}, '
              '利润{}, 预算{}, 花费{}, CPM{}, LOSS-{}, {}'
              .format(episode + 1, episode_imps, episode_win_imps, episode_clks, episode_real_clks,
                      episode_profit, budget, episode_spent,
                      episode_spent / episode_win_imps if episode_win_imps > 0 else 0, episode_loss, datetime.datetime.now()))
        print('\n---------测试---------\n')
        test_records, test_actions = run_test(budget_para, original_ctr)
        test_records_array.append(test_records)
        test_actions_array.append(test_actions)

        # print('\n---------all测试---------\n')
        # test_all_records, test_all_actions = run_all_test(budget_para, original_ctr)
        # test_all_records_array.append(test_all_records)
        # test_all_actions_array.append(test_all_actions)
        #
        # print('\n---------down测试---------\n')
        # test_down_records, test_down_actions = run_down_test(budget_para, original_ctr)
        # test_down_records_array.append(test_down_records)
        # test_down_actions_array.append(test_down_actions)

        episode_result_data = [episode_imps, episode_win_imps, episode_clks, episode_real_clks,
                               episode_profit, budget, episode_spent, episode_spent / episode_win_imps if episode_win_imps > 0 else 0]
        result_data.append(episode_result_data)

        episode_action_records.append(action_records)
    columns = ['real_imps', 'win_imps', 'clks', 'real_clks', 'profit', 'budget', 'spent', 'CPM']

    test_records_array_df = pd.DataFrame(data=test_records_array)
    test_records_array_df.to_csv('result/' + data_type['campaign_id'] + data_type['type'] + '/test_episode_results_' + str(budget_para) + '.csv')

    test_actions_array_df = pd.DataFrame(data=test_actions_array)
    test_actions_array_df.to_csv(
        'result/' + data_type['campaign_id'] + data_type['type'] + '/test_episode_actions_' + str(budget_para) + '.csv')

    # all sample
    # test_all_records_array_df = pd.DataFrame(data=test_all_records_array)
    # test_all_records_array_df.to_csv(
    #     'result/' + data_type['campaign_id'] + data_type['type'] + '/all_sample/test_episode_results_' + str(budget_para) + '.csv')
    #
    # test_all_actions_array_df = pd.DataFrame(data=test_all_actions_array)
    # test_all_actions_array_df.to_csv(
    #     'result/' + data_type['campaign_id'] + data_type['type'] + '/all_sample/test_episode_actions_' + str(budget_para) + '.csv')
    #
    # # down sample
    # test_down_records_array_df = pd.DataFrame(data=test_down_records_array)
    # test_down_records_array_df.to_csv(
    #     'result/' + data_type['campaign_id'] + data_type['type'] + '/down_sample/test_episode_results_' + str(budget_para) + '.csv')
    #
    # test_down_actions_array_df = pd.DataFrame(data=test_down_actions_array)
    # test_down_actions_array_df.to_csv(
    #     'result/' + data_type['campaign_id'] + data_type['type'] + '/down_sample/test_episode_actions_' + str(budget_para) + '.csv')

    action_df = pd.DataFrame(data=episode_action_records)
    action_df.to_csv('result/' + data_type['campaign_id'] + data_type['type'] + '/train_episode_actions_' + str(budget_para) + '.csv')

    result_data_df = pd.DataFrame(data=result_data, columns=columns)
    result_data_df.to_csv('result/' + data_type['campaign_id'] + data_type['type'] + '/train_episode_results_' + str(budget_para) + '.csv')

    return optimal_lamda

def run_down_test(budget_para, original_ctr):
    test_data = pd.read_csv('data/' + data_type['campaign_id'] + '/test_DRLB_down_sample.csv', header=None).drop([0])
    test_data.iloc[:, [0, 2, 3]] = test_data.iloc[:, [0, 2, 3]].astype(int)
    test_data.iloc[:, [1]] = test_data.iloc[:, [1]].astype(float)

    # config['test_budget'] = np.sum(test_data.iloc[:, 2])
    config['test_budget'] = 32000000

    config['test_auc_num'] = len(test_data)

    auc_num = config['test_auc_num']
    budget = config['test_budget'] * budget_para

    B_t = [0 for i in range(96)]
    B_t[0] = budget * budget_para

    remain_auc_num = [0 for i in range(96)]
    remain_auc_num[0] = auc_num

    RL.reset_epsilon(0.9)  # init epsilon value

    init_lamda = choose_init_lamda(data_type['campaign_id'], original_ctr)
    episode_clks = 0
    episode_real_clks = 0
    episode_imps = 0
    episode_win_imps = 0
    episode_spent = 0
    episode_profit = 0

    temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = 0, [], []

    action_records = [-1 for _ in range(96)]

    lamda_record = [init_lamda]
    action_t_next = 0
    for t in range(96):
        time_t = t

        # auc_data[0] 是否有点击；auc_data[1] pCTR；auc_data[2] 市场价格； auc_data[3] t划分[1-96]
        auc_t_datas = test_data[test_data.iloc[:, 3].isin([t + 1])]  # t时段的数据
        auc_t_data_pctrs = auc_t_datas.iloc[:, 1].values  # ctrs
        if t == 0:
            init_action = 0
            state_t, lamda_t, B_t, reward_t, origin_reward_t, profit_t, t_clks, bid_arrays, t_remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done = state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs, init_lamda, init_action, B_t, time_t, remain_auc_num)  # 1时段
            action = RL.choose_best_action(state_t)

            lamda_t_next = lamda_t * (1 + action)
            action_t_next = action
            temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = lamda_t_next, B_t, t_remain_auc_num
        else:
            state_t, lamda_t, B_t, reward_t, origin_reward_t, profit_t, t_clks, bid_arrays, t_remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done = state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs,
                                                                         temp_lamda_t_next, action_t_next, temp_B_t_next, time_t, temp_remain_t_auctions)
            action = RL.choose_best_action(state_t)

            lamda_t_next = lamda_t * (1 + action)
            action_t_next = action

            if t == 95:
                done = 1

            temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = lamda_t_next, B_t, t_remain_auc_num

            if t + 1 == 95:
                RL.reset_epsilon(0.05)
                lamda_record.append(lamda_t_next)

        RL.control_epsilon(t + 1)

        action_records[t] = action

        episode_clks += t_clks
        episode_real_clks += t_real_clks
        episode_imps += t_real_imps
        episode_win_imps += t_win_imps
        episode_spent += t_spent
        episode_profit += reward_t

        if done == 1:
            break

    print('测试集中：真实曝光数{}, 赢标数{}, 共获得{}个点击, 真实点击数{}, '
          '利润{}, 预算{}, 花费{}, CPM{}, {}'.format(episode_imps, episode_win_imps, episode_clks, episode_real_clks,
                                               episode_profit, budget, episode_spent, episode_spent / episode_win_imps, datetime.datetime.now()))

    temp_result = [episode_imps, episode_win_imps, episode_clks, episode_real_clks,
                             episode_profit, budget, episode_spent, episode_spent / episode_win_imps]

    return temp_result, action_records

def run_all_test(budget_para, original_ctr):
    test_data = pd.read_csv('data/' + data_type['campaign_id'] + '/test_DRLB_all_sample.csv', header=None).drop([0])
    test_data.iloc[:, [0, 2, 3]] = test_data.iloc[:, [0, 2, 3]].astype(int)
    test_data.iloc[:, [1]] = test_data.iloc[:, [1]].astype(float)

    # config['test_budget'] = np.sum(test_data.iloc[:, 2])
    config['test_budget'] = 32000000

    config['test_auc_num'] = len(test_data)

    auc_num = config['test_auc_num']
    budget = config['test_budget'] * budget_para

    B_t = [0 for i in range(96)]
    B_t[0] = budget * budget_para

    remain_auc_num = [0 for i in range(96)]
    remain_auc_num[0] = auc_num

    RL.reset_epsilon(0.9)  # init epsilon value

    init_lamda = choose_init_lamda(data_type['campaign_id'], original_ctr)
    episode_clks = 0
    episode_real_clks = 0
    episode_imps = 0
    episode_win_imps = 0
    episode_spent = 0
    episode_profit = 0

    temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = 0, [], []

    action_records = [-1 for _ in range(96)]

    lamda_record = [init_lamda]
    action_t_next = 0
    for t in range(96):
        time_t = t

        # auc_data[0] 是否有点击；auc_data[1] pCTR；auc_data[2] 市场价格； auc_data[3] t划分[1-96]
        auc_t_datas = test_data[test_data.iloc[:, 3].isin([t + 1])]  # t时段的数据
        auc_t_data_pctrs = auc_t_datas.iloc[:, 1].values  # ctrs
        if t == 0:
            init_action = 0
            state_t, lamda_t, B_t, reward_t, origin_reward_t, profit_t, t_clks, bid_arrays, t_remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done = state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs, init_lamda, init_action, B_t, time_t, remain_auc_num)  # 1时段
            action = RL.choose_best_action(state_t)

            lamda_t_next = lamda_t * (1 + action)
            action_t_next = action
            temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = lamda_t_next, B_t, t_remain_auc_num
        else:
            state_t, lamda_t, B_t, reward_t, origin_reward_t, profit_t, t_clks, bid_arrays, t_remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done = state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs,
                                                                         temp_lamda_t_next, action_t_next, temp_B_t_next, time_t, temp_remain_t_auctions)
            action = RL.choose_best_action(state_t)

            lamda_t_next = lamda_t * (1 + action)
            action_t_next = action

            if t == 95:
                done = 1

            temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = lamda_t_next, B_t, t_remain_auc_num

            if t + 1 == 95:
                RL.reset_epsilon(0.05)
                lamda_record.append(lamda_t_next)

        RL.control_epsilon(t + 1)

        action_records[t] = action

        episode_clks += t_clks
        episode_real_clks += t_real_clks
        episode_imps += t_real_imps
        episode_win_imps += t_win_imps
        episode_spent += t_spent
        episode_profit += reward_t

        if done == 1:
            break

    print('测试集中：真实曝光数{}, 赢标数{}, 共获得{}个点击, 真实点击数{}, '
          '利润{}, 预算{}, 花费{}, CPM{}, {}'.format(episode_imps, episode_win_imps, episode_clks, episode_real_clks,
                                               episode_profit, budget, episode_spent, episode_spent / episode_win_imps, datetime.datetime.now()))

    temp_result = [episode_imps, episode_win_imps, episode_clks, episode_real_clks,
                             episode_profit, budget, episode_spent, episode_spent / episode_win_imps]

    return temp_result, action_records

def run_test(budget_para, original_ctr):
    test_data = pd.read_csv('data/' + data_type['campaign_id'] + '/test_DRLB_data.csv', header=None).drop([0])
    test_data.iloc[:, [0, 2, 3]] = test_data.iloc[:, [0, 2, 3]].astype(int)
    test_data.iloc[:, [1]] = test_data.iloc[:, [1]].astype(float)

    # config['test_budget'] = np.sum(test_data.iloc[:, 2])
    config['test_budget'] = 32000000

    config['test_auc_num'] = len(test_data)

    auc_num = config['test_auc_num']
    budget = config['test_budget'] * budget_para

    B_t = [0 for i in range(96)]
    B_t[0] = budget * budget_para

    remain_auc_num = [0 for i in range(96)]
    remain_auc_num[0] = auc_num

    RL.reset_epsilon(0.9)  # init epsilon value

    init_lamda = choose_init_lamda(data_type['campaign_id'], original_ctr)
    episode_clks = 0
    episode_real_clks = 0
    episode_imps = 0
    episode_win_imps = 0
    episode_spent = 0
    episode_profit = 0

    temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = 0, [], []

    action_records = [-1 for _ in range(96)]

    lamda_record = [init_lamda]
    action_t_next = 0
    for t in range(96):
        time_t = t

        # auc_data[0] 是否有点击；auc_data[1] pCTR；auc_data[2] 市场价格； auc_data[3] t划分[1-96]
        auc_t_datas = test_data[test_data.iloc[:, 3].isin([t + 1])]  # t时段的数据
        auc_t_data_pctrs = auc_t_datas.iloc[:, 1].values  # ctrs
        if t == 0:
            init_action = 0
            state_t, lamda_t, B_t, reward_t, origin_reward_t, profit_t, t_clks, bid_arrays, t_remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done = state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs, init_lamda, init_action, B_t, time_t, remain_auc_num)  # 1时段
            action = RL.choose_best_action(state_t)

            lamda_t_next = lamda_t * (1 + action)
            action_t_next = action
            temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = lamda_t_next, B_t, t_remain_auc_num
        else:
            state_t, lamda_t, B_t, reward_t, origin_reward_t, profit_t, t_clks, bid_arrays, t_remain_auc_num, t_win_imps, t_real_imps, t_real_clks, t_spent, done = state_(budget, auc_num, auc_t_datas, auc_t_data_pctrs,
                                                                         temp_lamda_t_next, action_t_next, temp_B_t_next, time_t, temp_remain_t_auctions)
            action = RL.choose_best_action(state_t)

            lamda_t_next = lamda_t * (1 + action)
            action_t_next = action

            if t == 95:
                done = 1

            temp_lamda_t_next, temp_B_t_next, temp_remain_t_auctions = lamda_t_next, B_t, t_remain_auc_num

            if t + 1 == 95:
                RL.reset_epsilon(0.05)
                lamda_record.append(lamda_t_next)

        RL.control_epsilon(t + 1)

        action_records[t] = action

        episode_clks += t_clks
        episode_real_clks += t_real_clks
        episode_imps += t_real_imps
        episode_win_imps += t_win_imps
        episode_spent += t_spent
        episode_profit += reward_t

        if done == 1:
            break

    print('测试集中：真实曝光数{}, 赢标数{}, 共获得{}个点击, 真实点击数{}, '
          '利润{}, 预算{}, 花费{}, CPM{}, {}'.format(episode_imps, episode_win_imps, episode_clks, episode_real_clks,
                                               episode_profit, budget, episode_spent, episode_spent / episode_win_imps, datetime.datetime.now()))

    temp_result = [episode_imps, episode_win_imps, episode_clks, episode_real_clks,
                             episode_profit, budget, episode_spent, episode_spent / episode_win_imps]

    return temp_result, action_records

if __name__ == '__main__':
    env = AD_env()
    RL = DRLB([-0.08, -0.03, -0.01, 0, 0.01, 0.03, 0.08],  # 按照数据集中的“块”计量
             env.action_numbers, env.feature_numbers,
             learning_rate=config['learning_rate'],  # DQN更新公式的学习率
             reward_decay=config['reward_decay'],  # 奖励折扣因子
             e_greedy=config['e_greedy'],  # 贪心算法ε
             replace_target_iter=config['relace_target_iter'],  # 每200步替换一次target_net的参数
             memory_size=config['memory_size'],  # 经验池上限
             batch_size=config['batch_size'],  # 每次更新时从memory里面取多少数据出来，mini-batch
             device=config['device'],
             )

    RewardNet = RewardNet([-0.08, -0.03, -0.01, 0, 0.01, 0.03, 0.08],  # 按照数据集中的“块”计量
                          action_numbers=1, reward_numbers=1, feature_numbers=env.feature_numbers, memory_size=config['memory_size'],
                          batch_size=config['batch_size'], device=config['device'],)

    budget_para = config['budget_para']
    for i in range(len(budget_para)):
        print('-----当前预算条件{}----\n'.format(budget_para[i]))
        optimal_lamda = run_env(budget_para[i])