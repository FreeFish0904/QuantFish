import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
data_path = "/home/data/data_share/"
import utils, os

def backtest(f,start_date='20110101',end_date='20181231',alpha_type="longshort",hedge="None",group_num=0,capital=10000000):
    start_date,end_date,alpha_type,hedge,group_num,capital = utils.check_param(start_date,end_date,alpha_type,hedge,group_num,capital)
    ################################## 根据capital的情况设定自循环 ####################
    if isinstance(capital,bool):
        return backtest(f,start_date,end_date,alpha_type,hedge,group_num,capital=[1e7,1e8,1e9,1e10])
    elif isinstance(capital,list):
        result_list = []
        for i in capital:
            result_list.append(backtest(f,start_date,end_date,alpha_type,hedge,group_num,capital=i))
        sharpe_decay = []
        fitness_decay = []
        turnover_decay = []
        for i in result_list:
            sharpe_decay.append(i['summary']['sharpe'].iloc[-1])
            fitness_decay.append(i['summary']['fitness'].iloc[-1])
            turnover_decay.append(i['summary']['turnover'].iloc[-1])
        pd.DataFrame([sharpe_decay,fitness_decay],index=["sharpe_decay","fitness_decay"],columns=["%.1e"%i for i in capital]).T.plot()
        plt.show()
        return result_list
    
    data = utils.read_backtest_data(f,start_date,end_date,hedge)
    data["target_position"] = utils.factor_preprocess(data["factor"],alpha_type)
    data["position"] = utils.trade(data["target_position"], data["ret_c"], data["amount"], capital)
    

    
    
    ################################## calculate pnl ###############################
    
    result = {}
    # 得到多空收益率序列
    factor_ret = (data["position"]*(data["close_adj"]/data["vwap_adj"]-1) + \
                 data["position"].shift()*(data["vwap_adj"]/data["close_adj"].shift()-1) ).sum(axis=1)
    if hedge=="zz500":
        factor_ret -= data["zz500_ret"]
    elif hedge=="hs300":
        factor_ret -= data["hs300_ret"]
    factor_net_value = factor_ret.cumsum()
    result["factor_net_value"] = factor_net_value
    result["factor_ret"] = factor_ret
    ################################# performance ##################################
    # 计算回撤
    factor_net_value = factor_net_value.astype(float)
    drawdown = (factor_net_value.groupby(factor_net_value.index.year).cummax() - factor_net_value)  # 绝对值计算
    max_drawdown = drawdown.groupby(drawdown.index.year).max()
    drawdown_all = (factor_net_value.cummax() - factor_net_value)  # 绝对值计算
    max_drawdown_all = drawdown_all.max()
    # 计算年化夏普比率
    sharpe = (factor_ret.groupby(factor_ret.index.year).mean() / factor_ret.groupby(factor_ret.index.year).std() * np.sqrt(252))
    if factor_ret.std() != 0:
        sharpe_all = (factor_ret.mean() / factor_ret.std() * np.sqrt(252))
    else:
        sharpe_all = np.nan
    # 年化收益率
    annual_ret = (factor_ret.groupby(factor_ret.index.year).sum())
    annual_ret_all = (factor_ret.sum() / len(factor_ret) * 252)
    # 双边换手率
    turnover = data["position"].fillna(0).diff().abs().sum(axis=1)
    turnover_mean = (turnover.groupby(turnover.index.year).mean())
    turnover_mean_all = turnover.mean()
    # Fitness
    fitness = (sharpe * ((annual_ret.abs()/turnover_mean)**0.5))
    fitness_all = (sharpe_all * ((abs(annual_ret_all)/turnover_mean_all)**0.5))
    # Long short
    long_count = (data["position"] > 0).sum(axis=1).groupby(data["position"].index.year).mean().astype(int)
    short_count = (data["position"] < 0).sum(axis=1).groupby(data["position"].index.year).mean().astype(int)
    long = data["position"][data["position"] > 0].sum(axis=1).groupby(data["position"].index.year).mean()
    short = data["position"][data["position"] < 0].sum(axis=1).groupby(data["position"].index.year).mean()
    long_count_all = int((data["position"] > 0).sum(axis=1).mean())
    short_count_all = int((data["position"] < 0).sum(axis=1).mean())
    long_all = data["position"][data["position"] > 0].sum(axis=1).mean()
    short_all = data["position"][data["position"] < 0].sum(axis=1).mean()
    # Winrate
    # winrate = (factor_ret.groupby(factor_ret.index.year).apply(lambda x: (x>0).sum()) / factor_ret.groupby(factor_ret.index.year).count())
    # winrate_all = ((factor_ret>0).sum()/factor_ret.count())
    # odds
    # odds = -(factor_ret.groupby(factor_ret.index.year).apply(lambda x: x[x>0].mean()) / \
    #      factor_ret.groupby(factor_ret.index.year).apply(lambda x: x[x<0].mean()))
    # odds_all = -(factor_ret[factor_ret>0].mean() / factor_ret[factor_ret<0].mean())
    # calmar
    calmar = (annual_ret / max_drawdown)
    calmar_all = annual_ret_all / max_drawdown_all
    
    summary = pd.concat([long,short,long_count,short_count,sharpe,annual_ret,turnover_mean,max_drawdown,fitness,calmar],axis=1)
    summary.columns = ['long','short','long(num)','short(num)','sharpe','returns','turnover','drawdown','fitness','calmar']
    summary_all = pd.DataFrame([[long_all,short_all,long_count_all,short_count_all,sharpe_all,annual_ret_all\
                       ,turnover_mean_all,max_drawdown_all,fitness_all,calmar_all]])
    summary_all.columns = summary.columns
    summary_all.index = ['all']
    summary = pd.concat([summary,summary_all])
    
    # 处理小数点
    result["summary"] = summary.round(3)
    
    # 分组单调性
    if group_num>1:
        g_num = group_num
        factor_rank = pd.DataFrame(data["factor"].shift().values.argsort().argsort(),index=data["factor"].index,columns=data["factor"].columns)
        factor_rank[pd.isnull(data["factor"])] = np.nan
        factor_rank = factor_rank[factor_rank.count(axis=1)>=g_num]
        group = factor_rank.apply(pd.qcut,args=(g_num,False),axis=1)
        group_annual_ret = []
        group_daily_ret = []
        for i in range(g_num):
            group_daily_ret.append(((group == i).replace(False,np.nan) * data["ret_v"]).mean(axis=1))
            group_annual_ret.append(group_daily_ret[i].mean() * 252)
        group_annual_ret = pd.Series(group_annual_ret)
        group_daily_ret = pd.DataFrame(group_daily_ret).T
        result["group_annual_ret"] = group_annual_ret
        result["group_daily_ret"] = group_daily_ret
    
    return(result)


def loaddata(field):
    if isinstance(field,list):
        data = {}
        for i in field:
            if i in ["dates","tickers"]:
                data[i] = pd.read_pickle(data_path+i+".pkl").fillna(np.nan)
            for j in ["barra风格因子","行业分类与ST","个股日线行情","个股每日指标","指数成分与行情"]:
                if i+".pkl" in os.listdir(data_path+j):
                    data[i] = pd.read_pickle(data_path+j+"/"+i+".pkl").fillna(np.nan)
            
        return data
    else:
        raise ValueError("Please input a list!")

def show(result):
    display(result["summary"])
    result["factor_net_value"].plot(figsize=(9,5))
    if "group_daily_ret" in result.keys():
        result["group_daily_ret"].cumsum().plot(cmap="RdYlGn_r",figsize=(9,5))

def save(result,name,path="/home/quan.zhou/development/factor/share/output/"):
    if not os.path.exists(path+name):
        os.makedirs(path+name)
    for i in result.keys():
        if i == "factor_ret":
            result[i].to_pickle(path+name+"/factor_ret.pkl")
        if i == "summary":
            result[i].to_csv(path+name+"/summary.csv")
        if i == "factor_net_value":
            result[i].to_csv(path+name+"/因子单利累计收益率.csv")
        if i == "group_daily_ret":
            result[i].to_csv(path+name+"/因子分组日度收益率.csv")
        if i == "group_annual_ret":
            result[i].to_csv(path+name+"/因子分组年化收益率.csv")
            

def check_corr(result):
    alpha_path = "/home/cicc/release/pool/share/output/"
    alpha_list = []
    pnl_list = []
    sharpe_list = []
    fitness_list = []
    find_list = os.listdir(alpha_path)
    for i in find_list:
        try:
            pnl = pd.read_pickle(alpha_path+i+"/factor_ret.pkl")
            sharpe = pd.read_csv(alpha_path+i+"/summary.csv",index_col=0)["sharpe"]["all"]
            fitness = pd.read_csv(alpha_path+i+"/summary.csv",index_col=0)["fitness"]["all"]
            pnl_list.append(pnl)
            sharpe_list.append(sharpe)
            fitness_list.append(fitness)
            alpha_list.append(i)
        except:
            pass
    corr = pd.concat(pnl_list,axis=1).corrwith(result["factor_ret"]).to_list()
    corr = pd.DataFrame([corr,sharpe_list,fitness_list]).T.round(3)
    corr.index = alpha_list
    corr.columns = ["corr","sharpe","fitnes"]
    corr = corr.sort_values('corr',ascending=False)
    print(corr.head())
    print(corr.tail())
    if corr["corr"].max() >= 0.5:
        return False
    else:
        return True

def check(result):
    check_result = True
    sharpe = result["summary"]["sharpe"]['all']
    fitness = result["summary"]["fitness"]['all']
    turnover = result["summary"]["turnover"]['all']
    if not check_corr(result):
        print("Check correlation fail, max corr >= 0.5 !")
        check_result = False
    threshold = 2.0
    if result["summary"]["short"]["all"] == 0:
        threshold = 1.0
    if sharpe < threshold:
        print("Check sharpe fail, sharpe = %f"%sharpe)
        check_result = False
    if fitness < threshold:
        print("Check fitness fail, fitness = %f"%fitness)
        check_result = False
    if turnover >= 1.0:
        print("Check turnover fail, overall turnover >= 1.0 !")
        check_result = False
    if check_result:
        print("Check passed!")
    return check_result