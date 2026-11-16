import numpy as np
import pandas as pd
import sys
data_path = "/home/data/data_share/"


def trade(target_pos, ret_c, amount, capital):
    position = target_pos.copy()
    position_change = position.diff()
    upbound = (10*amount/capital).astype(float)
    lowbound = (-upbound).astype(float)
    position_change[position_change>upbound] = upbound
    position_change[position_change<lowbound] = lowbound
    position_change[ret_c>0.0995] = 0
    position_change[ret_c<-0.0995] = 0
    position = position.shift()+position_change
    position.iloc[0,:] = target_pos.iloc[0,:] 
    position = position.div(position.abs().sum(axis=1),axis=0) # scale，mean不一定0
    return(position)


def trade_mod(target_pos, ret_c, amount, capital):
    position = target_pos.copy()
    upbound = (10*amount/capital).astype(float)
    lowbound = (-1.0*upbound).astype(float)
    a = ret_c>0.0995
    b = ret_c<-0.0995
    position.iloc[0,:][a.iloc[0, :]] = 0
    position.iloc[0,:][b.iloc[0, :]] = 0
    position.iloc[0,:] = position.iloc[0,:].sub(position.iloc[0,:].mean())
    position.iloc[0,:] = position.iloc[0,:].div(position.iloc[0,:].abs().sum())
    for i in range(1, len(position)):
        today = position.iloc[i,:]
        last_day = position.iloc[i-1,:]
        position_change = today - last_day
        c = position_change>upbound.iloc[i,:]
        d = position_change<lowbound.iloc[i,:]
        tempa = a.iloc[i,:]&(position_change>0)
        tempb = b.iloc[i,:]&(position_change<0)
        temp_val = upbound.iloc[i,:][c].sum()+lowbound.iloc[i,:][d].sum()+last_day[tempa].sum()+last_day[tempb].sum()
        temp_val_abs = upbound.iloc[i,:][c].sum()+upbound.iloc[i,:][d].sum()+last_day[tempa|tempb].abs().sum()
        today[c|d|tempa|tempb] = np.nan
        today = today.sub(today.mean()-temp_val)
        today = (today.sub(temp_val_abs)).div(today.abs().sum()) # 存在调整后可能超过市场1%的情况
        today[tempa|tempb] = last_day.shift()
        today[c] = last_day + upbound.iloc[i,:]
        today[d] = last_day + lowbound.iloc[i,:]
    return(position)


def factor_preprocess(f,alpha_type):
    factor = f.copy()
    factor = factor.astype(float)
    factor[np.isinf(factor)] = np.nan
    if alpha_type == "longonly":
        factor[factor<0] = 0
    if alpha_type == "longshort":
        factor = factor.sub(factor.mean(axis=1),axis=0)
    factor = factor.div(factor.abs().sum(axis=1),axis=0) # scale
    return(factor)


def read_backtest_data(f,start_date,end_date,hedge):
    data = {}
    f_copy = f.copy()
    f_copy.index = pd.to_datetime(f_copy.index) # read factor and handle index
    
    data["ret_c"] = pd.read_pickle(data_path+"个股日线行情/"+'ret_c.pkl')
    data["ret_v"] = pd.read_pickle(data_path+"个股日线行情/"+'ret_v.pkl')
    data["close"] = pd.read_pickle(data_path+"个股日线行情/"+'close.pkl')
    data["vwap"] = pd.read_pickle(data_path+"个股日线行情/"+'vwap.pkl')
    data["adj"] = pd.read_pickle(data_path+"个股日线行情/"+"adj_factor.pkl")
    data["amount"] = pd.read_pickle(data_path+"个股日线行情/"+"amount.pkl")
    data["close_adj"] = data["close"] * data["adj"]
    data["vwap_adj"] = data["vwap"] * data["adj"]
    if hedge == "hs300":
        data["hs300_ret"] = pd.read_pickle(data_path+"指数成分与行情/"+"hs300_ret.pkl")
    if hedge == "zz500":
        data["zz500_ret"] = pd.read_pickle(data_path+"指数成分与行情/"+"zz500_ret.pkl")
    
    # align factor's columns
    data["factor"] = f_copy.shift()
    drop_num = len(set(data["factor"].columns)-set(data["close"].columns))
    if drop_num:
        print("warning: %d stocks have been dropped!"%drop_num)
    data["factor"] = data["factor"].reindex(data["close"].columns,axis=1)
    data["factor"] = data["factor"].reindex(data["close"].index)
    
    for i in data.keys():
        data[i] = data[i][(data[i].index>=start_date) & (data[i].index<end_date)]
    return(data)


def check_param(start_date,end_date,alpha_type,hedge,group_num,capital):
    print("backtest start...")
    print("start date: %s, end date: %s"%(start_date,end_date))
    start_date=pd.to_datetime(start_date)
    end_date=pd.to_datetime(end_date)
    alpha_type = alpha_type.lower()
    hedge = hedge.lower()
    group_num = int(group_num)
    
    #capital = float(capital)
    if start_date >= end_date:
        raise ValueError("end date cannot be earlier than start date")
    if alpha_type in ["longshort","longonly"]:
        print("alpha type: %s"%alpha_type)
    else:
        raise ValueError("unsupport alpha type")
    if hedge in ["zz500","hs300"]:
        if alpha_type == "longshort":
            raise ValueError("longshort factor not support index hedge")
        print("hedge index: %s"%hedge)
    elif hedge != "none":
        raise ValueError("unsupport hedge index")
    if group_num>1:
        print("group num: %d"%group_num)
    #if capital > 0:
    #    print("inital captial: %d"%capital)
    #else:
    #    raise ValueError("inital captial cannot be negative")
    if isinstance(capital,list):
        for i in capital:
            if not (isinstance(i,int) or isinstance(i,float)):
                raise ValueError("Each elements in capital should be int or float!")
            if i < 1000000:
                raise ValueError("capital cannot less than 1000000")
        capital.sort()
        print("inital captial: ",capital)
    elif isinstance(capital,bool):
        if capital == False:
            raise ValueError("capital cannot be False!")
    elif isinstance(capital,int):
        if capital < 1000000:
            raise ValueError("capital cannot less than 1000000")
        print("inital captial: ",capital)
    elif isinstance(capital,float):
        if capital < 1000000:
            raise ValueError("capital cannot less than 1000000")
        print("inital captial: ",capital)
    else:
        raise ValueError("Invalid capital!")
    return(start_date,end_date,alpha_type,hedge,group_num,capital)

def industry_neutral(factor,data,industry="sw1",neutral_type="longshort"):
    if industry=="sw1":
        ind_code = data["sw1_code"]
    elif industry=="sw2":
        ind_code = data["sw2_code"]
    else:
        raise ValueError("Industry not support, please choose from sw1 or sw2")
    a = list(ind_code.fillna(0).values.flatten())
    ind_code_list = list(set(a))
    ind_code_list = ind_code_list[1:]
    factor_new = pd.DataFrame(0, index=factor.index, columns=factor.columns)
    for i in ind_code_list:
        tempdf = factor[ind_code==i]
        factor_new = factor_new.add(tempdf.sub(tempdf.mean(axis=1), axis=0).fillna(0))
    factor_new[pd.isna(factor)] = np.nan
    return factor_new

def distribute(factor,bins=100):
    factor.stack().dropna().hist(bins=bins,figsize=(9,5))